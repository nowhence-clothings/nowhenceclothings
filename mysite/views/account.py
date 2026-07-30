"""Account views — profile, addresses, orders, returns."""

import re
from django.db import transaction
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.utils import timezone
from store.models import (
    Address, Order, OrderItem, ReturnExchange, UserProfile,
)
from .helpers import normalize_phone


# ── Profile ──

def profile(request):
    """Customer profile page — edit name & manage addresses."""
    if not request.user.is_authenticated or request.user.is_staff:
        return redirect('customer_login')

    user = request.user
    addresses = Address.objects.filter(user=user)
    user_profile, _ = UserProfile.objects.get_or_create(user=user)

    return render(request, 'profile.html', {
        'addresses': addresses,
        'user_phone': user_profile.phone or '',
    })


def profile_update(request):
    """AJAX: update user's first_name / last_name / email."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Not logged in.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    user = request.user
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip()
    phone = request.POST.get('phone', '').strip()

    errors = {}
    if not first_name:
        errors['first_name'] = 'First name is required.'
    if not email:
        errors['email'] = 'Email is required.'
    elif User.objects.filter(email=email).exclude(pk=user.pk).exists():
        errors['email'] = 'This email is already in use.'
    if phone:
        phone, phone_err = normalize_phone(phone)
        if phone_err:
            errors['phone'] = phone_err
        else:
            existing_profile = UserProfile.objects.filter(phone=phone).exclude(user=user).first()
            if existing_profile:
                errors['phone'] = 'This phone number is linked to another account.'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    user.first_name = first_name
    user.last_name = last_name
    user.email = email
    user.save()

    profile_obj, _ = UserProfile.objects.get_or_create(user=user)
    if phone:
        profile_obj.phone = phone
        profile_obj.save(update_fields=['phone'])

    # Clean up legacy username
    if user.username.startswith('phone_') or user.username.startswith('user_'):
        if phone:
            digits = re.sub(r'[^\d]', '', phone)[-10:]
            if digits and len(digits) == 10 and not User.objects.filter(username=digits).exclude(pk=user.pk).exists():
                user.username = digits
                user.save(update_fields=['username'])

    return JsonResponse({'ok': True, 'message': 'Profile updated successfully!'})


# ── Addresses ──

def _upsert_address_for_user(
    user,
    *,
    full_name,
    phone='',
    address_line1,
    address_line2='',
    city,
    state,
    pincode,
    label='',
    address_id='',
    set_as_default=False,
    require_existing=False,
):
    """Create or update a user's address while keeping a single default address."""
    with transaction.atomic():
        addr = None
        if address_id:
            addr = Address.objects.select_for_update().filter(pk=address_id, user=user).first()
            if not addr and require_existing:
                raise ValueError('Address not found.')

        if not addr:
            addr = Address(user=user)

        other_addresses = Address.objects.select_for_update().filter(user=user)
        if addr.pk:
            other_addresses = other_addresses.exclude(pk=addr.pk)

        existing_default = bool(addr.pk and addr.is_default)
        should_be_default = set_as_default or existing_default or not other_addresses.exists()

        if should_be_default:
            other_addresses.update(is_default=False)
        elif existing_default and not other_addresses.filter(is_default=True).exists():
            fallback_default = other_addresses.order_by('pk').first()
            if fallback_default:
                fallback_default.is_default = True
                fallback_default.save(update_fields=['is_default'])

        if label:
            addr.label = label
        elif not addr.pk:
            addr.label = 'home'

        addr.full_name = full_name
        addr.phone = phone
        addr.address_line1 = address_line1
        addr.address_line2 = address_line2
        addr.city = city
        addr.state = state
        addr.pincode = pincode
        addr.is_default = should_be_default
        addr.save()
        return addr


def address_save(request):
    """AJAX: create or update an address."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Not logged in.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    addr_id = request.POST.get('address_id', '').strip()
    errors = {}
    full_name = request.POST.get('full_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    line1 = request.POST.get('address_line1', '').strip()
    line2 = request.POST.get('address_line2', '').strip()
    city = request.POST.get('city', '').strip()
    state = request.POST.get('state', '').strip()
    pincode = request.POST.get('pincode', '').strip()
    label = request.POST.get('label', 'home').strip()
    is_default = request.POST.get('is_default') == 'on'

    if not full_name:
        errors['full_name'] = 'Full name is required.'
    if not line1:
        errors['address_line1'] = 'Address is required.'
    if not city:
        errors['city'] = 'City is required.'
    if not state:
        errors['state'] = 'State is required.'
    if not pincode or len(pincode) < 5:
        errors['pincode'] = 'Valid pincode is required.'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    try:
        addr = _upsert_address_for_user(
            request.user,
            full_name=full_name,
            phone=phone,
            address_line1=line1,
            address_line2=line2,
            city=city,
            state=state,
            pincode=pincode,
            label=label,
            address_id=addr_id,
            set_as_default=is_default,
            require_existing=bool(addr_id),
        )
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Address not found.'}, status=404)

    return JsonResponse({
        'ok': True,
        'message': 'Address saved!',
        'address': {
            'id': addr.pk,
            'label': addr.label,
            'full_name': addr.full_name,
            'phone': addr.phone,
            'address_line1': addr.address_line1,
            'address_line2': addr.address_line2,
            'city': addr.city,
            'state': addr.state,
            'pincode': addr.pincode,
            'is_default': addr.is_default,
        },
    })


def address_delete(request):
    """AJAX: delete an address."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Not logged in.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    addr_id = request.POST.get('address_id', '')
    with transaction.atomic():
        addr = Address.objects.select_for_update().filter(pk=addr_id, user=request.user).first()
        if not addr:
            return JsonResponse({'ok': False, 'error': 'Address not found.'}, status=404)

        remaining = Address.objects.select_for_update().filter(user=request.user).exclude(pk=addr.pk).order_by('pk')
        addr.delete()

        new_default = remaining.filter(is_default=True).first()
        if new_default:
            remaining.exclude(pk=new_default.pk).update(is_default=False)
        else:
            new_default = remaining.first()
            if new_default:
                new_default.is_default = True
                new_default.save(update_fields=['is_default'])

    return JsonResponse({
        'ok': True,
        'message': 'Address deleted.',
        'new_default_id': new_default.pk if new_default else None,
    })


# ── Order History ──

def order_history(request):
    """Customer order history page."""
    if not request.user.is_authenticated or request.user.is_staff:
        return redirect('customer_login')

    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    orders_qs = Order.objects.filter(user=request.user).prefetch_related('items', 'items__product')
    paginator = Paginator(orders_qs, 10)
    page_num = request.GET.get('page', 1)
    try:
        orders = paginator.page(page_num)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    return render(request, 'order_history.html', {'orders': orders, 'page_obj': orders})


# ── Track Order ──

def track_order(request):
    """Track order page — lookup by order number."""
    if not request.user.is_authenticated or request.user.is_staff:
        return redirect('customer_login')

    order = None
    error = ''
    order_number = request.GET.get('order_number', '').strip()

    if order_number:
        order = Order.objects.filter(
            order_number__iexact=order_number, user=request.user
        ).prefetch_related('items').first()
        if not order:
            error = 'Order not found. Please check the order number and try again.'

    orders = Order.objects.filter(user=request.user).prefetch_related('items', 'items__product')

    return render(request, 'track_order.html', {
        'order': order,
        'order_number': order_number,
        'error': error,
        'orders': orders,
    })


# ── Returns & Exchanges ──

def returns_exchanges(request):
    """Returns & Exchanges page — view existing requests and create new ones."""
    if not request.user.is_authenticated or request.user.is_staff:
        return redirect('customer_login')

    returns = ReturnExchange.objects.filter(user=request.user).select_related('order', 'order_item')
    eligible_orders = Order.objects.filter(
        user=request.user, status='delivered'
    ).prefetch_related('items')

    return render(request, 'returns_exchanges.html', {
        'returns': returns,
        'eligible_orders': eligible_orders,
        'reason_choices': ReturnExchange.REASON_CHOICES,
    })


def cancel_order(request):
    """AJAX: cancel an order (only if pending or confirmed)."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Not logged in.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    order_id = request.POST.get('order_id', '').strip()
    reason = request.POST.get('reason', '').strip()

    if not order_id:
        return JsonResponse({'ok': False, 'error': 'Order ID is required.'})

    from .checkout import _increment_order_stock, _decrement_coupon_usage

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id, user=request.user).first()
        if not order:
            return JsonResponse({'ok': False, 'error': 'Order not found.'}, status=404)

        if not order.can_cancel:
            if order.status in ('shipped', 'out_for_delivery'):
                msg = ('This order has already been shipped and cannot be cancelled online. '
                       'Please refuse the delivery when the delivery partner arrives at your doorstep '
                       'to automatically initiate a return.')
            else:
                msg = f'This order cannot be cancelled. Current status: {order.get_status_display()}.'
            return JsonResponse({'ok': False, 'error': msg})

        was_confirmed = order.status == 'confirmed'
        if was_confirmed:
            _increment_order_stock(order)
            _decrement_coupon_usage(order)

        refund = order.payment_status == 'paid' and order.payment_method != 'cod'
        order.status = 'cancelled'
        order.cancellation_reason = reason or 'Cancelled by customer'
        order.cancelled_at = timezone.now()
        order.payment_status = 'refunded' if refund else 'failed'
        order.save(update_fields=['status', 'cancellation_reason', 'cancelled_at', 'payment_status', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'message': f'Order {order.order_number} has been cancelled successfully.',
        'order_number': order.order_number,
        'refund': refund,
    })


def return_request_create(request):
    """AJAX: create a return/exchange request."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Not logged in.'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    order_id = request.POST.get('order_id', '').strip()
    item_id = request.POST.get('item_id', '').strip()
    request_type = request.POST.get('request_type', 'return').strip()
    reason = request.POST.get('reason', 'other').strip()
    details = request.POST.get('details', '').strip()

    errors = {}
    if not order_id:
        errors['order_id'] = 'Please select an order.'
    if not reason:
        errors['reason'] = 'Please select a reason.'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    order = Order.objects.filter(pk=order_id, user=request.user, status='delivered').first()
    if not order:
        return JsonResponse({'ok': False, 'error': 'Order not found or not eligible for return.'}, status=404)

    order_item = None
    if item_id:
        order_item = OrderItem.objects.filter(pk=item_id, order=order).first()

    existing = ReturnExchange.objects.filter(
        order=order, user=request.user
    ).exclude(status__in=['completed', 'rejected']).exists()
    if existing:
        return JsonResponse({'ok': False, 'error': 'An active return/exchange request already exists for this order.'})

    ret = ReturnExchange.objects.create(
        user=request.user,
        order=order,
        order_item=order_item,
        request_type=request_type,
        reason=reason,
        details=details,
    )

    return JsonResponse({
        'ok': True,
        'message': f'{ret.get_request_type_display()} request submitted successfully!',
        'request': {
            'id': ret.pk,
            'type': ret.get_request_type_display(),
            'reason': ret.get_reason_display(),
            'status': ret.get_status_display(),
            'order_number': order.order_number,
            'created_at': ret.created_at.strftime('%b %d, %Y'),
        },
    })
