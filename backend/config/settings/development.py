"""
Development Settings
====================
Settings for local development environment.
"""

import importlib.util
from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

postgres_driver_available = any(
    importlib.util.find_spec(module_name) is not None
    for module_name in ("psycopg", "psycopg2")
)

if not postgres_driver_available:
    raise ImproperlyConfigured(
        "PostgreSQL driver not installed. Install psycopg2-binary or psycopg."
    )

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': config('POSTGRES_DB', 'vetai_db'),
        'USER': config('POSTGRES_USER', 'postgres'),
        'PASSWORD': config('POSTGRES_PASSWORD', 'postgres'),
        'HOST': config('POSTGRES_HOST', 'localhost'),
        'PORT': config('POSTGRES_PORT', '5432'),
    }
}

# Disable some security features for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Always print emails to terminal in development/debug.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS - allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = []

# Django Debug Toolbar (optional)
if importlib.util.find_spec("django_extensions") is not None:
    INSTALLED_APPS += [
        "django_extensions",
        # "debug_toolbar",
    ]

# MIDDLEWARE += [
#     'debug_toolbar.middleware.DebugToolbarMiddleware',
# ]

INTERNAL_IPS = [
    '127.0.0.1',
]

# Logging - more verbose in development
LOGGING['root']['level'] = 'DEBUG'

# Custom test runner: applies all app migrations (shared + tenant) to a single
# schema so plain APITestCase/TestCase tests work without per-test tenant setup.
TEST_RUNNER = "config.test_runner.AllSchemasTestRunner"

# Celery - use eager execution in development (synchronous)
CELERY_TASK_ALWAYS_EAGER = config('CELERY_EAGER', default=True, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True
if CELERY_TASK_ALWAYS_EAGER:
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
