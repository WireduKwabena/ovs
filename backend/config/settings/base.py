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

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-j!^!kca^!j*r4=krx%(*1yfsg_5!mnehigj3svhs-64)t%p=h9')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

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
    "apps.campaigns",
    "apps.candidates",
    "apps.invitations",
    "apps.applications",
    "apps.interviews",
    "apps.rubrics",
    "apps.notifications.apps.NotificationsConfig",
    "apps.audit",
    "apps.fraud",
    "apps.ml_monitoring",
    "ai_ml_services.apps.AiMlServicesConfig",
]

if _has_module("daphne"):
    INSTALLED_APPS.insert(0, "daphne")
if _has_module("channels"):
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
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOW_CREDENTIALS = True

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
if _has_module("channels_redis") and USE_REDIS:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [CHANNELS_REDIS_URL],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
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
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend'
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
DJANGO_API_URL = config("DJANGO_API_URL", default="http://localhost:8000")
SERVICE_TOKEN = config("SERVICE_TOKEN", default="")



