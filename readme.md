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

1. **Buat dan aktifkan virtual environment:**

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    .venv\Scripts\activate     # Windows
    ```

2. **Install dependensi:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Jalankan migrasi database:**

    ```bash
    python manage.py migrate
    ```

## Membuat file .env lokal

Buat file `.env` untuk konfigurasi lokal dengan menyalin dari contoh berikut:

```bash
copy .env-example .env  # Windows
cp .env-example .env    # Linux/Mac
```

Edit file `.env` sesuai kebutuhan konfigurasi lokal Anda.

## Menjalankan Server Development

```bash
python manage.py runserver
```

Akses aplikasi di [http://localhost:8000](http://localhost:8000).

## Daftar library

| Library | Versi | Keterangan |
|---|---:|---|
| django-crispy-forms | 2.5 | Aplikasi Django untuk merapikan dan memudahkan pembuatan layout form. |
| crispy-bootstrap5 | 2025.6 | Template pack untuk `django-crispy-forms` agar form dirender menggunakan gaya Bootstrap 5. |
| django-import-export | 4.4.0 | Memudahkan impor dan ekspor data (CSV, Excel, dsb.) lewat admin Django. |

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

