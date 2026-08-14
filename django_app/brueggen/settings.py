import os
import secrets
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Azure detection ───────────────────────────────────────────────────────────
_ON_AZURE = bool(os.environ.get('WEBSITE_SITE_NAME', ''))

# ── Data directory (persistent on Azure: /home/data, local: data/) ────────────
_DATA_DIR = Path('/home/data') if _ON_AZURE else BASE_DIR / 'data'
_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Secret key ───────────────────────────────────────────────────────────────
# On Azure: set DJANGO_SECRET_KEY in App Service → Configuration → App settings
# Locally:  persisted in data/.secret_key so it survives restarts
_SECRET_KEY_ENV = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if _SECRET_KEY_ENV:
    SECRET_KEY = _SECRET_KEY_ENV
else:
    _KEY_FILE = _DATA_DIR / '.secret_key'
    if _KEY_FILE.exists():
        SECRET_KEY = _KEY_FILE.read_text().strip()
    else:
        SECRET_KEY = secrets.token_hex(32)
        _KEY_FILE.write_text(SECRET_KEY)

DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']

# Django 4.0+ requires CSRF_TRUSTED_ORIGINS for HTTPS requests.
# Azure sets WEBSITE_HOSTNAME automatically (e.g. myapp.azurewebsites.net).
_HOSTNAME = os.environ.get('WEBSITE_HOSTNAME', '').strip()
CSRF_TRUSTED_ORIGINS = [f'https://{_HOSTNAME}'] if _HOSTNAME else []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'protokoly',
    'serwerownia',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'protokoly.middleware.ForcePasswordChangeMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'brueggen.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'brueggen.wsgi.application'

# PostgreSQL if DATABASE_URL is set, e.g.
# postgresql://user:password@host.postgres.database.azure.com/dbname?sslmode=require
# (Azure App Service → Configuration → App settings), otherwise local SQLite.
_DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if _DATABASE_URL:
    _url = urlparse(_DATABASE_URL)
    _sslmode = parse_qs(_url.query).get('sslmode', ['require'])[0]
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': _url.hostname,
            'PORT': _url.port or 5432,
            'NAME': _url.path.lstrip('/'),
            'USER': _url.username,
            'PASSWORD': _url.password,
            'OPTIONS': {'sslmode': _sslmode},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': _DATA_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []  # Relaxed for internal tool

LANGUAGE_CODE = 'pl'
TIME_ZONE = 'Europe/Warsaw'
USE_I18N = True
USE_TZ = True

MEDIA_URL = '/media/'
MEDIA_ROOT = _DATA_DIR / 'media'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# Map Django's ERROR level to Bootstrap's 'danger' CSS class
from django.contrib.messages import constants as msg_const
MESSAGE_TAGS = {msg_const.ERROR: 'danger'}

SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours
