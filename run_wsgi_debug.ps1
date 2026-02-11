# WSGI Server with DEBUG enabled for PowerShell
# Usage: .\run_wsgi_debug.ps1

Set-ExecutionPolicy Unrestricted -Scope Process
. d:\diamond-web\.venv\Scripts\Activate.ps1

# Copy .env.wsgi to .env for this session
Copy-Item -Path d:\diamond-web\.env.wsgi -Destination d:\diamond-web\.env -Force

# Run WSGI server using gunicorn
gunicorn --bind 127.0.0.1:8000 --workers 1 --reload config.wsgi:application
