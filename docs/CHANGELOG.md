# Catatan Rilis & Perubahan

## [1.1.0] — 2026-07-13

### Ditambahkan
- **Modul Laporan (Halaman UI)** — Halaman antarmuka untuk modul laporan baru yang mencakup tampilan daftar laporan, filter, dan opsi ekspor.
- **CRUD Widget & Filter Komponen** — Komponen widget filter interaktif untuk tabel CRUD yang memungkinkan pencarian dan penyaringan data secara dinamis.
- **Global Shell, Halaman Home, & Login** — Penyempurnaan tata letak shell global secara menyeluruh, halaman beranda (home) yang diperbarui, serta halaman login yang lebih responsif.
- **Workflow Tiket P3DE (Backend)** — Implementasi alur kerja backend untuk siklus tiket P3DE, mencakup validasi transisi status, logging aksi, dan penanganan dokumen terkait.
- **Sinkronisasi Tiket (Backend)** — Penyempurnaan mekanisme sinkronisasi tiket dari Oracle ke database lokal, termasuk penanganan data tiket baru dan pembaruan status secara otomatis.

### Diubah
- **Refaktor Modul Dokumen Tiket** — Perombakan struktur kode pada modul dokumen tiket untuk meningkatkan maintainability, mengurangi duplikasi, dan memisahkan concerns antara frontend dan backend.
- **Perubahan Model Database (RFC)** — Penyesuaian skema model database berdasarkan hasil *Request for Comments* (RFC) guna menyelaraskan struktur data dengan kebutuhan bisnis yang berkembang.

### Diperbaiki
- Stabilitas sinkronisasi tiket Oracle ditingkatkan untuk menangani kasus tepi (data duplikat, koneksi terputus, dan inkonsistensi status).
- Bug minor pada rendering dokumen tiket pasca-refaktor.

## [1.0.0] — 2026-07-01 — Rilis Produksi Awal

### Ditambahkan
- **Sistem Autentikasi & Otorisasi**
  - Login, logout, dan ubah kata sandi berbasis Django session
  - Manajemen sesi dengan timeout 30 menit
  - Mekanisme keep-alive untuk mencegah session timeout
  - Halaman notifikasi session expired
- **Role-Based Access Control (RBAC)**
  - Tiga grup pengguna: `user_p3de`, `user_pide`, `user_pmde`
  - Admin panel khusus superuser
  - Filter menu dan aksi berdasarkan grup pengguna
  - Template tag `has_group` untuk pengaturan UI dinamis
- **Workflow Tiket Data (8 Status)**
  - Rekam penerimaan data tiket baru
  - Rekam hasil penelitian data
  - Kirim tiket ke PIDE
  - Identifikasi data oleh PIDE
  - Transfer ke PMDE untuk pengendalian mutu
  - Selesaikan tiket (selesai/langsung selesai jika baris lengkap = 0)
  - Batalkan tiket (oleh P3DE atau PIDE)
  - Detail tiket dengan riwayat aksi lengkap
- **Manajemen Data Master (CRUD)**
  - ILAP
  - Kategori ILAP
  - Jenis Data ILAP (dengan sub-jenis data)
  - Kanwil (Kantor Wilayah)
  - KPP (Kantor Pelayanan Pajak)
  - Kategori Wilayah
  - PIC P3DE, PIC PIDE, PIC PMDE
  - Status Data, Status Penelitian
  - Bentuk Data, Cara Penyampaian
  - Dasar Hukum, Media Backup
  - Periode Pengiriman, Periode Jenis Data
  - Jenis Prioritas Data
  - Nama Tabel
  - Template DOCX
  - Klasifikasi Jenis Data
  - Durasi Jatuh Tempo PIDE & PMDE
  - DataTables server-side processing untuk semua data master
- **Sinkronisasi Data Oracle**
  - Sinkronisasi data referensi dari Oracle ke database lokal
  - Sinkronisasi tiket dari Oracle
  - Mode check (dry-run) untuk melihat perubahan sebelum sinkronisasi
  - Progress bar real-time via AJAX polling dengan Redis cache
  - Kemampuan stop/resume sinkronisasi
  - Download error log sinkronisasi
  - Test koneksi Oracle melalui UI
  - Management command CLI: `sync_oracle_data`
- **Generator Dokumen (DOCX)**
  - Generate dokumen dari template DOCX dengan placeholder variables
  - 11 template default yang dikontrol versi
  - Template kustom dapat diunggah melalui UI
  - Jenis dokumen: Tanda Terima, ND Pengantar PIDE, Surat Klarifikasi, Surat PKDI (semua/sebagian), Register Penerimaan
  - Bulk generate dokumen (PKDI/Klarifikasi dan ND Pengantar)
- **Sistem Pelaporan (12 Laporan)**
  - Register Penerimaan Data
  - Laporan Transfer
  - SLA Perekaman
  - SLA Identifikasi
  - Metrik Data Eksternal
  - Pengendalian Mutu
  - Hasil Pengolahan Data Prioritas
  - Kelengkapan Data
  - Rekap Himpun Olah Data
  - Detail Himpun Olah Data
  - Ekspor Excel (.xlsx) untuk semua laporan
  - Filter laporan berbasis form
- **Monitoring**
  - Monitoring penyampaian data
  - Halaman quality control
- **Backup Data**
  - Pencatatan backup data
- **Notifikasi**
  - Sistem notifikasi internal pengguna
  - Tandai sudah dibaca (single dan massal)
  - Context processor notifikasi di seluruh halaman
- **Sistem Template DOCX**
  - Template default di fixtures (version-controlled)
  - Upload template kustom via UI
  - Management command: `load_default_templates`
- **Antarmuka Pengguna**
  - Desain responsif dengan Bootstrap 5.3.3
  - Tabel interaktif dengan DataTables 2.3.6
  - Ikon dengan Remix Icon 4.6.0
  - Sidebar navigasi role-based
  - Halaman home role-based (dashboard berbeda tiap grup)
- **Task Queue (Celery)**
  - Background task untuk sinkronisasi Oracle
  - Konfigurasi Celery dengan Redis sebagai broker
- **Pengujian**
  - 40+ file test dengan pytest
  - Target coverage 80%+
  - Test untuk model, view, form, dan utility
- **Deployment & DevOps**
  - Konfigurasi Gunicorn untuk production
  - Systemd service untuk web app dan Celery worker
  - Nginx reverse proxy configuration
  - Database backup & restore (django-dbbackup)
  - Static files management (collectstatic)

### Known Issues
- Data Kanwil dan KPP belum tersedia dan belum di-mapping ke ILAP regional
- Template dokumen (DOCX) belum sempurna — beberapa placeholder masih perlu penyesuaian
- Flow sinkronisasi ke bankdata untuk tiket baru belum lengkap

### Rencana
- Melengkapi data Kanwil & KPP dan mapping ke ILAP regional
- Pengembangan halaman Dashboard dengan Power BI
- Pengembangan halaman Profil ILAP
- Penyempurnaan template dokumen (Tanda Terima, ND Pengantar, Surat Klarifikasi, PKDI)
- Penyempurnaan flow sinkronisasi tiket new Diamond dari bankdata
