# Dokumentasi Keamanan

> **Terakhir Diperbarui:** June 23, 2026  
> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE

---

## Daftar Isi

- [Autentikasi & Otorisasi](#autentikasi--otorisasi)
- [Manajemen Sesi](#manajemen-sesi)
- [Perlindungan CSRF](#perlindungan-csrf)
- [Header Keamanan](#header-keamanan)
- [Keamanan Database](#keamanan-database)
- [Keamanan Upload File](#keamanan-upload-file)
- [Keamanan Koneksi Oracle](#keamanan-koneksi-oracle)
- [Variabel Lingkungan & Rahasia](#variabel-lingkungan--rahasia)
- [Validasi Input](#validasi-input)
- [Jejak Audit](#jejak-audit)
- [Checklist Keamanan Produksi](#checklist-keamanan-produksi)

---

## Autentikasi & Otorisasi

### Grup & Peran Pengguna

The application uses Django's built-in `Group` model for role-based access control.

| Grup | Deskripsi | Hak Akses |
|------|-----------|-----------|
| `user_p3de` | Tim pengumpulan data | Tiket rekam, kirim, backup, tanda terima, laporan P3DE |
| `user_pide` | Tim pemrosesan data | Identifikasi, penelitian, transfer, QC |
| `user_pmde` | Tim kendali mutu | Laporan kelengkapan, rekap himpun olah data |
| `admin` | Administrator | Sinkronisasi Oracle, manajemen pengguna, akses penuh |

### Implementasi

- Pengecekan grup dilakukan di views melalui `request.user.groups.filter(name='user_p3de').exists()`
- Template menggunakan template tag `has_group` (`diamond_web/templatetags/auth_extras.py`)
- Admin Django (`/admin/`) dibatasi hanya untuk **superuser**

### Kebijakan Password

Validator password bawaan Django diterapkan:

```python
AUTH_PASSWORD_VALIDATORS = [
    # UserAttributeSimilarityValidator — password too similar to user attributes
    # MinimumLengthValidator — minimum length (default: 8)
    # CommonPasswordValidator — password is not too common
    # NumericPasswordValidator — password is not entirely numeric
]
```

---

## Manajemen Sesi

### Configuration (`config/settings.py`)

| Pengaturan | Nilai | Deskripsi |
|------------|-------|-----------|
| `SESSION_COOKIE_AGE` | 1800 (30 mnt) | Masa berlaku sesi dalam detik |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | `False` | Sesi tetap ada setelah browser ditutup |
| `SESSION_SAVE_EVERY_REQUEST` | `False` | Jangan perbarui sesi setiap permintaan (mengurangi penulisan DB) |
| `SESSION_COOKIE_SECURE` | `True` (prod) / `False` (dev) | Hanya kirim cookie melalui HTTPS |
| `SESSION_COOKIE_HTTPONLY` | `True` (default Django) | Cookie tidak dapat diakses melalui JavaScript |

### Alur Kedaluwarsa Sesi

1. Pengguna tidak aktif selama 30 menit → sesi kedaluwarsa
2. Permintaan berikutnya dialihkan ke halaman `/session-expired/`
3. Pengguna harus masuk kembali

### Mekanisme Keep-Alive

- Endpoint: `GET /keep-alive/` — respons JSON ringan
- Digunakan oleh frontend untuk mencegah waktu tunggu sesi selama penggunaan aktif
- TIDAK memperpanjang sesi jika pengguna idle (hanya aktivitas nyata yang memperpanjang sesi)

---

## Perlindungan CSRF

### Konfigurasi

```python
CSRF_TRUSTED_ORIGINS = ["http://diamond.pajak.go.id"]
CSRF_COOKIE_SECURE = True  # in production
```

### Implementasi

- Semua formulir `POST` menyertakan `{% csrf_token %}`
- Permintaan AJAX `POST` memerlukan header `X-CSRFToken`
- Token CSRF diputar saat login
- Cookie CSRF diatur dengan `SameSite=Lax` (default Django)

---

## Header Keamanan

### Production (via Nginx or Django settings)

| Header | Nilai | Tujuan |
|--------|-------|--------|
| `X-Content-Type-Options` | `nosniff` | Mencegah sniffing tipe MIME |
| `X-Frame-Options` | `DENY` | Mencegah clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Filter XSS (browser lawas) |
| `Referrer-Policy` | `same-origin` (direkomendasikan) | Membatasi informasi referrer |

### Django Settings

```python
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"  # Prevents iframe embedding
```

---

## Keamanan Database

### PostgreSQL (Production)

| Praktik | Deskripsi |
|---------|-----------|
| Pengguna khusus | Aplikasi menggunakan pengguna database non-privilege |
| Autentikasi password | Autentikasi `md5` atau `scram-sha-256` |
| Ikat jaringan | PostgreSQL terikat ke `localhost` (tidak terekspos) |
| Hak akses minimal | Pengguna database hanya memiliki `INSERT`, `SELECT`, `UPDATE`, `DELETE` pada tabel aplikasi |
| Backup rutin | Backup otomatis harian (lihat [Pengaturan Produksi](PRODUCTION_SETUP.md#backup-configuration)) |

### SQLite (Pengembangan)

- Mode SQLite: `WAL` (Write-Ahead Logging) mencegah kunci baca
- Timeout: 30 detik untuk kontensi penulisan
- Hanya digunakan untuk pengembangan (tidak aman untuk produksi dengan akses bersamaan)

---

## Keamanan Upload File

### File Media

- File yang diupload disimpan di direktori `media/` (gitignored)
- Django menyajikan file media hanya di pengembangan (`DEBUG=True`)
- Di produksi, Nginx menyajikan file media secara langsung
- Tipe file divalidasi melalui Django forms

### Template DOCX

- Template yang diupload divalidasi sebagai file `.docx`
- Template disimpan dengan nama file acak di subdirektori `media/docx_templates/YYYYMMDD/`
- Template bawaan dikontrol versi di `fixtures/default_templates/`

### File Backup

- Backup database disimpan di `backups/` atau `BACKUP_DIR` yang dikonfigurasi
- File backup berisi data sensitif — pastikan izin direktori bersifat restriktif
- Untuk backup di luar lokasi, pertimbangkan enkripsi

---

## Keamanan Koneksi Oracle

- Kredensial Oracle disimpan di file `.env` (bukan di kode)
- Koneksi menggunakan `oracledb` dengan mode thick untuk versi Oracle produksi
- Koneksi dapat diuji melalui UI sebelum menjalankan sinkronisasi
- Tidak ada kredensial Oracle yang dicatat atau terekspos di pesan error

---

## Variabel Lingkungan & Rahasia

### .env File Security

| Praktik | Deskripsi |
|---------|-----------|
| Tidak dikomit | `.env` ada di `.gitignore` |
| Template disediakan | `.env.example.dev` dan `.env.example.prod` menunjukkan variabel yang diperlukan |
| Izin file | `.env` hanya dapat dibaca oleh pengguna aplikasi (`chmod 600`) |
| Kunci rahasia | Hasilkan kunci rahasia unik per deployment: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |

### Sensitive Variables

| Variabel | Sensitivitas | Catatan |
|----------|-------------|--------|
| `SECRET_KEY` | Kritis | Jaga kerahasiaan; rotasi membatalkan sesi |
| `DB_PASSWORD` | Kritis | Kredensial database |
| `ORACLE_PASSWORD` | Kritis | Kredensial Oracle |
| `EMAIL_HOST_PASSWORD` | Sedang | Password akun email |
| `AWS_SECRET_ACCESS_KEY` | Kritis | Kredensial penyimpanan cloud |

---

## Validasi Input

- Semua input formulir divalidasi melalui Django Forms
- Parameter DataTables sisi server telah dibersihkan
- Injeksi SQL dicegah oleh Django ORM (kueri terparameter)
- Scripting lintas situs (XSS) dimitigasi oleh auto-escaping template Django
- Upload file divalidasi oleh tipe bidang formulir

---

## Jejak Audit

Aplikasi memiliki model log audit (`AuditTrailModel`) yang mencatat:

- Perubahan model (buat/ubah/hapus)
- Stempel waktu perubahan
- Pengguna yang melakukan perubahan

Aksi tiket dilacak melalui model `TiketAction`:
- Setiap perubahan status dicatat
- Setiap aksi mencatat: pengguna, stempel waktu, jenis aksi, dan catatan

---

## Checklist Keamanan Produksi

- [ ] `DEBUG=False` — jangan pernah menjalankan mode debug di produksi
- [ ] `SECRET_KEY` unik dan bukan nilai default
- [ ] `ALLOWED_HOSTS` hanya berisi domain/IP produksi
- [ ] `CSRF_TRUSTED_ORIGINS` diatur dengan benar
- [ ] `X_FRAME_OPTIONS=DENY` (perlindungan clickjacking)
- [ ] Database menggunakan password kuat (bukan password default/dev)
- [ ] Redis terikat hanya ke `127.0.0.1`
- [ ] Izin file `.env` adalah `600` (hanya baca/tulis pemilik)
- [ ] Penyajian file statis/media ditangani oleh Nginx, bukan Django
- [ ] Jadwal backup rutin telah dikonfigurasi
- [ ] Firewall server membatasi akses hanya ke port yang diperlukan (80, 443, SSH)
- [ ] Upaya login gagal dipantau (pertimbangkan pembatasan rate)
- [ ] Log aplikasi dan sistem dipantau untuk aktivitas mencurigakan
