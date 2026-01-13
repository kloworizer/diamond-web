# Diamond

Repositori ini berisi proyek Django. Ikuti langkah-langkah berikut untuk mengkloning, mengatur, dan menjalankan server pengembangan.

## Cara Clone Repository

```bash
git clone https://github.com/kloworizer/diamond-web.git
cd diamond-web
```

## Setup Proyek Django

1. **Buat dan aktifkan virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/Mac
    venv\Scripts\activate     # Windows
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
| crispy-bootstrap5 | 2025.6 | Template pack untuk `django-crispy-forms` agar form dirender menggunakan gaya Bootstrap 5. |
| django-tables2 | 2.8.0 | Membantu merender tabel dari QuerySet dengan fitur paging, sorting, dan styling. |
| django-crispy-forms | 2.5 | Aplikasi Django untuk merapikan dan memudahkan pembuatan layout form. |
| django-filter | 25.2 | Menyediakan mekanisme filter untuk QuerySet pada views dan integrasi dengan Django REST/CBV. |
| django-import-export | 4.4.0 | Memudahkan impor dan ekspor data (CSV, Excel, dsb.) lewat admin Django. |
