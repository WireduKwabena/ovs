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
from decouple import config

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


# Application definition
INSTALLED_APPS = [
    "daphne",
    "channels",
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Custom apps
    "apps.core",
    "apps.authentication",
    "apps.campaigns",
    "apps.candidates",
    "apps.invitations",
]

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

MIDDLEWARE = ["django.middleware.security.SecurityMiddleware"]
if _has_module("whitenoise"):
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")
if _has_module("corsheaders"):
    MIDDLEWARE.append("corsheaders.middleware.CorsMiddleware")
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

# DATABASES = {
#     'default': dj_database_url.config(
#         default=config('DATABASE_URL', default='sqlite:///db.sqlite3'),
#         conn_max_age=600
#     )
# }

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
if _has_module("django_celery_beat"):
    CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
if _has_module("django_celery_results"):
    CELERY_RESULT_BACKEND = "django-db"

# Redis Configuration
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

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

# OAuth Settings
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_CLIENT_ID_2 = config('GOOGLE_CLIENT_ID_2', default='')

GITHUB_CLIENT_ID = config('GITHUB_CLIENT_ID', default='')
GITHUB_CLIENT_SECRET = config('GITHUB_CLIENT_SECRET', default='')

FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# -------------------------------------------------------------------
# Database
# -------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', 'vetai_db'),
        'USER': config('POSTGRES_USER', 'postgres'),
        'PASSWORD': config('POSTGRES_PASSWORD', 'postgres'),
        'HOST': config('POSTGRES_HOST', 'localhost'),
        'PORT': config('POSTGRES_PORT', '5432'),
        
    }
}

# backend/config/settings/base.py

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
