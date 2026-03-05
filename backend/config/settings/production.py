"""
Production Settings
===================
Settings for production deployment.
"""

import copy
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
BILLING_HEALTH_REQUIRE_STAFF = config(
    "BILLING_HEALTH_REQUIRE_STAFF",
    default=True,
    cast=bool,
)
INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED = config(
    "INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED",
    default=False,
    cast=bool,
)

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"


def _is_local_host(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}


normalized_allowed_hosts = [host.strip().lower() for host in ALLOWED_HOSTS if host.strip()]
if not normalized_allowed_hosts:
    raise ImproperlyConfigured("ALLOWED_HOSTS cannot be empty in production.")
if "*" in normalized_allowed_hosts:
    raise ImproperlyConfigured("ALLOWED_HOSTS cannot contain '*' in production.")
if any(_is_local_host(host) for host in normalized_allowed_hosts):
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS cannot include localhost/loopback values in production."
    )

if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be configured in production.")
for origin in CSRF_TRUSTED_ORIGINS:
    parsed = urlparse(origin)
    if parsed.scheme != "https":
        raise ImproperlyConfigured(
            f"CSRF_TRUSTED_ORIGINS entry must use https:// in production: {origin}"
        )
    if _is_local_host(parsed.hostname or ""):
        raise ImproperlyConfigured(
            f"CSRF_TRUSTED_ORIGINS cannot include localhost/loopback values: {origin}"
        )

for origin in CORS_ALLOWED_ORIGINS:
    parsed = urlparse(origin)
    if parsed.scheme and parsed.scheme != "https":
        raise ImproperlyConfigured(
            f"CORS_ALLOWED_ORIGINS entry must use https:// in production: {origin}"
        )
    if _is_local_host(parsed.hostname or ""):
        raise ImproperlyConfigured(
            f"CORS_ALLOWED_ORIGINS cannot include localhost/loopback values: {origin}"
        )

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
if not AI_ML_METRIC_GATES_ENABLED:
    raise ImproperlyConfigured(
        "AI_ML_METRIC_GATES_ENABLED cannot be disabled in production."
    )

AI_ML_MODEL_MANIFEST_REQUIRED = config(
    "AI_ML_MODEL_MANIFEST_REQUIRED",
    default=True,
    cast=bool,
)
if not AI_ML_MODEL_MANIFEST_REQUIRED:
    raise ImproperlyConfigured(
        "AI_ML_MODEL_MANIFEST_REQUIRED cannot be disabled in production."
    )
manifest_path = Path(str(AI_ML_MODEL_MANIFEST_PATH))
if not manifest_path.is_absolute():
    manifest_path = Path(BASE_DIR) / manifest_path
if not manifest_path.exists():
    raise ImproperlyConfigured(
        f"AI_ML_MODEL_MANIFEST_PATH must point to an existing file in production: {manifest_path}"
    )


def _require_min_metric(setting_name: str, value: float, minimum: float) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{setting_name} must be numeric in production."
        ) from exc

    if numeric_value < minimum:
        raise ImproperlyConfigured(
            f"{setting_name} must be >= {minimum:.2f} in production "
            f"(got {numeric_value:.4f})."
        )
    return numeric_value


AI_ML_METRIC_MIN_AUTHENTICITY_F1 = _require_min_metric(
    "AI_ML_METRIC_MIN_AUTHENTICITY_F1",
    AI_ML_METRIC_MIN_AUTHENTICITY_F1,
    0.70,
)
AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY = _require_min_metric(
    "AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY",
    AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY,
    0.70,
)
AI_ML_METRIC_MIN_SIGNATURE_F1 = _require_min_metric(
    "AI_ML_METRIC_MIN_SIGNATURE_F1",
    AI_ML_METRIC_MIN_SIGNATURE_F1,
    0.90,
)
AI_ML_METRIC_MIN_SIGNATURE_ACCURACY = _require_min_metric(
    "AI_ML_METRIC_MIN_SIGNATURE_ACCURACY",
    AI_ML_METRIC_MIN_SIGNATURE_ACCURACY,
    0.90,
)
AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1 = _require_min_metric(
    "AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1",
    AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1,
    0.60,
)
AI_ML_METRIC_MIN_MIDV500_MACRO_F1 = _require_min_metric(
    "AI_ML_METRIC_MIN_MIDV500_MACRO_F1",
    AI_ML_METRIC_MIN_MIDV500_MACRO_F1,
    0.40,
)


def _require_positive_days(setting_name: str, value: int, minimum: int = 1) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"{setting_name} must be an integer day count in production."
        ) from exc
    if days < minimum:
        raise ImproperlyConfigured(
            f"{setting_name} must be >= {minimum} day(s) in production (got {days})."
        )
    return days


PII_RETENTION_DAYS = _require_positive_days("PII_RETENTION_DAYS", PII_RETENTION_DAYS)
BIOMETRIC_RETENTION_DAYS = _require_positive_days(
    "BIOMETRIC_RETENTION_DAYS",
    BIOMETRIC_RETENTION_DAYS,
)
BACKGROUND_CHECK_RETENTION_DAYS = _require_positive_days(
    "BACKGROUND_CHECK_RETENTION_DAYS",
    BACKGROUND_CHECK_RETENTION_DAYS,
)
AUDIT_LOG_RETENTION_DAYS = _require_positive_days(
    "AUDIT_LOG_RETENTION_DAYS",
    AUDIT_LOG_RETENTION_DAYS,
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

# Always use SMTP backend in production.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

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
