# WSGI Environment Configuration with DEBUG enabled
# For testing WSGI deployment with debugging enabled

# Django Settings
SECRET_KEY=django-insecure-wsgi-debug-key-change-in-production
DEBUG=True
ENVIRONMENT=wsgi
ALLOWED_HOSTS=*

# CSRF Configuration
CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1

# Database Configuration
DB_ENGINE=sqlite3
# DB_ENGINE=postgresql
# DB_NAME=diamond_web_wsgi
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost
# DB_PORT=5432

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your_email@example.com
# EMAIL_HOST_PASSWORD=your_app_password
