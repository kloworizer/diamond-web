# Panduan Setup Template Default

## Gambaran Umum

Aplikasi sekarang menggunakan **template default yang dikontrol versi** yang dikomit ke git, sambil tetap memungkinkan pengguna mengunggah template kustom ke folder `media/`.

## Arsitektur

```
Project Root
├── diamond_web/
│   ├── fixtures/
│   │   └── default_templates/          ← COMMITTED TO GIT (examples)
│   │       ├── *.docx (11 templates)
│   │       └── README.md
│   └── media/
│       └── docx_templates/            ← IGNORED BY GIT (user uploads)
│           └── (FileField storage)
├── .gitignore                          ← Updated to allow fixtures
```

## Struktur File

### Fixtures (Dikontrol Versi)
**Lokasi:** `diamond_web/fixtures/default_templates/`

Berisi 11 file template DOCX default:
- File template dikomit ke git
- Digunakan sebagai contoh dan default pada setup pertama
- Referensi baca-saja untuk pengembang
- Dapat diedit dan dikomit untuk peningkatan template

### Media (Upload Pengguna - Tidak Dikontrol Versi)
**Lokasi:** `diamond_web/media/docx_templates/`

Berisi template yang diunggah pengguna yang disimpan melalui Django FileField:
- Semua file di sini diabaikan oleh git (sesuai `.gitignore`)
- Secara otomatis diatur berdasarkan tanggal (subdirektori `YYYYMMDD/`)
- File yang dibuat/diunggah berada di sini
- Data produksi tetap lokal untuk setiap deployment

## Konfigurasi .gitignore

```ignore
media/                                    # Ignore all media files
# But allow default templates in fixtures
!diamond_web/fixtures/default_templates/ # Exception: allow fixtures
!diamond_web/fixtures/default_templates/*.docx
```

Ini memungkinkan:
- ✓ File template DOCX di `fixtures/` untuk dikomit
- ✓ README.md di `fixtures/` untuk dikomit
- ✗ Semua file di `media/` untuk diabaikan

## Proses Setup

### Setup Pertama Kali

1. Clone repositori (template fixtures sudah termasuk)
2. Jalankan migrasi
3. Muat template default ke database:

```bash
python manage.py load_default_templates
```

Perintah ini:
- Membaca template dari `diamond_web/fixtures/default_templates/`
- Membuat record DocxTemplate di database
- Menyalin file ke `diamond_web/media/docx_templates/` melalui FileField
- Menandai semua template sebagai aktif

### Workflow

**Pada Setup Pertama:**
```
fixtures/default_templates/*.docx
           ↓ (via load_default_templates command)
        Database (DocxTemplate records)
           ↓ (FileField saves)
media/docx_templates/*.docx
           ↓ (used for document generation)
      Generated documents
```

**Saat Pengguna Mengunggah Template Kustom:**
```
User uploads via UI
           ↓
        Database (DocxTemplate record)
           ↓
media/docx_templates/*.docx (automatically saved)
           ↓ (used for document generation)
      Generated documents
```

## Perintah Manajemen Template

### Muat Template Default

```bash
# Load templates (skip if already exist)
python manage.py load_default_templates

# Reset and reload (deletes all, loads fresh)
python manage.py load_default_templates --reset
```

## Workflow Pengguna

### Pengguna Admin

1. **Lihat template:** Buka menu "Kelola Template Dokumen"
2. **Upload kustom:** Gunakan formulir untuk mengunggah template baru
3. **Edit:** Perbarui konten template langsung di UI
4. **Hapus:** Hapus template kustom
5. **Unduh:** Unduh template apa pun untuk memverifikasi konten

### Generasi Dokumen

Sistem secara otomatis:
1. Mendeteksi jenis dokumen yang diminta
2. Memeriksa tipe wilayah (Regional vs Nasional/Internasional) dari tiket
3. Memilih template yang sesuai dari database
4. Mengisi placeholder dengan data tiket
5. Mengembalikan file DOCX yang telah dibuat

## Panduan Placeholder Template

Template dokumen menggunakan dua jenis placeholder yang akan diganti secara otomatis dengan data dari sistem saat dokumen dibuat.

### 1. Placeholder Variabel Tunggal

Gunakan `{{nama_placeholder}}` untuk data tunggal seperti nama, nomor, tanggal, dan lain-lain.

**Contoh:**
- `{{nomor_tanda_terima}}`
- `{{diterima_dari}}`
- `{{nama_ilap}}`
- `{{jenis_data}}`
- `{{periode_data}}`
- `{{bentuk_data}}`
- `{{cara_penyampaian}}`
- `{{nama_pic_p3de}}`

### 2. Placeholder Baris Berulang (untuk Tabel)

Gunakan `{{row.nama_field}}` dalam tabel untuk data yang berisi banyak baris (lampiran, register data).

**Cara penggunaan:**
1. Buat tabel di dokumen Word dengan header dan satu baris template
2. Isi sel baris template dengan placeholder `{{row.field}}`
3. Saat dokumen dibuat, baris template akan otomatis diklon untuk setiap data

**Contoh:**
- `{{row.nama_ilap}}`
- `{{row.jenis_data}}`
- `{{row.periode_tahun}}`

**Field yang tersedia:**
`nomor`, `nama_kanwil`, `nama_ilap`, `jenis_data`, `periode_tahun`, `status_data`, `baris_diterima`, `dasar_hukum`, `nomor_tiket`, `baris_lengkap`, `baris_tidak_lengkap`

**Contoh struktur tabel di Word:**

| No | Kanwil | Nama ILAP | Jenis Data | Periode | Status |
|----|--------|-----------|------------|---------|--------|
| `{{row.nomor}}` | `{{row.nama_kanwil}}` | `{{row.nama_ilap}}` | `{{row.jenis_data}}` | `{{row.periode_tahun}}` | `{{row.status_data}}` |

## Workflow Pengembangan

### Meningkatkan Template

1. Edit file `.docx` di `diamond_web/fixtures/default_templates/`
2. Jaga variabel placeholder tetap utuh: `{{variable_name}}`
3. Uji coba di pengembangan
4. Komit perubahan ke git

### Untuk Reviewer
- Perubahan template terlihat di riwayat git
- Dapat melihat dengan tepat apa yang berubah di template
- Kualitas template adalah bagian dari review kode

## Skenario Reset Database

Jika database direset tetapi template tidak:

```bash
# Reload default templates from fixtures
python manage.py load_default_templates --reset

# This restores:
# - All 11 DocxTemplate records
# - All 11 DOCX files in media folder
# - All templates marked as active
```

## Keuntungan

✓ **Kontrol Versi:** Template dilacak di git seperti kode  
✓ **Reproduksibilitas:** Deployment baru secara otomatis mendapatkan template default  
✓ **Kustomisasi Pengguna:** Pengguna masih dapat mengunggah/mengelola template kustom  
✓ **Pemisahan:** Perubahan pengembangan (fixtures) terpisah dari data pengguna (media)  
✓ **Konsistensi:** Semua deployment dimulai dengan kualitas template yang sama  
✓ **Dokumentasi:** README menjelaskan sistem template kepada pengembang  

## Catatan Migrasi

Migrasi dari sistem lama:
1. ✓ Menghapus folder yang tidak digunakan (docx_templates/ lama, templates/uploads/)
2. ✓ Menyimpan template saat ini di media/ (aktif/digunakan)
3. ✓ Menyalin template ke fixtures/ (untuk kontrol versi)
4. ✓ Memperbarui .gitignore untuk mengizinkan fixtures tetapi tidak media
5. ✓ Membuat perintah manajemen untuk setup

Tidak ada perubahan database yang diperlukan - record DocxTemplate yang ada tetap utuh.
