"""
Django base settings for Nowhence Clothings.

Shared settings used by both dev and prod configurations.
"""

import os
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# Build paths — one extra .parent because settings is now a package
# ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Copy the logo_black_192.png file to the static images directory
try:
    import shutil
    src_logo = BASE_DIR / 'logo_black_192.png'
    dst_logo = BASE_DIR / 'mysite' / 'static' / 'images' / 'logo_black_192.png'
    if src_logo.exists():
        dst_logo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_logo, dst_logo)
except Exception as e:
    pass


# Load .env file if it exists (keeps secrets out of source control)
_env_path = BASE_DIR / '.env'
if _env_path.is_file():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _key, _, _val = _line.partition('=')
                os.environ.setdefault(_key.strip(), _val.strip())

# ────────────────────────────────────────────────────────────────
# Core settings
# ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-wmj7tf#2y)%q^z)9hl(wmw-0bw!5r@f2&=79u4!ipthq@snu=0',
)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

# ────────────────────────────────────────────────────────────────
# Application definition
# ────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'store',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mysite.wsgi.application'

# ────────────────────────────────────────────────────────────────
# Database
# ────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ────────────────────────────────────────────────────────────────
# Password validation
# ────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ────────────────────────────────────────────────────────────────
# Internationalisation
# ────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ────────────────────────────────────────────────────────────────
# Static & media files
# ────────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'mysite' / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'


def get_media_root(base_dir: Path) -> Path:
    configured_root = os.environ.get('MEDIA_ROOT')
    if configured_root:
        return Path(configured_root)

    render_data_dir = Path('/var/lib/render/project/.data')
    if os.environ.get('RENDER') and render_data_dir.exists():
        return render_data_dir / 'media'

    return base_dir / 'media'


STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = get_media_root(BASE_DIR)
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────────────────────
# Sessions
# ────────────────────────────────────────────────────────────────
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14       # 14 days
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = False

# ────────────────────────────────────────────────────────────────
# Caching (per-process in-memory — upgrade to Redis for multi-proc)
# ────────────────────────────────────────────────────────────────
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': BASE_DIR / 'cache',
        'TIMEOUT': 300,
    }
}

# ────────────────────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "store": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# ────────────────────────────────────────────────────────────────
# Social OAuth credentials
# ────────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID', '')
FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET', '')

MSG91_AUTH_KEY = os.environ.get('MSG91_AUTH_KEY', '')
MSG91_TEMPLATE_ID = os.environ.get('MSG91_TEMPLATE_ID', '')

# ────────────────────────────────────────────────────────────────
# Razorpay Payment Gateway
# Sign up at https://dashboard.razorpay.com and get your keys.
# Use TEST keys for development, LIVE keys for production.
# ────────────────────────────────────────────────────────────────
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')        # rzp_test_xxx or rzp_live_xxx
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_CURRENCY = 'INR'
