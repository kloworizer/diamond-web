# Dokumentasi API

> **Terakhir Diperbarui:** June 24, 2026  
> **Base URL:** `http://10.xxx.xxx.xxx`

---

## Daftar Isi

- [Autentikasi](#autentikasi)
- [Gambaran Endpoint API](#gambaran-endpoint-api)
- [Endpoint DataTables AJAX](#endpoint-datatables-ajax)
- [Endpoint CRUD Data Master](#endpoint-crud-data-master)
- [Endpoint Workflow Tiket](#endpoint-workflow-tiket)
- [Endpoint Laporan & Ekspor](#endpoint-laporan--ekspor)
- [Endpoint Generasi Dokumen](#endpoint-generasi-dokumen)
- [Endpoint Sinkronisasi Oracle](#endpoint-sinkronisasi-oracle)
- [Endpoint Notifikasi](#endpoint-notifikasi)
- [Endpoint Utilitas](#endpoint-utilitas)
- [Penanganan Error](#penanganan-error)

---

## Autentikasi

Aplikasi ini menggunakan autentikasi berbasis sesi bawaan Django. Semua endpoint yang memerlukan autentikasi membutuhkan sesi aktif.

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `POST` | `/login/` | Pengiriman formulir login (dilindungi CSRF) |
| `POST` | `/logout/` | Logout (memerlukan POST) |
| `GET` | `/accounts/password_change/` | Formulir ubah kata sandi |
| `POST` | `/accounts/password_change/` | Kirim perubahan kata sandi |

### Konfigurasi Sesi
- Waktu tunggu sesi: **30 menit** (`SESSION_COOKIE_AGE = 1800`)
- Sesi berakhir saat browser ditutup: **Tidak**

---

## Gambaran Endpoint API

### Endpoint JSON API (digunakan oleh frontend AJAX)

| Method | URL | Deskripsi | Autentikasi |
|--------|-----|-------------|------|
| `GET` | `/api/ilap/<ilap_id>/periode-jenis-data/` | Ambil data periode untuk ILAP | ✓ |
| `GET` | `/api/check-jenis-prioritas/<jenis_data_id>/<tahun>/` | Periksa status prioritas data | ✓ |
| `GET` | `/api/check-tiket-exists/` | Periksa apakah tiket sudah ada | ✓ |
| `GET` | `/api/preview-nomor-tiket/` | Pratinjau nomor tiket yang dihasilkan otomatis | ✓ |
| `GET` | `/api/ilap/<ilap_id>/periode-jenis-data/` | Ambil tipe data periode ILAP | ✓ |

### Endpoint Umum

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/` | Halaman beranda (dasbor berdasarkan peran) |
| `GET` | `/home/data/` | Data halaman beranda (AJAX) |
| `GET` | `/keep-alive/` | Pemeriksaan kesehatan / menjaga sesi tetap aktif |
| `GET` | `/session-expired/` | Halaman notifikasi sesi berakhir |
| `GET` | `/profil/` | Halaman profil pengguna |
| `GET` | `/docs/` | Indeks dokumentasi internal |
| `GET` | `/docs/<slug>/` | Detail dokumentasi internal |

---

## Endpoint DataTables AJAX

Semua tampilan daftar data master menyediakan endpoint JSON DataTables sisi server (melalui `GET` dengan parameter kueri DataTables).

### Parameter (dikirim oleh DataTables secara otomatis)
| Parameter | Deskripsi |
|-----------|-------------|
| `draw` | Penghitung draw (dikembalikan) |
| `start` | Offset untuk paginasi |
| `length` | Jumlah catatan per halaman |
| `order[0][column]` | Indeks kolom untuk diurutkan |
| `order[0][dir]` | Arah pengurutan (`asc`/`desc`) |
| `search[value]` | Nilai pencarian global |
| `columns[0][search][value]` | Pencarian khusus kolom |

### Format Respons
```json
{
    "draw": 1,
    "recordsTotal": 100,
    "recordsFiltered": 50,
    "data": [ ... ]
}
```

### Endpoint DataTables

| URL | Model |
|-----|-------|
| `/ilap/data/` | ILAP |
| `/kategori-ilap/data/` | Kategori ILAP |
| `/jenis-data-ilap/data/` | Jenis Data ILAP |
| `/jenis-tabel/data/` | Jenis Tabel |
| `/kategori-wilayah/data/` | Kategori Wilayah |
| `/kanwil/data/` | Kanwil |
| `/kpp/data/` | KPP |
| `/status-data/data/` | Status Data |
| `/status-penelitian/data/` | Status Penelitian |
| `/bentuk-data/data/` | Bentuk Data |
| `/cara-penyampaian/data/` | Cara Penyampaian |
| `/dasar-hukum/data/` | Dasar Hukum |
| `/media-backup/data/` | Media Backup |
| `/periode-pengiriman/data/` | Periode Pengiriman |
| `/periode-jenis-data/data/` | Periode Jenis Data |
| `/jenis-prioritas-data/data/` | Jenis Prioritas Data |
| `/pic-p3de/data/` | PIC P3DE |
| `/pic-pide/data/` | PIC PIDE |
| `/pic-pmde/data/` | PIC PMDE |
| `/nama-tabel/data/` | Nama Tabel |
| `/docx-template/data/` | Docx Template |
| `/klasifikasi-jenis-data/data/` | Klasifikasi Jenis Data |
| `/durasi-jatuh-tempo-pide/data/` | Durasi Jatuh Tempo PIDE |
| `/durasi-jatuh-tempo-pmde/data/` | Durasi Jatuh Tempo PMDE |

---

## Endpoint CRUD Data Master

Setiap modul data master mengikuti pola URL yang konsisten:

| Method | Pola URL | Deskripsi |
|--------|-------------|-------------|
| `GET` | `/{module}/` | Tampilan daftar (merender HTML) |
| `GET` | `/{module}/data/` | Data JSON DataTables |
| `GET` | `/{module}/create/` | Formulir buat (HTML) |
| `POST` | `/{module}/create/` | Kirim formulir buat |
| `GET` | `/{module}/<pk>/update/` | Formulir ubah (HTML) |
| `POST` | `/{module}/<pk>/update/` | Kirim formulir ubah |
| `POST` | `/{module}/<pk>/delete/` | Hapus catatan |

### Modul CRUD yang Tersedia

| Modul | Prefiks URL | Model |
|--------|-----------|-------|
| ILAP | `/ilap/` | `ILAP` |
| Kategori ILAP | `/kategori-ilap/` | `KategoriILAP` |
| Jenis Data ILAP | `/jenis-data-ilap/` | `JenisDataILAP` |
| Jenis Tabel | `/jenis-tabel/` | `JenisTabel` |
| Kategori Wilayah | `/kategori-wilayah/` | `KategoriWilayah` |
| Kanwil | `/kanwil/` | `Kanwil` |
| KPP | `/kpp/` | `KPP` |
| Status Data | `/status-data/` | `StatusData` |
| Status Penelitian | `/status-penelitian/` | `StatusPenelitian` |
| Bentuk Data | `/bentuk-data/` | `BentukData` |
| Cara Penyampaian | `/cara-penyampaian/` | `CaraPenyampaian` |
| Dasar Hukum | `/dasar-hukum/` | `DasarHukum` |
| Media Backup | `/media-backup/` | `MediaBackup` |
| Periode Pengiriman | `/periode-pengiriman/` | `PeriodePengiriman` |
| Periode Jenis Data | `/periode-jenis-data/` | `PeriodeJenisData` |
| Jenis Prioritas Data | `/jenis-prioritas-data/` | `JenisPrioritasData` |
| PIC P3DE | `/pic-p3de/` | `PIC` (tipe=P3DE) |
| PIC PIDE | `/pic-pide/` | `PIC` (tipe=PIDE) |
| PIC PMDE | `/pic-pmde/` | `PIC` (tipe=PMDE) |
| Nama Tabel | `/nama-tabel/` | `NamaTabel` |
| Docx Template | `/docx-template/` | `DocxTemplate` |
| Klasifikasi Jenis Data | `/klasifikasi-jenis-data/` | `KlasifikasiJenisData` |
| Durasi Jatuh Tempo PIDE | `/durasi-jatuh-tempo-pide/` | `DurasiJatuhTempo` (seksi=PIDE) |
| Durasi Jatuh Tempo PMDE | `/durasi-jatuh-tempo-pmde/` | `DurasiJatuhTempo` (seksi=PMDE) |

### Endpoint Khusus (non-standard CRUD)

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/ilap/next-id/` | Ambil ID ILAP berikutnya |
| `GET` | `/jenis-data/get-next-id/` | Ambil ID Jenis Data berikutnya |
| `GET` | `/jenis-data/existing/` | Ambil daftar Jenis Data yang ada |
| `GET` | `/jenis-data/sub/existing/` | Ambil daftar Sub Jenis Data yang ada |
| `GET` | `/jenis-data/sub/next/` | Ambil ID Sub Jenis Data berikutnya |
| `GET` | `/tanda-terima-data/next-number/` | Ambil nomor tanda terima berikutnya |
| `GET` | `/tanda-terima-data/tikets-by-ilap/` | Ambil tiket yang dikelompokkan berdasarkan ILAP |

---

## Endpoint Workflow Tiket

### Daftar & Detail

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/tiket/` | Tampilan daftar tiket (HTML) |
| `GET` | `/tiket/data/` | Data JSON DataTables tiket |
| `GET` | `/tiket/<pk>/` | Tampilan detail tiket (HTML) |
| `GET` | `/tiket/<pk>/documents/download/` | Unduh semua dokumen tiket (ZIP) |

### Langkah Workflow

| Method | URL | Deskripsi | Perubahan Status |
|--------|-----|-------------|---------------|
| `GET/POST` | `/tiket/rekam/` | Rekam tiket baru | → **Direkam (1)** |
| `GET/POST` | `/tiket/identifikasi/create/` | Rekam tiket baru (alur identifikasi) | → **Direkam (1)** |
| `GET/POST` | `/tiket/<pk>/rekam-hasil-penelitian/` | Rekam hasil penelitian (modal) | → **Diteliti (2)** |
| `GET/POST` | `/tiket/kirim-tiket/` | Kirim tiket ke PIDE | → **Dikirim ke PIDE (4)** |
| `GET/POST` | `/tiket/<pk>/kirim-pide/` | Kirim tiket tertentu ke PIDE | → **Dikirim ke PIDE (4)** |
| `GET/POST` | `/tiket/<pk>/identifikasi/` | Identifikasi data tiket | → **Identifikasi (5)** |
| `GET/POST` | `/tiket/<pk>/batalkan/` | Batalkan tiket (modal) | → **Dibatalkan (7)** |
| `GET/POST` | `/tiket/<pk>/dikembalikan/` | Kembalikan tiket ke P3DE (modal) | → **Dikembalikan (3)** |
| `GET/POST` | `/tiket/<pk>/transfer-ke-pmde/` | Transfer tiket ke PMDE (modal) | → **Pengendalian Mutu (6)** |
| `GET/POST` | `/tiket/<pk>/selesaikan/` | Selesaikan tiket (modal) | → **Selesai (8)** |

### Sub-endpoint Kirim Tiket

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/tiket/kirim-tiket/download/<id_temp>/` | Unduh ND Pengantar DOCX |
| `POST` | `/tiket/kirim-tiket/temp-update/<id_temp>/` | Perbarui data kirim sementara |
| `POST` | `/tiket/kirim-tiket/temp-delete/<id_temp>/` | Hapus data kirim sementara |
| `POST` | `/tiket/kirim-tiket/kirim-ke-pide/<id_temp>/` | Konfirmasi kirim ke PIDE |

### Tampilan Daftar yang Difilter

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/tiket/identifikasi/` | Daftar tiket difilter untuk identifikasi |
| `GET` | `/tiket/kirim/` | Daftar tiket difilter untuk pengiriman |
| `GET` | `/backup-data/filter-options/` | Opsi filter untuk data cadangan |

---

## Endpoint Laporan & Ekspor

### Laporan

Setiap laporan mengikuti pola yang konsisten:

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/laporan-{nama}/` | Halaman laporan (HTML dengan formulir filter) |
| `GET` | `/laporan-{nama}/data/` | Data laporan (DataTables JSON) |
| `GET` | `/laporan-{nama}/export/` | Ekspor ke Excel (.xlsx) |

### Laporan yang Tersedia

| Laporan | Prefiks URL | Deskripsi |
|--------|-----------|-------------|
| Register Penerimaan Data | `/register-penerimaan-data/` | Register penerimaan data |
| Laporan Transfer | `/laporan-transfer/` | Laporan transfer |
| SLA Perekaman | `/laporan-sla-perekaman/` | Laporan SLA perekaman |
| SLA Identifikasi | `/laporan-sla-identifikasi/` | Laporan SLA identifikasi |
| Metrik Data Eksternal | `/laporan-metrik-data-eksternal/` | Metrik data eksternal |
| Pengendalian Mutu | `/laporan-pengendalian-mutu/` | Laporan pengendalian mutu |
| Hasil Pengolahan Data Prioritas | `/laporan-hasil-pengolahan-data-prioritas/` | Pengolahan data prioritas |
| Kelengkapan Data | `/laporan-kelengkapan-data/` | Laporan kelengkapan data |
| Rekap Himpun Olah Data | `/laporan-rekap-himpun-olah-data/` | Rekap himpun olah data |
| Detail Himpun Olah Data | `/laporan-detail-himpun-olah-data/` | Laporan detail himpun olah data |

### Laporan & Ekspor Lainnya

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/backup-data/export/excel/` | Ekspor data cadangan (Excel) |
| `GET` | `/backup-data/export/pdf/` | Ekspor data cadangan (PDF) |
| `GET` | `/laporan-pide/filter-options/` | Opsi filter laporan PIDE (AJAX) |

---

## Endpoint Generasi Dokumen

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `POST` | `/bulk-generate/pkdi-klarifikasi/` | Hasilkan massal surat PKDI/Klarifikasi |
| `POST` | `/bulk-generate/nd-pengantar-pide/` | Hasilkan massal ND Pengantar PIDE |
| `GET` | `/docx-template/<pk>/download/` | Unduh template DOCX tertentu |

### Jenis Dokumen yang Dihasilkan

1. **Tanda Terima** — Nasional/Internasional & Regional (with attachment)
2. **ND Pengantar PIDE** — Surat pengantar ke PIDE
3. **Surat Klarifikasi** — Surat klarifikasi
4. **Surat PKDI** — Pemberitahuan Data Tidak Lengkap (full/partial)
5. **Register Penerimaan Data** — Register penerimaan data

### Alur Generasi Dokumen

```
Pengguna mengklik "Generate" → Sistem memilih template berdasarkan:
  1. Tipe dokumen
  2. Tipe wilayah (Regional vs Nasional/Internasional) dari tiket
  3. Mengisi placeholder {{variable}} dengan data tiket
  4. Mengembalikan file DOCX yang telah dihasilkan untuk diunduh
```

---

## Endpoint Sinkronisasi Oracle

### Sinkronisasi Data Referensi

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/sync-data-referensi/` | Halaman sinkronisasi (HTML) |
| `POST` | `/sync-data-referensi/test/` | Uji koneksi Oracle |
| `POST` | `/sync-data-referensi/check/` | Periksa perubahan data (dry-run) |
| `POST` | `/sync-data-referensi/run/` | Jalankan sinkronisasi data penuh |
| `POST` | `/sync-data-referensi/stop/` | Hentikan sinkronisasi yang berjalan |
| `GET` | `/sync-data-referensi/stop-check/` | Periksa apakah penghentian diminta |
| `GET` | `/sync-data-referensi/progress/` | Ambil progres sinkronisasi (polling AJAX) |
| `POST` | `/sync-data-referensi/truncate/` | Kosongkan tabel yang disinkronkan |
| `GET` | `/sync-data-referensi/download-errors/<sync_id>/` | Unduh log kesalahan |
| `POST` | `/sync-data-referensi/clear-session/` | Hapus data sesi sinkronisasi |

### Sinkronisasi Tiket

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/sync-tiket/` | Halaman sinkronisasi tiket (HTML) |
| `POST` | `/sync-tiket/test/` | Uji koneksi Oracle |
| `POST` | `/sync-tiket/check/` | Periksa perubahan tiket (dry-run) |
| `POST` | `/sync-tiket/run/` | Jalankan sinkronisasi tiket |
| `POST` | `/sync-tiket/stop/` | Hentikan sinkronisasi yang berjalan |
| `GET` | `/sync-tiket/stop-check/` | Periksa apakah penghentian diminta |
| `GET` | `/sync-tiket/progress/` | Ambil progres sinkronisasi (polling AJAX) |
| `POST` | `/sync-tiket/truncate/` | Kosongkan tabel tiket yang disinkronkan |
| `GET` | `/sync-tiket/download-errors/<sync_id>/` | Unduh log kesalahan |

### Format Respons Progres Sinkronisasi

```json
{
    "current": 5,
    "total": 12,
    "percentage": 41,
    "table_name": "REF_ILAP",
    "inserts": 10,
    "updates": 3,
    "errors": 0
}
```

---

## Endpoint Notifikasi

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/notifications/` | Daftar notifikasi |
| `POST` | `/notifications/read/<pk>/` | Tandai satu notifikasi sebagai sudah dibaca |
| `POST` | `/notifications/read-all/` | Tandai semua notifikasi sebagai sudah dibaca |

---

## Endpoint Utilitas

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/dashboard/` | Dasbor PowerBI tertanam |
| `GET` | `/quality-control/` | Halaman pengendalian mutu |
| `GET` | `/quality-control/data/` | Data JSON DataTables pengendalian mutu |
| `GET` | `/profil-ilap/` | Daftar profil ILAP |
| `GET` | `/profil-ilap/<pk>/` | Detail profil ILAP |
| `GET` | `/monitoring-penyampaian-data/` | Pemantauan penyampaian data |
| `GET` | `/monitoring-penyampaian-data/data/` | Data JSON DataTables pemantauan |

### Admin Django

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET/POST` | `/admin/` | Antarmuka admin Django (hanya superuser) |

### Endpoint Khusus Pengembangan (DEBUG=True)

| Method | URL | Deskripsi |
|--------|-----|-------------|
| `GET` | `/schema/` | Diagram ERD interaktif (django-schema-graph) |

---

## Penanganan Error

### Kode Status HTTP

| Kode | Deskripsi |
|------|-------------|
| `200` | Berhasil |
| `302` | Redirect (memerlukan login, dll.) |
| `400` | Permintaan buruk (data formulir tidak valid) |
| `403` | Dilarang (izin ditolak) |
| `404` | Tidak ditemukan |
| `405` | Metode tidak diizinkan |
| `500` | Kesalahan server internal |

### Format Respons Error (JSON)

```json
{
    "error": "Error message description",
    "details": {}
}
```

### Perlindungan CSRF

Semua permintaan `POST` memerlukan token CSRF. Sertakan dalam formulir:

```html
{% csrf_token %}
```

Untuk permintaan AJAX POST, sertakan header CSRF:

```javascript
// Dari dokumen Django - ambil token CSRF dari cookie
const csrftoken = getCookie('csrftoken');

fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
});
```
