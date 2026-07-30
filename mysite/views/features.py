"""Feature views — contact form, wishlist, reviews, coupons, password reset."""

import json
import logging
from django.db.models import Avg
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from store.models import (
    ContactMessage, Wishlist, ShowcaseProduct, Review, Coupon, Order,
)

logger = logging.getLogger(__name__)

# ── Helpers ──
MAX_SHORT_TEXT = 200   # name, subject, title
MAX_LONG_TEXT = 5000   # message, comment


def _get_request_payload(request):
    """Accept JSON and regular form posts so JS and non-JS flows both work."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


# ── Contact Form ──

@require_POST
def contact_submit(request):
    """AJAX: save a contact form message."""
    # Rate limit: 3 messages per IP per 10 minutes
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    rate_key = f'contact_rate:{ip}'
    attempts = cache.get(rate_key, 0)
    if attempts >= 3:
        return JsonResponse({'ok': False, 'error': 'Too many messages. Please try again in a few minutes.'}, status=429)

    body = _get_request_payload(request)
    if body is None:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    name = body.get('name', '').strip()[:MAX_SHORT_TEXT]
    email = body.get('email', '').strip()[:MAX_SHORT_TEXT]
    phone = body.get('phone', '').strip()[:20]
    subject = body.get('subject', '').strip()[:MAX_SHORT_TEXT]
    message = body.get('message', '').strip()[:MAX_LONG_TEXT]

    errors = {}
    if not name:
        errors['name'] = 'Name is required.'
    if not email:
        errors['email'] = 'Email is required.'
    if not message:
        errors['message'] = 'Message is required.'
    if errors:
        return JsonResponse({'ok': False, 'errors': errors})

    ContactMessage.objects.create(
        name=name, email=email, phone=phone,
        subject=subject, message=message,
    )

    # Increment rate limit counter
    cache.set(rate_key, attempts + 1, 600)  # 10 min window

    # Try to send email notification to admin
    try:
        from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@houseofambava.com')
        send_mail(
            subject=f'[House of Ambava] Contact: {subject or "New message"}',
            message=f'From: {name} ({email})\nPhone: {phone or "N/A"}\n\n{message}',
            from_email=from_email,
            recipient_list=[getattr(django_settings, 'EMAIL_HOST_USER', 'info@houseofambava.com')],
            fail_silently=True,
        )
    except Exception:
        pass  # Email config may not be set up yet

    return JsonResponse({'ok': True, 'message': 'Thank you for your message! We will get back to you soon.'})


# ── Wishlist ──

@require_POST
def wishlist_toggle(request):
    """AJAX: add/remove a product from the wishlist."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Please log in to use the wishlist.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    product_id = body.get('product_id')
    if not product_id:
        return JsonResponse({'ok': False, 'error': 'Product ID required.'}, status=400)

    try:
        product = ShowcaseProduct.objects.get(pk=product_id, is_active=True)
    except ShowcaseProduct.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Product not found.'}, status=404)

    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
        return JsonResponse({'ok': True, 'added': False, 'message': 'Removed from wishlist.'})

    return JsonResponse({'ok': True, 'added': True, 'message': 'Added to wishlist!'})


def wishlist_list(request):
    """AJAX: get the current user's wishlist product IDs."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': True, 'product_ids': []})

    ids = list(Wishlist.objects.filter(user=request.user).values_list('product_id', flat=True))
    return JsonResponse({'ok': True, 'product_ids': ids})


# ── Reviews ──

@require_POST
def review_submit(request):
    """AJAX: submit a product review."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Please log in to leave a review.'}, status=401)

    body = _get_request_payload(request)
    if body is None:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    # Rate limit: 5 reviews per user per hour
    review_rate_key = f'review_rate:{request.user.pk}'
    review_count = cache.get(review_rate_key, 0)
    if review_count >= 5:
        return JsonResponse({'ok': False, 'error': 'Too many reviews. Please try again later.'}, status=429)

    product_id = body.get('product_id')
    rating = body.get('rating', 5)
    title = body.get('title', '').strip()[:MAX_SHORT_TEXT]
    comment = body.get('comment', '').strip()[:MAX_LONG_TEXT]

    if not product_id:
        return JsonResponse({'ok': False, 'error': 'Product ID required.'}, status=400)

    try:
        product = ShowcaseProduct.objects.get(pk=product_id, is_active=True)
    except ShowcaseProduct.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Product not found.'}, status=404)

    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            raise ValueError
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Rating must be 1-5.'}, status=400)

    # Only verified purchasers can leave reviews
    has_purchased = Order.objects.filter(
        user=request.user,
        items__product=product,
        status='delivered',
    ).exists()
    if not has_purchased:
        return JsonResponse({'ok': False, 'error': 'You can only review products you have purchased.'}, status=403)

    # Auto-approve verified purchase reviews; others go to moderation
    review, created = Review.objects.update_or_create(
        product=product,
        user=request.user,
        defaults={
            'rating': rating,
            'title': title,
            'comment': comment,
            'is_approved': has_purchased,
        },
    )

    # Increment rate limit counter
    cache.set(review_rate_key, review_count + 1, 3600)  # 1 hour window

    msg = 'Review submitted! Thank you.' if created else 'Review updated!'
    if not review.is_approved:
        msg += ' It will appear after moderation.'

    return JsonResponse({
        'ok': True,
        'message': msg,
        'review': {
            'id': review.pk,
            'rating': review.rating,
            'title': review.title,
            'comment': review.comment,
            'user': request.user.first_name or request.user.username,
            'created_at': review.created_at.strftime('%b %d, %Y'),
            'verified_purchase': has_purchased,
        },
    })


def review_list(request):
    """AJAX: get reviews for a product."""
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'ok': False, 'error': 'Product ID required.'}, status=400)

    reviews = Review.objects.filter(
        product_id=product_id, is_approved=True
    ).select_related('user').order_by('-created_at')[:20]

    approved_reviews = Review.objects.filter(product_id=product_id, is_approved=True)
    total_reviews = approved_reviews.count()
    average_rating = approved_reviews.aggregate(avg=Avg('rating'))['avg'] or 0

    # Check which reviewers are verified purchasers
    verified_users = set(Order.objects.filter(
        items__product_id=product_id,
        status='delivered',
    ).values_list('user_id', flat=True))

    data = []
    for r in reviews:
        data.append({
            'id': r.pk,
            'rating': r.rating,
            'title': r.title,
            'comment': r.comment,
            'user': r.user.first_name or r.user.username,
            'created_at': r.created_at.strftime('%b %d, %Y'),
            'date': r.created_at.strftime('%b %d, %Y'),
            'verified_purchase': r.user_id in verified_users,
            'verified': r.user_id in verified_users,
        })

    return JsonResponse({
        'ok': True,
        'average': round(float(average_rating), 1),
        'total': total_reviews,
        'reviews': data,
    })


# ── Coupon ──

@require_POST
def coupon_apply(request):
    """AJAX: validate and return discount for a coupon code."""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Please log in to use coupons.'}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    code = body.get('code', '').strip().upper()[:30]
    order_total = body.get('order_total', 0)

    if not code:
        return JsonResponse({'ok': False, 'error': 'Please enter a coupon code.'})

    # NOTE: order_total here is a client-side preview only.
    # The actual discount is recalculated server-side during checkout.
    try:
        order_total = max(0, min(float(order_total), 10_000_000))  # Clamp to sane range
    except (ValueError, TypeError):
        order_total = 0

    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Invalid coupon code.'})

    is_valid, error_msg = coupon.is_valid(order_total, request.user)
    if not is_valid:
        return JsonResponse({'ok': False, 'error': error_msg})

    discount = coupon.calculate_discount(order_total)

    return JsonResponse({
        'ok': True,
        'code': coupon.code,
        'discount': float(discount),
        'description': coupon.description or str(coupon),
        'message': f'Coupon applied! You save ₹{discount:,.0f}',
    })


@require_POST
def coupon_remove(request):
    """AJAX: remove applied coupon."""
    return JsonResponse({'ok': True, 'message': 'Coupon removed.'})


# ── Password Reset ──

@require_POST
def password_reset_request(request):
    """AJAX: send a password reset link via email."""
    # Accept both JSON and form-urlencoded data
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)
        email = body.get('email', '').strip()
    else:
        email = request.POST.get('email', '').strip()
    if not email:
        return JsonResponse({'ok': False, 'error': 'Email is required.'})

    # Rate limit: 1 reset per email per 2 minutes
    rate_key = f'pwd_reset:{email}'
    if cache.get(rate_key):
        return JsonResponse({'ok': False, 'error': 'Please wait before requesting another reset.'}, status=429)

    user = User.objects.filter(email=email).first()
    if not user:
        # Don't reveal whether email exists — always return success
        return JsonResponse({'ok': True, 'message': 'If this email is registered, a reset link has been sent.'})

    # Generate cryptographically-safe token (survives server restarts, unlike cache)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    cache.set(rate_key, 1, 120)  # Rate limit 2 min

    # Send email
    reset_url = f'{request.scheme}://{request.get_host()}/account/reset-password/?uid={uid}&token={token}'
    try:
        from_email = getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@houseofambava.com')
        send_mail(
            subject='Reset your House of Ambava password',
            message=f'Hi {user.first_name or user.username},\n\n'
                    f'Click the link below to reset your password:\n{reset_url}\n\n'
                    f'This link expires in 1 hour.\n\n'
                    f'If you did not request this, please ignore this email.\n\n'
                    f'— House of Ambava',
            from_email=from_email,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f'Password reset email failed: {e}')
        return JsonResponse({'ok': False, 'error': 'Failed to send email. Please try again later.'})

    return JsonResponse({'ok': True, 'message': 'If this email is registered, a reset link has been sent.'})


@require_POST
def password_reset_confirm(request):
    """AJAX: set a new password using the reset token."""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    token = body.get('token', '').strip()
    uid = body.get('uid', '').strip()
    new_password = body.get('password', '')
    confirm_password = body.get('confirm_password', '')

    if not token or not uid:
        return JsonResponse({'ok': False, 'error': 'Invalid or expired reset link.'})
    if not new_password:
        return JsonResponse({'ok': False, 'error': 'Password is required.'})
    if new_password != confirm_password:
        return JsonResponse({'ok': False, 'error': 'Passwords do not match.'})

    # Decode UID and find user
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return JsonResponse({'ok': False, 'error': 'Invalid reset link.'})

    # Verify token (cryptographic, survives server restarts)
    if not default_token_generator.check_token(user, token):
        return JsonResponse({'ok': False, 'error': 'This reset link has expired. Please request a new one.'})

    # Validate password using Django's configured validators
    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return JsonResponse({'ok': False, 'error': ' '.join(e.messages)})

    user.set_password(new_password)
    user.save()

    return JsonResponse({'ok': True, 'message': 'Password reset successfully! You can now log in.'})
