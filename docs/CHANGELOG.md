# Changelog

> All notable changes to the Diamond project will be documented in this file.

---

## [1.0.0] — 2026-06-23 — Initial Production Release

### Added
- Full tiket workflow management (8 status stages)
- Role-based access control (P3DE, PIDE, PMDE, admin)
- Oracle data synchronization (referensi + tiket)
- DOCX document generation (Tanda Terima, ND Pengantar, Surat Klarifikasi, Surat PKDI)
- 10+ report types with Excel export
- Power BI dashboard integration
- CRUD management for all master data (ILAP, KPP, Kanwil, PIC, etc.)
- Bulk document generation (PKDI/Klarifikasi, ND Pengantar)
- Quality control workflow
- User notification system
- Session management with keep-alive mechanism
- Database backup/restore via django-dbbackup
- Comprehensive test suite (40+ test files)
- Production deployment documentation

### Technical Highlights
- Django 5.2 with unified settings (dev/prod via environment variables)
- PostgreSQL support for production, SQLite for development
- Celery async task queue for Oracle sync operations
- Redis cache for progress tracking and distributed state
- Server-side DataTables processing for all list views
- Bootstrap 5 responsive UI with Remix icons

### Dependencies
- Python 3.10+
- Django 5.2.14
- Celery 5.3+
- PostgreSQL 14+ / SQLite
- Redis 6+
- Oracle Instant Client 21+ (for sync feature)
