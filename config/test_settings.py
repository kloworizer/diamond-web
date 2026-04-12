"""Test-specific Django settings."""
from config.settings import *  # noqa: F401, F403

# Disable debug toolbar and other debug-only apps during testing
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ['debug_toolbar', 'schema_graph']]
MIDDLEWARE = [m for m in MIDDLEWARE if 'debug_toolbar' not in m and 'schema_graph' not in m]

# Ensure essential middleware is present for tests
essential_middleware = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

for middleware in essential_middleware:
    if middleware not in MIDDLEWARE:
        MIDDLEWARE = list(MIDDLEWARE) + [middleware]

DEBUG = False

