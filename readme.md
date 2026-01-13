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

## Menjalankan Server Development

```bash
python manage.py runserver
```

Akses aplikasi di [http://localhost:8000](http://localhost:8000).
