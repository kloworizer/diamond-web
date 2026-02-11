@echo off
REM WSGI Server with DEBUG enabled
REM Usage: run_wsgi_debug.bat

cd /d %~dp0
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else if exist .venv\Scripts\activate (
    . .venv/Scripts/activate
)

REM Copy .env.wsgi to .env for this session
copy .env.wsgi .env /Y

REM Run WSGI server using gunicorn
gunicorn --bind 127.0.0.1:8000 --workers 1 --reload config.wsgi:application

REM Restore previous .env if needed
