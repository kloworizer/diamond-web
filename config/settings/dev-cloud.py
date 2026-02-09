"""
Development settings.
"""

from .base import *
import socket

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow hosts for development
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Development-specific apps
INSTALLED_APPS += [
    "debug_toolbar",
    "schema_graph",
]

# Development-specific middleware
# Ensure debug toolbar middleware is present near the top
if "debug_toolbar.middleware.DebugToolbarMiddleware" not in MIDDLEWARE:
    try:
        # Prefer placing after SecurityMiddleware when available
        idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1
    except ValueError:
        idx = 0
    MIDDLEWARE.insert(idx, "debug_toolbar.middleware.DebugToolbarMiddleware")

# Dynamically detect INTERNAL_IPS (works on PythonAnywhere)
try:
    _, _, _ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = ["127.0.0.1"] + [ip[:-1] + "1" for ip in _ips]
except Exception:
    INTERNAL_IPS = ["127.0.0.1"]

# Always show the toolbar in this demo/dev environment
DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": lambda request: True,
}

# Email backend for development (console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Development-specific security settings (more permissive)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
