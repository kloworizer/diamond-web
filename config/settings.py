"""
Unified Django settings for config project.
All environment-specific configurations are driven by environment variables in .env
"""

from pathlib import Path
import os
from dotenv import load_dotenv
from django.contrib.messages import constants as messages

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load the .env file from the project root
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

# Determine environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key-for-dev")

# Debug mode
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
import sys

# Detect when Django is running tests so development-only apps (like debug_toolbar)
# are not installed during test runs. Django sets DEBUG=False when running tests,
# but the toolbar may still be installed from DEBUG=True in .env — avoid that.
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"

# Allow hosts from environment variable
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'django_extensions',
    "diamond_web",
    "crispy_forms",
    "crispy_bootstrap5",
    "import_export",
    "dbbackup",  # django-dbbackup: database backup/restore management commands
]

# Development-only apps (skip during test runs)
if DEBUG and not RUNNING_TESTS:
    INSTALLED_APPS += [
        "debug_toolbar",
        "schema_graph",
    ]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Add debug toolbar middleware in development (skip during test runs)
if DEBUG and not RUNNING_TESTS:
    try:
        idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1
    except ValueError:
        idx = 0
    MIDDLEWARE.insert(idx, "debug_toolbar.middleware.DebugToolbarMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "diamond_web.context_processors.notifications",
                "diamond_web.context_processors.git_commit",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite3").lower()

if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "diamond_web"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    # Default to SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                # WAL mode: readers never block writers and writers never block readers.
                # This prevents "database is locked" when a long sync task holds a
                # write transaction while other requests try to read.
                "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
                # Extra wait time as a fallback for writer-writer contention.
                "timeout": 30,
            },
        }
    }

# ---------------------------------------------------------------------------
# django-dbbackup — database backup and restore
# https://django-dbbackup.readthedocs.io/
# ---------------------------------------------------------------------------
DBBACKUP_DATE_FORMAT = "%Y%m%d-%H%M%S"
DBBACKUP_FILENAME_TEMPLATE = "{datetime}.{extension}"
DBBACKUP_SEND_EMAIL = False  # set to True and configure EMAIL_* for email reports
# Backup storage is configured via STORAGES["dbbackup"] below.

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Use STORAGES (Django 4.2+ unified storage setting) for static files and dbbackup
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
    "dbbackup": {
        "BACKEND": os.getenv(
            "BACKUP_STORAGE",
            "django.core.files.storage.FileSystemStorage",
        ),
        "OPTIONS": {
            "location": os.getenv(
                "BACKUP_DIR",
                str(BASE_DIR / "backups"),
            ),
        },
    },
}

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication settings
LOGIN_URL = "login"  # Redirect to login page when user not authenticated
LOGIN_REDIRECT_URL = "home"  # Redirect to home after successful login
LOGOUT_REDIRECT_URL = "login"  # Redirect to login after logout

# Crispy forms configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Message tags configuration
MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

# Session settings: 30 minutes
SESSION_COOKIE_AGE = 30 * 60  # 30 minutes (in seconds)
SESSION_SAVE_EVERY_REQUEST = False  # avoid write-on-every-request (reduces SQLite lock contention)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Email configuration
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Security settings
if not DEBUG:
    # Production security settings
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "False").lower() == "true"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False").lower() == "true"
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
else:
    # Development security settings (more permissive)
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None

# Debug toolbar configuration (development only; skip during test runs)
if DEBUG and not RUNNING_TESTS:
    import socket
    import ipaddress

    # Base internal IPs
    INTERNAL_IPS = ["127.0.0.1", "::1", "localhost"]

    # Add any IPs specified in ALLOWED_HOSTS (if they are IPs) or resolve hostnames
    for host in ALLOWED_HOSTS:
        try:
            # If host is an IP literal, add it directly
            ipaddress.ip_address(host)
            INTERNAL_IPS.append(host)
        except Exception:
            # Try resolving hostname to IPs, ignore failures
            try:
                resolved = socket.gethostbyname_ex(host)[2]
                INTERNAL_IPS += [ip for ip in resolved if ip]
            except Exception:
                pass

    # Also add addresses derived from the server hostname (helpful in some container setups)
    try:
        _, _, _ips = socket.gethostbyname_ex(socket.gethostname())
        INTERNAL_IPS += [ip for ip in _ips if ip]
    except Exception:
        pass

    # Only show toolbar when DEBUG is True and either:
    # - request comes from an INTERNAL_IP, OR
    # - request includes ?djdt=1, OR
    # - DEBUG_TOOLBAR_ALWAYS env var is set to true
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG and (
            (request.META.get("REMOTE_ADDR") in INTERNAL_IPS)
            or (request.GET.get("djdt") == "1")
            or (os.getenv("DEBUG_TOOLBAR_ALWAYS", "False").lower() == "true")
        ),
    }

# ---------------------------------------------------------------------------
# Celery configuration
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True  # re-queue task if worker crashes mid-execution
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # one task per worker at a time (sync jobs are long)
CELERY_WORKER_POOL = 'solo'           # Windows: prefork uses POSIX semaphores (unsupported); solo runs tasks in-process

# ---------------------------------------------------------------------------
# Cache — use Redis so the Celery worker and the web process share state.
# Falls back to LocMemCache only if REDIS_CACHE_URL is explicitly set to 'locmem'.
# ---------------------------------------------------------------------------
_REDIS_CACHE_URL = os.getenv('REDIS_CACHE_URL', os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'))

if _REDIS_CACHE_URL == 'locmem':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _REDIS_CACHE_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
                'IGNORE_EXCEPTIONS': False,
            },
            'KEY_PREFIX': 'diamond',
        }
    }

# Logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO" if not DEBUG else "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": False,
        },
        "django.template": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.utils.autoreload": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
