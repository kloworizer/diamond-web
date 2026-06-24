# Dokumen Serah Terima Proyek

> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE  
> **Tanggal Serah Terima:** June 23, 2026  
> **Disiapkan untuk:** Tim pengembangan / tim pemeliharaan

---

## Daftar Isi

- [1. Ringkasan Eksekutif](#1-ringkasan-eksekutif)
- [2. Gambaran Proyek](#2-gambaran-proyek)
- [3. Arsitektur Sistem](#3-arsitektur-sistem)
- [4. Tech Stack & Dependensi](#4-tech-stack--dependensi)
- [5. Navigasi Codebase](#5-navigasi-codebase)
- [6. Modul & Fitur Utama](#6-modul--fitur-utama)
- [7. Gambaran Database](#7-gambaran-database)
- [8. Integrasi Eksternal](#8-integrasi-eksternal)
- [9. Workflow Pengembangan](#9-workflow-pengembangan)
- [10. Deployment & Infrastruktur](#10-deployment--infrastruktur)
- [11. Tugas & Operasi Umum](#11-tugas--operasi-umum)
- [12. Masalah & Keterbatasan yang Diketahui](#12-masalah--keterbatasan-yang-diketahui)
- [14. Kontak & Pemangku Kepentingan](#14-kontak--pemangku-kepentingan)
- [15. Lampiran](#15-lampiran)

---

## 1. Ringkasan Eksekutif

**Diamond** adalah sistem alur kerja pengumpulan data berbasis web yang dibangun dengan Django 5.2, melayani lingkungan Direktorat Jenderal Pajak (DJP). Aplikasi ini mengelola siklus hidup lengkap **Tiket Data** — mulai dari penerimaan, penelitian, pengiriman, identifikasi, pengendalian mutu, hingga penyelesaian.

### Tujuan Bisnis Inti

Sistem ini menangani alur kerja data eksternal yang dikelola oleh tiga unit:
- **P3DE** (Penghimpunan Data Eksternal) — Penghimpunan Data
- **PIDE** (Pengolahan Informasi Data Eksternal) — Pengolahan Data Eksternal
- **PMDE** (Pengendalian Mutu Data Eksternal) — Pengendalian Mutu Data Eksternal

### Kemampuan Utama
- Manajemen tiket & alur kerja dengan 8 tahap status
- Sinkronisasi database Oracle (data referensi & tiket)
- Pembuatan dokumen DOCX otomatis dari template
- 10+ jenis laporan dengan ekspor Excel
- Dashboard terintegrasi Power BI
- Kontrol akses berbasis peran (3 grup pengguna + admin)

---

## 2. Gambaran Proyek

### Konteks Bisnis

Aplikasi ini dikembangkan untuk mendigitalkan dan menyederhanakan alur kerja pengumpulan data yang sebelumnya dilakukan secara manual atau dengan spreadsheet. Sistem ini menggantikan sistem berbasis Oracle lama untuk pelacakan data dan memperkenalkan:

- **Transparansi** — Setiap tindakan dicatat dengan cap waktu dan info pengguna
- **Akuntabilitas** — Kepemilikan yang jelas (PIC) di setiap tahap alur kerja
- **Efisiensi** — Pembuatan dokumen otomatis mengurangi pekerjaan manual
- **Pemantauan** — Pelacakan SLA dan pelaporan yang komprehensif

### Peran Pengguna

| Peran | Tanggung Jawab | Tugas Harian |
|------|---------------|-------------|
| **user_p3de** | Mencatat data masuk, meneliti, mengirim ke PIDE | Membuat tiket, mencatat penelitian, mengunggah ND, menghasilkan laporan |
| **user_pide** | Mengidentifikasi data, melakukan QC, mentransfer ke PMDE | Mengidentifikasi tiket, mencatat hasil, mentransfer ke PMDE |
| **user_pmde** | Pengendalian mutu akhir, menyelesaikan tiket | Tinjauan QC, menyelesaikan tiket, menghasilkan laporan |
| **admin** | Administrasi sistem | Sinkronisasi Oracle, manajemen pengguna, manajemen template |

---

## 3. Arsitektur Sistem

### Arsitektur Tingkat Tinggi

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

### Alur Permintaan

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

### Struktur File

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

## 4. Tech Stack & Dependensi

### Teknologi Inti

| Teknologi | Versi | Tujuan |
|------------|---------|---------|
| Python | 3.10+ | Runtime |
| Django | 5.2.14 | Kerangka Web |
| Celery | 5.3+ | Antrian tugas async |
| PostgreSQL | 14+ | Database produksi |
| Redis | 6+ | Cache & broker pesan |
| Nginx | 1.24+ | Reverse proxy |
| Gunicorn | (latest) | Server WSGI (Linux) |

### Pustaka Python Utama

| Pustaka | Tujuan |
|---------|---------|
| `oracledb` | Konektivitas database Oracle |
| `python-docx` | Pembuatan dokumen DOCX |
| `django-crispy-forms` | Render formulir Bootstrap 5 |
| `django-import-export` | Impor/ekspor data (admin) |
| `django-dbbackup` | Cadangan/pemulihan database |
| `django-debug-toolbar` | Debugging pengembangan |
| `django-schema-graph` | Visualisasi ERD |
| `django-redis` | Backend cache Redis |
| `openpyxl` | Pembuatan file Excel |
| `django-filter` | Filtering lanjutan |
| `django-tables2` | Render tabel |
| `pytest` | Kerangka pengujian |

### Pustaka Frontend (CDN)

| Pustaka | Versi | Tujuan |
|---------|---------|---------|
| Bootstrap | 5.3.3 | Kerangka UI |
| DataTables | 2.3.6 | Tabel interaktif |
| jQuery | 3.7.1 | Manipulasi DOM |
| Remix Icon | 4.6.0 | Set ikon |

---

## 5. Navigasi Codebase

### Titik Masuk

| Berkas | Tujuan |
|------|---------|
| `manage.py` | Titik masuk CLI Django |
| `config/wsgi.py` | Titik masuk server WSGI |
| `config/asgi.py` | Titik masuk server ASGI |
| `config/celery.py` | Titik masuk worker Celery |
| `config/settings.py` | Semua pengaturan Django |
| `config/urls.py` | Konfigurasi URL root |

### Direktori Utama

| Direktori | Konten | Kompleksitas |
|-----------|----------|------------|
| `diamond_web/views/` | Semua logika view (50+ berkas) | ⭐⭐⭐ |
| `diamond_web/models/` | Model database (30 berkas) | ⭐⭐⭐ |
| `diamond_web/forms/` | Formulir Django (35+ berkas) | ⭐⭐ |
| `diamond_web/templates/` | Template HTML | ⭐⭐ |
| `diamond_web/utils/oracle_sync.py` | Mesin sinkronisasi Oracle | ⭐⭐⭐⭐⭐ (3373 baris) |
| `diamond_web/tests/` | Rangkaian pengujian | ⭐⭐ |

---

## 6. Modul & Fitur Utama

### 6.1 Alur Kerja Tiket (Fitur Inti)

**Lokasi:** `diamond_web/views/tiket/` (8 berkas) + `diamond_web/models/tiket.py`

Alur kerja tiket adalah inti dari aplikasi. Berkas-berkas utama:

| Berkas | Tujuan |
|------|---------|
| `views/tiket/list.py` | Daftar tiket dengan DataTables |
| `views/tiket/detail.py` | Halaman detail tiket |
| `views/tiket/rekam_tiket.py` | Membuat tiket baru |
| `views/tiket/kirim_tiket.py` | Mengirim tiket ke PIDE |
| `models/tiket.py` | Model tiket (model paling kompleks, ~200 field) |
| `models/tiket_action.py` | Model log aksi |
| `models/tiket_pic.py` | Model penugasan PIC |

**Alur Status:** Lihat `docs/status_tiket_flow.md` untuk diagram detail.

### 6.2 Sinkronisasi Data Oracle

**Lokasi:** `diamond_web/utils/oracle_sync.py` (3373 baris)

Ini adalah modul terbesar dan paling kompleks. Modul ini menangani:

- Koneksi ke database Oracle eksternal
- Perbandingan data (mode periksa — dry run)
- Sinkronisasi data penuh (mode sync — insert/update)
- Dua jenis: **Sinkronisasi Referensi** dan **Sinkronisasi Tiket**
- Pelaporan progres melalui cache Redis
- Kemampuan berhenti/melanjutkan
- Pencatatan error

**Tampilan:** `views/sync_data_referensi.py`, `views/sync_tiket.py`  
**Tugas Celery:** `tasks.py`

### 6.3 Generator Dokumen (DOCX)

**Lokasi:** `diamond_web/utils/docx_template.py`

Menghasilkan dokumen Word dari template dengan variabel placeholder.

**Jenis template:** Tanda Terima, ND Pengantar, Surat Klarifikasi, Surat PKDI, Register Penerimaan

**Lokasi template:** `diamond_web/fixtures/default_templates/` (11 berkas template)

### 6.4 Sistem Pelaporan

**Lokasi:** `diamond_web/views/laporan_*.py` (12 berkas laporan)

Setiap laporan memiliki:
- Halaman HTML dengan formulir filter
- Endpoint data sisi server DataTables
- Endpoint ekspor Excel

Laporan: Register Penerimaan, Transfer, SLA Perekaman, SLA Identifikasi, Metrik Data Eksternal, Pengendalian Mutu, Hasil Pengolahan Data Prioritas, Kelengkapan Data, Rekap Himpun Olah Data, Detail Himpun Olah Data.

### 6.5 CRUD Data Master

Semua modul data master mengikuti pola yang sama (ListView, DataTables, CreateView, UpdateView, DeleteView). Setiap modul memiliki berkas di:
- `diamond_web/views/<modul>.py` — Logika view
- `diamond_web/models/<modul>.py` — Definisi model
- `diamond_web/forms/<modul>.py` — Definisi formulir
- `diamond_web/templates/<modul>/` — Template HTML

---

## 7. Gambaran Database

### Database Saat Ini: SQLite (Pengembangan) → PostgreSQL (Produksi)

Lihat `docs/models_erd.md` untuk diagram ERD lengkap.

### Tabel Utama

| Tabel | Rekam (perkiraan) | Deskripsi |
|-------|------------------|-------------|
| `Tiket` | Bervariasi | Tiket data inti (tabel paling kompleks) |
| `ILAP` | ~500 | Institusi ILAP |
| `JenisDataILAP` | ~5,000 | Jenis data dengan sub-jenis |
| `KPP` | ~300 | Kantor Pelayanan Pajak |
| `Kanwil` | ~30 | Kantor Wilayah |
| `TiketAction` | 1.5× Tiket | Log audit aksi |
| `Notification` | Bervariasi | Notifikasi pengguna |
| `DocxTemplate` | 11 | Template dokumen default |

### Catatan Penting

- Database menggunakan **mode WAL** (pengembangan SQLite) untuk mencegah kunci baca selama penulisan
- Beberapa field adalah peninggalan Oracle (mis., flag `old_db` pada Tiket)
- Jejak audit ditangani melalui model `TiketAction` (bukan audit bawaan Django)
- Tidak ada masalah `on_delete=models.CASCADE` — semua relasi dilindungi

---

## 8. Integrasi Eksternal

### 8.1 Database Oracle

| Detail | Nilai |
|--------|-------|
| Tujuan | Sumber data untuk sinkronisasi (referensi + tiket) |
| Koneksi | `oracledb` (thick mode) |
| Frekuensi | Sesuai permintaan (pemicu manual melalui UI) |
| Tabel yang disinkronkan | ~20 tabel referensi + tabel tiket |

### 8.2 Dashboard Power BI

| Detail | Nilai |
|--------|-------|
| URL | `/dashboard/` |
| Integrasi | Iframe tersemat |
| Autentikasi | Terpisah dari Diamond |

---

## 9. Workflow Pengembangan

### Kontrol Versi

- **Repositori:** GitHub (privat)
- **Strategi branch:** Branch fitur → PR → `main`
- **Format tag:** `v1.0.0`, `v1.1.0`, dll.

### Pengembangan Lokal

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

### Pengujian

- Kerangka: `pytest` + `pytest-django`
- Target cakupan: 80%+
- Berkas pengujian: 40+ berkas di `diamond_web/tests/`
- Jalankan: `pytest -v`

---

## 10. Deployment & Infrastruktur

### Lingkungan Produksi

| Komponen | Konfigurasi |
|-----------|---------------|
| OS | Ubuntu 22.04 LTS |
| App Server | Gunicorn (3 workers) |
| Reverse Proxy | Nginx |
| Database | PostgreSQL 14+ |
| Cache/Broker | Redis 6+ |
| Python | 3.10+ |
| Process Manager | Systemd |

### Langkah Deployment

Lihat `docs/PRODUCTION_SETUP.md` untuk instruksi detail.

**Deploy cepat:**
```bash
git pull origin main
pip install -r requirements/prod.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart diamond_web_gunicorn diamond_web_celery
```

### Layanan

| Layanan | Unit Systemd | Port |
|---------|-------------|------|
| Web App | `diamond_web_gunicorn` | 8000 (internal) |
| Celery | `diamond_web_celery` | — |
| Nginx | `nginx` | 80/443 |
| PostgreSQL | `postgresql` | 5432 |
| Redis | `redis` | 6379 |

---

## 11. Tugas & Operasi Umum

### Operasi Harian

```bash
# Check service health
sudo systemctl status diamond_web_gunicorn

# Check logs
sudo journalctl -u diamond_web_gunicorn -n 100 -f

# Run Oracle sync (via management command)
python manage.py sync_oracle_data
python manage.py sync_oracle_data --check-only
```

### Cadangan Database

```bash
# Manual backup
python manage.py dbbackup

# List backups
python manage.py listbackups

# Restore
python manage.py dbrestore -i <filename>
```

### Menambahkan Data Master Baru

1. Buat model di `diamond_web/models/<modul>.py`
2. Buat formulir di `diamond_web/forms/<modul>.py`
3. Buat view di `diamond_web/views/<modul>.py`
4. Buat template di `diamond_web/templates/<modul>/`
5. Tambahkan URL ke `diamond_web/urls.py`
6. Jalankan `python manage.py makemigrations && python manage.py migrate`
7. Tambahkan pengujian di `diamond_web/tests/`

### Menambahkan Laporan Baru

1. Buat view di `diamond_web/views/laporan_<nama>.py`
2. Buat template di `diamond_web/templates/laporan_<nama>/`
3. Tambahkan endpoint DataTables + endpoint ekspor
4. Tambahkan URL ke `diamond_web/urls.py`
5. Daftarkan di `diamond_web/views/__init__.py`

---

## 12. Masalah & Keterbatasan yang Diketahui

### Masalah Teknis

| Masalah | Deskripsi | Solusi Sementara |
|-------|-------------|------------|
| SQLite concurrency | SQLite hanya dapat menangani penulisan konkuren yang terbatas | Gunakan PostgreSQL di produksi; mode WAL membantu |
| Oracle sync speed | Dataset besar mungkin memakan waktu 30+ menit | Berjalan async melalui Celery; bilah progres di UI |
| Celery on Windows | Pool `prefork` tidak didukung (tidak ada semaphore POSIX) | Gunakan `--pool=solo` di Windows |
| No automated sync | Sinkronisasi Oracle memerlukan pemicu manual | Dapat diotomatiskan dengan Celery Beat |
| Template placeholders | Harus cocok persis dengan nama variabel di kode | Lihat `fixtures/default_templates/README.md` |

### Keterbatasan Fungsional

| Keterbatasan | Dampak | Peningkatan Masa Depan |
|------------|--------|--------------------|
| Tidak ada REST API | Tidak ada aplikasi mobile atau integrasi pihak ketiga | Tambahkan Django REST Framework |
| Tidak ada notifikasi email | Pengguna harus memeriksa aplikasi secara manual | Konfigurasi email + Celery Beat |
| Tidak ada pengarsipan data | Rekaman lama tetap berada di tabel aktif | Implementasikan strategi pengarsipan |
| Tidak ada audit untuk data master | Hanya aksi tiket yang dicatat | Tambahkan jejak audit tingkat model |
| Tidak ada pratinjau file | Lampiran ditampilkan hanya sebagai tautan unduhan | Tambahkan pratinjau inline |
| Tidak ada paginasi di semua tempat | Beberapa dropdown mungkin lambat dengan dataset besar | Tambahkan select2 atau pencarian sisi server |

---

## 14. Kontak & Pemangku Kepentingan

### Tim Pengembangan

| Peran | Nama | Kontak |
|------|------|---------|
| Project Lead | *(to be filled)* | *(to be filled)* |
| Lead Developer | *(to be filled)* | *(to be filled)* |
| Frontend Developer | *(to be filled)* | *(to be filled)* |
| QA / Tester | *(to be filled)* | *(to be filled)* |

### Pemangku Kepentingan Bisnis

| Peran | Unit |
|------|------|
| Product Owner | P3DE — Direktorat Jenderal Pajak |
| Key User | P3DE, PIDE, PMDE teams |

*Catatan: Perbarui informasi kontak sebelum serah terima.*

---

## 15. Lampiran

### A. Indeks Dokumentasi

| Dokumen | Lokasi | Deskripsi |
|----------|----------|-------------|
| README Utama | `readme.md` | Gambaran proyek & pengaturan |
| Dokumentasi API | `docs/API_DOCUMENTATION.md` | Semua endpoint didokumentasikan |
| Pengaturan Produksi | `docs/PRODUCTION_SETUP.md` | Panduan deployment |
| Keamanan | `docs/SECURITY.md` | Tindakan keamanan |
| Daftar Periksa Deployment | `docs/DEPLOYMENT_CHECKLIST.md` | Daftar periksa pra-rilis |
| Kontribusi | `docs/CONTRIBUTING.md` | Panduan pengembang |
| ERD / Model | `docs/models_erd.md` | ERD Database |
| Alur Status | `docs/status_tiket_flow.md` | Diagram alur kerja |
| Pengaturan Oracle | `docs/ORACLE_SETUP.md` | Konektivitas Oracle |
| Pengaturan Template | `docs/TEMPLATES_SETUP.md` | Sistem template DOCX |
| Changelog | `docs/CHANGELOG.md` | Riwayat rilis |

### B. Perintah Referensi Cepat

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

### C. Berkas Lingkungan

| Berkas | Tujuan |
|------|---------|
| `.env.example.dev` | Template lingkungan pengembangan |
| `.env.example.prod` | Template lingkungan produksi |
| `.env` | Konfigurasi lingkungan aktif (tidak di git) |

---

> **Disiapkan oleh:** Tim Pengembangan  
> **Tanggal:** June 23, 2026  
> **Pertanyaan?** Lihat `docs/CONTRIBUTING.md` atau buka issue di repositori.
