# Production Deployment Checklist

> **Project:** Diamond — Sistem P3DE/PIDE/PMDE  
> **Use this checklist before each production release.**

---

## ✅ Pre-Deployment Preparation

### Code & Version Control
- [ ] All features are merged to `main` branch
- [ ] No unstaged or uncommitted changes
- [ ] Git tag created for release: `git tag v1.0.0 && git push --tags`
- [ ] Release branch (if any) is up to date with `main`
- [ ] CHANGELOG.md updated with release notes

### Environment Configuration
- [ ] `.env` file is configured for production (use `.env.example.prod` as reference)
- [ ] `SECRET_KEY` is a unique, long, random string (generate with: `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- [ ] `DEBUG=False`
- [ ] `ALLOWED_HOSTS` includes the production domain(s) and IP(s)
- [ ] `CSRF_TRUSTED_ORIGINS` includes the production origin(s)
- [ ] Database connection settings are correct (`DB_ENGINE=postgresql`)
- [ ] `CELERY_BROKER_URL` and `REDIS_CACHE_URL` point to the correct Redis instance
- [ ] Email configuration is correct (if used)

### Database
- [ ] All migrations are created and reviewed: `python manage.py makemigrations --check`
- [ ] Migrations applied successfully: `python manage.py migrate --run-syncdb`
- [ ] Database backed up before migration: `python manage.py dbbackup`
- [ ] If migrating from SQLite to PostgreSQL, data has been migrated
- [ ] Database indexes are optimized (run `python manage.py sqlmigrate` to review)

### Static & Media Files
- [ ] Static files collected: `python manage.py collectstatic --noinput --clear`
- [ ] Media directory exists with correct permissions
- [ ] Default DOCX templates loaded: `python manage.py load_default_templates`

---

## 🧪 Testing

### Automated Tests
- [ ] All unit tests pass: `pytest -v`
- [ ] Coverage report reviewed: target ≥ 80%
- [ ] No new test failures compared to previous release

### Manual Testing Checklist

#### Authentication
- [ ] Login with valid credentials works
- [ ] Login with invalid credentials shows error
- [ ] Logout works and redirects to login page
- [ ] Session timeout after 30 minutes of inactivity
- [ ] Password change flow works

#### Role-Based Access
- [ ] **user_p3de** can access P3DE menus only
- [ ] **user_pide** can access PIDE menus only
- [ ] **user_pmde** can access PMDE menus only
- [ ] **admin** can access sync pages and admin panel
- [ ] Unauthorized users see 403 Forbidden

#### Tiket Workflow
- [ ] Tiket can be created (Rekam)
- [ ] Research results can be recorded
- [ ] Tiket can be sent to PIDE (with ND Pengantar generation)
- [ ] PIDE can identify tiket
- [ ] PIDE can return tiket to P3DE
- [ ] PIDE can transfer tiket to PMDE
- [ ] PMDE can perform quality control
- [ ] PMDE can complete tiket
- [ ] Tiket can be cancelled at any stage

#### Master Data CRUD
- [ ] Create, Read, Update, Delete works for all master data modules
- [ ] DataTables server-side processing works (pagination, search, sort)
- [ ] Form validation works (required fields, unique constraints)

#### Reports
- [ ] All 10+ report pages load correctly
- [ ] Report filters work
- [ ] Excel export generates valid `.xlsx` files
- [ ] Report data matches database records

#### Document Generation
- [ ] Tanda Terima documents generate correctly
- [ ] ND Pengantar PIDE generates correctly
- [ ] Surat Klarifikasi generates correctly
- [ ] Surat PKDI generates correctly
- [ ] Bulk document generation works
- [ ] All placeholders are correctly populated

#### Oracle Sync (if configured)
- [ ] Connection test succeeds
- [ ] Check (dry-run) reports correct changes
- [ ] Sync completes without errors
- [ ] Synced data matches Oracle source
- [ ] Stop button works during sync
- [ ] Error log download works

#### Dashboard & Monitoring
- [ ] Dashboard (Power BI embed) loads correctly
- [ ] Quality Control page loads and displays data
- [ ] Monitoring pages load correctly

---

## 🚀 Deployment Steps

### 1. Preparation
```bash
# SSH into production server
ssh user@production-server

# Navigate to project directory
cd /home/pajak/diamond-web

# Activate virtual environment
source .venv/bin/activate
```

### 2. Pull Latest Code
```bash
# Backup current state
python manage.py dbbackup

# Pull latest changes
git pull origin main

# Install any new dependencies
pip install -r requirements/prod.txt
```

### 3. Apply Changes
```bash
# Run new migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput --clear

# Load default templates (if new templates added)
python manage.py load_default_templates
```

### 4. Restart Services
```bash
# Restart Gunicorn
sudo systemctl restart diamond_web_gunicorn

# Restart Celery worker
sudo systemctl restart diamond_web_celery

# Reload Nginx (if config changed)
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Verify Deployment
```bash
# Check service status
sudo systemctl status diamond_web_gunicorn
sudo systemctl status diamond_web_celery
sudo systemctl status nginx

# Check application health
curl -I https://diamond.pajak.go.id/keep-alive/
# Should return HTTP 200

# Check logs for errors
sudo tail -f /var/log/diamond/gunicorn-error.log
```

---

## 🔄 Rollback Plan

### If deployment fails, rollback immediately:

```bash
# 1. Revert code
git checkout [previous-stable-tag]

# 2. Restore database (if migration caused issues)
python manage.py dbrestore -i [pre-deployment-backup]

# 3. Restore static files
python manage.py collectstatic --noinput --clear

# 4. Restart services
sudo systemctl restart diamond_web_gunicorn
sudo systemctl restart diamond_web_celery
```

---

## 📊 Post-Deployment Monitoring

### First Hour
- [ ] Monitor application logs for errors
- [ ] Check all critical workflows (login, tiket creation, reports)
- [ ] Verify database connections (both PostgreSQL and Oracle)
- [ ] Monitor server resource usage (CPU, memory, disk)

### First Day
- [ ] Review slow queries / database performance
- [ ] Check Celery task queue for backlog
- [ ] Verify backup cron jobs ran successfully
- [ ] Collect user feedback on any issues

### First Week
- [ ] Review error logs for patterns
- [ ] Check disk usage (media, backups, logs)
- [ ] Verify all scheduled tasks are running
- [ ] Performance review and optimization if needed

---

## 🔐 Security Verification

- [ ] `DEBUG=False` confirmed
- [ ] `SECRET_KEY` is not default/known
- [ ] HTTPS is enforced (SSL redirect active)
- [ ] `SESSION_COOKIE_SECURE=True`
- [ ] `CSRF_COOKIE_SECURE=True`
- [ ] `X_FRAME_OPTIONS=DENY`
- [ ] `SECURE_BROWSER_XSS_FILTER=True`
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF=True`
- [ ] Database password is strong and not default
- [ ] Redis is bound to localhost (not exposed to network)
- [ ] File permissions are restrictive (755 for dirs, 644 for files)
- [ ] `.env` file is not readable by other users
- [ ] Sensitive data in backups is encrypted (if stored off-site)
