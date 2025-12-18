"""
Django settings for annotation_platform project.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
from decouple import config
from django.contrib.messages import constants as messages

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Configure WhiteNoise to serve .cjs files with the correct MIME type
WHITENOISE_MIMETYPES = {
    '.cjs': 'application/javascript',
}


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: It is strongly recommended to load the secret key from an environment variable
# instead of hardcoding it in the settings file. This prevents the key from being exposed in source control.
SECRET_KEY = config(
    "DJANGO_SECRET_KEY", default="s%45k1x(sst=dp92(kzve50jkhr*$)@#(2ly=w1q=_xr@y2(qp"
)
ADMIN_USERNAME = config("ADMIN_USERNAME", default="admin")


# SECURITY WARNING: Running a production server with DEBUG = True is a major security risk.
# It exposes sensitive information, such as detailed error pages and configuration details.
# Always set DEBUG = False in a production environment.)
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
IP_TO_LAUNCH = config("IP_TO_LAUNCH", default="http://127.0.0.1:8000/")

# As requested, host permissions are not being strictly configured for this stage.
# However, for production, you should replace '*' with your actual domain names.
# Example: ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
ALLOWED_HOSTS = ["*"]
LOGIN_URL = "/user/login/"

# Application definition

# Add this line to specify the root URL configuration
ROOT_URLCONF = "annotation_platform.urls"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "captcha",
    "task_manager",
    "user_system.apps.UserSystemConfig",
    "discussion",
    'msg_system',
    'core',
    'benchmark',
    "dashboard",
]

# Captcha Configuration
CAPTCHA_OUTPUT_FORMAT = "%(hidden_field)s%(text_field)s%(image)s"
CAPTCHA_FONT_SIZE = 40
CAPTCHA_LETTER_COLOR_FUNCT = "annotation_platform.utils.random_color_func"
CAPTCHA_IMAGE_SIZE = (150, 50)

MESSAGE_TAGS = {
    messages.DEBUG: "alert-info",
    messages.INFO: "alert-info",
    messages.SUCCESS: "alert-success",
    messages.WARNING: "alert-warning",
    messages.ERROR: "alert-danger",
}

AUTH_USER_MODEL = "user_system.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "user_system.middleware.EnforceConsentMiddleware",
    "user_system.middleware.ExtensionSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

SECURE_CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "font-src": ["'self'", "*"],
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "annotation_platform.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# SECURITY WARNING: While SQLite is convenient for development, it is not recommended for production
# due to its limitations with concurrent requests. For a production environment, consider using a more
# robust database such as PostgreSQL or MySQL.
DATABASE_TYPE = config("DATABASE_TYPE", default="sqlite")

if DATABASE_TYPE == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB"),
            "USER": config("POSTGRES_USER"),
            "PASSWORD": config("POSTGRES_PASSWORD"),
            "HOST": config("POSTGRES_HOST", default="localhost"),
            "PORT": config("POSTGRES_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
            "timeout": 30,
        }
    }


# -- Redis Configuration --
REDIS_HOST = config("REDIS_HOST", default="127.0.0.1")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_DB = config("REDIS_DB", default=0, cast=int)

# Redis Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}


# LANGUAGE_CODE = 'zh-Hans'
LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# DATA_UPLOAD_MAX_MEMORY_SIZE = None # No limit
DATA_UPLOAD_MAX_MEMORY_SIZE = None  # No limit

APPEND_SLASH = True

# Email
# For production, configure your actual email service provider's settings.

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT", cast=int)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# CSRF and CORS
CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    CORS_ORIGIN_ALLOW_ALL = True
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^http://localhost:\d+$",
        r"^http://127.0.0.1:\d+$",
        r"^chrome-extension://.*$",
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:8080",
        "http://127.0.0.1:8000",
        IP_TO_LAUNCH.rstrip("/"),
    ]
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^chrome-extension://.*$",
    ]

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    IP_TO_LAUNCH.rstrip("/"),
]

CSRF_TRUSTED_ORIGINS_REGEXES = [
    r"^chrome-extension://.*$",
]

CORS_ALLOW_METHODS = (
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
    "VIEW",
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.TemplateHTMLRenderer",
    ),
}

# SESSION_COOKIE_SAMESITE = 'None'  # Samesite='None' requires Secure=True
SESSION_COOKIE_SECURE = False  # Set to False because the server uses HTTP
# CSRF_COOKIE_SAMESITE = 'None'  # Samesite='None' requires Secure=True
CSRF_COOKIE_SECURE = False  # Set to False because the server uses HTTP

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Django 6.0 transitional setting for URLField
FORMS_URLFIELD_ASSUME_HTTPS = True

# Compression setting for rrweb_record
ENABLE_RRWEB_COMPRESSION = True