"""
WareFlow Django Settings
────────────────────────
Sensitive values (SECRET_KEY, DEBUG, etc.) are loaded from the .env file.
Never hardcode secrets directly in this file.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

# ── Load environment variables from .env ─────────────────────────────────────
load_dotenv()

# ── Base directory (root of the project) ─────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent


# ════════════════════════════════════════════════════════════════════════════
# SECURITY SETTINGS
# ════════════════════════════════════════════════════════════════════════════

SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-insecure-key-dev-only')

# DEBUG should be False in production
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Parse comma-separated hosts from .env
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')


# ════════════════════════════════════════════════════════════════════════════
# INSTALLED APPLICATIONS
# ════════════════════════════════════════════════════════════════════════════

INSTALLED_APPS = [
    # ── Django built-ins ─────────────────────────────────────────────────────
    'django.contrib.admin',         # Django admin (kept for dev debugging)
    'django.contrib.auth',          # Authentication framework
    'django.contrib.contenttypes',  # Content type system
    'django.contrib.sessions',      # Session management
    'django.contrib.messages',      # Flash messages (used for toasts/alerts)
    'django.contrib.staticfiles',   # Static file management

    # ── WareFlow business apps ───────────────────────────────────────────────
    'accounts',     # User authentication, roles, user management
    'warehouse',    # Core inventory domain (products, stock, locations, etc.)
    'reports',      # Dashboards, KPIs, charts, low-stock monitoring
    'audit',        # Audit log history (read-only)
]


# ════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE
# ════════════════════════════════════════════════════════════════════════════

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ════════════════════════════════════════════════════════════════════════════
# URL CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

ROOT_URLCONF = 'WareFlow.urls'


# ════════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ════════════════════════════════════════════════════════════════════════════

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # ── Templates are centralized at project root, not inside each app ──
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

WSGI_APPLICATION = 'WareFlow.wsgi.application'


# ════════════════════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════════════════════

# Using SQLite3 for development.
# When switching to MySQL later, only this block needs to change.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ════════════════════════════════════════════════════════════════════════════
# CUSTOM USER MODEL
# ════════════════════════════════════════════════════════════════════════════

# IMPORTANT: This must be set BEFORE the first migration.
# Tells Django to use our custom User model from the accounts app
# instead of the default django.contrib.auth.models.User.
AUTH_USER_MODEL = 'accounts.User'


# ════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION REDIRECTS
# ════════════════════════════════════════════════════════════════════════════

# Where unauthenticated users are sent
LOGIN_URL = '/login/'

# Where users land after login (the dashboard view will redirect by role)
LOGIN_REDIRECT_URL = '/'

# Where users land after logout
LOGOUT_REDIRECT_URL = '/login/'


# ════════════════════════════════════════════════════════════════════════════
# PASSWORD VALIDATION
# ════════════════════════════════════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ════════════════════════════════════════════════════════════════════════════
# INTERNATIONALISATION
# ════════════════════════════════════════════════════════════════════════════

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'      # Change to local timezone if needed, e.g. 'Asia/Kuala_Lumpur'
USE_I18N = True
USE_TZ = True


# ════════════════════════════════════════════════════════════════════════════
# STATIC FILES (CSS, JavaScript, Images)
# ════════════════════════════════════════════════════════════════════════════

STATIC_URL = '/static/'

# Where Django looks for static files during development
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Where collectstatic gathers files for production deployment
STATIC_ROOT = BASE_DIR / 'staticfiles'


# ════════════════════════════════════════════════════════════════════════════
# MEDIA FILES (User-uploaded files, if any)
# ════════════════════════════════════════════════════════════════════════════

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ════════════════════════════════════════════════════════════════════════════
# DEFAULT PRIMARY KEY TYPE
# ════════════════════════════════════════════════════════════════════════════

# Uses auto-incrementing integers as PKs (matches DBML schema)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'