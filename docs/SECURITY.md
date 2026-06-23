# Security Documentation

> **Last Updated:** June 23, 2026  
> **Project:** Diamond — Sistem P3DE/PIDE/PMDE

---

## Table of Contents

- [Authentication & Authorization](#authentication--authorization)
- [Session Management](#session-management)
- [CSRF Protection](#csrf-protection)
- [HTTPS & SSL](#https--ssl)
- [Security Headers](#security-headers)
- [Database Security](#database-security)
- [File Upload Security](#file-upload-security)
- [Oracle Connection Security](#oracle-connection-security)
- [Environment Variables & Secrets](#environment-variables--secrets)
- [Input Validation](#input-validation)
- [Audit Trail](#audit-trail)
- [Production Security Checklist](#production-security-checklist)

---

## Authentication & Authorization

### User Groups & Roles

The application uses Django's built-in `Group` model for role-based access control.

| Group | Description | Access Rights |
|-------|-------------|---------------|
| `user_p3de` | Data collection team | Tiket rekam, kirim, backup, tanda terima, laporan P3DE |
| `user_pide` | Data processing team | Identifikasi, penelitian, transfer, QC |
| `user_pmde` | Quality control team | Laporan kelengkapan, rekap himpun olah data |
| `admin` | Administrators | Oracle sync, user management, full access |

### Implementation

- Group checking is done in views via `request.user.groups.filter(name='user_p3de').exists()`
- Templates use the `has_group` template tag (`diamond_web/templatetags/auth_extras.py`)
- Django Admin (`/admin/`) is restricted to **superusers only**

### Password Policies

Django's built-in password validators are enforced:

```python
AUTH_PASSWORD_VALIDATORS = [
    # UserAttributeSimilarityValidator — password too similar to user attributes
    # MinimumLengthValidator — minimum length (default: 8)
    # CommonPasswordValidator — password is not too common
    # NumericPasswordValidator — password is not entirely numeric
]
```

---

## Session Management

### Configuration (`config/settings.py`)

| Setting | Value | Description |
|---------|-------|-------------|
| `SESSION_COOKIE_AGE` | 1800 (30 min) | Session lifetime in seconds |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | `False` | Session persists after browser close |
| `SESSION_SAVE_EVERY_REQUEST` | `False` | Don't update session on every request (reduces DB writes) |
| `SESSION_COOKIE_SECURE` | `True` (prod) / `False` (dev) | Only send cookie over HTTPS |
| `SESSION_COOKIE_HTTPONLY` | `True` (Django default) | Cookie not accessible via JavaScript |

### Session Expiry Flow

1. User is inactive for 30 minutes → session expires
2. Next request redirects to `/session-expired/` page
3. User must log in again

### Keep-Alive Mechanism

- Endpoint: `GET /keep-alive/` — lightweight JSON response
- Used by frontend to prevent session timeout during active use
- Does NOT extend session if user is idle (only actual activity extends session)

---

## CSRF Protection

### Configuration

```python
CSRF_TRUSTED_ORIGINS = ["https://diamond.pajak.go.id"]
CSRF_COOKIE_SECURE = True  # in production
```

### Implementation

- All `POST` forms include `{% csrf_token %}`
- AJAX `POST` requests require `X-CSRFToken` header
- CSRF token is rotated on login
- CSRF cookie is set with `SameSite=Lax` (Django default)

---

## HTTPS & SSL

### Production Settings

```python
SECURE_SSL_REDIRECT = True    # Redirect HTTP → HTTPS
SESSION_COOKIE_SECURE = True  # Session cookies only over HTTPS
CSRF_COOKIE_SECURE = True     # CSRF cookies only over HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
```

### Nginx SSL Configuration

See [Production Setup Guide](PRODUCTION_SETUP.md#nginx-reverse-proxy) for full Nginx SSL configuration including:
- TLS certificate configuration
- HSTS headers
- Strong cipher suites (if configured)

---

## Security Headers

### Production (via Nginx or Django settings)

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | Enforce HTTPS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter (legacy browsers) |
| `Referrer-Policy` | `same-origin` (recommended) | Limit referrer information |

### Django Settings

```python
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"  # Prevents iframe embedding
```

---

## Database Security

### PostgreSQL (Production)

| Practice | Description |
|----------|-------------|
| Dedicated user | Application uses a non-privileged database user |
| Password auth | `md5` or `scram-sha-256` authentication |
| Network binding | PostgreSQL bound to `localhost` (not exposed) |
| Least privilege | Database user has only `INSERT`, `SELECT`, `UPDATE`, `DELETE` on application tables |
| Regular backups | Automated daily backups (see [Production Setup](PRODUCTION_SETUP.md#backup-configuration)) |

### SQLite (Development)

- SQLite mode: `WAL` (Write-Ahead Logging) prevents read locks
- Timeout: 30 seconds for write contention
- Used only for development (not production-safe for concurrent access)

---

## File Upload Security

### Media Files

- Uploaded files are stored in `media/` directory (gitignored)
- Django serves media files only in development (`DEBUG=True`)
- In production, Nginx serves media files directly
- File type is validated via Django forms

### DOCX Templates

- Uploaded templates are validated as `.docx` files
- Templates are stored with randomized filenames in `media/docx_templates/YYYYMMDD/` subdirectories
- Default templates are version-controlled in `fixtures/default_templates/`

### Backup Files

- Database backups are stored in `backups/` or configured `BACKUP_DIR`
- Backup files contain sensitive data — ensure directory permissions are restrictive
- For off-site backups, consider encryption

---

## Oracle Connection Security

- Oracle credentials stored in `.env` file (not in code)
- Connection uses `oracledb` with thick mode for production Oracle versions
- Connection can be tested via UI before running sync
- No Oracle credentials are logged or exposed in error messages

---

## Environment Variables & Secrets

### .env File Security

| Practice | Description |
|----------|-------------|
| Not committed | `.env` is in `.gitignore` |
| Template provided | `.env.example.dev` and `.env.example.prod` show required variables |
| File permissions | `.env` should be readable only by the application user (`chmod 600`) |
| Secret key | Generate unique secret key per deployment: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |

### Sensitive Variables

| Variable | Sensitivity | Notes |
|----------|-------------|-------|
| `SECRET_KEY` | Critical | Keep secret; rotating invalidates sessions |
| `DB_PASSWORD` | Critical | Database credentials |
| `ORACLE_PASSWORD` | Critical | Oracle credentials |
| `EMAIL_HOST_PASSWORD` | Medium | Email account password |
| `AWS_SECRET_ACCESS_KEY` | Critical | Cloud storage credentials |

---

## Input Validation

- All form inputs are validated via Django Forms
- Server-side DataTables parameters are sanitized
- SQL injection is prevented by Django ORM (parameterized queries)
- Cross-site scripting (XSS) is mitigated by Django template auto-escaping
- File uploads are validated by form field types

---

## Audit Trail

The application has an audit log model (`AuditTrailModel`) that records:

- Model changes (create/update/delete)
- Timestamp of changes
- User who made the change

Tiket actions are tracked via `TiketAction` model:
- Every status change is logged
- Each action records: user, timestamp, action type, and notes

---

## Production Security Checklist

- [ ] `DEBUG=False` — never run with debug mode in production
- [ ] `SECRET_KEY` is unique and not the default value
- [ ] HTTPS is enforced (`SECURE_SSL_REDIRECT=True`)
- [ ] `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True`
- [ ] `ALLOWED_HOSTS` only contains production domains/IPs
- [ ] `CSRF_TRUSTED_ORIGINS` is set correctly
- [ ] `X_FRAME_OPTIONS=DENY` (clickjacking protection)
- [ ] Database uses strong password (not default/dev password)
- [ ] Redis is bound to `127.0.0.1` only
- [ ] `.env` file permissions are `600` (owner read/write only)
- [ ] Static/media file serving is handled by Nginx, not Django
- [ ] Regular backup schedule is configured
- [ ] Server firewall restricts access to necessary ports only (80, 443, SSH)
- [ ] Failed login attempts are monitored (consider rate limiting)
- [ ] Application and system logs are monitored for suspicious activity
