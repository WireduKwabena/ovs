"""
Django Settings - Base Configuration
=====================================
Common settings for all environments.

Academic Note:
--------------
Implements 12-factor app methodology for configuration management.
Environment-specific settings in separate files.
"""

import os
import importlib.util
from pathlib import Path

try:
    from decouple import config
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight dev/test envs
    def config(name, default=None, cast=None):
        value = os.getenv(name, default)
        if cast is None:
            return value
        if cast is bool:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
        return cast(value)

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

def env_bool(name: str, default: bool = False) -> bool:
    """Parse bool-like env values robustly (including deployment aliases)."""
    value = config(name, default=default)
    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()
    truthy = {"1", "true", "t", "yes", "y", "on"}
    falsy = {"0", "false", "f", "no", "n", "off", "", "prod", "production", "release"}

    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    return bool(default)


def env_list(name: str, default: str = "") -> list[str]:
    """Parse CSV or JSON-ish list env values into a clean string list."""
    raw = config(name, default=default)
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]

    text = str(raw or "").strip()
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]

    values: list[str] = []
    for chunk in text.split(","):
        item = chunk.strip().strip("\"'")
        if item:
            values.append(item)
    return values

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-j!^!kca^!j*r4=krx%(*1yfsg_5!mnehigj3svhs-64)t%p=h9')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', default=False)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', default='localhost,127.0.0.1')

def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _redis_db_url(redis_url: str, db_index: int) -> str:
    """Swap Redis DB index while preserving host/auth query parts."""
    if not isinstance(redis_url, str):
        return redis_url
    parts = redis_url.rsplit("/", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return f"{parts[0]}/{db_index}"
    return redis_url


# Application definition
ENABLE_REALTIME = config("ENABLE_REALTIME", default=False, cast=bool)

INSTALLED_APPS = [
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Custom apps
    "apps.core",
    "apps.admin_dashboard",
    "apps.authentication",
    "apps.governance",
    "apps.campaigns",
    "apps.positions",
    "apps.personnel",
    "apps.appointments",
    "apps.candidates",
    "apps.invitations",
    "apps.applications",
    "apps.interviews",
    "apps.video_calls",
    "apps.rubrics",
    "apps.notifications.apps.NotificationsConfig",
    "apps.audit",
    "apps.fraud",
    "apps.billing",
    "apps.background_checks",
    "apps.ml_monitoring",
    "ai_ml_services.apps.AiMlServicesConfig",
]

if ENABLE_REALTIME and _has_module("daphne"):
    INSTALLED_APPS.insert(0, "daphne")
if ENABLE_REALTIME and _has_module("channels"):
    INSTALLED_APPS.insert(1 if "daphne" in INSTALLED_APPS else 0, "channels")

INSTALLED_APPS.append("rest_framework")
if _has_module("rest_framework_simplejwt"):
    INSTALLED_APPS.append("rest_framework_simplejwt")
if _has_module("corsheaders"):
    INSTALLED_APPS.append("corsheaders")
if _has_module("django_filters"):
    INSTALLED_APPS.append("django_filters")
if _has_module("django_celery_beat"):
    INSTALLED_APPS.append("django_celery_beat")
if _has_module("django_celery_results"):
    INSTALLED_APPS.append("django_celery_results")
if _has_module("drf_spectacular"):
    INSTALLED_APPS.append("drf_spectacular")

USE_REDIS = config("USE_REDIS", default=True, cast=bool)

MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
if _has_module("whitenoise"):
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
if _has_module("corsheaders"):
    MIDDLEWARE.append("corsheaders.middleware.CorsMiddleware")
if _has_module("redis") and USE_REDIS:
    MIDDLEWARE.append("ai_ml_services.middleware.rate_limit.DjangoRateLimitMiddleware")
MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
try:
    import dj_database_url  # noqa: F401
except ImportError:  # pragma: no cover - optional in local/dev
    dj_database_url = None


# Custom User Model
AUTH_USER_MODEL = 'authentication.User'
AUTH_PUBLIC_REGISTRATION_ENABLED = env_bool('AUTH_PUBLIC_REGISTRATION_ENABLED', default=False)
AUTH_TWO_FACTOR_CHALLENGE_TTL_SECONDS = config(
    'AUTH_TWO_FACTOR_CHALLENGE_TTL_SECONDS',
    default=300,
    cast=int,
)
AUTH_TWO_FACTOR_BACKUP_CODE_COUNT = config(
    'AUTH_TWO_FACTOR_BACKUP_CODE_COUNT',
    default=8,
    cast=int,
)
AUTH_TWO_FACTOR_BACKUP_CODE_LENGTH = config(
    'AUTH_TWO_FACTOR_BACKUP_CODE_LENGTH',
    default=8,
    cast=int,
)
AUTH_RECENT_AUTH_MAX_AGE_SECONDS = config(
    'AUTH_RECENT_AUTH_MAX_AGE_SECONDS',
    default=900,
    cast=int,
)
AUTHZ_STAFF_IMPLIES_ADMIN = config(
    'AUTHZ_STAFF_IMPLIES_ADMIN',
    default=False,
    cast=bool,
)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
if _has_module("whitenoise"):
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework Configuration
default_authentication_classes = [
    "rest_framework.authentication.SessionAuthentication",
]
if _has_module("rest_framework_simplejwt"):
    default_authentication_classes.insert(
        0, "rest_framework_simplejwt.authentication.JWTAuthentication"
    )
default_filter_backends = [
    "rest_framework.filters.SearchFilter",
    "rest_framework.filters.OrderingFilter",
]
if _has_module("django_filters"):
    default_filter_backends.insert(0, "django_filters.rest_framework.DjangoFilterBackend")

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': default_authentication_classes,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': default_filter_backends,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}
if _has_module("drf_spectacular"):
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

SPECTACULAR_SETTINGS = {
    "TITLE": "AI Vetting System API",
    "DESCRIPTION": "API schema for campaign orchestration and vetting workflows.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "CommunicationChannelEnum": "apps.candidates.models.Candidate.CHANNEL_CHOICES",
        "VettingCasePriorityEnum": "apps.applications.models.VettingCase.PRIORITY_CHOICES",
        "NotificationPriorityEnum": "apps.notifications.models.Notification.PRIORITY_CHOICES",
        "VettingCaseStatusEnum": "apps.applications.models.VettingCase.STATUS_CHOICES",
        "CampaignStatusEnum": "apps.campaigns.models.VettingCampaign.STATUS_CHOICES",
        "EnrollmentStatusEnum": "apps.candidates.models.CandidateEnrollment.STATUS_CHOICES",
        "InterviewSessionStatusEnum": "apps.interviews.models.InterviewSession.STATUS_CHOICES",
        "NotificationStatusEnum": "apps.notifications.models.Notification.STATUS_CHOICES",
        "BackgroundCheckStatusEnum": "apps.background_checks.models.BackgroundCheck.STATUS_CHOICES",
        "BackgroundCheckRiskLevelEnum": "apps.background_checks.models.BackgroundCheck.RISK_LEVEL_CHOICES",
        "GovernmentBranchEnum": "apps.positions.models.GovernmentPosition.BRANCH_CHOICES",
        "FraudRiskLevelEnum": "apps.fraud.models.FraudDetectionResult.RISK_LEVELS",
        "VideoMeetingEventScopeEnum": "apps.video_calls.models.VideoMeetingEvent.SCOPE_CHOICES",
        "VideoMeetingSeriesScopeEnum": "apps.video_calls.serializers.VIDEO_MEETING_SERIES_SCOPE_CHOICES",
    },
}

# JWT Configuration
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', default='http://localhost:3000')
CORS_ALLOW_CREDENTIALS = True
if _has_module("corsheaders"):
    try:
        from corsheaders.defaults import default_headers as cors_default_headers
    except Exception:  # pragma: no cover - defensive fallback
        cors_default_headers = (
            "accept",
            "accept-encoding",
            "authorization",
            "content-type",
            "dnt",
            "origin",
            "user-agent",
            "x-csrftoken",
            "x-requested-with",
        )

    # Active organization context is carried in a custom request header.
    # Explicitly allow it for browser preflight checks.
    CORS_ALLOW_HEADERS = tuple(
        dict.fromkeys([*cors_default_headers, "x-active-organization-id"])
    )
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000",
)

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_WORKER_SEND_TASK_EVENTS = config(
    "CELERY_WORKER_SEND_TASK_EVENTS", default=True, cast=bool
)
CELERY_TASK_SEND_SENT_EVENT = config(
    "CELERY_TASK_SEND_SENT_EVENT", default=True, cast=bool
)
CELERY_BEAT_MAX_LOOP_INTERVAL = config(
    "CELERY_BEAT_MAX_LOOP_INTERVAL", default=60, cast=int
)
if _has_module("django_celery_beat"):
    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
if _has_module("django_celery_results"):
    CELERY_RESULT_BACKEND = "django-db"

# Redis Configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CHANNELS_REDIS_URL = config('CHANNELS_REDIS_URL', default=REDIS_URL)
if ENABLE_REALTIME and _has_module("channels_redis") and USE_REDIS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CHANNELS_REDIS_URL],
            },
        }
    }
elif ENABLE_REALTIME and _has_module("channels"):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
else:
    CHANNEL_LAYERS = {}
AI_ML_RATE_LIMIT_PER_MINUTE = config('AI_ML_RATE_LIMIT_PER_MINUTE', default=120, cast=int)
AI_ML_RATE_LIMIT_REDIS_URL = config('AI_ML_RATE_LIMIT_REDIS_URL', default=REDIS_URL)
AI_ML_RATE_LIMIT_PATH_PREFIXES = tuple(
    config('AI_ML_RATE_LIMIT_PATH_PREFIXES', default='/api/', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])
)
AI_ML_MONITOR_ENABLED = config("AI_ML_MONITOR_ENABLED", default=True, cast=bool)
AI_ML_MONITOR_USE_REDIS = config(
    "AI_ML_MONITOR_USE_REDIS", default=USE_REDIS, cast=bool
)
AI_ML_MONITOR_REDIS_URL = config(
    "AI_ML_MONITOR_REDIS_URL", default=_redis_db_url(REDIS_URL, 2)
)
AI_ML_MONITOR_WINDOW_SIZE = config("AI_ML_MONITOR_WINDOW_SIZE", default=1000, cast=int)
AI_ML_MONITOR_MIN_CONFIDENCE_THRESHOLD = config(
    "AI_ML_MONITOR_MIN_CONFIDENCE_THRESHOLD", default=0.7, cast=float
)
AI_ML_MONITOR_MAX_PROCESSING_TIME = config(
    "AI_ML_MONITOR_MAX_PROCESSING_TIME", default=5.0, cast=float
)
AI_ML_MONITOR_DRIFT_WINDOW_SIZE = config(
    "AI_ML_MONITOR_DRIFT_WINDOW_SIZE", default=100, cast=int
)
AI_ML_MONITOR_DRIFT_THRESHOLD = config(
    "AI_ML_MONITOR_DRIFT_THRESHOLD", default=0.1, cast=float
)
AI_ML_APPROVAL_THRESHOLD = config("AI_ML_APPROVAL_THRESHOLD", default=85.0, cast=float)
AI_ML_MANUAL_REVIEW_THRESHOLD = config(
    "AI_ML_MANUAL_REVIEW_THRESHOLD", default=70.0, cast=float
)
AI_ML_CONSISTENCY_WEIGHTS = {
    "name": config("AI_ML_CONSISTENCY_WEIGHT_NAME", default=0.60, cast=float),
    "date": config("AI_ML_CONSISTENCY_WEIGHT_DATE", default=0.40, cast=float),
}
AI_ML_CONSISTENCY_THRESHOLDS = {
    "approve": config("AI_ML_CONSISTENCY_APPROVE_THRESHOLD", default=85.0, cast=float),
    "manual_review": config(
        "AI_ML_CONSISTENCY_MANUAL_REVIEW_THRESHOLD", default=70.0, cast=float
    ),
}

# AWS S3 Configuration (Optional)
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    
    # Storage backends
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# Email Configuration
# Environment-specific settings can override this in development/production modules.
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@vetting-system.com')

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# AI/ML Model Paths
MODEL_PATH = BASE_DIR / 'models'
MODEL_PATH.mkdir(exist_ok=True)
AI_ML_AUTHENTICITY_MODEL_PATH = config(
    "AI_ML_AUTHENTICITY_MODEL_PATH",
    default=str(MODEL_PATH / "authenticity_best.h5"),
)
AI_ML_AUTHENTICITY_TORCH_MODEL_PATH = config(
    "AI_ML_AUTHENTICITY_TORCH_MODEL_PATH",
    default=str(MODEL_PATH / "authenticity_detector.pth"),
)
AI_ML_FRAUD_MODEL_PATH = config(
    "AI_ML_FRAUD_MODEL_PATH",
    default=str(MODEL_PATH / "fraud_classifier.pkl"),
)
AI_ML_SIGNATURE_MODEL_PATH = config(
    "AI_ML_SIGNATURE_MODEL_PATH",
    default=str(MODEL_PATH / "signature_authenticity.pkl"),
)
AI_ML_RVL_CDIP_MODEL_PATH = config(
    "AI_ML_RVL_CDIP_MODEL_PATH",
    default=str(MODEL_PATH / "rvl_cdip_classifier.pkl"),
)
AI_ML_MIDV500_MODEL_PATH = config(
    "AI_ML_MIDV500_MODEL_PATH",
    default=str(MODEL_PATH / "midv500_classifier.pkl"),
)
AI_ML_PREFLIGHT_IMPORT_TIMEOUT_SECONDS = config(
    "AI_ML_PREFLIGHT_IMPORT_TIMEOUT_SECONDS",
    default=20,
    cast=int,
)
AI_ML_TRAINING_REPORT_PATH = config(
    "AI_ML_TRAINING_REPORT_PATH",
    default=str(MODEL_PATH / "training_report.json"),
)
AI_ML_DOC_CLASSIFIER_REPORT_PATH = config(
    "AI_ML_DOC_CLASSIFIER_REPORT_PATH",
    default=str(MODEL_PATH / "document_classifier_training_report.json"),
)
AI_ML_MODEL_MANIFEST_PATH = config(
    "AI_ML_MODEL_MANIFEST_PATH",
    default=str(MODEL_PATH / "model_manifest.json"),
)
AI_ML_MODEL_MANIFEST_REQUIRED = config(
    "AI_ML_MODEL_MANIFEST_REQUIRED",
    default=False,
    cast=bool,
)
AI_ML_METRIC_GATES_ENABLED = config(
    "AI_ML_METRIC_GATES_ENABLED",
    default=False,
    cast=bool,
)
AI_ML_METRIC_MIN_AUTHENTICITY_F1 = config(
    "AI_ML_METRIC_MIN_AUTHENTICITY_F1",
    default=0.70,
    cast=float,
)
AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY = config(
    "AI_ML_METRIC_MIN_AUTHENTICITY_ACCURACY",
    default=0.70,
    cast=float,
)
AI_ML_METRIC_MIN_SIGNATURE_F1 = config(
    "AI_ML_METRIC_MIN_SIGNATURE_F1",
    default=0.70,
    cast=float,
)
AI_ML_METRIC_MIN_SIGNATURE_ACCURACY = config(
    "AI_ML_METRIC_MIN_SIGNATURE_ACCURACY",
    default=0.70,
    cast=float,
)
AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1 = config(
    "AI_ML_METRIC_MIN_RVL_CDIP_MACRO_F1",
    default=0.60,
    cast=float,
)
AI_ML_METRIC_MIN_MIDV500_MACRO_F1 = config(
    "AI_ML_METRIC_MIN_MIDV500_MACRO_F1",
    default=0.40,
    cast=float,
)
AI_ML_POPPLER_PATH = config("AI_ML_POPPLER_PATH", default="")
AI_ML_IDENTITY_MATCH_THRESHOLD = config(
    "AI_ML_IDENTITY_MATCH_THRESHOLD",
    default=0.72,
    cast=float,
)
AI_ML_IDENTITY_EMBEDDING_BACKEND = config(
    "AI_ML_IDENTITY_EMBEDDING_BACKEND",
    default="auto",
)
AI_ML_IDENTITY_FACENET_WEIGHTS = config(
    "AI_ML_IDENTITY_FACENET_WEIGHTS",
    default="vggface2",
)
AI_ML_IDENTITY_VIDEO_SAMPLE_RATE = config(
    "AI_ML_IDENTITY_VIDEO_SAMPLE_RATE",
    default=8,
    cast=int,
)
AI_ML_DOC_TYPE_MISMATCH_ENABLED = config(
    "AI_ML_DOC_TYPE_MISMATCH_ENABLED",
    default=True,
    cast=bool,
)
AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE = config(
    "AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE",
    default=0.65,
    cast=float,
)
AI_ML_SOCIAL_CONSENT_REQUIRED = config(
    "AI_ML_SOCIAL_CONSENT_REQUIRED",
    default=True,
    cast=bool,
)
AI_ML_SOCIAL_VERIFY_URLS = config(
    "AI_ML_SOCIAL_VERIFY_URLS",
    default=False,
    cast=bool,
)
AI_ML_SOCIAL_HTTP_TIMEOUT = config(
    "AI_ML_SOCIAL_HTTP_TIMEOUT",
    default=5.0,
    cast=float,
)
AI_ML_SOCIAL_ALLOWED_PLATFORMS = config(
    "AI_ML_SOCIAL_ALLOWED_PLATFORMS",
    default="",
)
BACKGROUND_CHECK_DEFAULT_PROVIDER = config("BACKGROUND_CHECK_DEFAULT_PROVIDER", default="mock")
BACKGROUND_CHECK_REQUIRE_CONSENT = config("BACKGROUND_CHECK_REQUIRE_CONSENT", default=True, cast=bool)
BACKGROUND_CHECK_WEBHOOK_TOKEN = config("BACKGROUND_CHECK_WEBHOOK_TOKEN", default="")
BACKGROUND_CHECK_HTTP_BASE_URL = config("BACKGROUND_CHECK_HTTP_BASE_URL", default="")
BACKGROUND_CHECK_HTTP_API_KEY = config("BACKGROUND_CHECK_HTTP_API_KEY", default="")
BACKGROUND_CHECK_HTTP_TIMEOUT = config("BACKGROUND_CHECK_HTTP_TIMEOUT", default=15.0, cast=float)
BACKGROUND_CHECK_HTTP_SUBMIT_PATH = config("BACKGROUND_CHECK_HTTP_SUBMIT_PATH", default="/checks")
BACKGROUND_CHECK_HTTP_REFRESH_PATH_TEMPLATE = config(
    "BACKGROUND_CHECK_HTTP_REFRESH_PATH_TEMPLATE",
    default="/checks/{external_reference}",
)
BACKGROUND_CHECK_HTTP_AUTH_HEADER = config("BACKGROUND_CHECK_HTTP_AUTH_HEADER", default="Authorization")
BACKGROUND_CHECK_HTTP_AUTH_SCHEME = config("BACKGROUND_CHECK_HTTP_AUTH_SCHEME", default="Bearer")
BILLING_SUBSCRIPTION_TICKET_TTL_HOURS = config("BILLING_SUBSCRIPTION_TICKET_TTL_HOURS", default=24, cast=int)
BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED = config(
    "BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED",
    default=True,
    cast=bool,
)
BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE = config(
    "BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE",
    default=30,
    cast=int,
)
BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_ENABLED = config(
    "BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_ENABLED",
    default=True,
    cast=bool,
)
BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_PER_MINUTE = config(
    "BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_PER_MINUTE",
    default=30,
    cast=int,
)
BILLING_HEALTH_REQUIRE_STAFF = config(
    "BILLING_HEALTH_REQUIRE_STAFF",
    default=False,
    cast=bool,
)
BILLING_QUOTA_ENFORCEMENT_ENABLED = config(
    "BILLING_QUOTA_ENFORCEMENT_ENABLED",
    default=True,
    cast=bool,
)
BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH = config(
    "BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH",
    default=150,
    cast=int,
)
BILLING_PLAN_GROWTH_CANDIDATES_PER_MONTH = config(
    "BILLING_PLAN_GROWTH_CANDIDATES_PER_MONTH",
    default=600,
    cast=int,
)
BILLING_PLAN_ENTERPRISE_CANDIDATES_PER_MONTH = config(
    "BILLING_PLAN_ENTERPRISE_CANDIDATES_PER_MONTH",
    default=0,
    cast=int,
)
BILLING_PLAN_DEFAULT_CANDIDATES_PER_MONTH = config(
    "BILLING_PLAN_DEFAULT_CANDIDATES_PER_MONTH",
    default=0,
    cast=int,
)
BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED = config(
    "BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED",
    default=True,
    cast=bool,
)
BILLING_PLAN_STARTER_ORG_SEATS = config(
    "BILLING_PLAN_STARTER_ORG_SEATS",
    default=25,
    cast=int,
)
BILLING_PLAN_GROWTH_ORG_SEATS = config(
    "BILLING_PLAN_GROWTH_ORG_SEATS",
    default=100,
    cast=int,
)
BILLING_PLAN_ENTERPRISE_ORG_SEATS = config(
    "BILLING_PLAN_ENTERPRISE_ORG_SEATS",
    default=0,
    cast=int,
)
BILLING_PLAN_DEFAULT_ORG_SEATS = config(
    "BILLING_PLAN_DEFAULT_ORG_SEATS",
    default=0,
    cast=int,
)
BILLING_VETTING_REQUIRE_SCOPE_RESOLUTION = config(
    "BILLING_VETTING_REQUIRE_SCOPE_RESOLUTION",
    default=True,
    cast=bool,
)
TENANT_ORG_INTEGRITY_CHECK_ENABLED = config(
    "TENANT_ORG_INTEGRITY_CHECK_ENABLED",
    default=True,
    cast=bool,
)
TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS = config(
    "TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS",
    default=False,
    cast=bool,
)
TENANT_FAIL_ON_CROSS_ORG_LINKAGE_MISMATCH = config(
    "TENANT_FAIL_ON_CROSS_ORG_LINKAGE_MISMATCH",
    default=False,
    cast=bool,
)
BILLING_ORG_ONBOARDING_DEFAULT_TTL_HOURS = config(
    "BILLING_ORG_ONBOARDING_DEFAULT_TTL_HOURS",
    default=72,
    cast=int,
)
BILLING_ORG_ONBOARDING_DEFAULT_MAX_USES = config(
    "BILLING_ORG_ONBOARDING_DEFAULT_MAX_USES",
    default=25,
    cast=int,
)
BILLING_ORG_ONBOARDING_TOKEN_PEPPER = config(
    "BILLING_ORG_ONBOARDING_TOKEN_PEPPER",
    default="",
)
INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED = config(
    "INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED",
    default=True,
    cast=bool,
)
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_BILLING_PORTAL_RETURN_URL = config("STRIPE_BILLING_PORTAL_RETURN_URL", default="")
PAYSTACK_SECRET_KEY = config("PAYSTACK_SECRET_KEY", default="")
PAYSTACK_BASE_URL = config("PAYSTACK_BASE_URL", default="https://api.paystack.co")
PAYSTACK_CURRENCY = config("PAYSTACK_CURRENCY", default="USD")
PAYSTACK_USD_EXCHANGE_RATE = config("PAYSTACK_USD_EXCHANGE_RATE", default=1.0, cast=float)
EXCHANGE_RATE_API_URL = config("EXCHANGE_RATE_API_URL", default="")
EXCHANGE_RATE_API_TIMEOUT_SECONDS = config("EXCHANGE_RATE_API_TIMEOUT_SECONDS", default=8, cast=int)
EXCHANGE_RATE_CACHE_TTL_SECONDS = config("EXCHANGE_RATE_CACHE_TTL_SECONDS", default=3600, cast=int)
# Security Settings (will be overridden in production)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

# Application-specific settings
VETTING_SETTINGS = {
    'MAX_DOCUMENTS_PER_CASE': 20,
    'MAX_INTERVIEW_DURATION_MINUTES': 60,
    'DEFAULT_RUBRIC_NAME': 'General Purpose',
    'AUTO_ASSIGN_RUBRIC': True,
    'REQUIRE_EMAIL_VERIFICATION': True,
}

FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')
CANDIDATE_ACCESS_FRONTEND_PATH = config("CANDIDATE_ACCESS_FRONTEND_PATH", default="/candidate/access")
CANDIDATE_ACCESS_PASS_TTL_HOURS = config("CANDIDATE_ACCESS_PASS_TTL_HOURS", default=72, cast=int)
CANDIDATE_ACCESS_SESSION_TTL_HOURS = config("CANDIDATE_ACCESS_SESSION_TTL_HOURS", default=12, cast=int)
CANDIDATE_ACCESS_MAX_USES = config("CANDIDATE_ACCESS_MAX_USES", default=50, cast=int)

# Data retention policy (days)
PII_RETENTION_DAYS = config("PII_RETENTION_DAYS", default=365, cast=int)
BIOMETRIC_RETENTION_DAYS = config("BIOMETRIC_RETENTION_DAYS", default=180, cast=int)
BACKGROUND_CHECK_RETENTION_DAYS = config("BACKGROUND_CHECK_RETENTION_DAYS", default=365, cast=int)
AUDIT_LOG_RETENTION_DAYS = config("AUDIT_LOG_RETENTION_DAYS", default=730, cast=int)




# AI Interview Settings
AI_INTERVIEW_SETTINGS = {
    'MIN_QUESTIONS': 5,
    'MAX_QUESTIONS': 15,
    'REQUIRED_TOPICS': ['background', 'experience', 'education', 'motivation'],
    'DEFAULT_RESPONSE_TIMEOUT': 180,  # 3 minutes max per response
    'ENABLE_VOICE_SYNTHESIS': True,
    'TRANSCRIPTION_SERVICE': 'google',  # 'google' or 'assemblyai'
}

# OpenAI Configuration
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_MODEL = 'gpt-4'  # or 'gpt-3.5-turbo' for cost savings

# Google Cloud Configuration  
GOOGLE_APPLICATION_CREDENTIALS = config("GOOGLE_APPLICATION_CREDENTIALS", default="")


# backend/config/settings/base.py

HEYGEN_API_KEY = config("HEYGEN_API_KEY", default="")
HEYGEN_AVATAR_ID = config('HEYGEN_AVATAR_ID', default='default_professional_avatar')
HEYGEN_VOICE_ID = config('HEYGEN_VOICE_ID', default='40532bc2b15c49f2b0f4deee08ce674d')  # Professional male
HEYGEN_FRONTEND_SDK_ENABLED = config("HEYGEN_FRONTEND_SDK_ENABLED", default=False, cast=bool)
HEYGEN_AVATAR_QUALITY = config("HEYGEN_AVATAR_QUALITY", default="medium")
HEYGEN_AVATAR_ACTIVITY_IDLE_TIMEOUT = config(
    "HEYGEN_AVATAR_ACTIVITY_IDLE_TIMEOUT",
    default=300,
    cast=int,
)
HEYGEN_AVATAR_LANGUAGE = config("HEYGEN_AVATAR_LANGUAGE", default="en")
LIVEKIT_URL = config("LIVEKIT_URL", default="")
LIVEKIT_API_KEY = config("LIVEKIT_API_KEY", default="")
LIVEKIT_API_SECRET = config("LIVEKIT_API_SECRET", default="")
LIVEKIT_TOKEN_TTL_SECONDS = config("LIVEKIT_TOKEN_TTL_SECONDS", default=3600, cast=int)
VIDEO_CALLS_JOIN_GRACE_MINUTES = config(
    "VIDEO_CALLS_JOIN_GRACE_MINUTES",
    default=30,
    cast=int,
)
VIDEO_CALLS_MAX_REMINDER_BEFORE_MINUTES = config(
    "VIDEO_CALLS_MAX_REMINDER_BEFORE_MINUTES",
    default=120,
    cast=int,
)
VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS = config(
    "VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS",
    default=3,
    cast=int,
)
VIDEO_CALLS_REMINDER_RETRY_BASE_SECONDS = config(
    "VIDEO_CALLS_REMINDER_RETRY_BASE_SECONDS",
    default=60,
    cast=int,
)
VIDEO_CALLS_REMINDER_RETRY_MAX_SECONDS = config(
    "VIDEO_CALLS_REMINDER_RETRY_MAX_SECONDS",
    default=900,
    cast=int,
)
DJANGO_API_URL = config("DJANGO_API_URL", default="http://localhost:8000")
SERVICE_TOKEN = config("SERVICE_TOKEN", default="")

TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN", default="")
TWILIO_PHONE_NUMBER = config("TWILIO_PHONE_NUMBER", default="")
NOTIFICATIONS_SMS_ENABLED = config("NOTIFICATIONS_SMS_ENABLED", default=False, cast=bool)








