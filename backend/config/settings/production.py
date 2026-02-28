"""
Production Settings
===================
Settings for production deployment.
"""

import copy

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Database - use PostgreSQL in production
database_url = config("DATABASE_URL", default="")
if not database_url:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set in production and must point to PostgreSQL."
    )

if not database_url.startswith(("postgres://", "postgresql://")):
    raise ImproperlyConfigured(
        "DATABASE_URL must use a PostgreSQL scheme (postgres:// or postgresql://)."
    )

if not dj_database_url:
    raise ImproperlyConfigured(
        "dj-database-url is required in production to parse DATABASE_URL."
    )

DATABASES = {
    "default": dj_database_url.config(
        default=database_url,
        conn_max_age=600,
        ssl_require=True,
    )
}

# Require a strong explicit secret key in production.
if not SECRET_KEY or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured(
        "SECRET_KEY cannot use the default insecure Django value in production."
    )
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
    raise ImproperlyConfigured(
        "SECRET_KEY must be at least 50 chars with adequate entropy in production."
    )

# AI quality gates should be enforced in production by default.
AI_ML_METRIC_GATES_ENABLED = config(
    "AI_ML_METRIC_GATES_ENABLED",
    default=True,
    cast=bool,
)

# Background checks must not run against mock providers in production.
background_provider = str(BACKGROUND_CHECK_DEFAULT_PROVIDER or "").strip().lower()
if background_provider == "mock":
    raise ImproperlyConfigured(
        "BACKGROUND_CHECK_DEFAULT_PROVIDER cannot be 'mock' when DEBUG=False."
    )

if not BACKGROUND_CHECK_WEBHOOK_TOKEN:
    raise ImproperlyConfigured(
        "BACKGROUND_CHECK_WEBHOOK_TOKEN is required in production."
    )

if background_provider == "http":
    if not BACKGROUND_CHECK_HTTP_BASE_URL:
        raise ImproperlyConfigured(
            "BACKGROUND_CHECK_HTTP_BASE_URL is required for http background check provider."
        )
    if not str(BACKGROUND_CHECK_HTTP_BASE_URL).startswith(("http://", "https://")):
        raise ImproperlyConfigured(
            "BACKGROUND_CHECK_HTTP_BASE_URL must start with http:// or https://."
        )
    if not BACKGROUND_CHECK_HTTP_API_KEY:
        raise ImproperlyConfigured(
            "BACKGROUND_CHECK_HTTP_API_KEY is required for http background check provider."
        )

# Email - use real SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Logging - log to file and external service
LOGGING = copy.deepcopy(LOGGING)
LOGGING['handlers']['file']['filename'] = config(
    'DJANGO_LOG_FILE',
    default=str(BASE_DIR / 'logs' / 'django.log')
)

# Optional: Sentry for error tracking
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ModuleNotFoundError:
        sentry_sdk = None
        DjangoIntegration = None
    if sentry_sdk and DjangoIntegration:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False
        )

# Disable browsable API in production
REST_FRAMEWORK = copy.deepcopy(REST_FRAMEWORK)
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]