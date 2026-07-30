"""AJAX API endpoints — search, pincode check, OTP."""

import json
import random
from django.http import JsonResponse
from django.db.models import Q
from store.models import (
    FeaturedCollection, ShowcaseProduct, CollectionCard, PincodeAvailability,
)
from .helpers import normalize_phone, store_otp, is_rate_limited


def search_api(request):
    """AJAX search endpoint — searches featured collections, showcase products, and collection cards."""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    results = []

    # Search Featured Collections
    for item in FeaturedCollection.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True
    )[:6]:
        results.append({
            'name': item.name,
            'description': item.description,
            'price': item.formatted_price,
            'discounted_price': item.formatted_discounted_price if item.has_discount else '',
            'discount': item.discount_percent if item.has_discount else 0,
            'image': item.image.url if item.image else '',
            'category': 'Featured Collection',
            'section': '#collection',
        })

    # Search Showcase Products
    for item in ShowcaseProduct.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True
    )[:6]:
        results.append({
            'name': item.name,
            'price': item.formatted_price,
            'discounted_price': item.formatted_discounted_price if item.has_discount else '',
            'discount': item.discount_percent if item.has_discount else 0,
            'image': item.image.url if item.image else '',
            'category': item.get_category_display(),
            'section': '#showcase',
            'url': f'/shop/{item.slug}/',
        })

    # Search Collection Cards
    for item in CollectionCard.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query),
        is_active=True
    )[:4]:
        results.append({
            'name': item.name,
            'description': item.description,
            'image': item.image.url if item.image else '',
            'category': 'Collection',
            'section': '#collection',
        })

    return JsonResponse({'results': results[:12]})


def check_pincode_availability(request):
    """AJAX endpoint to check product availability in a pincode."""
    pincode = request.GET.get('pincode', '').strip()
    product_id = request.GET.get('product_id', '')

    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        return JsonResponse({
            'available': False,
            'message': 'Please enter a valid 6-digit pincode'
        }, status=400)

    if not product_id:
        return JsonResponse({
            'available': False,
            'message': 'Product not found'
        }, status=400)

    try:
        ShowcaseProduct.objects.get(id=product_id)
    except ShowcaseProduct.DoesNotExist:
        return JsonResponse({
            'available': False,
            'message': 'Product not found'
        }, status=404)

    is_available, delivery_days, extra_charge = PincodeAvailability.is_product_available_in_pincode(
        product_id, pincode
    )

    if is_available:
        message = f'Delivery in {delivery_days} days'
        if extra_charge > 0:
            message += f' • Shipping: ₹{extra_charge:.0f}'
        return JsonResponse({
            'available': True,
            'delivery_days': delivery_days,
            'extra_charge': float(extra_charge),
            'message': message
        })
    else:
        return JsonResponse({
            'available': False,
            'message': 'Currently not available for this area'
        })


def send_otp(request):
    """Generate a 6-digit OTP for a phone number.
    Currently returns demo OTP in response.
    TODO: Integrate MSG91 to send real SMS.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    raw_phone = body.get('phone', '').strip()
    if not raw_phone:
        return JsonResponse({'ok': False, 'error': 'Enter a valid phone number.'})
    phone, phone_err = normalize_phone(raw_phone)
    if phone_err:
        return JsonResponse({'ok': False, 'error': phone_err})

    if is_rate_limited(phone):
        return JsonResponse({'ok': False, 'error': 'Please wait before requesting another OTP.'}, status=429)

    from django.conf import settings as django_settings
    if getattr(django_settings, 'DEBUG', False):
        # ── DEMO MODE: fixed OTP for development ──
        # TODO: Replace with real SMS API (e.g. MSG91) before deploying
        otp = '123456'
    else:
        otp = str(random.randint(100000, 999999))

    store_otp(phone, otp, raw_phone)

    response = {'ok': True, 'message': f'OTP sent to {phone}'}
    if getattr(django_settings, 'DEBUG', False):
        response['demo_otp'] = otp
    return JsonResponse(response)
