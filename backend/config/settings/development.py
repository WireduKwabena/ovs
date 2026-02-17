"""
Development Settings
====================
Settings for local development environment.
"""

import importlib.util

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Database - use local PostgreSQL or SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Disable some security features for development
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Use console email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

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

# Celery - use eager execution in development (synchronous)
CELERY_TASK_ALWAYS_EAGER = config('CELERY_EAGER', default=True, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True
