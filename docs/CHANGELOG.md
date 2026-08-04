# Catatan Rilis & Perubahan

## [1.2.1] — 2026-08-04

### Ditambahkan
- **Jatuh Tempo Permintaan Khusus** — Field baru `tgl_special_request` pada tiket untuk mencatat batas waktu permintaan khusus. Jatuh tempo **wajib diisi** selama penanda `special_request` aktif dan otomatis dikosongkan saat penanda dimatikan; aturan yang sama berlaku pada formulir Rekam Tiket maupun modal Special Request. Tanggal dipilih sebagai tanggal saja lalu disimpan pada pukul 23:59:59 (helper `end_of_day`) agar batas waktu tetap berlaku sepanjang hari tersebut. Kolom **Jatuh Tempo** ikut tampil pada daftar tiket dan pada kartu Special Request di dashboard.
- **Grafik Jml Progress per Jatuh Tempo (Quality Control)** — Grafik garis pada halaman Quality Control dengan satu garis per PIC PMDE, sumbu-X berupa sisa hari menuju jatuh tempo dan sumbu-Y berupa total Jml Progress. Warna dan pola garis ditetapkan di sisi server atas lingkup penuh sehingga seorang PIC selalu memakai garis yang sama pada filter apa pun; tiket tanpa PIC PMDE aktif memakai garis abu-abu terpisah. Grafik dan tabel dibaca dari parameter filter yang sama melalui endpoint `get_chart_data=1`.
- **Edit Tiket oleh Admin: Hasil Penelitian & Pengiriman ke PIDE** — Modal Edit Tiket kini menampilkan bagian khusus Admin P3DE untuk mengoreksi `tgl_teliti`, `baris_lengkap`, `baris_tidak_lengkap` (dengan `status_penelitian` dihitung ulang otomatis) serta `tgl_nadine`, `nomor_nd_nadine`, dan `tgl_kirim_pide`. Bagian tersebut hanya muncul untuk tahap yang sudah dilalui tiket, dan field-nya dikeluarkan dari form — bukan sekadar disembunyikan — sehingga tidak dapat dikirim lewat POST maupun ikut terkosongkan saat penyimpanan.
- **Pengujian Validasi End-to-End** — Skenario `rule_*` / `val_*` baru yang memverifikasi pesan galat milik masing-masing aturan, mencakup rantai kronologi tanggal penuh (`dip ≤ tanda terima ≤ teliti ≤ nadine ≤ kirim PIDE ≤ rekam PIDE ≤ transfer`), total baris/QC, jatuh tempo permintaan khusus, aturan kata sandi pada Profil, serta aturan form data master (rentang tanggal tumpang tindih, kunci ganda, batas tahun Sequence Tanda Terima, dan lingkup Tanda Terima). Ditambah pengujian unit untuk grafik Quality Control dan bagian khusus admin pada Edit Tiket.

### Diubah
- **Riwayat & Notifikasi Special Request** — Aksi `401/402` kini juga dicatat ketika hanya jatuh temponya yang berubah, dengan catatan otomatis yang menyebutkan tanggal jatuh tempo dan pesan toast yang membedakan perubahan penanda dari perubahan jatuh tempo.
- **Edit Tiket Tidak Pernah Memindahkan Status** — `status_tiket` dipastikan tidak berubah oleh aksi Edit Tiket; perpindahan status tetap hanya melalui aksi alur kerja masing-masing.
- **Perlindungan Pengosongan & Validasi Bersyarat pada Edit Tiket** — Isian yang sudah tersimpan tidak boleh dikosongkan (masih boleh dikoreksi), `baris_diterima` wajib sama dengan `baris_lengkap + baris_tidak_lengkap`, dan validasi kronologi hanya diperiksa untuk pasangan tanggal yang benar-benar diubah — agar tiket hasil migrasi (`old_db`) yang datanya sudah melanggar aturan tidak menghalangi koreksi field lain.
- **Refaktor Perhitungan Jatuh Tempo Quality Control** — Subquery durasi dan perhitungan tanggal deadline dipindahkan ke helper `_durasi_subquery()` dan `_deadline_day()` agar tabel dan grafik memakai satu sumber perhitungan yang sama.
- **Deadline & Jatuh Tempo Dihitung dari Tanggal Rematch** — Tiket yang sudah di-*rematch* memulai hitungannya kembali dari `tgl_rematch`; `tgl_transfer` hanya dipakai bila `tgl_rematch` kosong. Tanggal acuan ini berlaku seragam untuk pemilihan baris `DurasiJatuhTempo` yang aktif, kolom **Deadline** dan **Jatuh Tempo** pada tabel, pengurutan kolom tersebut, serta grafik Jml Progress per Jatuh Tempo.
- **Dokumentasi Alur Tiket** — `docs/status_tiket_flow.md` diperluas dengan tabel isian yang dapat diubah per peran, syarat tampil bagian khusus admin, aturan perlindungan pengosongan, dan ketentuan jatuh tempo permintaan khusus.

### Diperbaiki
- **Tanggal Terima Vertikal tidak ikut dinonaktifkan untuk ILAP non-Regional** — Sejak pemasangan datepicker global (flatpickr), field tanggal yang tampak di layar bukan lagi `<input type="date">` aslinya: flatpickr menyembunyikan input asli dan menaruh input teks terpisah di depannya, serta hanya menyalin `disabled`/`required` satu kali saat inisialisasi. Akibatnya, `disabled` yang diset saat ILAP berubah hanya mengenai input tersembunyi — hanya keterangan *"Tidak dapat diisi untuk kategori ILAP non-Regional"* yang muncul, sementara field tetap dapat diisi dan nilainya justru hilang diam-diam saat disimpan (kontrol `disabled` tidak ikut terkirim). Ditambahkan helper global `setDateInputState()` pada `base.html` yang menyelaraskan status kedua elemen sekaligus mengosongkan nilai melalui instance flatpickr; dipakai pada formulir **Rekam Tiket** dan modal **Edit Tiket**.

### Known Issues
- Pemetaan wilayah baru mencakup ILAP kategori `PV` (Pemda Provinsi) yang di-seed langsung ke Kanwil. Data KPP dan pemetaan ILAP kategori `PD` (Pemda Kabupaten/Kota) ke KPP masih perlu dilengkapi.
- Template dokumen (DOCX) belum sempurna — beberapa placeholder masih perlu penyesuaian.
- Flow sinkronisasi ke bankdata untuk tiket baru belum lengkap.

### Rencana
- Pengembangan halaman Dashboard dengan Power BI.
- Penyempurnaan template dokumen (Tanda Terima, ND Pengantar, Surat Klarifikasi, PKDI).
- Penyempurnaan flow sinkronisasi tiket new Diamond dari bankdata.
- Melengkapi data KPP dan pemetaan ILAP kategori `PD` ke KPP.

## [1.2.0] — 2026-07-28

### Ditambahkan
- **Edit Isian Tiket** — Aksi baru `Edit Tiket` (modal AJAX) bagi PIC P3DE aktif untuk memperbaiki isian tiket selama tiket masih berstatus *Direkam* dan belum memiliki tanda terima. Admin P3DE (`admin`, `admin_p3de`, superuser) dikecualikan dari pembatasan tersebut sehingga dapat mengoreksi tiket pada titik mana pun dalam alur kerja. Setiap perubahan dicatat pada riwayat aksi tiket sebagai *Isian Tiket Diubah* (`action = 10`).
- **Special Request pada Tiket** — Penanda `special_request` pada tiket yang dapat diaktifkan/dinonaktifkan melalui modal oleh PIC aktif pemilik tiket sesuai statusnya (P3DE untuk status 1–3, PIDE untuk 4–5, PMDE untuk 6). Perubahan nilai dicatat sebagai aksi *Special Request Diaktifkan/Dinonaktifkan* (`action = 401/402`), tersedia sebagai kolom & filter pada daftar tiket, serta ditonjolkan pada dashboard.
- **Pemetaan ILAP ke Kanwil (kategori PV)** — `ILAPKPP` kini dapat memetakan ILAP langsung ke Kanwil tanpa melalui KPP, ditentukan oleh flag `kpp`. ILAP kategori `PD` (Pemda Kabupaten/Kota) tetap memetakan ke KPP, sedangkan ILAP kategori `PV` (Pemda Provinsi) memetakan ke Kanwil. Disertai seed pemetaan ILAP–Kanwil dan properti bantu `ILAP.kanwil` / `ILAP.kanwil_list`.
- **Tanda Terima Berlingkup Kanwil & ND Pengantar** — Tanda terima kini dapat direkam per **Kanwil** (ILAP regional) atau per **ILAP** (nasional/internasional) melalui selektor *lingkup*, dengan opsi penyaringan tambahan berdasarkan **Nomor ND Pengantar**. Nomor tanda terima dialokasikan di sisi server saat penyimpanan sehingga aman terhadap perebutan nomor dan perpindahan tahun seri.
- **Profil Sub Jenis Data** — Halaman profil per sub jenis data (`/jenis-data-ilap/<id_sub_jenis_data>/`) berisi ringkasan periode dan capaian per tahun beserta daftar tiket terkait. Halaman Profil ILAP diperkaya dengan rekap sub jenis data dan tiket.
- **Pencarian Global di Navbar** — Kotak pencarian pada navbar dengan saran (*suggestions*) berperingkat untuk ILAP dan sub jenis data, serta pencocokan persis untuk kode ILAP, kode sub jenis data, dan nomor tiket. Hasil selalu dibatasi sesuai hak akses pengguna.
- **Grup Kasi (Supervisor)** — Tiga grup pengawas baru: `kasi_p3de`, `kasi_pide`, `kasi_pmde`. Kasi bukan admin, namun tidak dibatasi pada tiket tempat mereka menjadi PIC aktif sehingga dapat memantau seluruh tiket unitnya.
- **Dashboard Tugas Saya: Quick-Assign PIC & SLA Kustom** — Tombol penugasan cepat PIC P3DE/PIDE/PMDE langsung dari dashboard untuk tiket tanpa PIC, kolom **Nama Tabel I**, badge jumlah tugas real-time, toolbar terpadu, serta filter kelompok umur tiket berbasis SLA PIDE 30 hari kerja dan PMDE 85 hari kerja.
- **Sliding Session Middleware** — `SlidingSessionMiddleware` memperpanjang masa sesi pengguna yang aktif menjelajah tanpa menulis baris sesi pada setiap request (menghindari *lock contention* SQLite). Pengguna yang menganggur tetap keluar sesuai jadwal.
- **Ringkasan Tiket pada Formulir Backup Data** — Endpoint `GET /backup-data/tiket-info/<tiket_pk>/` yang mengisi ILAP, jenis data, periode, dan jumlah baris pada formulir Rekam Backup Data, dengan pembatasan akses setara daftar tiket.
- **Panduan Menu Admin** — Dokumen baru `docs/ADMIN_MENU_GUIDE.md` yang menjelaskan menu administratif P3DE, PIDE, dan PMDE; ikut ditampilkan pada halaman Dokumentasi.
- **Pengujian End-to-End (Playwright)** — Suite E2E pada direktori `e2e/` yang mencakup alur normal tiket, alur alternatif, validasi form, aksi tambahan tiket, dan CRUD data master, dilengkapi skrip penyiapan data uji dan *runner*.

### Diubah
- **Input Tanggal Alur Kerja Menjadi Tanggal Saja** — Field `tgl_teliti`, `tgl_nadine`, `tgl_kirim_pide`, `tgl_rekam_pide`, dan `tgl_transfer` beralih dari `datetime-local` ke pemilih tanggal, dengan jam diisi otomatis dari waktu server saat perekaman.
- **Perombakan Tampilan Detail Tiket & Modal Form** — Tata letak halaman detail tiket, modal konfirmasi, dan formulir alur kerja ditata ulang; daftar unduhan dokumen disajikan sebagai *list-group* dengan tombol *outline*, dan tombol *Tanda Terima* digabung menjadi **Tanda Terima & Lampiran**.
- **Filter Daftar Tiket** — Filter beralih ke Select2 *multi-select* dengan tombol **Reset**, ditambah filter *Special Request*.
- **Akses Daftar Tiket & Monitoring untuk Kasi** — `can_access_tiket_list` dan penyaringan pada daftar tiket, monitoring, serta backup data kini mengizinkan anggota grup kasi melihat seluruh tiket unitnya.
- **URL Profil ILAP** — Berubah dari `/profil-ilap/<pk>/` menjadi `/profil-ilap/<id_ilap>/` (mis. `/profil-ilap/BI001/`).
- **Helper Wilayah Terpusat** — Penyelesaian relasi ILAP/Tiket ke Kanwil dipindahkan ke `diamond_web/utils/wilayah.py` sehingga daftar tiket, monitoring, laporan, dan quality control memakai satu jalur relasi yang sama dan mendukung ILAP tanpa KPP.
- **Penyegaran Gaya Tabel, Tombol, & Aksesibilitas** — Penyeragaman gaya tabel dan tombol pada seluruh template daftar, halaman login, navbar, notifikasi, dan formulir PIC, termasuk perbaikan kontras warna judul modal.
- **Validasi & Tampilan Formulir Data Master** — Penyempurnaan validasi serta tampilan pada formulir Dasar Hukum, Durasi Jatuh Tempo, Jenis Prioritas Data, Periode Jenis Data, PIC, dan Profil pengguna.
- **Formulir & Daftar Backup Data** — Perombakan tampilan modal Rekam Backup Data agar selaras dengan gaya formulir lain, serta penyegaran daftar Backup Data.

### Diperbaiki
- Validasi sisi server pada penyelesaian tiket: `lolos_qc` + `tidak_lolos_qc` wajib sama dengan `baris_i`, sehingga selisih QC tidak lagi lolos tanpa pemeriksaan.
- Validasi kronologi tanggal: `tgl_teliti` tidak boleh mendahului tanggal tanda terima tiket (pemeriksaan terpisah karena tanda terima berada di tabel lain).
- Kebocoran informasi tiket pada endpoint ringkasan tiket di Backup Data — pengguna `user_p3de` sebelumnya dapat menelusuri id tiket secara berurutan dan membaca ILAP, jenis data, periode, serta jumlah baris tiket yang sengaja disembunyikan dari daftar tiketnya.
- Sesi berakhir di tengah pekerjaan meskipun pengguna aktif menjelajah, karena `SESSION_SAVE_EVERY_REQUEST=False` membuat masa berlaku sesi tidak pernah diperpanjang dan *keep-alive* sisi klien baru berjalan sepuluh menit setelah halaman dimuat.
- `AttributeError` pada helper `_merge_docx` akibat dekorator view yang tidak seharusnya melekat, yang membuat penggabungan dokumen gagal.
- Pemeriksaan izin pada aksi *Tidak Diterbitkan* mengembalikan status yang membuat *fetch* global mengalihkan pengguna ke halaman login.
- `formatDateTime` tak terdefinisi pada formulir rekam tiket, serta variabel yang dideklarasikan ganda pada validasi *submit*.
- Visibilitas dinamis status ketersediaan data dan alasan ketidaktersediaan pada formulir rekam tiket.
- Berbagai bug Select2: penanganan pilihan, pembungkusan/kliping daftar pilihan, ikon hapus, dan *z-index*.
- Peringatan aksesibilitas `aria-hidden` saat fokus berpindah ke tombol submit pada modal konfirmasi.
- Filter `has_group` tidak lagi galat ketika `user` bernilai `None`.
- *Dropdown* ILAP & Jenis Data pada formulir rekam tiket beserta *fallback* queryset ILAP dan pemeriksaan grup admin pada `TiketForm`.

### Known Issues
- Pemetaan wilayah baru mencakup ILAP kategori `PV` (Pemda Provinsi) yang di-seed langsung ke Kanwil. Data KPP dan pemetaan ILAP kategori `PD` (Pemda Kabupaten/Kota) ke KPP masih perlu dilengkapi.
- Template dokumen (DOCX) belum sempurna — beberapa placeholder masih perlu penyesuaian.
- Flow sinkronisasi ke bankdata untuk tiket baru belum lengkap.

### Rencana
- Pengembangan halaman Dashboard dengan Power BI.
- Penyempurnaan template dokumen (Tanda Terima, ND Pengantar, Surat Klarifikasi, PKDI).
- Penyempurnaan flow sinkronisasi tiket new Diamond dari bankdata.
- Melengkapi data KPP dan pemetaan ILAP kategori `PD` ke KPP.

## [1.1.1] — 2026-07-17

### Ditambahkan
- **Penyempurnaan Workflow Tiket P3DE (Backend)** — Kelanjutan pengembangan alur kerja backend untuk tiket P3DE dengan penanganan transisi status tambahan dan integrasi yang lebih baik.

### Diubah
- **Enhancement TiketForm & PeriodeJenisData** — Peningkatan tampilan *dropdown* dan validasi pada `TiketForm` dan model `PeriodeJenisData` untuk pengalaman pengguna yang lebih baik dan konsistensi data.

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
