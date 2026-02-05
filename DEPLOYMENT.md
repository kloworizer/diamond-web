# Deployment Guide: PythonAnywhere - Complete Commands

This guide provides complete step-by-step commands to deploy the Django Diamond Web application to PythonAnywhere.

## Prerequisites
- PythonAnywhere account (username: `diamondweb` or your choice)
- Git repository URL
- Site URL will be: `https://diamondweb.pythonanywhere.com/`

---

## PART A: Setup on PythonAnywhere Console

### Step 1: Create PythonAnywhere Account
1. Go to https://www.pythonanywhere.com/
2. Sign up with username `diamondweb`
3. From dashboard, click **"Consoles"** → **"Bash"**

### Step 2: Clone and Setup Project
Run these commands in the PythonAnywhere Bash console:

```bash
# Navigate to home directory
cd ~

# Clone your repository (replace with your actual repo URL)
git clone https://github.com/yourusername/diamond-web.git diamond-web

# Enter project directory
cd diamond-web

# Create virtual environment with Python 3.10
mkvirtualenv --python=/usr/bin/python3.10 diamond-web

# Virtual environment is now active (you'll see (diamond-web) in prompt)
# Install dependencies
pip install -r requirements/base.txt
pip install -r requirements/dev.txt
```

### Step 3: Create .env Configuration File
```bash
# Copy the example file
cp .env.pythonanywhere.example .env

# Generate a secure SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the generated key, then edit .env:
```bash
# Edit the .env file
nano .env
```

Update with these values (replace SECRET_KEY with your generated one):
```ini
SECRET_KEY=paste-your-generated-secret-key-here
DEBUG=True
DJANGO_SETTINGS_MODULE=config.settings.dev
ALLOWED_HOSTS=diamondweb.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://diamondweb.pythonanywhere.com
```

Press `Ctrl+X`, then `Y`, then `Enter` to save and exit.

### Step 4: Setup Database
```bash
# Run migrations
python manage.py migrate

# Create superuser account
python manage.py createsuperuser
```

Enter admin credentials when prompted:
- Username: (your choice)
- Email: (optional)
- Password: (secure password)

### Step 5: Collect Static Files
```bash
python manage.py collectstatic --noinput
```

You should see static files being copied to `staticfiles/` directory.

---

## PART B: Configure Web App on PythonAnywhere Dashboard

### Step 6: Create Web App
1. Click **"Web"** tab in PythonAnywhere dashboard
2. Click **"Add a new web app"**
3. Click **"Next"** (confirms domain: diamondweb.pythonanywhere.com)
4. Select **"Manual configuration"**
5. Select **"Python 3.10"**
6. Click **"Next"** to complete

### Step 7: Set Virtual Environment Path
In the **Web** tab, find **"Virtualenv"** section:
1. Enter path: `/home/diamondweb/.virtualenvs/diamond-web`
   *(Replace `diamondweb` with your actual username)*
2. Click the checkmark ✓ to save

### Step 8: Configure WSGI File
1. In **Web** tab, find **"Code"** section
2. Click the **WSGI configuration file** link (blue text)
3. **Delete ALL existing content**
4. Paste this code:

```python
# =========================================================================
# WSGI Configuration for Diamond Web on PythonAnywhere
# =========================================================================

import os
import sys

# Add project directory to Python path
path = '/home/diamondweb/diamond-web'
if path not in sys.path:
    sys.path.insert(0, path)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(path, '.env'))

# Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**IMPORTANT:** Change `diamondweb` to your actual PythonAnywhere username in the path!

5. Click **"Save"** button (top right corner)

### Step 9: Configure Static Files
In **Web** tab, scroll to **"Static files"** section:

**Add static mapping:**
1. URL: `/static/`
2. Directory: `/home/diamondweb/diamond-web/staticfiles`
   *(Replace `diamondweb` with your username)*

Click checkmarks to save.

### Step 10: Reload Web App
1. Scroll to top of **Web** tab
2. Click the big green **"Reload diamondweb.pythonanywhere.com"** button
3. Wait 5-10 seconds

### Step 11: Test Your Site
Open in browser: **https://diamondweb.pythonanywhere.com/**

You should see your Diamond Web application running!

---

## PART C: Verify Deployment

### Check Admin Panel
Visit: https://diamondweb.pythonanywhere.com/admin/

Login with the superuser credentials you created in Step 4.

### If You See Errors

**Check Error Log:**
1. In **Web** tab, scroll to **"Log files"**
2. Click **"Error log"** link
3. Look for error messages

**Common fixes:**

```bash
# Re-activate virtual environment
workon diamond-web
cd ~/diamond-web

# Verify settings module
python manage.py check

# Re-run migrations if needed
python manage.py migrate

# Re-collect static files
python manage.py collectstatic --noinput

# Check if .env is loaded properly
python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); print('ALLOWED_HOSTS:', os.getenv('ALLOWED_HOSTS'))"
```

Then reload the web app from Web tab.

---

## PART D: Post-Deployment Commands

### Viewing Logs (in Bash console)
```bash
# View error log (live)
tail -f /var/log/diamondweb.pythonanywhere.com.error.log

# View last 50 lines of error log
tail -n 50 /var/log/diamondweb.pythonanywhere.com.error.log

# View server log
tail -f /var/log/diamondweb.pythonanywhere.com.server.log

# Press Ctrl+C to stop watching logs
```

### Update Application (After Code Changes)
```bash
# Activate virtual environment
workon diamond-web

# Navigate to project
cd ~/diamond-web

# Pull latest changes from git
git pull origin main

# Install any new dependencies
pip install -r requirements/base.txt
pip install -r requirements/dev.txt

# Run new migrations (if any)
python manage.py migrate

# Collect updated static files
python manage.py collectstatic --noinput
```

Then reload web app from **Web** tab.

### Django Management Commands
```bash
# Always activate environment first
workon diamond-web
cd ~/diamond-web

# Check for issues
python manage.py check

# Show migrations status
python manage.py showmigrations

# Create new migrations (if models changed)
python manage.py makemigrations

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Change user password
python manage.py changepassword username

# Django shell
python manage.py shell

# Run custom management commands
python manage.py your_custom_command
```

### Database Operations
```bash
# Backup database
cp ~/diamond-web/db.sqlite3 ~/diamond-web/db.sqlite3.backup

# Restore database
cp ~/diamond-web/db.sqlite3.backup ~/diamond-web/db.sqlite3

# Download database to local machine (from your local terminal)
scp diamondweb@ssh.pythonanywhere.com:~/diamond-web/db.sqlite3 ./db.sqlite3
```

---

## PART E: Troubleshooting Guide

### Common Issues and Solutions

**Issue: "DisallowedHost at /"**
```bash
# Check .env file
cat ~/diamond-web/.env

# Should contain:
# ALLOWED_HOSTS=diamondweb.pythonanywhere.com

# If missing, add it:
nano ~/diamond-web/.env
```
Then reload web app.

**Issue: "ImportError: No module named 'dotenv'"**
```bash
workon diamond-web
pip install python-dotenv
```
Then reload web app.

**Issue: Static files not loading (CSS/JS missing)**
```bash
workon diamond-web
cd ~/diamond-web
python manage.py collectstatic --noinput
```
Verify static files mapping in Web tab: `/static/` → `/home/diamondweb/diamond-web/staticfiles`

**Issue: Database errors**
```bash
workon diamond-web
cd ~/diamond-web

# Check migration status
python manage.py showmigrations

# Run migrations
python manage.py migrate

# If migration fails, check database file permissions
ls -la db.sqlite3
```

**Issue: "Internal Server Error"**
1. Check error log in Web tab
2. Verify WSGI file path is correct
3. Verify virtualenv path is correct
4. Test Django manually:
```bash
workon diamond-web
cd ~/diamond-web
python manage.py check
python manage.py runserver
# Ctrl+C to stop
```

**Issue: Changes not appearing after git pull**
```bash
# Verify you're in right directory
pwd
# Should show: /home/diamondweb/diamond-web

# Check what branch you're on
git branch

# Check for uncommitted changes
git status
---

## PART F: Switching to Production Mode

When ready to deploy with production settings:

### Step 1: Update .env File
```bash
workon diamond-web
cd ~/diamond-web
nano .env
```

Change these values:
```ini
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.prod
```

### Step 2: Run Django Deployment Check
```bash
python manage.py check --deploy
```

Review and address any warnings.

### Step 3: Update WSGI File (Optional)
If you want to enforce production settings in WSGI:
```python
# In WSGI file, before load_dotenv:
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.prod'
```

### Step 4: Reload Web App
Reload from Web tab.

---

## Quick Reference Commands

```bash
# Activate environment
workon diamond-web
cd ~/diamond-web

# Check status
python manage.py check

# View migrations
python manage.py showmigrations

# Run migrations
python manage.py migrate

# Collect static
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell

# View error logs
tail -n 50 /var/log/diamondweb.pythonanywhere.com.error.log

# View live logs
tail -f /var/log/diamondweb.pythonanywhere.com.error.log

# Backup database
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d)

# Pull updates
git pull origin main
pip install -r requirements/base.txt
python manage.py migrate
python manage.py collectstatic --noinput
# Then reload web app
```

---

## Security Checklist

- ✓ Strong SECRET_KEY generated
- ✓ DEBUG=False in production
- ✓ ALLOWED_HOSTS configured
- ✓ CSRF_TRUSTED_ORIGINS configured
- ✓ .env file not in git repository
- ✓ Static files served correctly
- ✓ HTTPS enabled (automatic on PythonAnywhere)
- ✓ Admin credentials are strong
- ✓ Regular database backups

---

## Resources

- [PythonAnywhere Help](https://help.pythonanywhere.com/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [PythonAnywhere Forums](https://www.pythonanywhere.com/forums/)
- [Django Documentation](https://docs.djangoproject.com/)

---

**Last Updated:** February 5, 2026  
**Django Version:** 5.2.10  
**Python Version:** 3.10
3. Consider:
   - Upgrading to MySQL database (paid plans)
   - Setting up proper email backend
   - Enabling additional security features
   - Setting up monitoring and logging

4. Reload the web app

## Additional Resources

- [PythonAnywhere Help](https://help.pythonanywhere.com/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [PythonAnywhere Forums](https://www.pythonanywhere.com/forums/)

## Support

For issues:
1. Check error logs first
2. Review this deployment guide
3. Check PythonAnywhere help pages
4. Contact PythonAnywhere support

---

**Last Updated:** February 5, 2026
