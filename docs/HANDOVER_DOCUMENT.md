# Project Handover Document

> **Project:** Diamond — Sistem P3DE/PIDE/PMDE  
> **Handover Date:** June 23, 2026  
> **Prepared for:** Incoming development team / maintenance team

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Project Overview](#2-project-overview)
- [3. System Architecture](#3-system-architecture)
- [4. Tech Stack & Dependencies](#4-tech-stack--dependencies)
- [5. Codebase Navigation](#5-codebase-navigation)
- [6. Key Modules & Features](#6-key-modules--features)
- [7. Database Overview](#7-database-overview)
- [8. External Integrations](#8-external-integrations)
- [9. Development Workflow](#9-development-workflow)
- [10. Deployment & Infrastructure](#10-deployment--infrastructure)
- [11. Common Tasks & Operations](#11-common-tasks--operations)
- [12. Known Issues & Limitations](#12-known-issues--limitations)
- [13. Future Roadmap](#13-future-roadmap)
- [14. Contacts & Stakeholders](#14-contacts--stakeholders)
- [15. Appendices](#15-appendices)

---

## 1. Executive Summary

**Diamond** is a web-based data collection workflow system built with Django 5.2, serving the Direktorat Jenderal Pajak (DJP) environment. The application manages the complete lifecycle of **Tiket Data** (data tickets) — from receipt, research, submission, identification, quality control, to completion.

### Core Business Purpose

The system handles the workflow of external data managed by three units:
- **P3DE** (Penghimpunan Data Eksternal) — Data Collection
- **PIDE** (Pengolahan Informasi Data Eksternal) — External Data Processing
- **PMDE** (Pengendalian Mutu Data Eksternal) — External Data Quality Control

### Key Capabilities
- Ticketing & workflow management with 8 status stages
- Oracle database synchronization (data reference & tickets)
- Automated DOCX document generation from templates
- 10+ types of reports with Excel export
- Power BI integrated dashboard
- Role-based access control (3 user groups + admin)

---

## 2. Project Overview

### Business Context

The application was developed to digitize and streamline the data collection workflow that was previously done manually or with spreadsheets. It replaces a legacy Oracle-based system for data tracking and introduces:

- **Transparency** — Every action is logged with timestamps and user info
- **Accountability** — Clear ownership (PIC) at each workflow stage
- **Efficiency** — Automated document generation reduces manual work
- **Monitoring** — SLA tracking and comprehensive reporting

### User Roles

| Role | Responsibility | Daily Tasks |
|------|---------------|-------------|
| **user_p3de** | Records incoming data, researches, sends to PIDE | Create tiket, record research, upload ND, generate reports |
| **user_pide** | Identifies data, performs QC, transfers to PMDE | Identify tiket, record results, transfer to PMDE |
| **user_pmde** | Final quality control, completes tiket | QC review, complete tiket, generate reports |
| **admin** | System administration | Oracle sync, user management, template management |

---

## 3. System Architecture

### High-Level Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Browser   │────▶│   Nginx      │────▶│  Gunicorn   │
│ (Bootstrap  │     │ (Reverse     │     │ (WSGI       │
│  5 + JS)    │     │  Proxy)      │     │  Server)    │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌───────────────────────────┼───────────────────────┐
                    │                           │                       │
                    ▼                           ▼                       ▼
            ┌──────────────┐           ┌──────────────┐        ┌──────────────┐
            │  PostgreSQL  │           │    Redis     │        │   Celery     │
            │  (Primary    │           │  (Cache &    │        │  (Task Queue │
            │   Database)  │           │   Broker)    │        │   Worker)    │
            └──────────────┘           └──────────────┘        └──────┬───────┘
                                                                      │
                                                                      ▼
                                                              ┌──────────────┐
                                                              │   Oracle DB  │
                                                              │  (External)  │
                                                              └──────────────┘
```

### Request Flow

```
1. User → Browser → HTTP Request
2. Nginx terminates SSL, proxies to Gunicorn
3. Gunicorn → Django (WSGI) processes request
4. Django ORM queries PostgreSQL
5. Response → Gunicorn → Nginx → Browser

Async (Oracle Sync):
1. User clicks "Sync" in browser
2. View kicks off Celery task
3. Celery worker reads from Oracle DB
4. Writes/updates to PostgreSQL
5. Progress updates via Redis cache (AJAX polling)
```

### File Structure

```
diamond-web/
├── config/              # Django project configuration
│   ├── settings.py      # Unified settings (dev + prod)
│   ├── urls.py          # Root URL routing
│   ├── wsgi.py          # WSGI entry point
│   ├── asgi.py          # ASGI (for async)
│   └── celery.py        # Celery task queue config
├── diamond_web/         # Main application
│   ├── models/          # Database models (30 files)
│   ├── views/           # Views (50+ files)
│   ├── forms/           # Django forms (35+ files)
│   ├── templates/       # HTML templates (30+ folders)
│   ├── utils/           # Utility modules
│   │   ├── oracle_sync.py   # Oracle sync engine (3373 lines)
│   │   └── docx_template.py # DOCX generation engine
│   ├── constants/       # Status constants
│   ├── templatetags/    # Custom template tags
│   ├── management/      # Django management commands
│   ├── static/          # Static assets (CSS, JS, images)
│   ├── tests/           # Test suite (40+ test files)
│   └── fixtures/        # Default data fixtures
├── docs/                # Documentation
├── requirements/        # Python dependencies
├── Duralux-admin/       # Frontend HTML mockup (reference)
├── backups/             # Database backups
├── media/               # User-uploaded files
├── sync_logs/           # Oracle sync logs
└── staticfiles/         # Collected static files (production)
```

---

## 4. Tech Stack & Dependencies

### Core Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime |
| Django | 5.2.14 | Web framework |
| Celery | 5.3+ | Async task queue |
| PostgreSQL | 14+ | Production database |
| Redis | 6+ | Cache & message broker |
| Nginx | 1.24+ | Reverse proxy |
| Gunicorn | (latest) | WSGI server (Linux) |

### Key Python Libraries

| Library | Purpose |
|---------|---------|
| `oracledb` | Oracle database connectivity |
| `python-docx` | DOCX document generation |
| `django-crispy-forms` | Bootstrap 5 form rendering |
| `django-import-export` | Data import/export (admin) |
| `django-dbbackup` | Database backup/restore |
| `django-debug-toolbar` | Development debugging |
| `django-schema-graph` | ERD visualization |
| `django-redis` | Redis cache backend |
| `openpyxl` | Excel file generation |
| `django-filter` | Advanced filtering |
| `django-tables2` | Table rendering |
| `pytest` | Testing framework |

### Frontend Libraries (CDN-delivered)

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.3 | UI framework |
| DataTables | 2.3.6 | Interactive tables |
| jQuery | 3.7.1 | DOM manipulation |
| Remix Icon | 4.6.0 | Icon set |

---

## 5. Codebase Navigation

### Entry Points

| File | Purpose |
|------|---------|
| `manage.py` | Django CLI entry point |
| `config/wsgi.py` | WSGI server entry point |
| `config/asgi.py` | ASGI server entry point |
| `config/celery.py` | Celery worker entry point |
| `config/settings.py` | All Django settings |
| `config/urls.py` | Root URL configuration |

### Key Directories

| Directory | Contents | Complexity |
|-----------|----------|------------|
| `diamond_web/views/` | All view logic (50+ files) | ⭐⭐⭐ |
| `diamond_web/models/` | Database models (30 files) | ⭐⭐⭐ |
| `diamond_web/forms/` | Django Forms (35+ files) | ⭐⭐ |
| `diamond_web/templates/` | HTML templates | ⭐⭐ |
| `diamond_web/utils/oracle_sync.py` | Oracle sync engine | ⭐⭐⭐⭐⭐ (3373 lines) |
| `diamond_web/tests/` | Test suite | ⭐⭐ |

---

## 6. Key Modules & Features

### 6.1 Tiket Workflow (Core Feature)

**Location:** `diamond_web/views/tiket/` (8 files) + `diamond_web/models/tiket.py`

The tiket workflow is the heart of the application. Key files:

| File | Purpose |
|------|---------|
| `views/tiket/list.py` | Tiket list with DataTables |
| `views/tiket/detail.py` | Tiket detail page |
| `views/tiket/rekam_tiket.py` | Create new tiket |
| `views/tiket/kirim_tiket.py` | Send tiket to PIDE |
| `models/tiket.py` | Tiket model (most complex model, ~200 fields) |
| `models/tiket_action.py` | Action log model |
| `models/tiket_pic.py` | PIC assignment model |

**Status Flow:** See `docs/status_tiket_flow.md` for detailed diagram.

### 6.2 Oracle Data Sync

**Location:** `diamond_web/utils/oracle_sync.py` (3373 lines)

This is the largest and most complex module. It handles:

- Connection to external Oracle database
- Data comparison (check mode — dry run)
- Full data synchronization (sync mode — inserts/updates)
- Two types: **Referensi sync** and **Tiket sync**
- Progress reporting via Redis cache
- Stop/resume capability
- Error logging

**Views:** `views/sync_data_referensi.py`, `views/sync_tiket.py`  
**Celery tasks:** `tasks.py`

### 6.3 Document Generator (DOCX)

**Location:** `diamond_web/utils/docx_template.py`

Generates Word documents from templates with placeholder variables.

**Template types:** Tanda Terima, ND Pengantar, Surat Klarifikasi, Surat PKDI, Register Penerimaan

**Templates location:** `diamond_web/fixtures/default_templates/` (11 template files)

### 6.4 Reporting System

**Location:** `diamond_web/views/laporan_*.py` (12 report files)

Each report has:
- HTML page with filter form
- DataTables server-side data endpoint
- Excel export endpoint

Reports: Register Penerimaan, Transfer, SLA Perekaman, SLA Identifikasi, Metrik Data Eksternal, Pengendalian Mutu, Hasil Pengolahan Data Prioritas, Kelengkapan Data, Rekap Himpun Olah Data, Detail Himpun Olah Data.

### 6.5 Master Data CRUD

All master data modules follow the same pattern (ListView, DataTables, CreateView, UpdateView, DeleteView). Each module has files in:
- `diamond_web/views/<module>.py` — View logic
- `diamond_web/models/<module>.py` — Model definition
- `diamond_web/forms/<module>.py` — Form definition
- `diamond_web/templates/<module>/` — HTML templates

---

## 7. Database Overview

### Current Database: SQLite (Development) → PostgreSQL (Production)

See `docs/models_erd.md` for complete ERD diagram.

### Key Tables

| Table | Records (approx.) | Description |
|-------|------------------|-------------|
| `Tiket` | Varies | Core data tickets (most complex table) |
| `ILAP` | ~500 | ILAP institutions |
| `JenisDataILAP` | ~5,000 | Data types with sub-types |
| `KPP` | ~300 | Tax service offices |
| `Kanwil` | ~30 | Regional offices |
| `TiketAction` | 1.5× Tiket | Action audit log |
| `Notification` | Varies | User notifications |
| `DocxTemplate` | 11 | Default document templates |

### Important Notes

- Database uses **WAL mode** (SQLite dev) to prevent read locks during writes
- Some fields are Oracle legacy (e.g., `old_db` flag on Tiket)
- Audit trail is handled via `TiketAction` model (not Django's built-in audit)
- No `on_delete=models.CASCADE` concerns — all relationships are protected

---

## 8. External Integrations

### 8.1 Oracle Database

| Detail | Value |
|--------|-------|
| Purpose | Data source for sync (referensi + tiket) |
| Connection | `oracledb` (thick mode) |
| Frequency | On-demand (manual trigger via UI) |
| Tables synced | ~20 reference tables + tiket tables |

### 8.2 Power BI Dashboard

| Detail | Value |
|--------|-------|
| URL | `/dashboard/` |
| Integration | Embedded iframe |
| Authentication | Separate from Diamond |

---

## 9. Development Workflow

### Version Control

- **Repository:** GitHub (private)
- **Branch strategy:** Feature branches → PR → `main`
- **Tag format:** `v1.0.0`, `v1.1.0`, etc.

### Local Development

```bash
# Standard workflow
git checkout -b feature-name
# ... make changes ...
pytest           # Run tests
python manage.py runserver  # Test manually
git add .
git commit -m "feat(scope): description"
git push origin feature-name
# Create PR on GitHub
```

### Testing

- Framework: `pytest` + `pytest-django`
- Coverage target: 80%+
- Test files: 40+ files in `diamond_web/tests/`
- Run: `pytest -v`

---

## 10. Deployment & Infrastructure

### Production Environment

| Component | Configuration |
|-----------|---------------|
| OS | Ubuntu 22.04 LTS |
| App Server | Gunicorn (3 workers) |
| Reverse Proxy | Nginx |
| Database | PostgreSQL 14+ |
| Cache/Broker | Redis 6+ |
| Python | 3.10+ |
| Process Manager | Systemd |

### Deployment Steps

See `docs/PRODUCTION_SETUP.md` for detailed instructions.

**Quick deploy:**
```bash
git pull origin main
pip install -r requirements/prod.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart diamond_web_gunicorn diamond_web_celery
```

### Services

| Service | Systemd Unit | Port |
|---------|-------------|------|
| Web App | `diamond_web_gunicorn` | 8000 (internal) |
| Celery | `diamond_web_celery` | — |
| Nginx | `nginx` | 80/443 |
| PostgreSQL | `postgresql` | 5432 |
| Redis | `redis` | 6379 |

---

## 11. Common Tasks & Operations

### Daily Operations

```bash
# Check service health
sudo systemctl status diamond_web_gunicorn

# Check logs
sudo journalctl -u diamond_web_gunicorn -n 100 -f

# Run Oracle sync (via management command)
python manage.py sync_oracle_data
python manage.py sync_oracle_data --check-only
```

### Database Backup

```bash
# Manual backup
python manage.py dbbackup

# List backups
python manage.py listbackups

# Restore
python manage.py dbrestore -i <filename>
```

### Adding New Master Data

1. Create model in `diamond_web/models/<module>.py`
2. Create form in `diamond_web/forms/<module>.py`
3. Create views in `diamond_web/views/<module>.py`
4. Create templates in `diamond_web/templates/<module>/`
5. Add URLs to `diamond_web/urls.py`
6. Run `python manage.py makemigrations && python manage.py migrate`
7. Add tests in `diamond_web/tests/`

### Adding New Report

1. Create view in `diamond_web/views/laporan_<nama>.py`
2. Create template in `diamond_web/templates/laporan_<nama>/`
3. Add DataTables endpoint + export endpoint
4. Add URLs to `diamond_web/urls.py`
5. Register in `diamond_web/views/__init__.py`

---

## 12. Known Issues & Limitations

### Technical Issues

| Issue | Description | Workaround |
|-------|-------------|------------|
| SQLite concurrency | SQLite can handle limited concurrent writes | Use PostgreSQL in production; WAL mode helps |
| Oracle sync speed | Large datasets may take 30+ minutes | Runs async via Celery; progress bar in UI |
| Celery on Windows | `prefork` pool not supported (no POSIX semaphores) | Use `--pool=solo` on Windows |
| No automated sync | Oracle sync requires manual trigger | Could be automated with Celery Beat |
| Template placeholders | Must match exactly with variable names in code | See `fixtures/default_templates/README.md` |

### Functional Limitations

| Limitation | Impact | Future Improvement |
|------------|--------|--------------------|
| No REST API | No mobile app or third-party integration | Add Django REST Framework |
| No email notifications | Users must check app manually | Configure email + Celery Beat |
| No data archival | Old records stay in active tables | Implement archival strategy |
| No audit for master data | Only tiket actions are logged | Add model-level audit trail |
| No file preview | Attachments shown as download links only | Add inline preview |
| No pagination in all places | Some dropdowns may be slow with large datasets | Add select2 or server-side search |

---

## 13. Future Roadmap

### Short-term (Q3 2026)

- [ ] Implement automated Oracle sync via Celery Beat (scheduled)
- [ ] Add email notifications for ticket status changes
- [ ] Improve report performance with database indexes
- [ ] Data archival strategy for old tiket records

### Medium-term (Q4 2026)

- [ ] Add Django REST Framework for API development
- [ ] Develop mobile-friendly views
- [ ] Implement file preview (PDF/Image) in browser
- [ ] Add advanced search with Elasticsearch (if needed)

### Long-term

- [ ] Microservices migration (separate sync service, report service)
- [ ] Replace Oracle sync with API-based integration
- [ ] Single Sign-On (SSO) integration with corporate ID
- [ ] Real-time dashboard with WebSockets

---

## 14. Contacts & Stakeholders

### Development Team

| Role | Name | Contact |
|------|------|---------|
| Project Lead | *(to be filled)* | *(to be filled)* |
| Lead Developer | *(to be filled)* | *(to be filled)* |
| Frontend Developer | *(to be filled)* | *(to be filled)* |
| QA / Tester | *(to be filled)* | *(to be filled)* |

### Business Stakeholders

| Role | Unit |
|------|------|
| Product Owner | P3DE — Direktorat Jenderal Pajak |
| Key User | P3DE, PIDE, PMDE teams |

*Note: Update contact information before handover.*

---

## 15. Appendices

### A. Documentation Index

| Document | Location | Description |
|----------|----------|-------------|
| Main README | `readme.md` | Project overview & setup |
| API Documentation | `docs/API_DOCUMENTATION.md` | All endpoints documented |
| Production Setup | `docs/PRODUCTION_SETUP.md` | Deployment guide |
| Security | `docs/SECURITY.md` | Security measures |
| Deployment Checklist | `docs/DEPLOYMENT_CHECKLIST.md` | Pre-release checklist |
| Contributing | `docs/CONTRIBUTING.md` | Developer guidelines |
| ERD / Models | `docs/models_erd.md` | Database ERD |
| Status Flow | `docs/status_tiket_flow.md` | Workflow diagram |
| Oracle Setup | `docs/ORACLE_SETUP.md` | Oracle connectivity |
| Template Setup | `docs/TEMPLATES_SETUP.md` | DOCX template system |
| Changelog | `docs/CHANGELOG.md` | Release history |

### B. Quick Reference Commands

```bash
# Development
python manage.py runserver
python manage.py shell_plus
python manage.py show_urls | grep tiket
pytest -v -k "test_tiket"

# Testing with coverage
pytest --cov-report=html --cov-report=term

# Database
python manage.py makemigrations
python manage.py migrate
python manage.py dbbackup
python manage.py dbrestore

# Production
python manage.py collectstatic --noinput
sudo systemctl restart diamond_web_gunicorn
sudo journalctl -u diamond_web_gunicorn -f

# Oracle
python manage.py sync_oracle_data --check-only
python manage.py sync_oracle_data

# Templates
python manage.py load_default_templates
python manage.py load_default_templates --reset

# Celery
celery -A config worker -l info --pool=solo
```

### C. Environment Files

| File | Purpose |
|------|---------|
| `.env.example.dev` | Development environment template |
| `.env.example.prod` | Production environment template |
| `.env` | Active environment configuration (not in git) |

---

> **Prepared by:** Development Team  
> **Date:** June 23, 2026  
> **Questions?** Refer to `docs/CONTRIBUTING.md` or open an issue in the repository.
