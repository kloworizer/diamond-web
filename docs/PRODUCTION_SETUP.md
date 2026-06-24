# Panduan Setup Produksi

> **Terakhir Diperbarui:** June 23, 2026  
> **Target:** Deployment produksi aplikasi Diamond Web

---

## Daftar Isi

- [Kebutuhan Sistem](#kebutuhan-sistem)
- [Variabel Lingkungan](#variabel-lingkungan)
- [Setup Database (PostgreSQL)](#setup-database-postgresql)
- [Instalasi Dependensi](#instalasi-dependensi)
- [File Statis & Media](#file-statis--media)
- [Konfigurasi Web Server](#konfigurasi-web-server)
  - [Gunicorn (Layanan Systemd)](#gunicorn-layanan-systemd)
  - [Reverse Proxy Nginx](#reverse-proxy-nginx)
- [Setup Celery & Redis](#setup-celery--redis)
- [Konfigurasi Backup](#konfigurasi-backup)
- [Logging & Monitoring](#logging--monitoring)
- [Health Check & Keep-Alive](#health-check--keep-alive)
- [Pemecahan Masalah](#pemecahan-masalah)

---

## Kebutuhan Sistem

### Minimum (Deploy Kecil)
| Resource | Spec |
|----------|------|
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 20 GB SSD |
| OS | Ubuntu 22.04 LTS / Rocky Linux 9 / Windows Server 2022 |

### Rekomendasi (Produksi)
| Resource | Spec |
|----------|------|
| CPU | 4+ cores |
| RAM | 8+ GB |
| Disk | 50 GB SSD (expandable for media/backups) |
| OS | Ubuntu 22.04 LTS |

### Kebutuhan Software
| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Application runtime |
| PostgreSQL | 14+ | Primary database (production) |
| Redis | 6+ | Cache & Celery broker |
| Nginx | 1.24+ | Reverse proxy & static files |
| Oracle Instant Client | 21+ | Oracle sync (thick mode) — optional |

---

## Variabel Lingkungan

Copy the production environment template:

```bash
cp .env.example.prod .env
```

### Variabel Wajib

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key (generate a long random string) | `django-insecure-<64-char-random>` |
| `DEBUG` | Must be `False` in production | `False` |
| `ALLOWED_HOSTS` | Comma-separated domain/IP list | `diamond.pajak.go.id,10.10.10.50` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins for CSRF | `http://diamond.pajak.go.id` |
| `DB_ENGINE` | Database engine | `postgresql` |
| `DB_NAME` | Database name | `diamond_web_prod` |
| `DB_USER` | Database user | `diamond_user` |
| `DB_PASSWORD` | Database password | *(secure password)* |
| `DB_HOST` | Database host | `localhost` or `10.10.10.x` |
| `DB_PORT` | Database port | `5432` |
| `CELERY_BROKER_URL` | Redis URL for Celery broker | `redis://localhost:6379/0` |
| `REDIS_CACHE_URL` | Redis URL for cache | `redis://localhost:6379/1` |

### Variabel Sinkronisasi Oracle (jika digunakan)

| Variable | Description |
|----------|-------------|
| `ORACLE_USER` | Oracle database username |
| `ORACLE_PASSWORD` | Oracle database password |
| `ORACLE_HOST` | Oracle server hostname/IP |
| `ORACLE_PORT` | Oracle listener port (default: 1521) |
| `ORACLE_SERVICE_NAME` | Oracle service name (e.g., `ORCLPDB1`) |
| `ORACLE_SECONDARY_*` | Secondary Oracle connection (optional) |

### Variabel Email (jika digunakan)

| Variable | Description |
|----------|-------------|
| `EMAIL_HOST` | SMTP server |
| `EMAIL_PORT` | SMTP port (587 for TLS) |
| `EMAIL_USE_TLS` | `True` to use TLS |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |

---

## Setup Database (PostgreSQL)

### 1. Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib libpq-dev

# Rocky Linux / CentOS
sudo dnf install postgresql-server postgresql-contrib postgresql-devel
sudo postgresql-setup --initdb
sudo systemctl start postgresql
```

### 2. Create Database & User

```bash
sudo -u postgres psql
```

```sql
CREATE USER diamond_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE diamond_web_prod OWNER diamond_user;
GRANT ALL PRIVILEGES ON DATABASE diamond_web_prod TO diamond_user;

-- Grant schema permissions
\c diamond_web_prod
GRANT ALL ON SCHEMA public TO diamond_user;
```

### 3. Configure pg_hba.conf

Edit `/etc/postgresql/*/main/pg_hba.conf` to allow password-based login:

```conf
# IPv4 local connections:
host    diamond_web_prod    diamond_user    127.0.0.1/32    md5
```

### 4. Run Migrations

```bash
python manage.py migrate
```

---

## Instalasi Dependensi

### Di server dengan akses internet

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements/prod.txt
```

### Di server tanpa internet

1. On a development machine with internet, download packages:

```bash
pip download -r requirements/prod.txt -d ./packages
```

2. Copy the `packages/` folder to the server (e.g., via SCP or USB).

3. On the server, install from local packages:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --no-index --find-links=./packages -r requirements/prod.txt
```

---

## File Statis & Media

```bash
# Collect all static files into STATIC_ROOT
python manage.py collectstatic --noinput
```

Static files will be collected to `staticfiles/` directory.

Media files (user uploads, generated documents) are stored in `media/`.

---

## Konfigurasi Web Server

### Gunicorn (Layanan Systemd)

Create `/etc/systemd/system/diamond_web_gunicorn.service`:

```ini
[Unit]
Description=Diamond Web - Gunicorn WSGI Server
After=network.target postgresql.service redis.service

[Service]
User=pajak
Group=pajak
WorkingDirectory=/home/pajak/diamond-web
EnvironmentFile=/home/pajak/diamond-web/.env
Environment=PYTHONUNBUFFERED=1
Environment=DJANGO_SETTINGS_MODULE=config.settings
ExecStart=/home/pajak/diamond-web/.venv/bin/gunicorn \
    --workers 3 \
    --worker-class sync \
    --timeout 120 \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/diamond/gunicorn-access.log \
    --error-logfile /var/log/diamond/gunicorn-error.log \
    --log-level info \
    config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable diamond_web_gunicorn
sudo systemctl start diamond_web_gunicorn
```

> **Note:** `gunicorn` is only available on Linux/Unix. On Windows Server, use `waitress` instead:
> ```bash
> pip install waitress
> waitress-serve --port=8000 config.wsgi:application
> ```

### Reverse Proxy Nginx

Create `/etc/nginx/sites-available/diamond`:

```nginx
server {
    listen 80;
    server_name diamond.pajak.go.id;

    client_max_body_size 50M;

    # Static files
    location /static/ {
        alias /home/pajak/diamond-web/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/pajak/diamond-web/media/;
        expires 7d;
        add_header Cache-Control "public";
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    # WebSocket support for keep-alive endpoint
    location /keep-alive/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/diamond /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Setup Celery & Redis

### Instalasi Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl enable redis
sudo systemctl start redis

# Verify
redis-cli ping
# Output: PONG
```

### Layanan Celery Worker

Create `/etc/systemd/system/diamond_web_celery.service`:

```ini
[Unit]
Description=Diamond Web - Celery Worker
After=network.target redis.service

[Service]
User=pajak
Group=pajak
WorkingDirectory=/home/pajak/diamond-web
EnvironmentFile=/home/pajak/diamond-web/.env
Environment=PYTHONUNBUFFERED=1
Environment=DJANGO_SETTINGS_MODULE=config.settings
ExecStart=/home/pajak/diamond-web/.venv/bin/celery \
    -A config worker \
    -l info \
    --concurrency=1 \
    --pool=solo
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable diamond_web_celery
sudo systemctl start diamond_web_celery
```

> **Note:** `--pool=solo` is required on Windows. On Linux, you can use `--pool=prefork` for better performance (multiple workers).

### Monitoring Celery

```bash
# Check worker status
sudo systemctl status diamond_web_celery

# View logs
sudo journalctl -u diamond_web_celery -f

# Flower (web-based monitoring, optional)
pip install flower
celery -A config flower --port=5555
```

---

## Konfigurasi Backup

### Backup Harian Otomatis (Cron)

Add to crontab (`crontab -e`):

```cron
# Daily database backup at 2 AM
0 2 * * * cd /home/pajak/diamond-web && .venv/bin/python manage.py dbbackup >> /var/log/diamond/backup.log 2>&1

# Daily media backup at 3 AM
0 3 * * * cd /home/pajak/diamond-web && .venv/bin/python manage.py mediabackup >> /var/log/diamond/backup.log 2>&1

# Cleanup backups older than 30 days
0 4 * * * find /var/backups/diamond -type f -name "*.dump" -mtime +30 -delete
```

### Restore dari Backup

```bash
# List available backups
python manage.py listbackups

# Restore latest
python manage.py dbrestore

# Restore specific backup
python manage.py dbrestore -i 20260622-020000.dump
```

---

## Logging & Monitoring

### Log Aplikasi

| Log | Location |
|-----|----------|
| Gunicorn access | `/var/log/diamond/gunicorn-access.log` |
| Gunicorn error | `/var/log/diamond/gunicorn-error.log` |
| Celery worker | `sudo journalctl -u diamond_web_celery` |
| Oracle sync logs | `sync_logs/` (in project directory) |

### Buat Direktori Log

```bash
sudo mkdir -p /var/log/diamond
sudo chown pajak:pajak /var/log/diamond
```

### Endpoint Health Check

The application provides a keep-alive endpoint at `/keep-alive/` that returns HTTP 200. Configure your load balancer or monitoring tool to hit this endpoint every 30 seconds to verify the application is running.

### Monitoring Resource

```bash
# Monitor Gunicorn workers
sudo systemctl status diamond_web_gunicorn

# Check memory usage
htop

# Disk usage
df -h

# Redis status
redis-cli INFO stats
```

---

## Health Check & Keep-Alive

The app has a built-in keep-alive mechanism:

- **Endpoint:** `GET /keep-alive/` — returns a lightweight JSON response to verify the app is running
- **Session timeout:** 30 minutes (`SESSION_COOKIE_AGE = 1800`)
- **Session expiry page:** `/session-expired/`

Configure your reverse proxy or load balancer to periodically ping `/keep-alive/` to prevent idle session timeouts.

---

### Setelah Git Pull di VM

Setelah melakukan `git pull` di server VM, layanan berikut WAJIB di-restart agar perubahan kode diterapkan:

```bash
# Restart Redis (jika ada perubahan konfigurasi)
sudo systemctl restart redis

# Restart Celery Worker
sudo systemctl restart diamond_web_celery

# Restart Gunicorn
sudo systemctl restart diamond_web_gunicorn
```

> **Penting:** Jika tidak merestart Redis, Celery, dan Gunicorn setelah git pull, perubahan kode tidak akan terlihat karena proses worker masih menggunakan kode lama yang sudah di-cache di memori.

---

## Pemecahan Masalah

### "502 Bad Gateway" from Nginx
- Check if Gunicorn is running: `sudo systemctl status diamond_web_gunicorn`
- Check Gunicorn error logs: `sudo tail -f /var/log/diamond/gunicorn-error.log`
- Verify Gunicorn is binding to `127.0.0.1:8000`

### "Database connection refused"
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check credentials in `.env`
- Test connection: `psql -U diamond_user -d diamond_web_prod -h localhost`

### "Celery task not executing"
- Verify Redis is running: `redis-cli ping`
- Check Celery worker status: `sudo systemctl status diamond_web_celery`
- View Celery logs: `sudo journalctl -u diamond_web_celery -f`

### "Static files 404"
- Run `python manage.py collectstatic --noinput`
- Verify Nginx `location /static/` block points to correct directory
- Check file permissions

### "Oracle sync fails with DPY-3010"
- Follow the [Oracle Setup Guide](ORACLE_SETUP.md) to enable thick mode
- Ensure Oracle Instant Client is installed
- Verify `LD_LIBRARY_PATH` is set correctly

### "Permission denied" for media uploads
```bash
sudo chown -R pajak:pajak /home/pajak/diamond-web/media
sudo chmod -R 755 /home/pajak/diamond-web/media
```
