"""Checkout views — checkout page, inline login, place order, Razorpay payment."""

import json
import logging
from django.db import transaction
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from store.models import (
    Address, Order, OrderItem, ShowcaseProduct, UserProfile,
)
from .helpers import normalize_phone, get_otp, clear_otp, get_or_create_phone_user
from .account import _upsert_address_for_user

logger = logging.getLogger(__name__)


def _get_coupon_for_update(order):
    if not order.coupon_code or order.discount_amount <= 0:
        return None

    from store.models import Coupon

    return Coupon.objects.select_for_update().filter(code__iexact=order.coupon_code).first()


def _decrement_order_stock(order):
    """Reserve stock once an order is actually confirmed."""
    for item in order.items.select_related('product').order_by('pk'):
        if not item.product_id:
            continue
        product = ShowcaseProduct.objects.select_for_update().filter(pk=item.product_id).first()
        if not product:
            continue
        if product.stock_quantity < item.quantity:
            raise ValueError(f'Insufficient stock for {item.product_name}.')
        product.stock_quantity -= item.quantity
        product.save(update_fields=['stock_quantity'])


def _increment_order_stock(order):
    """Return reserved stock to inventory when a confirmed order is cancelled."""
    for item in order.items.select_related('product').order_by('pk'):
        if not item.product_id:
            continue
        product = ShowcaseProduct.objects.select_for_update().filter(pk=item.product_id).first()
        if not product:
            continue
        product.stock_quantity += item.quantity
        product.save(update_fields=['stock_quantity'])


def _increment_coupon_usage(order, *, strict=True):
    """Count coupon usage only for completed/confirmed orders."""
    coupon = _get_coupon_for_update(order)
    if not coupon:
        return
    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        if strict:
            raise ValueError('This coupon is no longer available. Please place the order again.')
        logger.warning('Coupon %s exceeded usage limit during late finalization for order %s', coupon.code, order.order_number)
        return
    coupon.used_count += 1
    coupon.save(update_fields=['used_count'])


def _decrement_coupon_usage(order):
    """Release a previously counted coupon usage when a confirmed order is cancelled."""
    coupon = _get_coupon_for_update(order)
    if not coupon or coupon.used_count <= 0:
        return
    coupon.used_count -= 1
    coupon.save(update_fields=['used_count'])


def _finalize_confirmed_order(order, *, strict_coupon_usage=True):
    """Apply side effects only after an order is fully confirmed."""
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        _decrement_order_stock(locked_order)
        _increment_coupon_usage(locked_order, strict=strict_coupon_usage)
    _send_order_email_safe(locked_order)
    return locked_order


def _confirm_online_payment(order, razorpay_payment_id, razorpay_signature):
    """Confirm a pending online order exactly once."""
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.payment_status == 'paid':
            return locked_order, False

        _decrement_order_stock(locked_order)
        _increment_coupon_usage(locked_order)

        locked_order.razorpay_payment_id = razorpay_payment_id
        locked_order.razorpay_signature = razorpay_signature
        locked_order.payment_status = 'paid'
        locked_order.status = 'confirmed'
        locked_order.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'payment_status', 'status'])

    _send_order_email_safe(locked_order)
    return locked_order, True


# ── Checkout page ──

@ensure_csrf_cookie
def checkout(request):
    """Checkout page — renders the multi-step checkout form.
    Cart data lives in localStorage and is passed via JS.
    If logged in, pre-fill saved addresses.
    """
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        messages.info(request, 'You are browsing as an admin. To checkout, please log in with a customer account.')
        return redirect('home')

    addresses = []
    user_phone = ''
    if request.user.is_authenticated:
        addresses = list(
            Address.objects.filter(user=request.user).values(
                'id', 'label', 'full_name', 'phone',
                'address_line1', 'address_line2', 'city', 'state', 'pincode', 'is_default',
            )
        )
        prof = UserProfile.objects.filter(user=request.user).first()
        if prof and prof.phone:
            user_phone = prof.phone

    return render(request, 'checkout.html', {
        'saved_addresses': addresses,
        'user_phone': user_phone,
    })


# ── Checkout profile update ──

@require_POST
def checkout_update_profile(request):
    """AJAX: update user profile fields from checkout shipping step."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    user = request.user
    full_name = body.get('full_name', '').strip()
    changed_fields = []

    if full_name:
        parts = full_name.split(None, 1)
        new_first = parts[0]
        new_last = parts[1] if len(parts) > 1 else ''
        if user.first_name != new_first:
            user.first_name = new_first
            changed_fields.append('first_name')
        if user.last_name != new_last:
            user.last_name = new_last
            changed_fields.append('last_name')

    if changed_fields:
        user.save(update_fields=changed_fields)

    return JsonResponse({
        'ok': True,
        'user': {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
        },
    })


# ── Checkout inline login ──

@require_POST
def checkout_login(request):
    """AJAX: login from checkout page without losing cart."""
    action = request.POST.get('action', 'login')

    if action == 'login':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        if not password:
            errors['password'] = 'Password is required.'
        if errors:
            return JsonResponse({'ok': False, 'errors': errors})

        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse({'ok': False, 'errors': {'__all__': 'Invalid credentials.'}})
        if user.is_superuser or user.is_staff:
            return JsonResponse({'ok': False, 'errors': {'__all__': 'Please use the admin panel.'}})

        login(request, user)
        prof = UserProfile.objects.filter(user=user).first()
        user_phone = prof.phone if prof else ''
        addresses = list(
            Address.objects.filter(user=user).values(
                'id', 'label', 'full_name', 'phone',
                'address_line1', 'address_line2', 'city', 'state', 'pincode', 'is_default',
            )
        )
        return JsonResponse({
            'ok': True,
            'user': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'username': user.username,
                'phone': user_phone,
            },
            'addresses': addresses,
        })

    elif action == 'signup':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        if not email:
            errors['email'] = 'Email is required.'
        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 6:
            errors['password'] = 'Password must be at least 6 characters.'
        if password and confirm and password != confirm:
            errors['confirm_password'] = 'Passwords do not match.'
        if username and User.objects.filter(username=username).exists():
            errors['username'] = 'Username already taken.'
        if email and User.objects.filter(email=email).exists():
            errors['email'] = 'Email already registered.'
        if errors:
            return JsonResponse({'ok': False, 'errors': errors})

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )
        UserProfile.objects.get_or_create(user=user)
        login(request, user)
        return JsonResponse({
            'ok': True,
            'user': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'username': user.username,
                'phone': '',
            },
            'addresses': [],
        })

    elif action == 'phone_login':
        raw_phone = request.POST.get('phone', '').strip()
        otp = request.POST.get('otp', '').strip()
        errors = {}
        phone = None
        if not raw_phone:
            errors['phone'] = 'Phone number is required.'
        else:
            phone, phone_err = normalize_phone(raw_phone)
            if phone_err:
                errors['phone'] = phone_err
        if not otp:
            errors['otp'] = 'OTP is required.'
        if errors:
            return JsonResponse({'ok': False, 'errors': errors})

        stored_otp = get_otp(phone, raw_phone)
        if stored_otp != otp:
            return JsonResponse({'ok': False, 'errors': {'otp': 'Invalid or expired OTP.'}})

        # OTP valid — find or create user by phone
        clear_otp(phone, raw_phone)
        user = get_or_create_phone_user(phone)

        if user.is_superuser or user.is_staff:
            return JsonResponse({'ok': False, 'errors': {'__all__': 'Please use the admin panel.'}})

        login(request, user)
        addresses = list(
            Address.objects.filter(user=user).values(
                'id', 'label', 'full_name', 'phone',
                'address_line1', 'address_line2', 'city', 'state', 'pincode', 'is_default',
            )
        )
        prof_obj = UserProfile.objects.filter(user=user).first()
        user_phone = prof_obj.phone if prof_obj else phone
        return JsonResponse({
            'ok': True,
            'user': {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'username': user.username,
                'phone': user_phone,
            },
            'addresses': addresses,
        })

    return JsonResponse({'ok': False, 'error': 'Invalid action.'}, status=400)


# ── Place order ──

@require_POST
def place_order(request):
    """AJAX: create an order from cart JSON payload.
    For COD — order is confirmed immediately.
    For Razorpay — order is created as pending and a Razorpay order is generated.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    items = body.get('items', [])
    shipping = body.get('shipping', {})
    email = body.get('email', '').strip()
    save_address_raw = body.get('save_address', False)
    if isinstance(save_address_raw, str):
        save_address = save_address_raw.strip().lower() in ('1', 'true', 'yes', 'on')
    else:
        save_address = bool(save_address_raw)
    address_id = str(body.get('address_id', '')).strip()
    payment_method = body.get('payment_method', 'cod').strip()

    errors = {}
    if not items:
        errors['items'] = 'Cart is empty.'
    if not shipping.get('full_name'):
        errors['full_name'] = 'Full name is required.'
    if not shipping.get('phone'):
        errors['phone'] = 'Phone number is required.'
    if not shipping.get('address_line1'):
        errors['address_line1'] = 'Address is required.'
    if not shipping.get('city'):
        errors['city'] = 'City is required.'
    if not shipping.get('state'):
        errors['state'] = 'State is required.'
    if not shipping.get('pincode') or len(shipping.get('pincode', '')) < 5:
        errors['pincode'] = 'Valid pincode is required.'
    if not email:
        errors['email'] = 'Email is required.'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    # Fill in any missing user profile fields from checkout data
    user = request.user
    changed_fields = []
    full_name = shipping.get('full_name', '').strip()
    if full_name:
        name_parts = full_name.split(None, 1)
        if not user.first_name:
            user.first_name = name_parts[0]
            changed_fields.append('first_name')
        if not user.last_name and len(name_parts) > 1:
            user.last_name = name_parts[1]
            changed_fields.append('last_name')
    if not user.email and email:
        user.email = email
        changed_fields.append('email')
    if changed_fields:
        user.save(update_fields=changed_fields)

    # Save phone to UserProfile if missing
    checkout_phone = shipping.get('phone', '').strip()
    if checkout_phone:
        prof, _ = UserProfile.objects.get_or_create(user=user)
        if not prof.phone:
            prof.phone = checkout_phone
            prof.save(update_fields=['phone'])

    # Save address for future if requested
    if save_address:
        _upsert_address_for_user(
            user,
            full_name=shipping['full_name'],
            phone=shipping.get('phone', ''),
            address_line1=shipping['address_line1'],
            address_line2=shipping.get('address_line2', ''),
            city=shipping['city'],
            state=shipping['state'],
            pincode=shipping['pincode'],
            label=shipping.get('label', ''),
            address_id=address_id,
            set_as_default=False,
            require_existing=False,
        )

    # Calculate totals — validate prices server-side
    subtotal = 0
    order_items_data = []
    out_of_stock = []
    for it in items:
        product_name = str(it.get('name', '')).strip() or 'Unknown'
        product_slug = str(it.get('slug', '')).strip()
        qty = max(1, int(it.get('quantity', 1)))
        size = str(it.get('size', '')).strip()

        # Lookup product from DB to validate price
        product = None
        if product_slug:
            product = ShowcaseProduct.objects.filter(slug=product_slug, is_active=True).first()
        else:
            matching_products = list(
                ShowcaseProduct.objects.filter(name=product_name, is_active=True)[:2]
            )
            if len(matching_products) > 1:
                return JsonResponse({
                    'ok': False,
                    'error': f'Cart item "{product_name}" needs to be refreshed. Please remove it and add it again.',
                }, status=400)
            if matching_products:
                product = matching_products[0]

        if product:
            product_name = product.name
            available_sizes = [s.strip() for s in product.size_list if s.strip()]
            if available_sizes:
                normalized_sizes = {s.upper(): s for s in available_sizes}
                if not size:
                    return JsonResponse({
                        'ok': False,
                        'error': f'Please select a size for "{product_name}" before checkout.',
                    }, status=400)
                matched_size = normalized_sizes.get(size.upper())
                if not matched_size:
                    return JsonResponse({
                        'ok': False,
                        'error': f'Invalid size selected for "{product_name}". Please re-add it from the product page.',
                    }, status=400)
                size = matched_size
            # Use server-side price (discounted if available)
            price = int(product.discounted_price if product.discounted_price else product.price)
            # Check stock
            if product.stock_quantity < qty:
                out_of_stock.append(f'{product_name} (only {product.stock_quantity} left)')
                continue
        else:
            # Product not found — reject
            return JsonResponse({'ok': False, 'error': f'Product "{product_name}" not found or unavailable.'})

        subtotal += price * qty
        order_items_data.append({
            'product': product,
            'product_slug': product.slug,
            'product_name': product_name,
            'price': price,
            'quantity': qty,
            'total': price * qty,
            'image': it.get('image', ''),
            'size': size,
        })

    if out_of_stock:
        return JsonResponse({'ok': False, 'error': f'Insufficient stock: {", ".join(out_of_stock)}'})
    if not order_items_data:
        return JsonResponse({'ok': False, 'error': 'No valid items in cart.'})

    shipping_charge = 0 if subtotal >= 5000 else 199

    # ── Apply coupon if provided ──
    coupon_code = body.get('coupon_code', '').strip().upper()[:30]
    discount_amount = 0
    if coupon_code:
        from store.models import Coupon
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
        except Coupon.DoesNotExist:
            return JsonResponse({
                'ok': False,
                'error': 'This coupon is no longer valid. Please remove it and try again.',
            }, status=400)

        is_valid, coupon_error = coupon.is_valid(order_total=subtotal, user=request.user)
        if not is_valid:
            return JsonResponse({
                'ok': False,
                'error': coupon_error or 'This coupon is no longer valid. Please remove it and try again.',
            }, status=400)
        discount_amount = coupon.calculate_discount(subtotal)

    total = max(0, subtotal + shipping_charge - discount_amount)

    # Determine payment status based on method
    is_online = payment_method in ('razorpay', 'upi', 'card', 'netbanking')

    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            status='pending' if is_online else 'confirmed',
            payment_status='pending' if is_online else 'paid',
            payment_method='razorpay' if is_online else 'cod',
            shipping_full_name=shipping['full_name'],
            shipping_phone=shipping.get('phone', ''),
            shipping_address=f"{shipping['address_line1']}, {shipping.get('address_line2', '')}".rstrip(', '),
            shipping_city=shipping['city'],
            shipping_state=shipping['state'],
            shipping_pincode=shipping['pincode'],
            subtotal=subtotal,
            shipping_charge=shipping_charge,
            total=total,
            coupon_code=coupon_code if discount_amount else '',
            discount_amount=discount_amount,
        )

        for oi in order_items_data:
            product = oi.get('product')
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=oi['product_name'],
                price=oi['price'],
                quantity=oi['quantity'],
                total=oi['total'],
                size=oi.get('size', ''),
            )

    # For online payment methods — create a Razorpay order
    if is_online:
        from django.conf import settings as django_settings
        import razorpay

        rzp_key = getattr(django_settings, 'RAZORPAY_KEY_ID', '')
        rzp_secret = getattr(django_settings, 'RAZORPAY_KEY_SECRET', '')
        rzp_currency = getattr(django_settings, 'RAZORPAY_CURRENCY', 'INR')

        if not rzp_key or not rzp_secret:
            # Razorpay not configured — fall back to COD
            order.payment_method = 'cod'
            order.status = 'confirmed'
            order.payment_status = 'paid'
            order.save(update_fields=['payment_method', 'status', 'payment_status'])
            try:
                _finalize_confirmed_order(order)
            except ValueError as exc:
                order.payment_status = 'failed'
                order.status = 'cancelled'
                order.notes = str(exc)
                order.save(update_fields=['payment_status', 'status', 'notes'])
                return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
            return JsonResponse({
                'ok': True,
                'order_number': order.order_number,
                'total': str(order.total),
                'payment_method': 'cod',
                'message': 'Online payment is not configured. Order placed as Cash on Delivery.',
            })

        try:
            client = razorpay.Client(auth=(rzp_key, rzp_secret))
            razorpay_order = client.order.create({
                'amount': int(total * 100),  # Razorpay expects paise
                'currency': rzp_currency,
                'receipt': order.order_number,
                'notes': {
                    'order_number': order.order_number,
                    'customer_email': email,
                },
            })
            order.razorpay_order_id = razorpay_order['id']
            order.save(update_fields=['razorpay_order_id'])

            return JsonResponse({
                'ok': True,
                'order_number': order.order_number,
                'total': str(order.total),
                'payment_method': 'razorpay',
                'razorpay': {
                    'order_id': razorpay_order['id'],
                    'key_id': rzp_key,
                    'amount': int(total * 100),
                    'currency': rzp_currency,
                    'name': 'Nowhence Clothiongs',
                    'description': f'Order #{order.order_number}',
                    'prefill': {
                        'name': shipping['full_name'],
                        'email': email,
                        'contact': shipping.get('phone', ''),
                    },
                },
                'message': 'Razorpay order created. Complete payment.',
            })
        except Exception as e:
            logger.error(f'Razorpay order creation failed: {e}')
            order.delete()
            return JsonResponse({
                'ok': False,
                'error': 'Payment gateway error. Please try again or use Cash on Delivery.',
            })

    # COD — order is already confirmed
    try:
        _finalize_confirmed_order(order)
    except ValueError as exc:
        order.payment_status = 'failed'
        order.status = 'cancelled'
        order.notes = str(exc)
        order.save(update_fields=['payment_status', 'status', 'notes'])
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    return JsonResponse({
        'ok': True,
        'order_number': order.order_number,
        'total': str(order.total),
        'payment_method': 'cod',
        'message': 'Order placed successfully!',
    })


# Send order confirmation email (COD & Razorpay)
def _send_order_email_safe(order):
    """Send confirmation email, swallowing errors."""
    try:
        from store.emails import send_order_confirmation
        send_order_confirmation(order)
    except Exception as e:
        logger.error(f'Order email error: {e}')


@require_POST
def verify_razorpay_payment(request):
    """AJAX: verify Razorpay payment signature after successful checkout."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    razorpay_order_id = body.get('razorpay_order_id', '')
    razorpay_payment_id = body.get('razorpay_payment_id', '')
    razorpay_signature = body.get('razorpay_signature', '')
    order_number = body.get('order_number', '')

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, order_number]):
        return JsonResponse({'ok': False, 'error': 'Missing payment details.'}, status=400)

    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
        razorpay_order_id=razorpay_order_id,
    ).first()

    if not order:
        return JsonResponse({'ok': False, 'error': 'Order not found.'}, status=404)

    if order.payment_status == 'paid':
        return JsonResponse({
            'ok': True,
            'order_number': order.order_number,
            'message': 'Payment already verified.',
        })

    from django.conf import settings as django_settings
    import razorpay

    rzp_key = getattr(django_settings, 'RAZORPAY_KEY_ID', '')
    rzp_secret = getattr(django_settings, 'RAZORPAY_KEY_SECRET', '')

    try:
        client = razorpay.Client(auth=(rzp_key, rzp_secret))
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        order.payment_status = 'failed'
        order.status = 'cancelled'
        order.save(update_fields=['payment_status', 'status'])
        return JsonResponse({'ok': False, 'error': 'Payment verification failed. Please contact support.'})
    except Exception as e:
        logger.error(f'Razorpay verification error: {e}')
        return JsonResponse({'ok': False, 'error': 'Payment verification error. Please contact support.'})

    # Signature verified — mark order as paid
    try:
        order, confirmed_now = _confirm_online_payment(order, razorpay_payment_id, razorpay_signature)
    except ValueError as exc:
        order.payment_status = 'failed'
        order.status = 'cancelled'
        order.notes = str(exc)
        order.save(update_fields=['payment_status', 'status', 'notes'])
        return JsonResponse({'ok': False, 'error': str(exc)})

    if not confirmed_now:
        return JsonResponse({
            'ok': True,
            'order_number': order.order_number,
            'message': 'Payment already verified.',
        })

    return JsonResponse({
        'ok': True,
        'order_number': order.order_number,
        'message': 'Payment successful! Your order has been confirmed.',
    })


@require_POST
def razorpay_payment_failed(request):
    """AJAX: handle failed Razorpay payment — mark order as failed."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Login required.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    order_number = body.get('order_number', '')
    error_description = body.get('error_description', '')

    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
        payment_status='pending',
    ).first()

    if order:
        order.payment_status = 'failed'
        order.status = 'cancelled'
        order.notes = f'Payment failed: {error_description}'
        order.save(update_fields=['payment_status', 'status', 'notes'])

    return JsonResponse({
        'ok': True,
        'message': 'Payment was not completed. You can try again from your orders page.',
    })
