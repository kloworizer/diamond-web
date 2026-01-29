# Diamond

Repositori ini berisi proyek Django. Ikuti langkah-langkah berikut untuk mengatur dan menjalankan server pengembangan.

## Kebutuhan Software

Pastikan Anda telah menginstal perangkat lunak berikut sebelum memulai:

- **Python** (versi 3.10 atau lebih baru): [Download Python](https://www.python.org/downloads/)
- **Git for Windows**: [Download Git](https://git-scm.com/download/win)

## Cara Fork Repository

Agar dapat berkontribusi, lakukan *fork* ke akun GitHub Anda, lalu clone dari repo hasil fork tersebut:

```bash
# Klik tombol 'Fork' di halaman repo utama: https://github.com/kloworizer/diamond-web
# Setelah fork, clone repo dari akun Anda sendiri

git clone https://github.com/<username-anda>/diamond-web.git
cd diamond-web
```

Setelah selesai mengembangkan, Anda dapat membuat pull request ke repo utama.

## Setup Proyek Django

### Struktur Requirements dan Settings

Proyek ini menggunakan pemisahan antara konfigurasi development dan production:

```
requirements/
├── base.txt     # Dependencies umum untuk semua environment
├── dev.txt      # Dependencies khusus development
└── prod.txt     # Dependencies khusus production

config/settings/
├── base.py      # Settings umum
├── dev.py       # Settings development
└── prod.py      # Settings production
```

### Langkah Setup Development

1. **Buat dan aktifkan virtual environment:**

    ```bash
    python -m venv .venv
    .venv\Scripts\activate     # Windows
    source .venv/bin/activate  # Linux/Mac
    ```

2. **Install dependensi development:**

    ```bash
    pip install -r requirements/dev.txt
    ```

3. **Buat file .env untuk konfigurasi lokal:**

    ```bash
    copy .env.example .env  # Windows
    cp .env.example .env    # Linux/Mac
    ```

    Edit file `.env` dan sesuaikan nilai-nilainya:
    ```
    SECRET_KEY=your-secret-key-here
    DEBUG=True
    ALLOWED_HOSTS=127.0.0.1,localhost
    DJANGO_SETTINGS_MODULE=config.settings.dev
    ```

4. **Jalankan migrasi database:**

    ```bash
    python manage.py migrate
    ```

## Menjalankan Server Development

```bash
python manage.py runserver
```

Akses aplikasi di [http://localhost:8000](http://localhost:8000).

### Menjalankan dengan Settings Spesifik

Secara default, `manage.py` menggunakan `config.settings.dev`. Untuk menggunakan settings lain:

```bash
# Gunakan settings production
python manage.py runserver --settings=config.settings.prod

# Atau set environment variable
$env:DJANGO_SETTINGS_MODULE="config.settings.prod"  # Windows PowerShell
export DJANGO_SETTINGS_MODULE=config.settings.prod  # Linux/Mac
```

## Tools Development

### Django Schema Graph (Database ERD)

**Django Schema Graph** hanya tersedia di environment development untuk memvisualisasikan struktur database.

#### Cara Mengakses:

1. Pastikan server development berjalan:
   ```bash
   python manage.py runserver
   ```

2. Akses schema graph melalui browser:
   - URL: [http://localhost:8000/schema/](http://localhost:8000/schema/)

3. Fitur yang tersedia:
   - Visualisasi tabel dan relasi antar model
   - Filter berdasarkan aplikasi
   - Zoom in/out diagram
   - Export diagram

**Catatan:** Tool ini tidak tersedia di production untuk alasan keamanan dan performa.

## Daftar library

| Library | Versi | Keterangan |
|---|---:|---|
| django-crispy-forms | 2.5 | Aplikasi Django untuk merapikan dan memudahkan pembuatan layout form. |
| crispy-bootstrap5 | 2025.6 | Template pack untuk `django-crispy-forms` agar form dirender menggunakan gaya Bootstrap 5. |
| django-import-export | 4.4.0 | Memudahkan impor dan ekspor data (CSV, Excel, dsb.) lewat admin Django. |

### Development Tools

| Library | Versi | Keterangan |
|---|---:|---|
| django-debug-toolbar | 6.1.0 | Toolbar debugging untuk development yang menampilkan informasi SQL queries, performance, dan lainnya. |
| django-schema-graph | 3.1.0 | Tools untuk memvisualisasikan struktur database dalam bentuk diagram ERD interaktif. |

### Frontend Libraries

| Library | Versi | Keterangan |
|---|---:|---|
| DataTables | 2.3.6 | Library JavaScript untuk tabel interaktif dengan fitur server-side processing, paging, sorting, dan column filtering. |
| Bootstrap | 5.3.3 | Framework CSS untuk styling dan komponen UI. |
| Remix Icon | 4.6.0 | Icon library untuk ikon modern dan konsisten. |
| jQuery | 3.7.1 | Library JavaScript untuk manipulasi DOM dan AJAX requests. |


## Panduan Kolaborasi

Agar kolaborasi lebih terstruktur, ikuti langkah berikut:

### 1. Membuat Branch Fitur

Gunakan format `nama-tim-fitur` untuk nama branch. Contoh:

```bash
git checkout -b esha-backend-fitur_login_logout
```

### 2. Menambahkan Remote ke Repo Utama

Setelah melakukan fork dan clone, tambahkan remote ke repo utama agar bisa melakukan pull request:

```bash
git remote add upstream https://github.com/kloworizer/diamond-web.git
git fetch upstream
```

### 3. Sinkronisasi dengan Repo Utama

Sebelum mulai mengembangkan, pastikan branch Anda selalu update dengan repo utama:

```bash
git checkout main
git pull upstream main
```

### 4. Membuat Pull Request

Setelah selesai mengembangkan di branch fitur, push ke repo fork Anda dan buat pull request ke repo utama melalui GitHub.

