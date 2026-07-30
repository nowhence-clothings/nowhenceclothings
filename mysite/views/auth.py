"""Authentication views — login, logout, Google OAuth, Facebook OAuth."""

import json
import logging
import urllib.request
import urllib.parse
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings as django_settings
from store.models import UserProfile
from .helpers import (normalize_phone, get_otp, clear_otp, get_or_create_phone_user,
                      check_login_rate_limit, record_login_failure,
                      clear_login_failures)

logger = logging.getLogger(__name__)


def customer_login(request):
    """Customer login & signup page (not admin)."""
    from django.shortcuts import render

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.POST.get('_ajax') == '1'
        or request.headers.get('Accept', '').startswith('application/json')
    )

    if request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser):
        if is_ajax:
            return JsonResponse({'ok': True, 'redirect': '/'})
        return redirect('home')

    if request.method == 'POST':
        action = request.POST.get('action', 'login')

        if action == 'login':
            # ── Brute-force protection ──
            blocked, wait = check_login_rate_limit(request)
            if blocked:
                err = f'Too many failed attempts. Try again in {wait // 60} minutes.'
                if is_ajax:
                    return JsonResponse({'ok': False, 'errors': {'__all__': err}})
                messages.error(request, err)
                return render(request, 'login.html')

            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')

            errors = {}
            if not username:
                errors['username'] = 'Username is required.'
            if not password:
                errors['password'] = 'Password is required.'
            if errors:
                if is_ajax:
                    return JsonResponse({'ok': False, 'errors': errors})
                for msg in errors.values():
                    messages.error(request, msg)
            else:
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    if user.is_superuser or user.is_staff:
                        err = 'Please use the admin panel to sign in.'
                        if is_ajax:
                            return JsonResponse({'ok': False, 'errors': {'__all__': err}})
                        messages.error(request, err)
                    else:
                        login(request, user)
                        clear_login_failures(request)
                        next_url = request.GET.get('next', '/')
                        if is_ajax:
                            return JsonResponse({
                                'ok': True,
                                'redirect': next_url,
                                'message': f'Welcome back, {user.first_name or user.username}!',
                            })
                        return redirect(next_url)
                else:
                    record_login_failure(request)
                    err = 'Invalid username or password.'
                    if is_ajax:
                        return JsonResponse({'ok': False, 'errors': {'__all__': err}})
                    messages.error(request, err)

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
            if not confirm:
                errors['confirm_password'] = 'Please confirm your password.'
            if username and User.objects.filter(username=username).exists():
                errors['username'] = 'Username already taken.'
            if email and User.objects.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

            if errors:
                if is_ajax:
                    return JsonResponse({'ok': False, 'errors': errors})
                for msg in errors.values():
                    messages.error(request, msg)
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                UserProfile.objects.get_or_create(user=user)
                login(request, user)
                welcome = f'Welcome, {first_name or username}! Your account has been created.'
                if is_ajax:
                    return JsonResponse({'ok': True, 'redirect': '/', 'message': welcome})
                messages.success(request, welcome)
                return redirect('home')

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

            stored_otp = get_otp(phone, raw_phone)
            logger.debug("[PHONE_LOGIN] normalized=%s", phone)

            if errors:
                if is_ajax:
                    return JsonResponse({'ok': False, 'errors': errors})
                for msg in errors.values():
                    messages.error(request, msg)
            elif stored_otp != otp:
                err = 'Invalid or expired OTP.'
                if is_ajax:
                    return JsonResponse({'ok': False, 'errors': {'otp': err}})
                messages.error(request, err)
            else:
                # OTP valid — find or create user by phone
                clear_otp(phone, raw_phone)
                user = get_or_create_phone_user(phone)
                if user.is_superuser or user.is_staff:
                    err = 'Please use the admin panel to sign in.'
                    if is_ajax:
                        return JsonResponse({'ok': False, 'errors': {'__all__': err}})
                    messages.error(request, err)
                else:
                    login(request, user)
                    logger.debug("[PHONE_LOGIN] Login SUCCESS for user=%s", user.username)
                    if is_ajax:
                        return JsonResponse({'ok': True, 'redirect': '/', 'message': 'Signed in successfully!'})
                    return redirect('home')

    # Catch-all: if somehow an AJAX POST fell through without returning
    if request.method == 'POST' and is_ajax:
        return JsonResponse({'ok': False, 'errors': {'__all__': 'Something went wrong. Please try again.'}})

    return render(request, 'login.html')


def customer_logout(request):
    """Logout customer and redirect to home."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


# ── Google OAuth ──

def google_login(request):
    """Redirect to Google OAuth consent screen."""
    client_id = getattr(django_settings, 'GOOGLE_CLIENT_ID', '')
    redirect_uri = request.build_absolute_uri('/account/google/callback/')
    scope = 'openid email profile'
    url = (
        f'https://accounts.google.com/o/oauth2/v2/auth?'
        f'client_id={client_id}&redirect_uri={redirect_uri}'
        f'&response_type=code&scope={scope}&access_type=offline&prompt=consent'
    )
    if not client_id:
        messages.error(request, 'Google login is not configured yet.')
        return redirect('customer_login')
    return redirect(url)


def google_callback(request):
    """Handle Google OAuth callback — exchange code for user info."""
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Google login failed.')
        return redirect('customer_login')

    client_id = getattr(django_settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(django_settings, 'GOOGLE_CLIENT_SECRET', '')
    redirect_uri = request.build_absolute_uri('/account/google/callback/')

    token_data = urllib.parse.urlencode({
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }).encode()
    try:
        token_req = urllib.request.Request('https://oauth2.googleapis.com/token', data=token_data)
        token_resp = urllib.request.urlopen(token_req)
        tokens = json.loads(token_resp.read())
        access_token = tokens['access_token']
    except Exception:
        messages.error(request, 'Failed to authenticate with Google.')
        return redirect('customer_login')

    try:
        info_req = urllib.request.Request('https://www.googleapis.com/oauth2/v2/userinfo')
        info_req.add_header('Authorization', f'Bearer {access_token}')
        info_resp = urllib.request.urlopen(info_req)
        info = json.loads(info_resp.read())
    except Exception:
        messages.error(request, 'Failed to get Google profile.')
        return redirect('customer_login')

    email = info.get('email', '')
    google_id = info.get('id', '')

    user = None
    profile = UserProfile.objects.filter(google_id=google_id).select_related('user').first() if google_id else None
    if profile:
        user = profile.user
    if not user and email:
        user = User.objects.filter(email=email).first()
    if not user:
        username = email.split('@')[0] if email else f'google_{google_id}'
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{n}'
            n += 1
        user = User.objects.create_user(
            username=username, email=email,
            first_name=info.get('given_name', ''),
            last_name=info.get('family_name', ''),
        )
        user.set_unusable_password()
        user.save()

    changed_fields = []
    if not user.first_name and info.get('given_name'):
        user.first_name = info['given_name']
        changed_fields.append('first_name')
    if not user.last_name and info.get('family_name'):
        user.last_name = info['family_name']
        changed_fields.append('last_name')
    if not user.email and email:
        user.email = email
        changed_fields.append('email')
    if changed_fields:
        user.save(update_fields=changed_fields)

    prof, _ = UserProfile.objects.get_or_create(user=user)
    if google_id and not prof.google_id:
        prof.google_id = google_id
        prof.save(update_fields=['google_id'])
    if user.is_superuser or user.is_staff:
        messages.error(request, 'Admin accounts cannot log in here. Please use the admin panel.')
        return redirect('customer_login')
    login(request, user)
    messages.success(request, f'Welcome, {user.first_name or user.username}!')
    return redirect('home')


# ── Facebook OAuth ──

def facebook_login(request):
    """Redirect to Facebook OAuth consent screen."""
    app_id = getattr(django_settings, 'FACEBOOK_APP_ID', '')
    redirect_uri = request.build_absolute_uri('/account/facebook/callback/')
    url = (
        f'https://www.facebook.com/v18.0/dialog/oauth?'
        f'client_id={app_id}&redirect_uri={redirect_uri}'
        f'&scope=email,public_profile'
    )
    if not app_id:
        messages.error(request, 'Facebook login is not configured yet.')
        return redirect('customer_login')
    return redirect(url)


def facebook_callback(request):
    """Handle Facebook OAuth callback."""
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Facebook login failed.')
        return redirect('customer_login')

    app_id = getattr(django_settings, 'FACEBOOK_APP_ID', '')
    app_secret = getattr(django_settings, 'FACEBOOK_APP_SECRET', '')
    redirect_uri = request.build_absolute_uri('/account/facebook/callback/')

    token_url = (
        f'https://graph.facebook.com/v18.0/oauth/access_token?'
        f'client_id={app_id}&redirect_uri={urllib.parse.quote(redirect_uri)}'
        f'&client_secret={app_secret}&code={code}'
    )
    try:
        token_resp = urllib.request.urlopen(token_url)
        tokens = json.loads(token_resp.read())
        access_token = tokens['access_token']
    except Exception:
        messages.error(request, 'Failed to authenticate with Facebook.')
        return redirect('customer_login')

    try:
        info_url = f'https://graph.facebook.com/me?fields=id,first_name,last_name,email&access_token={access_token}'
        info_resp = urllib.request.urlopen(info_url)
        info = json.loads(info_resp.read())
    except Exception:
        messages.error(request, 'Failed to get Facebook profile.')
        return redirect('customer_login')

    email = info.get('email', '')
    fb_id = info.get('id', '')

    user = None
    profile = UserProfile.objects.filter(facebook_id=fb_id).select_related('user').first() if fb_id else None
    if profile:
        user = profile.user
    if not user and email:
        user = User.objects.filter(email=email).first()
    if not user and fb_id:
        user = User.objects.filter(username=f'fb_{fb_id}').first()
    if not user:
        username = email.split('@')[0] if email else f'fb_{fb_id}'
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{n}'
            n += 1
        user = User.objects.create_user(
            username=username, email=email,
            first_name=info.get('first_name', ''),
            last_name=info.get('last_name', ''),
        )
        user.set_unusable_password()
        user.save()

    changed_fields = []
    if not user.first_name and info.get('first_name'):
        user.first_name = info['first_name']
        changed_fields.append('first_name')
    if not user.last_name and info.get('last_name'):
        user.last_name = info['last_name']
        changed_fields.append('last_name')
    if not user.email and email:
        user.email = email
        changed_fields.append('email')
    if changed_fields:
        user.save(update_fields=changed_fields)

    prof, _ = UserProfile.objects.get_or_create(user=user)
    if fb_id and not prof.facebook_id:
        prof.facebook_id = fb_id
        prof.save(update_fields=['facebook_id'])
    if user.is_superuser or user.is_staff:
        messages.error(request, 'Admin accounts cannot log in here. Please use the admin panel.')
        return redirect('customer_login')
    login(request, user)
    messages.success(request, f'Welcome, {user.first_name or user.username}!')
    return redirect('home')
