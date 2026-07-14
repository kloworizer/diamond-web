# Diamond — Sistem P3DE/PIDE/PMDE

**Diamond** adalah aplikasi berbasis Django untuk **data collection workflow** pada lingkungan P3DE (Pengelolaan Data dan Evaluasi), PIDE (Pengolahan Informasi Data Eksternal), dan PMDE (Pengelolaan Metadata Data Eksternal) di lingkungan Direktorat Jenderal Pajak.

Aplikasi ini mengelola siklus hidup **Tiket Data** — dari penerimaan, penelitian, pengiriman, hingga penyelesaian — serta menyediakan:

- **Ticketing & Workflow** — Rekam, teliti, kirim, identifikasi, kendali mutu, selesaikan tiket data.
- **Oracle Data Sync** — Sinkronisasi data referensi dan tiket dari database Oracle eksternal ke database lokal.
- **Document Generator (DOCX)** — Generate dokumen otomatis (tanda terima, surat pengantar, surat klarifikasi, PKDI) dari template DOCX.
- **Laporan & Monitoring** — Dashboard Power BI terintegrasi, laporan SLA, register penerimaan, rekap himpun olah data, dll.
- **Manajemen Data Master** — CRUD untuk ILAP, KPP, Kanwil, Kategori Wilayah, Jenis Data, PIC, dll.

---

## 📚 Daftar Isi

- [Diamond — Sistem P3DE/PIDE/PMDE](#diamond--sistem-p3depidepmde)
- [📚 Daftar Isi](#-daftar-isi)
- [🎯 Arsitektur & Alur Kerja](#-arsitektur--alur-kerja)
  - [Siklus Hidup Tiket](#siklus-hidup-tiket)
  - [Tiga Peran (Role) Pengguna](#tiga-peran-role-pengguna)
- [📁 Struktur Proyek](#-struktur-proyek)
- [⚙️ Setup Development](#️-setup-development)
  - [Kebutuhan Software](#kebutuhan-software)
  - [Langkah Setup](#langkah-setup)
- [🚀 Menjalankan Server](#-menjalankan-server)
- [🔐 User Login \& Grup](#-user-login--grup)
- [📋 Fitur Aplikasi](#-fitur-aplikasi)
  - [1. Manajemen Data Master](#1-manajemen-data-master)
  - [2. Tiket Workflow](#2-tiket-workflow)
  - [3. Document Generator (DOCX)](#3-document-generator-docx)
  - [4. Oracle Data Sync](#4-oracle-data-sync)
  - [5. Laporan \& Monitoring](#5-laporan--monitoring)
- [📄 Template DOCX](#-template-docx)
- [🔄 Oracle Sync](#-oracle-sync)
  - [Sync Data Referensi](#sync-data-referensi)
  - [Sync Tiket](#sync-tiket)
- [🧪 Testing](#-testing)
- [🛠️ Development Tools](#️-development-tools)
- [📦 Library yang Digunakan](#-library-yang-digunakan)
- [🤝 Panduan Kolaborasi](#-panduan-kolaborasi)
- [💾 Database Backup & Restore](#-database-backup--restore)
- [📋 Misc Commands](#-misc-commands)

---

## 📖 Dokumentasi Lengkap

Seluruh dokumentasi proyek tersedia di folder [`docs/`](docs/):

| Dokumen | Deskripsi |
|---------|-----------|
| [📘 **PRODUCTION_SETUP.md**](docs/PRODUCTION_SETUP.md) | Panduan deployment produksi (server, Nginx, Gunicorn, Celery, Redis) |
| [🔐 **SECURITY.md**](docs/SECURITY.md) | Dokumentasi keamanan (autentikasi, session, CSRF) |
| [🌐 **API_DOCUMENTATION.md**](docs/API_DOCUMENTATION.md) | Dokumentasi semua endpoint API |
| [🗄️ **models_erd.md**](docs/models_erd.md) | Diagram ERD dan dokumentasi model database |
| [📋 **DEPLOYMENT_CHECKLIST.md**](docs/DEPLOYMENT_CHECKLIST.md) | Checklist pre-deployment untuk production release |
| [📤 **HANDOVER_DOCUMENT.md**](docs/HANDOVER_DOCUMENT.md) | Dokumen serah terima proyek untuk tim baru |
| [🤝 **CONTRIBUTING.md**](docs/CONTRIBUTING.md) | Panduan kontribusi untuk developer |
| [📝 **CHANGELOG.md**](docs/CHANGELOG.md) | Riwayat rilis dan perubahan |
| [🔄 **ORACLE_SETUP.md**](docs/ORACLE_SETUP.md) | Panduan setup koneksi Oracle (thick mode) |
| [📊 **status_tiket_flow.md**](docs/status_tiket_flow.md) | Diagram alur status tiket |
| [📄 **TEMPLATES_SETUP.md**](docs/TEMPLATES_SETUP.md) | Setup template DOCX |
| [🔑 **RBAC_MATRIX.md**](docs/RBAC_MATRIX.md) | Matriks RBAC & hak akses menu berdasarkan role |

---

## 🎯 Arsitektur & Alur Kerja

### Siklus Hidup Tiket

Setiap data yang masuk diproses melalui alur **Tiket** dengan status sebagai berikut:

```
Direkam (1) → Diteliti (2) → Dikirim ke PIDE (4) → Identifikasi (5)
                                                         ↓
                                              Pengendalian Mutu (6)
                                                         ↓
                                                   Selesai (8)

Dapat Dikembalikan (3) atau Dibatalkan (7) di setiap tahap.
```

Penjelasan status:

| Status | Arti |
|--------|------|
| **Direkam (1)** | Tiket baru direkam oleh user P3DE |
| **Diteliti (2)** | Data sedang diteliti kelengkapannya |
| **Dikembalikan (3)** | Data dikembalikan karena tidak lengkap |
| **Dikirim ke PIDE (4)** | Data dikirim ke unit PIDE |
| **Identifikasi (5)** | Proses identifikasi oleh PIDE |
| **Pengendalian Mutu (6)** | Quality control oleh PIDE |
| **Dibatalkan (7)** | Tiket dibatalkan |
| **Selesai (8)** | Tiket selesai diproses |

> Definisi status ada di `diamond_web/constants/tiket_status.py`.

### Tiga Peran (Role) Pengguna

Aplikasi ini memiliki **3 grup pengguna**, masing-masing dengan view dan akses berbeda:

| Grup | Tanggung Jawab | Contoh Menu |
|------|----------------|-------------|
| **user_p3de** | Merekam, meneliti, mengirim data | Tiket Rekam, Tiket Kirim, Backup Data, Tanda Terima, Laporan P3DE |
| **user_pide** | Identifikasi | Tiket Detail (Batalkan, Rekam Penelitian, Transfer PMDE, Selesaikan) |
| **user_pmde** | Pengendalian mutu | Laporan Kelengkapan Data, Rekap Himpun Olah Data |

> File terkait: `diamond_web/views/home.py` mengecek grup user dan menampilkan tampilan berbeda.
> Template tag `has_group` di `diamond_web/templatetags/auth_extras.py` dipakai di template untuk filter UI.

---

## 📁 Struktur Proyek

```
diamond-web/
│
├── manage.py                  # Entry point Django (CLI)
├── .env                       # Konfigurasi lokal (tidak di-git)
├── .env.example               # Template untuk .env
├── pytest.ini                 # Konfigurasi pytest
│
├── config/                    # Konfigurasi Django
│   ├── __init__.py
│   ├── settings.py            # Settings terpadu (DEV + PROD via .env)
│   ├── test_settings.py       # Setting khusus untuk testing
│   ├── urls.py                # URL root: /admin/, /schema/, /accounts/, dan include diamond_web
│   ├── wsgi.py                # WSGI untuk production deployment
│   ├── asgi.py                # ASGI (untuk async)
│   └── celery.py              # Konfigurasi Celery (task queue untuk background job)
│
├── diamond_web/               # 🎯 Main Django app
│   ├── apps.py                # Nama app: 'diamond_web'
│   ├── admin.py               # Registrasi model ke Django Admin
│   ├── urls.py                # ~300+ baris routing (semua endpoint aplikasi)
│   ├── signals.py             # Signal: sambutan login
│   ├── context_processors.py  # Context processor: notifikasi, git commit, tahun
│   ├── tasks.py               # Celery tasks: background sync Oracle
│   │
│   ├── models/                # 📦 Model-model database
│   │   ├── tiket.py           # Model utama: Tiket (paling kompleks)
│   │   ├── tiket_action.py    # Riwayat aksi pada tiket
│   │   ├── tiket_pic.py       # PIC yang ditugaskan ke tiket
│   │   ├── ilap.py            # ILAP
│   │   ├── kategori_ilap.py   # Kategori ILAP
│   │   ├── jenis_data_ilap.py # Jenis data dalam ILAP (dengan sub-jenis)
│   │   ├── periode_jenis_data.py, periode_pengiriman.py  # Periode data
│   │   ├── kanwil.py, kpp.py, kategori_wilayah.py        # Wilayah
│   │   ├── pic.py             # Person In Charge
│   │   ├── tanda_terima_data.py, detil_tanda_terima.py   # Tanda terima
│   │   ├── backup_data.py     # Data backup
│   │   ├── docx_template.py   # Template DOCX
│   │   ├── status_data.py, status_penelitian.py          # Status referensi
│   │   ├── dasar_hukum.py, bentuk_data.py, cara_penyampaian.py  # Data master
│   │   ├── klasifikasi_jenis_data.py, jenis_tabel.py     # Klasifikasi
│   │   ├── jenis_prioritas_data.py, durasi_jatuh_tempo.py # Prioritas & SLA
│   │   ├── notification.py    # Notifikasi pengguna
│   │   ├── kirim_pide_temp.py  # Temp data saat kirim ke PIDE
│   │   ├── media_backup.py    # Backup media penyimpanan
│   │   └── audit.py           # Log audit trail
│   │
│   ├── views/                 # 👁️ View (controller)
│   │   ├── __init__.py        # Re-export semua view dari sub-modul
│   │   ├── home.py            # Halaman utama (role-based dashboard)
│   │   ├── dashboard.py       # Dashboard monitoring (Power BI)
│   │   ├── tiket/             # ✨ Tiket workflow (complex)
│   │   │   ├── list.py        # List tiket + DataTables server-side
│   │   │   ├── detail.py      # Detail tiket
│   │   │   ├── rekam_tiket.py # Step 1: Rekam tiket baru
│   │   │   ├── kirim_tiket.py # Step 3: Kirim ke PIDE (dengan upload ND pengantar)
│   │   │   ├── rekam_hasil_penelitian.py   # Modal: Rekam hasil penelitian
│   │   │   ├── batalkan_tiket.py           # Modal: Batalkan tiket
│   │   │   ├── dikembalikan_tiket.py       # Modal: Kembalikan tiket
│   │   │   ├── identifikasi_tiket.py       # Modal: Identifikasi tiket
│   │   │   ├── transfer_ke_pmde.py         # Modal: Transfer ke PMDE
│   │   │   ├── selesaikan_tiket.py         # Modal: Selesaikan tiket
│   │   │   └── documents.py  # Download dokumen tiket
│   │   ├── backup_data.py, tanda_terima_data.py, monitoring_penyampaian_data.py
│   │   ├── ilap.py, jenis_data_ilap.py, profil_ilap.py, periode_jenis_data.py
│   │   ├── kanwil.py, kpp.py, kategori_wilayah.py, pic.py
│   │   ├── docx_template.py, bulk_document_generation.py
│   │   ├── sync_data_referensi.py  # Oracle sync via Web UI
│   │   ├── sync_tiket.py          # Sync tiket dari Oracle
│   │   ├── laporan_*.py       # Berbagai laporan (12 file laporan!)
│   │   └── ... (20+ file view lainnya)
│   │
│   ├── forms/                 # 📝 Django Forms
│   │   ├── base.py            # Base form (stylesheet, helper)
│   │   ├── tiket.py, identifikasi_tiket.py, kirim_tiket.py  # Form tiket
│   │   ├── batalkan_tiket.py, dikembalikan_tiket.py, selesaikan_tiket.py
│   │   ├── rekam_hasil_penelitian.py, transfer_ke_pmde.py
│   │   ├── backup_data.py, tanda_terima_data.py
│   │   └── ... (35+ file form)
│   │
│   ├── templates/             # 🎨 HTML Templates (Django Templates)
│   │   ├── base.html          # Base layout (navbar, sidebar, notifikasi)
│   │   ├── navbar.html        # Navigasi bar
│   │   ├── home.html          # Halaman utama
│   │   ├── login/             # Halaman login
│   │   ├── registration/      # Login, change password
│   │   ├── dashboard/         # Dashboard monitoring
│   │   ├── tiket/             # Template tiket workflow
│   │   ├── laporan_*/         # Template laporan (12 folder)
│   │   └── ... (30+ folder template)
│   │
│   ├── templatetags/
│   │   └── auth_extras.py    # Template tags: has_group, get_item, format_periode
│   │
│   ├── utils/
│   │   ├── oracle_sync.py    # 🔄 Oracle sync service (3368 baris!)
│   │   └── docx_template.py  # 📄 DOCX template processing
│   │
│   ├── constants/
│   │   ├── tiket_status.py        # Status tiket & badge classes
│   │   ├── tiket_action_types.py  # Tipe aksi tiket
│   │   ├── tiket_action_badges.py # Badge untuk action
│   │   └── jenis_tabel.py         # Tipe tabel
│   │
│   ├── management/commands/  # Custom Django management commands
│   │   ├── sync_oracle_data.py      # CLI: sync data dari Oracle
│   │   └── load_default_templates.py # CLI: load default DOCX templates
│   │
│   ├── fixtures/
│   │   └── default_templates/  # Template DOCX default (11 file)
│   │       └── README.md       # Dokumentasi template variables
│   │
│   ├── tests/                 # 🧪 Unit & integration tests
│   ├── static/                # Static files (CSS, JS, images)
│   └── media/                 # User-uploaded files (tidak di-git)
│
├── Duralux-admin/             # 🎨 Frontend HTML template (static mockup)
├── requirements/              # 📦 Python dependencies
│   ├── base.txt               # Base dependencies
│   ├── dev.txt                # Development dependencies
│   └── prod.txt               # Production dependencies
│
├── docs/
│   └── models_erd.md          # ERD documentation
│
├── htmlcov/                   # Coverage report (hasil pytest --cov)
├── sync_logs/                 # Log sinkronisasi Oracle
├── coverage.xml               # Coverage report XML
└── db.sqlite3                 # Database SQLite (development)
```

---

## ⚙️ Setup Development

### Kebutuhan Software

- **Python** versi 3.10 atau lebih baru: [Download Python](https://www.python.org/downloads/)
- **Git for Windows**: [Download Git](https://git-scm.com/download/win)
- **Database**: SQLite (default, sudah built-in Python)

> **Untuk developer baru**: Jika Anda hanya ingin menjalankan aplikasi di lokal tanpa fitur Oracle Sync, Anda cukup mengikuti langkah-langkah di bawah. Fitur Oracle Sync hanya diperlukan jika Anda ingin menguji sinkronisasi data dari database Oracle.

### Langkah Setup

#### 1. Clone repositori

```bash
git clone https://github.com/<username-anda>/diamond-web.git
cd diamond-web
```

#### 2. Buat virtual environment

```bash
python -m venv .venv
```

Aktifkan:

- **Windows (PowerShell)**:
  ```powershell
  Set-ExecutionPolicy Unrestricted -Scope Process; .\.venv\Scripts\Activate.ps1
  ```
- **Windows (CMD)**:
  ```cmd
  .venv\Scripts\activate
  ```
- **Linux/Mac**:
  ```bash
  source .venv/bin/activate
  ```

#### 3. Install dependencies

```bash
pip install -r requirements/dev.txt
```

#### 4. Buat file `.env`

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

Edit file `.env` minimal:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SETTINGS_MODULE=config.settings

# Oracle Sync (hanya jika ingin pakai fitur sync)
ORACLE_USER=your_oracle_user
ORACLE_PASSWORD=your_oracle_password
ORACLE_HOST=10.10.10.10
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=ORCLPDB1
```

> `DJANGO_SETTINGS_MODULE` sekarang langsung mengarah ke `config.settings` (tidak ada lagi folder `settings/` terpisah). Semua konfigurasi diatur via environment variable di `.env`.

#### 5. Jalankan migrasi database

```bash
python manage.py migrate
```

#### 6. (Opsional) Load default DOCX templates

```bash
python manage.py load_default_templates
```

---

## 🚀 Menjalankan Server

```bash
python manage.py runserver
```

Akses aplikasi di [http://localhost:8000](http://localhost:8000).

**Halaman utama** setelah login akan menampilkan dashboard yang berbeda tergantung role user:
- **P3DE**: Melihat daftar tiket yang perlu ditindaklanjuti (rekam backup, buat tanda terima, kirim ke PIDE, dll.)
- **PIDE/PMDE**: Melihat ringkasan tiket yang perlu diidentifikasi, di-quality control, dsb.

### Menjalankan Celery (untuk background sync Oracle)

Fitur sinkronisasi Oracle berjalan secara **async** menggunakan Celery. Untuk menjalankan worker:

```bash
# Terminal 1: Celery worker
celery -A config worker -l info

# Terminal 2: Celery beat (untuk periodic task, jika dikonfigurasi)
celery -A config beat -l info
```

> Jika tidak menjalankan Celery, fitur sync tetap bisa dijalankan via management command `sync_oracle_data` (synchronous di terminal).

---

## 🔐 User Login & Grup

Untuk login, buat **superuser** terlebih dahulu:

```bash
python manage.py createsuperuser
```

Setelah login sebagai superuser, buka [http://localhost:8000/admin/](http://localhost:8000/admin/) dan:

1. **Buat grup** dengan nama: `user_p3de`, `user_pide`, `user_pmde`, `admin`
2. **Assign user** ke grup yang sesuai
3. Login ke aplikasi di [http://localhost:8000](http://localhost:8000)

| Grup | Akses |
|------|-------|
| `user_p3de` | Tiket Rekam, Kirim, Backup Data, Tanda Terima, Laporan P3DE |
| `user_pide` | Identifikasi, Penelitian, Transfer ke PMDE, Kendali Mutu |
| `user_pmde` | Laporan Kelengkapan Data, Rekap Himpun Olah Data |
| `admin` | Sync Oracle via Web UI |

> Cek kode di `diamond_web/views/home.py` untuk detail view berdasarkan grup.

---

## 📋 Fitur Aplikasi

### 1. Manajemen Data Master

Aplikasi memiliki banyak data master yang bisa dikelola via CRUD (Create, Read, Update, Delete):

| Modul | URL Prefix | Model |
|-------|-----------|-------|
| ILAP | `/ilap/` | Indeks Layanan Administrasi Perpajakan |
| Kategori ILAP | `/kategori-ilap/` | Kategori ILAP |
| Jenis Data ILAP | `/jenis-data-ilap/` | Jenis data & sub-jenis dalam ILAP |
| KPP | `/kpp/` | Kantor Pelayanan Pajak |
| Kanwil | `/kanwil/` | Kantor Wilayah |
| Kategori Wilayah | `/kategori-wilayah/` | Regional grouping |
| Status Data | `/status-data/` | Status data referensi |
| Status Penelitian | `/status-penelitian/` | Status hasil penelitian |
| Dasar Hukum | `/dasar-hukum/` | Landasan hukum |
| Bentuk Data | `/bentuk-data/` | Format data |
| Cara Penyampaian | `/cara-penyampaian/` | Metode pengiriman data |
| Periode Pengiriman | `/periode-pengiriman/` | Periode pengiriman data |
| Periode Jenis Data | `/periode-jenis-data/` | Periode per jenis data |
| Jenis Prioritas Data | `/jenis-prioritas-data/` | Tingkat prioritas data |
| PIC P3DE | `/pic-p3de/` | Person in Charge P3DE |
| PIC PIDE | `/pic-pide/` | Person in Charge PIDE |
| PIC PMDE | `/pic-pmde/` | Person in Charge PMDE |
| Template DOCX | `/docx-template/` | Template dokumen |
| Nama Tabel | `/nama-tabel/` | Nama tabel referensi |

> Setiap modul punya URL pattern: `list`, `data` (DataTables JSON), `create`, `<pk>/update`, `<pk>/delete`.

### 2. Tiket Workflow

Tiket adalah **inti dari aplikasi**. Workflow dimulai dari data masuk hingga selesai diproses.

| Tahap | URL | Form Terkait |
|-------|-----|-------------|
| **Rekam Tiket** | `/tiket/rekam/` | Rekam data tiket baru |
| **Identifikasi** | `/tiket/<pk>/identifikasi/` | Identifikasi data |
| **Kirim ke PIDE** | `/tiket/kirim-tiket/` | Upload ND Pengantar, kirim ke PIDE |
| **Rekam Penelitian** | `/tiket/<pk>/rekam-hasil-penelitian/` | Hasil penelitian PIDE |
| **Batalkan** | `/tiket/<pk>/batalkan/` | Pembatalan tiket |
| **Dikembalikan** | `/tiket/<pk>/dikembalikan/` | Pengembalian data |
| **Transfer ke PMDE** | `/tiket/<pk>/transfer-ke-pmde/` | Transfer data ke PMDE |
| **Selesaikan** | `/tiket/<pk>/selesaikan/` | Penyelesaian tiket |

> Aksi modal (batalkan, penelitian, dll.) diakses dari halaman **Detail Tiket** (`/tiket/<pk>/`).

**API Endpoints (JSON)**:

| Endpoint | Fungsi |
|----------|--------|
| `/api/ilap/<id>/periode-jenis-data/` | Ambil periode data untuk ILAP tertentu |
| `/api/check-jenis-prioritas/<jenis_data_id>/<tahun>/` | Cek prioritas data |
| `/api/check-tiket-exists/` | Cek apakah tiket sudah ada |
| `/api/preview-nomor-tiket/` | Preview nomor tiket |

### 3. Document Generator (DOCX)

Aplikasi bisa **generate dokumen Word (.docx)** secara otomatis dari template.

**Dokumen yang bisa di-generate:**

1. **Tanda Terima** — Nasional/Internasional & Regional (beserta lampiran)
2. **ND Pengantar PIDE** — Nota Dinas pengantar ke PIDE
3. **Surat Klarifikasi** — Surat klarifikasi data
4. **Surat PKDI** — Pemberitahuan Kurang Data/Benahi Data (lengkap/sebagian)
5. **Register Penerimaan Data** — Register penerimaan

**Bulk Document Generation:**

- `/bulk-generate/pkdi-klarifikasi/` — Generate massal surat PKDI/klarifikasi
- `/bulk-generate/nd-pengantar-pide/` — Generate massal ND pengantar

> Template disimpan di database via model `DocxTemplate` dan file fisiknya di `media/docx_templates/`.

### 4. Oracle Data Sync

Ada **dua jenis sinkronisasi** dari database Oracle eksternal:

| Tipe | URL | Celery Task | Management Command |
|------|-----|-------------|-------------------|
| **Sync Referensi** | `/sync-data-referensi/` | `check_referensi_data_task`, `sync_referensi_data_task` | `python manage.py sync_oracle_data` |
| **Sync Tiket** | `/sync-tiket/` | `check_tiket_data_task`, `sync_tiket_data_task` | (N/A) |

Keduanya bisa dijalankan dari **Web UI** (halaman sync) atau dari **terminal**.

> Mapping tabel sync di-hardcode di `diamond_web/utils/oracle_sync.py` pada `HARD_CODED_SYNC_TABLES`.

### 5. Laporan & Monitoring

Aplikasi memiliki **12+ jenis laporan** yang bisa diexport ke Excel:

| Laporan | URL | Deskripsi |
|---------|-----|-----------|
| Register Penerimaan Data | `/register-penerimaan-data/` | Laporan penerimaan data |
| Laporan Transfer | `/laporan-transfer/` | Laporan transfer data |
| SLA Perekaman | `/laporan-sla-perekaman/` | SLA perekaman data |
| SLA Identifikasi | `/laporan-sla-identifikasi/` | SLA identifikasi data |
| Metrik Data Eksternal | `/laporan-metrik-data-eksternal/` | Metrik data eksternal |
| Pengendalian Mutu | `/laporan-pengendalian-mutu/` | Laporan QC |
| Hasil Pengolahan Data Prioritas | `/laporan-hasil-pengolahan-data-prioritas/` | Prioritas data |
| Kelengkapan Data | `/laporan-kelengkapan-data/` | Kelengkapan data |
| Rekap Himpun Olah Data | `/laporan-rekap-himpun-olah-data/` | Rekap penghimpunan & pengolahan |
| Detail Himpun Olah Data | `/laporan-detail-himpun-olah-data/` | Detail penghimpunan & pengolahan |

Selain itu, ada **Dashboard Monitoring** di `/dashboard/` yang menampilkan Power BI report embedded.

---

## 📄 Template DOCX

Dokumentasi lengkap template DOCX ada di `diamond_web/fixtures/default_templates/README.md`.

**Intinya:**

- Ada **11 template default** untuk berbagai jenis dokumen
- Template menggunakan **placeholders** seperti `{{nomor_tiket}}`, `{{nama_pic}}`, `{{tanggal_penerimaan}}`
- Load template ke database: `python manage.py load_default_templates`
- Reset template: `python manage.py load_default_templates --reset`
- User bisa upload template kustom via halaman **Docx Template** di aplikasi

> File template yang diupload user disimpan di `media/docx_templates/` (tidak di-git).

---

## 🔄 Oracle Sync

### Sync Data Referensi

Sinkronisasi data referensi dari database Oracle eksternal ke database lokal.

**Via Terminal:**

```bash
# Cek perubahan (dry-run, tidak menulis data)
python manage.py sync_oracle_data --check-only

# Jalankan insert/update
python manage.py sync_oracle_data
```

**Via Web UI:**

1. Buka menu **Sync Data Referensi** (sidebar kiri)
2. Klik **Test Koneksi** untuk verifikasi koneksi Oracle
3. Klik **Cek Data** untuk melihat perubahan
4. Klik **Sync Data** untuk menjalankan sinkronisasi

### Sync Tiket

Sinkronisasi tiket dari database Oracle. Sama seperti di atas, tersedia via **Web UI** di menu **Sync Tiket**.

> Kedua fitur sync bisa dihentikan di tengah jalan dengan tombol **Stop**.

---

## 🧪 Testing

```bash
# Jalankan semua test
pytest

# Jalankan test dengan output detail
pytest -v

# Jalankan test tertentu berdasarkan marker
pytest -m unit       # Hanya unit test
pytest -m integration  # Hanya integration test

# Jalankan test dengan coverage report
pytest --cov-report=html
```

Konfigurasi test ada di `pytest.ini`:
- Settings: `config.test_settings`
- Coverage: views, models, forms, context_processors
- Report: HTML, terminal, XML

---

## 🛠️ Development Tools

### Django Debug Toolbar

Toolbar debugging yang muncul di browser saat development. Menampilkan:
- SQL queries yang dieksekusi
- Waktu rendering template
- Request/response headers
- Settings yang digunakan

Aktif otomatis saat `DEBUG=True`.

### Django Schema Graph (ERD)

Visualisasi struktur database dalam bentuk diagram ERD interaktif.

**Akses:** [http://localhost:8000/schema/](http://localhost:8000/schema/)

Fitur:
- Tabel dan relasi antar model
- Filter berdasarkan aplikasi
- Zoom in/out
- Export diagram

> Hanya tersedia saat `DEBUG=True`.

### Django Extensions

Kumpulan utilitas Django untuk development:

```bash
# Melihat semua URL yang terdaftar
python manage.py show_urls

# Melihat SQL query yang di-generate oleh ORM
python manage.py sqlmigrate diamond_web 0001

# Shell Django dengan model auto-import
python manage.py shell_plus
```

---

## 📦 Library yang Digunakan

### Core Libraries

| Library | Versi | Kegunaan |
|---------|------:|----------|
| Django | 5.2 | Web framework utama |
| Celery | - | Task queue untuk background job (sync Oracle) |
| oracledb | - | Koneksi ke database Oracle |
| python-docx | - | Generate & proses dokumen Word (.docx) |
| python-decouple / python-dotenv | - | Baca konfigurasi dari `.env` |
| django-crispy-forms | 2.5 | Membantu layout form Bootstrap |
| crispy-bootstrap5 | 2025.6 | Template pack Bootstrap 5 untuk crispy forms |
| django-import-export | 4.4.0 | Import/export data (CSV, Excel) via admin |

### Development Tools

| Library | Versi | Kegunaan |
|---------|------:|----------|
| django-debug-toolbar | 6.1.0 | Toolbar debugging (SQL, performa) |
| django-schema-graph | 3.1.0 | Diagram ERD interaktif |
| django-extensions | - | Utilitas Django (`shell_plus`, `show_urls`, dll) |
| pytest | - | Framework testing |
| pytest-django | - | Integrasi pytest dengan Django |
| pytest-cov | - | Coverage reporting |

### Frontend Libraries

| Library | Versi | Kegunaan |
|---------|------:|----------|
| DataTables | 2.3.6 | Tabel interaktif (server-side processing, paging, sorting, filtering) |
| Bootstrap | 5.3.3 | Framework CSS & component UI |
| Remix Icon | 4.6.0 | Ikon modern dan konsisten |
| jQuery | 3.7.1 | Manipulasi DOM & AJAX |

---

## 🤝 Panduan Kolaborasi

### 1. Fork Repository

```bash
# Klik tombol 'Fork' di https://github.com/kloworizer/diamond-web
# Clone dari repo hasil fork Anda
git clone https://github.com/<username-anda>/diamond-web.git
cd diamond-web
```

### 2. Tambahkan Remote ke Repo Utama

```bash
git remote add upstream https://github.com/kloworizer/diamond-web.git
git fetch upstream
```

### 3. Buat Branch Fitur

Gunakan format `nama-tim-fitur`:

```bash
git checkout -b esha-backend-fitur_login_logout
```

### 4. Sinkronisasi dengan Repo Utama

Sebelum mulai/mengirim PR, pastikan branch Anda update:

```bash
git checkout main
git pull upstream main
git checkout -b nama-tim-fitur
# atau merge ke branch fitur:
git merge main
```

### 5. Commit & Push

```bash
git add .
git commit -m "feat: menambahkan fitur login logout"
git push origin esha-backend-fitur_login_logout
```

### 6. Buat Pull Request

Buka repositori fork Anda di GitHub, klik **Contribute > Open Pull Request** ke repo utama.

---

## � Database Backup & Restore

Django-dbbackup is integrated for database backup and restore. It works with both SQLite (dev) and PostgreSQL (prod).

### Backup

```powershell
# Backup the database (auto-detects engine: SQLite or PostgreSQL)
python manage.py dbbackup

# Backup with a custom filename
python manage.py dbbackup -o diamond-20260622.dump

# Backup media files
python manage.py mediabackup

# Compress the backup (gzip)
python manage.py dbbackup -c
```

### Restore

```powershell
# List available backups
python manage.py listbackups

# Restore the latest backup
python manage.py dbrestore

# Restore a specific backup file
python manage.py dbrestore -i 20260622-120000.dump

# Restore to a different database engine (e.g., restore SQLite backup to PostgreSQL)
# django-dbbackup auto-detects the format; for cross-engine restore, use -r:
python manage.py dbrestore -r sqlite  # force restore as SQLite
python manage.py dbrestore -r postgresql  # force restore as PostgreSQL

# Restore media files
python manage.py mediarestore
```

> Backups are stored in the directory configured via `BACKUP_DIR` (default: `backups/` in the project root, or `/var/backups/diamond` in production).

---

## 📋 Misc Commands

```powershell
# ─── VENV ───
# Aktivasi venv di PowerShell lokal
Set-ExecutionPolicy Unrestricted -Scope Process; .\.venv\Scripts\Activate.ps1

# ─── GIT ───
# Push dari lokal ke VM production
git push work-vm main

# Pull & restart di VM production
git pull origin main
sudo systemctl restart diamond_web_gunicorn
sudo systemctl restart celery && sudo systemctl restart redis


# ─── PIP (offline install untuk VM tanpa internet) ───
# Di lokal: download packages
pip download -r requirements/base.txt -d ./packages
pip download -r requirements/dev.txt -d ./packages
pip download -r requirements/prod.txt -d ./packages
scp -r .\packages\* user@vm:/home/pajak/diamond-web/packages

# Di VM: install dari folder packages (tanpa internet)
pip install --no-index --find-links=./packages -r requirements/base.txt
```

---

> **Butuh bantuan?** Lihat dokumentasi lebih lanjut di folder `docs/`:
> - [Panduan Deployment](docs/PRODUCTION_SETUP.md)
> - [Dokumentasi API](docs/API_DOCUMENTATION.md)
> - [Dokumentasi Keamanan](docs/SECURITY.md)
> - [Checklist Deployment](docs/DEPLOYMENT_CHECKLIST.md)
> - [Dokumen Serah Terima](docs/HANDOVER_DOCUMENT.md)
> - [Panduan Kontribusi](docs/CONTRIBUTING.md)
> - [Riwayat Rilis](docs/CHANGELOG.md)
> - Template DOCX di `diamond_web/fixtures/default_templates/README.md`