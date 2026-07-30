"""Shared helper utilities used across view modules."""

import re
from django.contrib.auth.models import User
from django.core.cache import cache as _cache
from django.db import IntegrityError, transaction

from store.models import UserProfile

# ── Phone normalisation ──────────────────────────────────────────

def normalize_phone(raw):
    """Normalize a phone number to +91XXXXXXXXXX format (13 chars, no spaces).
    Returns (normalized, error) — error is None if valid."""
    digits = re.sub(r'[^\d]', '', raw)
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0'):
        digits = digits[1:]
    if len(digits) != 10:
        return None, 'Enter a valid 10-digit phone number.'
    return f'+91{digits}', None


def phone_digits(phone):
    """Return the last 10 digits of a normalized phone number."""
    return re.sub(r'[^\d]', '', phone)[-10:]


def _build_unique_phone_username(phone):
    digits = phone_digits(phone)
    if len(digits) == 10 and not User.objects.filter(username=digits).exists():
        return digits

    base = f'phone_{digits or "user"}'
    candidate = base
    suffix = 2
    while User.objects.filter(username=candidate).exists():
        candidate = f'{base}_{suffix}'
        suffix += 1
    return candidate


def get_or_create_phone_user(phone):
    """Resolve a user for an OTP-verified phone without hijacking numeric usernames."""
    digits = phone_digits(phone)
    profile = UserProfile.objects.filter(phone=phone).select_related('user').first()
    if profile:
        user = profile.user
        if (
            len(digits) == 10
            and user.username.startswith(('user_', 'phone_'))
            and not User.objects.filter(username=digits).exclude(pk=user.pk).exists()
        ):
            user.username = digits
            user.save(update_fields=['username'])
        return user

    while True:
        username = _build_unique_phone_username(phone)
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=username)
                user.set_unusable_password()
                user.save(update_fields=['password'])
                UserProfile.objects.create(user=user, phone=phone)
            return user
        except IntegrityError:
            # Rare race on username/profile uniqueness — retry with a fresh candidate.
            continue


# ── OTP helpers (cache-backed — works across workers) ────────────

_OTP_TTL = 300          # OTP valid for 5 minutes
_OTP_RATE_WINDOW = 60   # 1 request per phone per minute


def _otp_key(phone):
    return f'otp:{phone}'


def _otp_rate_key(phone):
    return f'otp_rate:{phone}'


def store_otp(phone, otp, raw_phone=None):
    _cache.set(_otp_key(phone), otp, _OTP_TTL)
    if raw_phone and raw_phone != phone:
        _cache.set(_otp_key(raw_phone), otp, _OTP_TTL)


def get_otp(phone, raw_phone=None):
    return _cache.get(_otp_key(phone)) or (
        _cache.get(_otp_key(raw_phone)) if raw_phone else None
    )


def clear_otp(phone, raw_phone=None):
    _cache.delete(_otp_key(phone))
    if raw_phone:
        _cache.delete(_otp_key(raw_phone))


def is_rate_limited(phone):
    key = _otp_rate_key(phone)
    if _cache.get(key):
        return True
    _cache.set(key, 1, _OTP_RATE_WINDOW)
    return False


# ── Login brute-force protection ─────────────────────────────────

_LOGIN_MAX_ATTEMPTS = 5       # lock after 5 failed attempts
_LOGIN_LOCKOUT_TIME = 900     # 15 minutes lockout


def _login_fail_key(identifier):
    return f'login_fail:{identifier}'


def get_client_ip(request):
    """Extract the real client IP, respecting X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def check_login_rate_limit(request):
    """Return (is_blocked, remaining_seconds).
    Call BEFORE authentication attempt."""
    ip = get_client_ip(request)
    key = _login_fail_key(ip)
    data = _cache.get(key)
    if data and data.get('count', 0) >= _LOGIN_MAX_ATTEMPTS:
        ttl = _cache.ttl(key) if hasattr(_cache, 'ttl') else _LOGIN_LOCKOUT_TIME
        return True, ttl
    return False, 0


def record_login_failure(request):
    """Record a failed login attempt for the client IP."""
    ip = get_client_ip(request)
    key = _login_fail_key(ip)
    data = _cache.get(key) or {'count': 0}
    data['count'] += 1
    _cache.set(key, data, _LOGIN_LOCKOUT_TIME)


def clear_login_failures(request):
    """Clear failed login counter on successful login."""
    ip = get_client_ip(request)
    _cache.delete(_login_fail_key(ip))
