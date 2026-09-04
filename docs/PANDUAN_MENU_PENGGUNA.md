# Panduan Menu Pengguna (P3DE, PIDE, PMDE)

> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE
> **Untuk:** Seluruh pengguna operasional — P3DE, PIDE, PMDE, dan Kasi (Kepala Seksi)

Dokumen ini menjelaskan seluruh menu yang dipakai sehari-hari oleh pengguna operasional Diamond: untuk apa menu itu, kriteria/data yang ditampilkan, kolom dan field yang ada, filter yang tersedia, serta aksi apa saja yang bisa dilakukan pengguna. Dokumen ini melengkapi tiga dokumen lain:

- **[Panduan Menu Admin](ADMIN_MENU_GUIDE.md)** — menu khusus role admin (`admin`, `admin_p3de`, `admin_pide`, `admin_pmde`): pengelolaan data referensi, PIC, template dokumen, dan sinkronisasi Oracle. Menu **PIC P3DE/PIDE/PMDE** dan referensi admin lainnya tidak diulang di dokumen ini — lihat panduan tersebut.
- **[Matriks RBAC & Hak Akses Menu](RBAC_MATRIX.md)** — tabel ringkas siapa boleh mengakses menu apa.
- **[Diagram Alur Status Tiket](status_tiket_flow.md)** — penjelasan lengkap & diagram alur kerja tiket dari Direkam sampai Selesai. Hampir semua menu di bawah berkaitan dengan satu tahap dalam alur ini, sehingga dokumen tersebut banyak dirujuk di bawah.

> **Catatan tentang hak akses di dokumen ini.** Setiap menu di bawah diverifikasi langsung dari kode aplikasi (pengecekan grup pada view-nya), bukan sekadar disalin dari `RBAC_MATRIX.md` atau dari penempatan tautan di navbar. Penelusuran ini menemukan beberapa menu yang aturan aksesnya tidak sesuai dengan penempatan tautannya di navbar; yang bisa diselaraskan dengan memperluas akses (Laporan Rekap & Detail Himpun Olah Data, kini juga terbuka untuk P3DE) sudah diperbaiki, dan `RBAC_MATRIX.md` sudah diperbarui mengikuti perbaikan tersebut. Satu kejanggalan masih dibiarkan apa adanya secara sengaja: pada **Monitoring**, **Kelola Tanda Terima**, dan **Kelola Backup Data**, pengguna `admin_p3de` murni dapat membuka halamannya tapi tabel/filternya gagal dimuat karena endpoint datanya lebih ketat daripada halaman itu sendiri — dicatat pada menu masing-masing.

---

## Daftar Isi

- [Ringkasan Alur Kerja Tiket](#ringkasan-alur-kerja-tiket)
- [Menu Umum (Semua Pengguna)](#menu-umum-semua-pengguna)
  - [Home ("Tugas Saya")](#home-tugas-saya)
  - [Dashboard](#dashboard)
  - [Daftar Tiket](#daftar-tiket)
  - [Detail Tiket](#detail-tiket)
  - [Profil ILAP](#profil-ilap)
  - [Profil PIC](#profil-pic)
  - [Notifikasi](#notifikasi)
  - [Profil Saya (Akun)](#profil-saya-akun)
  - [Pencarian Navbar](#pencarian-navbar)
- [Menu P3DE](#menu-p3de)
  - [Monitoring](#monitoring)
  - [Rekam Penerimaan Data](#rekam-penerimaan-data)
  - [Kelola Tanda Terima](#kelola-tanda-terima)
  - [Register Penerimaan Data](#register-penerimaan-data)
  - [Kelola Backup Data](#kelola-backup-data)
  - [Kirim Tiket ke PIDE](#kirim-tiket-ke-pide)
  - [Generate PKDI/Klarifikasi (Bulk)](#generate-pkdiklarifikasi-bulk)
  - [Laporan Rekap Himpun Olah Data](#laporan-rekap-himpun-olah-data)
  - [Laporan Detail Penghimpunan dan Pengolahan Data](#laporan-detail-penghimpunan-dan-pengolahan-data)
- [Menu PIDE](#menu-pide)
  - [Identifikasi](#identifikasi)
  - [Laporan SLA Perekaman](#laporan-sla-perekaman)
  - [Laporan SLA Identifikasi](#laporan-sla-identifikasi)
  - [Laporan Transfer](#laporan-transfer)
  - [Laporan Metrik Data Eksternal](#laporan-metrik-data-eksternal)
- [Menu PMDE](#menu-pmde)
  - [Quality Control](#quality-control)
  - [Laporan Pengendalian Mutu](#laporan-pengendalian-mutu)
  - [Laporan Kelengkapan Data](#laporan-kelengkapan-data)
  - [Laporan Hasil Pengolahan Data Prioritas](#laporan-hasil-pengolahan-data-prioritas)
- [Lihat Juga](#lihat-juga)

---

## Ringkasan Alur Kerja Tiket

Sebagian besar menu pada dokumen ini berhubungan dengan satu (atau beberapa) tahap dalam alur kerja tiket berikut. Untuk detail lengkap tiap tahap — field yang direkam, validasi, dan efek sampingnya — lihat **[Diagram Alur Status Tiket](status_tiket_flow.md)**.

```
Direkam (1) → Diteliti (2) → Dikirim ke PIDE (4) → Identifikasi (5) → Pengendalian Mutu (6) → Selesai (8)
```

*(Data yang ternyata tidak tersedia sama sekali melompat langsung dari Direkam ke Selesai; Dibatalkan (7) dapat terjadi dari beberapa titik — lihat diagram lengkapnya.)*

| Status | Penanggung Jawab | Menu tempat aksinya dijalankan |
|---|---|---|
| 1. Direkam | P3DE | **Rekam Penerimaan Data** (Menu P3DE) |
| 2. Diteliti | P3DE | Rekam Hasil Penelitian — modal di **Detail Tiket** |
| 4. Dikirim ke PIDE | P3DE → PIDE | **Kirim Tiket ke PIDE** (Menu P3DE) |
| 5. Identifikasi | PIDE | Proses Identifikasi / Transfer ke PMDE — modal di **Detail Tiket**; antreannya terlihat di **Identifikasi** (Menu PIDE) |
| 6. Pengendalian Mutu | PMDE | Selesaikan Tiket — modal di **Detail Tiket**; antreannya terlihat di **Quality Control** (Menu PMDE) |
| 7. Dibatalkan | P3DE / PIDE | Batalkan Tiket / Kembalikan ke P3DE — modal di **Detail Tiket** |
| 8. Selesai | PMDE / P3DE | Tahap akhir — tercapai dari Selesaikan Tiket, atau langsung dari Rekam Penerimaan Data bila data tidak tersedia |

Setiap tiket dapat dilihat dari dua sudut pandang yang saling melengkapi: **[Home](#home-tugas-saya)** mengelompokkannya menurut apa yang harus dikerjakan pengguna saat ini, sedangkan **[Daftar Tiket](#daftar-tiket)** menampilkannya sebagai satu tabel besar yang bisa difilter bebas lintas status/divisi.

---

## Menu Umum (Semua Pengguna)


Menu-menu berikut tampil untuk **semua pengguna yang sudah login**, apa pun rolenya (P3DE, PIDE, PMDE, kasi, maupun admin) — berbeda dengan menu per-divisi yang hanya tampil sesuai keanggotaan grup.

### Home ("Tugas Saya")

**URL:** `/` (nama url `home`) — halaman pertama yang tampil setelah login.

Home adalah dashboard kerja pribadi. Judul di halaman ini adalah **"Tugas Saya"**: bukan katalog atau laporan, melainkan daftar tiket yang **menunggu tindakan** dari pengguna yang sedang login, dikelompokkan menjadi kategori-kategori sesuai divisi (P3DE/PIDE/PMDE) tempat ia terdaftar. Seseorang yang merangkap PIC di lebih dari satu divisi akan melihat blok-blok tersebut sekaligus, ditumpuk berurutan.

Sidebar kiri berisi daftar kategori (dengan badge jumlah tiket di tiap kategori); mengklik satu kategori menampilkan tabelnya di area kanan. Kategori dengan angka 0 (kosong) tetap muncul di sidebar tapi tanpa badge.

**Cakupan data per kategori** — sama seperti aturan di seluruh aplikasi: pengguna biasa (pelaksana) hanya melihat tiket yang menjadi tanggung jawabnya sendiri (PIC aktif untuk peran terkait), sedangkan **kasi** (`kasi_p3de`/`kasi_pide`/`kasi_pmde`) melihat seluruh tiket unitnya tanpa perlu jadi PIC — karena kasi mengawasi antrean satu seksi secara keseluruhan, bukan hanya pekerjaannya sendiri.

#### Kategori untuk PIC P3DE (`user_p3de` / `kasi_p3de`)

| Kategori (label sidebar) | Kriteria tiket yang ditampilkan | Aksi cepat dari baris tabel |
|---|---|---|
| **Belum Rekam Backup Data** | Status **Direkam** DAN belum ada data backup tercatat untuk tiket tsb. | Tombol "Rekam Backup Data" (modal langsung dari baris, tanpa pindah halaman) |
| **Belum Dibuat Tanda Terima** | Status **Direkam** DAN tanda terima belum dibuat. | Tombol "Buat Tanda Terima" (modal) |
| **Belum Diteliti** | Status **Direkam**, DAN backup data sudah ada, DAN tanda terima sudah ada — artinya kedua prasyarat sudah lengkap tapi hasil penelitian belum direkam. | Tombol "Rekam Hasil Penelitian" (modal) |
| **Belum Dikirim ke PIDE** | Status **Diteliti** DAN jumlah baris lengkap lebih dari 0. (Tiket Diteliti dengan baris lengkap = 0 tidak pernah muncul di sini karena otomatis berstatus **Selesai** — lihat [Diagram Alur Status Tiket](status_tiket_flow.md).) | — |
| **Pengembalian Seluruhnya dari PIDE** | Tiket yang **pernah** punya riwayat aksi "Dikembalikan" oleh PIDE (dicek dari riwayat aksi, bukan status saat ini — jadi tetap muncul walau tiket sudah diproses ulang). | — |
| **Pengembalian Sebagian dari PIDE** | Ada baris berstatus **CDE** (bermasalah) tapi jumlahnya belum sama dengan total baris lengkap — artinya sebagian data bermasalah, bukan keseluruhan tiket. | — |
| **Monitor Klarifikasi** | Kombinasi kriteria: tiket ini adalah **pengiriman/penyampaian terbaru** dibanding seluruh riwayat pengiriman lain untuk kombinasi jenis data + periode + tahun yang sama, statusnya sudah melewati Diteliti (sedang berjalan di PIDE/PMDE atau sudah selesai), **dan** (status penelitiannya bukan "Lengkap" **atau** masih ada baris CDE). Singkatnya: kiriman ulang/klarifikasi data yang datanya belum sepenuhnya bersih dan masih perlu dipantau. | — |
| **Permintaan Khusus** | Tiket bertanda **Special Request** aktif, dibatasi ke tiket yang PIC-nya adalah pengguna ybs (kasi melihat semua). Sama persis dengan kategori "Permintaan Khusus" di blok PIDE/PMDE di bawah — hanya ditampilkan sekali sesuai divisi pertama yang dimiliki pengguna agar tidak dobel bagi yang merangkap peran. | — |

Khusus **Admin P3DE** (`admin_p3de`), sidebar menambahkan blok kedua:

| Kategori | Kriteria |
|---|---|
| **Jenis Data Tidak Punya PIC Aktif** | Bukan daftar tiket, melainkan daftar **Jenis Data ILAP** yang sama sekali tidak memiliki PIC P3DE aktif (End Date kosong) — alat bantu admin menemukan data "yatim" yang belum ada penanggung jawabnya. |
| **Periode Tiket Null** | Tiket dengan tahun = **2099**, nilai penanda (sentinel) untuk data bermasalah/periode tidak valid, umumnya peninggalan migrasi data lama. |

#### Kategori untuk PIC PIDE (`user_pide` / `kasi_pide`)

| Kategori | Kriteria | Urgensi |
|---|---|---|
| **Belum Mulai Proses Identifikasi** | Status **Dikirim ke PIDE**. | Dihitung dari tanggal kirim ke PIDE: **Baru** jika < 42 hari kalender (≈30 hari kerja), **Perlu Segera** jika ≥ 42 hari (SLA identifikasi terlewati). Tidak ada tingkat "Perlu Perhatian" di kategori ini (berbeda dari kategori P3DE). |
| **Dalam Proses Identifikasi** | Status **Identifikasi**. | Sama ambang 42 hari, dihitung dari tanggal rekam PIDE (atau tanggal kirim ke PIDE bila tanggal rekam belum terisi). |
| **Permintaan Khusus** | Sama seperti P3DE, discope ke PIC PIDE aktif. Hanya tampil sebagai blok tersendiri bila pengguna **bukan** juga anggota P3DE (untuk menghindari duplikasi). | — |

Khusus **Admin PIDE** (`admin_pide`):

| Kategori | Kriteria |
|---|---|
| **Jenis Data Tidak Punya PIC Aktif** | Jenis Data ILAP tanpa PIC PIDE aktif. |
| **Tiket Status Dikirim Ke PIDE Belum Punya PIC** | Tiket berstatus Dikirim ke PIDE tapi belum ada PIC PIDE aktif yang ditugaskan. Baris pada tabel ini punya tombol pintas **"Assign PIC PIDE"** (modal, memilih pengguna dari grup `user_pide`) sehingga admin bisa langsung menugaskan tanpa membuka menu PIC PIDE terpisah. |

#### Kategori untuk PIC PMDE (`user_pmde` / `kasi_pmde`)

| Kategori | Kriteria | Catatan |
|---|---|---|
| **Dalam Proses Pengendalian Mutu** | Status **Pengendalian Mutu**. | Filter urgensinya **berbeda pola**: bukan "usia sejak diterima" seperti P3DE/PIDE, melainkan **jatuh tempo** (sisa hari menuju tenggat QC), dengan dua ambang: kurang dari 10 hari lagi, dan kurang dari 30 hari lagi. Perhitungan jatuh tempo memakai fungsi yang sama dengan menu Quality Control (lihat Menu PMDE), sehingga kedua halaman selalu sepakat soal kapan sebuah tiket jatuh tempo. |
| **Masih di P3DE & PIDE** | Tiket yang **belum** menjadi tanggung jawab PMDE saat ini (statusnya masih Direkam/Diteliti/Dikirim ke PIDE/Identifikasi) tapi **sudah** termasuk cakupan PIC PMDE — karena PIC PMDE ditugaskan sejak tiket direkam, bukan baru saat ditransfer ke PMDE. Kategori ini berfungsi sebagai "radar" beban kerja yang akan datang. Tabelnya punya filter tombol P3DE/PIDE untuk melihat unit mana yang sedang memegang tiket tsb. | — |
| **Permintaan Khusus** | Sama pola seperti di atas, discope ke PIC PMDE aktif; hanya tampil sebagai blok tersendiri bila pengguna bukan juga anggota P3DE maupun PIDE. | — |

Khusus **Admin PMDE** (`admin_pmde`):

| Kategori | Kriteria |
|---|---|
| **Jenis Data Tidak Punya PIC Aktif** | Jenis Data ILAP tanpa PIC PMDE aktif. |
| **Tiket Status Pengendalian Mutu Belum Punya PIC** | Tiket berstatus Pengendalian Mutu tapi belum ada PIC PMDE aktif. Tombol pintas **"Assign PIC PMDE"**, sama pola dengan PIDE di atas. |

#### Elemen yang sama di setiap tabel kategori

- **Toolbar ringkasan**: tiga angka di kiri atas tabel — jumlah **Tiket**, jumlah **ILAP** unik, dan jumlah **Jenis Data** unik dalam kategori tsb (dihitung dari hasil filter yang sedang aktif).
- **Filter urgensi** (tombol berlabel "Semua / Baru / Perlu Perhatian / Perlu Segera" atau "Semua / <10 hari / <30 hari" tergantung kategori) — lihat kolom "Urgensi/Catatan" pada tabel-tabel di atas untuk ambang tiap kategori.
- **Kolom tabel** bervariasi per kategori, tapi umumnya memuat: Nomor Tiket, Nama ILAP, Jenis Data, jumlah baris terkait tahap tsb, tanggal acuan (tanggal terima DIP / tanggal kirim PIDE / tanggal transfer, sesuai kategori), penanda **Prioritas** (bila tiket memakai jenis data yang ditandai prioritas), dan kolom **Aksi**.
- **Pencarian & filter tambahan**: kotak pencarian bebas (nomor tiket/ILAP/jenis data), sakelar **"Hanya Prioritas"**, dan sakelar **"Hanya yang Dipantau"**.
- **Fitur Bintang (Pantauan/Watchlist)**: pengguna dapat menandai bintang pada tiket tertentu — lepas dari kategori atau status apa pun — agar mudah ditemukan lagi lewat sakelar "Hanya yang Dipantau" di atas. Ini murni preferensi pribadi per pengguna, tidak memengaruhi tiket itu sendiri.
- Tombol **"Lihat"** selalu tersedia dan membuka [Detail Tiket](#detail-tiket) di tab baru. Beberapa kategori (Belum Rekam Backup Data, Belum Dibuat Tanda Terima, Belum Diteliti, Belum Mulai Proses Identifikasi, serta kedua kategori admin "belum punya PIC") menambahkan tombol pintas yang langsung membuka modal aksi terkait tanpa perlu berpindah ke halaman detail.

### Dashboard

**URL:** `/dashboard/` (nama url `dashboard_monitoring`).

Halaman ini menampilkan laporan **Power BI** ("DDE - Monitoring Tiket") yang disisipkan (embed) lewat iframe — sajian analitik/visualisasi data tiket lintas divisi dari sistem pelaporan Power BI. Semua logika filter, drill-down, dan visualisasi ada **di dalam laporan Power BI itu sendiri**; aplikasi Diamond hanya menampilkannya, tanpa memproses data tambahan. Dapat diakses siapa pun yang sudah login, tanpa batasan role.

> **Catatan penamaan:** jangan tertukar dengan menu **Home** (`/`, di atas). `RBAC_MATRIX.md` mencantumkan baris "Dashboard" pada path `/` — itu sebenarnya merujuk ke halaman Home/Tugas Saya, bukan menu Dashboard Power BI ini.

### Daftar Tiket

**URL:** `/tiket/` (nama url `tiket_list`).

Tabel utama berisi seluruh tiket yang boleh dilihat pengguna, dengan puluhan kombinasi filter untuk penelusuran. Kegunaannya berbeda dari Home: Home mengelompokkan tiket menurut **apa yang harus dikerjakan**, sedangkan Daftar Tiket cocok dipakai ketika pengguna sudah tahu **apa yang dicari** (nomor tiket tertentu, ILAP tertentu, dsb.) atau ingin menelusuri/menganalisis lintas kategori dan lintas status sekaligus.

**Siapa yang boleh membuka menu ini:** admin/superuser, seluruh kasi, anggota `user_p3de`/`user_pide`/`user_pmde`, atau siapa pun yang minimal punya satu penugasan PIC pada tiket manapun.

**Cakupan data (baris yang tampil):**
- Superuser, anggota grup admin (global maupun per-divisi), dan seluruh kasi (`kasi_p3de`/`kasi_pide`/`kasi_pmde`) melihat **semua** tiket.
- Pengguna lain hanya melihat tiket yang padanya ia tercatat sebagai PIC — aktif **maupun** tidak aktif (pernah ditugaskan sudah cukup untuk tetap terlihat, sebagai jejak histori).

**Kolom tabel:** Nomor Tiket, Kode & Nama ILAP, Kode & Nama Sub Jenis Data, Periode (diformat otomatis sesuai tipenya: bulanan/triwulanan/semesteran/tahunan), Status Tiket, Status Ketersediaan Data (Ya/Tidak), Special Request (Ya/Tidak), Baris Diterima, Baris Lengkap, Tanggal Special Request, dan Aksi. Tidak ada tombol Edit/Hapus di baris tabel ini — perubahan data tiket hanya dilakukan dari halaman [Detail Tiket](#detail-tiket).

**Filter yang tersedia** (semuanya *cascading* — memilih satu filter otomatis mempersempit pilihan pada filter lain, dan mendukung pilih lebih dari satu nilai sekaligus):

Nomor Tiket, Nomor ND Nadine, Tahun, Periode (bulanan/triwulanan/semester/tahunan), Periode Penerimaan, **PIC P3DE**, **PIC PIDE**, **PIC PMDE** (tiga filter terpisah, masing-masing hanya menampilkan pengguna yang PIC aktif untuk peran tsb), Kategori ILAP, ILAP, Jenis Data, Sub Jenis Data, Kanwil, KPP, Kategori Wilayah, Jenis Tabel, Dasar Hukum, Periode Pengiriman, Status Tiket, Status Penelitian, Status Ketersediaan Data, dan Special Request.

### Detail Tiket

**URL:** `/tiket/<id>/` (nama url `tiket_detail`) — dibuka dari tombol "Lihat" di Daftar Tiket, Home, atau menu manapun yang menampilkan daftar tiket.

Halaman ini adalah pusat kendali satu tiket: seluruh informasi, riwayat, dan tombol aksi alur kerja berkumpul di sini. Untuk penjelasan lengkap tiap aksi (kapan tersedia, apa yang berubah di baliknya, dan validasinya), lihat **[Diagram Alur Status Tiket](status_tiket_flow.md)** — bagian ini merangkum apa yang tampil di halamannya.

**Syarat membuka halaman:**
- Superuser, anggota grup `admin`, **Admin P3DE** (`admin`/`admin_p3de`/superuser), dan seluruh kasi selalu boleh membuka tiket apa pun. Bagi kasi ini bersifat lihat-saja — tombol aksi tetap mengikuti aturan PIC aktif di bawah, kasi tidak otomatis bisa menjalankan aksinya.
- Pengguna lain wajib pernah/sedang tercatat sebagai PIC (`TiketPIC`) pada tiket tsb — aktif ataupun tidak aktif — kalau tidak, akses ditolak.

**Informasi yang ditampilkan:**
- Ringkasan ILAP & jenis data: nama ILAP, kategori ILAP, kategori wilayah, kode & nama sub jenis data, nama tabel I, jenis tabel, deskripsi & tipe periode, penanda prioritas, daftar dasar hukum/klasifikasi.
- Seluruh isian tiket (tanggal terima, bentuk & cara penyampaian, jumlah baris di tiap tahap — diterima/lengkap/tidak lengkap/I/U/Res/CDE/sudah-belum QC/lolos-tidak lolos QC — serta tanggal-tanggal alur kerja). Field yang nilainya kosong atau nol disembunyikan agar tampilan tidak dipenuhi angka nol yang tidak relevan pada tahap tsb.
- Badge status tiket saat ini, dan penanda **Data Migrasi** bila tiket berasal dari migrasi database lama (`old_db`) — beberapa aturan validasi memang lebih longgar untuk tiket semacam ini karena datanya tidak selalu lengkap.
- **Daftar PIC** tiket ini (P3DE/PIDE/PMDE) beserta status aktif/tidak aktifnya masing-masing.
- **Riwayat Aksi** (audit trail) — daftar kronologis setiap aksi yang pernah terjadi pada tiket ini, lengkap dengan pelaku dan waktunya. Jenis aksi yang mungkin tercatat: Direkam, Diteliti, Dikembalikan, Dikirim ke PIDE, Identifikasi, Pengendalian Mutu, Dibatalkan, Selesai, Ditransfer ke PMDE, Isian Tiket Diubah, Special Request Diaktifkan/Dinonaktifkan.
- **Daftar Backup Data** yang sudah direkam untuk tiket ini.
- **Daftar Tanda Terima** yang mencantumkan tiket ini.
- **Riwayat Tiket** — daftar tiket *lain* dengan sub jenis data + periode + tahun yang **sama** (biasanya versi pengiriman/klarifikasi sebelumnya untuk data yang sama), diurutkan dari yang pertama diterima. Inilah dasar dari kategori "Monitor Klarifikasi" pada Home.
- Tautan unduh dokumen **ND Pengantar PIDE**, bila sudah pernah digenerate untuk tiket ini.

**Tombol aksi** — kemunculannya bergantung status tiket saat ini *dan* apakah pengguna adalah PIC aktif untuk peran yang berwenang di status tsb:

| Aksi | Muncul pada status | Yang berwenang |
|---|---|---|
| Edit Tiket | **Direkam**, dan tanda terima belum terbit (Admin P3DE: status apa pun) | PIC P3DE aktif, atau Admin P3DE tanpa syarat status |
| Rekam Hasil Penelitian | **Direkam** | PIC P3DE aktif |
| Batalkan Tiket | **Direkam** atau **Diteliti** | PIC P3DE aktif |
| Generate ND Pengantar / Kirim ke PIDE | **Diteliti** (dengan syarat tanda terima & baris lengkap, lihat Menu P3DE → Kirim Tiket ke PIDE) | PIC P3DE aktif |
| Proses Identifikasi | **Dikirim ke PIDE** | PIC PIDE aktif |
| Kembalikan ke P3DE | **Dikirim ke PIDE** atau **Identifikasi** | PIC PIDE aktif |
| Transfer ke PMDE | **Identifikasi** | PIC PIDE aktif |
| Selesaikan Tiket (Quality Control) | **Pengendalian Mutu** | PIC PMDE aktif |
| Special Request (aktifkan/nonaktifkan) | Status 1–6 (bukan Dibatalkan/Selesai) | PIC aktif dari divisi yang sedang memegang tiket sesuai statusnya (P3DE utk status 1–3, PIDE utk 4–5, PMDE utk 6) |

### Profil ILAP

**URL:** `/profil-ilap/` (daftar, nama url `profil_ilap_list`) · `/profil-ilap/<id_ilap>/` (detail, nama url `profil_ilap_detail`) · `/jenis-data-ilap/<id_sub_jenis_data>/` (profil sub jenis data, nama url `jenis_data_ilap_profil`).

Ini adalah **katalog** data yang diterima DJP dari seluruh ILAP — bukan daftar tiket per pengguna, melainkan rujukan "instansi apa mengirim data apa, dan siapa yang menanganinya". Terbuka untuk **semua** pengguna yang sudah login, apa pun rolenya (bukan cuma P3DE) — karena siapa pun mungkin perlu tahu jenis data apa yang tersedia dan siapa PIC-nya.

**Halaman daftar** berisi tiga bagian:
1. **Direktori Profil PDE** — daftar staf aktif di tiga seksi (P3DE/PIDE/PMDE), sebagai pintu masuk ke [Profil PIC](#profil-pic) tiap orang. Akun superuser tidak dihitung sebagai staf seksi mana pun (meski tercatat di ketiga grup sekaligus agar bisa bertindak di mana saja), dan akun nonaktif disembunyikan dari direktori ini (riwayat tiketnya tetap bisa ditelusuri lewat tautan dari tiket yang pernah ia tangani).
2. **Ringkasan ILAP** — tabel silang **Kategori ILAP × Kategori Wilayah** berisi jumlah ILAP pada tiap kombinasi; setiap sel dapat diklik untuk langsung memfilter tabel katalog di bawahnya ke kombinasi tsb.
3. **Tabel katalog ILAP** — daftar seluruh ILAP dengan kolom Kode ILAP, Kategori, Nama ILAP, Wilayah, dan tombol Detail. Mendukung pencarian & filter per kolom.

**Halaman detail ILAP** menampilkan profil satu instansi (kategori, wilayah) beserta **matriks tahunan** seluruh sub jenis data milik ILAP tsb — tiap sel matriks menunjukkan `jumlah tiket diterima / jumlah periode yang seharusnya` pada tahun itu (misalnya `7/12` untuk data bulanan yang baru diterima 7 dari 12 bulan), sehingga terlihat langsung tahun/periode mana yang datanya belum lengkap. Blok **Informasi PIC & Kontak** (nama, jabatan, email, telepon PIC instansi, faksimile, tujuan surat, tembusan) hanya tampil untuk pengguna tertentu — lihat catatan akses di bawah.

**Halaman profil Sub Jenis Data** (dibuka dari matriks di atas atau dari [pencarian navbar](#pencarian-navbar)) merinci satu jenis data: dasar hukum, daftar periode yang berlaku, matriks tahunan yang sama (untuk satu jenis data ini saja), daftar PIC (dikelompokkan P3DE/PIDE/PMDE), dan daftar seluruh tiket yang pernah tercatat untuk jenis data ini.

**Akses blok "Informasi PIC & Kontak"** (bukan akses ke halamannya — itu terbuka untuk semua pengguna login):
- Superuser, `admin`, `admin_p3de`, dan `kasi_p3de` selalu melihatnya, untuk ILAP mana pun.
- Pengguna lain (termasuk `kasi_pide`/`kasi_pmde`) hanya melihatnya bila ia adalah PIC aktif — tipe P3DE, PIDE, atau PMDE, yang mana saja — pada minimal satu jenis data milik ILAP tersebut.

### Profil PIC

**URL:** `/profil-pic/<username>/` (nama url `profil_pic_detail`) — dibuka dari nama pengguna mana pun yang tercantum di aplikasi (Riwayat Aksi tiket, daftar PIC, Direktori Profil PDE, hasil [pencarian navbar](#pencarian-navbar)), termasuk tautan **"Profil PIC Saya"** pada menu akun sendiri.

Kebalikan dari Profil ILAP: bila Profil ILAP membaca "dari data ke orang", Profil PIC membaca "dari orang ke data" — menunjukkan semua ILAP, jenis data, tabel bank data, dan tiket yang menjadi tanggung jawab satu orang. Berguna saat menemukan nama PIC yang tidak dikenal di suatu tiket dan ingin tahu apa lagi yang ia tangani, tanpa perlu bertanya langsung.

**Berisi:**
- Identitas & seksi (P3DE/PIDE/PMDE) orang tersebut.
- Ringkasan **ILAP** yang ditangani (dikelompokkan per ILAP, ditandai aktif/tidak aktif), dipecah lagi menurut kategori wilayah (Nasional/Regional/Internasional/lainnya).
- Ringkasan **Sub Jenis Data** yang ditangani.
- Ringkasan **Nama Tabel** (tabel bank data) yang datanya bersumber dari jenis data yang ia tangani, dipecah aktif/tidak aktif — sebuah tabel dianggap "aktif" bila ada tiket apa pun (dari siapa pun, bukan cuma dari orang ini) yang masuk ke tabel itu dalam **2 tahun terakhir**.
- Ringkasan **status tiket** — jumlah tiket per status, dari seluruh tiket yang pernah ia pegang sebagai PIC.
- Tabel seluruh **penugasan tiket**-nya — satu baris per penugasan PIC, bukan per tiket, sehingga bila seseorang pernah menjadi PIC dua kali atas tiket yang sama (misalnya menerima kembali setelah serah terima), atau memegang dua peran berbeda atas satu tiket, baris-nya tetap tercatat terpisah.

**Akses:** halaman ini **terbatas** — tidak seperti Profil ILAP yang terbuka untuk semua. Hanya dapat dibuka oleh:
- Diri sendiri (siapa pun boleh membuka profilnya sendiri).
- Kasi atau admin dari divisi yang sama dengan orang tsb (mis. `kasi_p3de`/`admin_p3de` dapat membuka profil siapa pun di grup `user_p3de`).
- Superuser dan anggota grup `admin` global (dapat membuka siapa saja).

Pengguna dari divisi lain tanpa relasi pengawasan di atas akan ditolak aksesnya. Aturan yang sama juga menentukan apakah nama seseorang tampil sebagai **tautan** (bisa diklik) atau sekadar teks biasa di halaman lain (Riwayat Aksi, daftar PIC, dsb.) — nama yang profilnya tidak boleh dibuka pembaca akan ditampilkan sebagai teks polos.

### Notifikasi

**URL:** `/notifications/` (nama url `notification_list`), dibuka dari ikon lonceng di header.

Daftar notifikasi sistem untuk pengguna yang sedang login, terurut dari yang terbaru, dengan paginasi 15 per halaman. Notifikasi dikirim otomatis oleh sistem pada momen-momen tertentu dalam alur kerja tiket — misalnya PIC PIDE aktif diberi tahu saat sebuah tiket dikirim ke PIDE, PIC PMDE aktif diberi tahu saat tiket ditransfer ke PMDE, dan PIC P3DE aktif diberi tahu saat tiketnya dikembalikan oleh PIDE (lihat **[Diagram Alur Status Tiket](status_tiket_flow.md)** untuk pemicu masing-masing).

Ikon lonceng di header menampilkan **badge jumlah notifikasi belum dibaca**, dengan dropdown ringkas berisi notifikasi terbaru. Mengklik satu notifikasi (dari dropdown maupun halaman penuh) menandainya sudah dibaca dan mengarahkan kembali ke halaman terkait. Tersedia juga tombol **"Tandai Semua Dibaca"**.

### Profil Saya (Akun)

**URL:** `/profil/` (nama url `user_profil`), dibuka dari menu dropdown akun di kanan atas header → **"Profil"**.

Halaman untuk mengubah data akun sendiri: nama depan, nama belakang, dan (opsional) kata sandi — semuanya dalam satu form. Mengganti kata sandi **tidak** memaksa keluar dari sesi yang sedang berjalan. Berbeda dengan **"Profil PIC Saya"** (menu di sebelahnya pada dropdown yang sama — lihat [Profil PIC](#profil-pic)) yang bersifat baca-saja dan menunjukkan tanggung jawab kerja pengguna, halaman ini murni untuk mengubah identitas akun/kata sandi.

### Pencarian Navbar

Kotak pencarian di header (ikon kaca pembesar, tersedia di semua halaman untuk pengguna yang login) mempercepat perpindahan ke ILAP/jenis data/tabel/PIC/tiket tertentu tanpa harus membuka menu masing-masing satu per satu.

Mengetik minimal 3 karakter memunculkan saran (autocomplete) dari empat sumber sekaligus:
- **ILAP** — dicari dari kode dan nama.
- **Jenis Data** — dicari dari kode dan nama sub jenis data.
- **Nama Tabel** — dicari dari nama tabel bank data (satu saran per nama tabel, meski tabel itu dipakai banyak sub jenis data).
- **PIC** — dicari dari nama/username kolega, **dibatasi sesuai hak lihat Profil PIC** pengguna yang mencari (lihat aturan akses pada [Profil PIC](#profil-pic) di atas — pengguna biasa hanya akan disarankan dirinya sendiri, kasi/admin divisi disarankan seluruh staf divisinya).

Istilah yang diketik lebih dari satu kata harus cocok pada **semua** kata itu (tidak harus berurutan), sehingga pencarian bisa cukup spesifik.

Bila istilah yang diketik cocok **persis** dengan satu kode ILAP, kode sub jenis data, atau nama tabel, menekan Enter/tombol cari langsung membuka halaman tsb tanpa menampilkan daftar saran. Kalau tidak ada satu pun kecocokan dari keempat sumber di atas, sistem mencobanya sebagai **Nomor Tiket**: kecocokan tunggal langsung membuka [Detail Tiket](#detail-tiket), kecocokan ganda diarahkan ke [Daftar Tiket](#daftar-tiket) dengan filter nomor tiket tsb sudah terisi.

> Khusus pengguna P3DE (`user_p3de`/`admin_p3de`), header juga menampilkan tombol pintas **"+ Rekam Tiket"** di sebelah kotak pencarian, langsung menuju menu **Rekam Penerimaan Data** (lihat Menu P3DE).

---

## Menu P3DE

Menu-menu berikut muncul pada blok **P3DE** di navbar, untuk role `admin_p3de` dan `user_p3de`. P3DE (Penghimpunan Data Eksternal) adalah divisi yang menerima dan mencatat data dari ILAP — tahap pertama alur kerja tiket. Menu **PIC P3DE** tidak dibahas di sini karena sudah didokumentasikan lengkap di [Panduan Menu Admin](ADMIN_MENU_GUIDE.md).

---


### Monitoring

Halaman ini adalah alat monitor kepatuhan ILAP dalam menyampaikan data sesuai jadwal yang seharusnya (SLA penyampaian). Berbeda dari Daftar Tiket yang hanya menampilkan tiket yang sudah direkam, Monitoring **membangkitkan sendiri** daftar "periode yang seharusnya sudah disampaikan" untuk tiap Sub Jenis Data ILAP — dari tanggal mulai berlaku (`start_date`) sampai hari ini (atau `end_date` bila periode itu sudah berakhir) — lalu mencocokkan tiap periode dengan Tiket yang benar-benar ada. Ini membantu P3DE menindaklanjuti ILAP yang belum mengirim data **sebelum** tiket sempat direkam, sehingga menjadi langkah pemantauan yang mendahului Langkah 1 alur tiket (Rekam Penerimaan Data).

#### Kriteria/Data yang Ditampilkan

- Basis data adalah `PeriodeJenisData` (satu baris per Sub Jenis Data ILAP + periode pengiriman yang berlaku). Untuk tiap baris, sistem membangkitkan periode-periode sesuai pola frekuensi ILAP (Harian/Mingguan/2 Mingguan/Bulanan/Triwulanan/Kuartal/Semesteran/Tahunan). Frekuensi penyampaian sub-bulanan (Harian/Mingguan/2 Mingguan) selalu **dikelompokkan bulanan** untuk keperluan penerimaan, terlepas dari nilai frekuensi penerimaan yang tersimpan.
- Setiap periode dicocokkan dengan Tiket yang `penyampaian = 1` (pengiriman **pertama** untuk kombinasi Jenis Data + periode + tahun tsb — bila ILAP mengirim berkali-kali dalam satu periode, hanya pengiriman pertama yang menentukan status "sudah menyampaikan"). Batas waktu (deadline) = akhir periode + jumlah hari toleransi (`akhir_penyampaian`).
- **Cakupan pengguna:** superuser atau anggota grup `admin` melihat seluruh Sub Jenis Data ILAP. Selain itu — termasuk `admin_p3de` dan `user_p3de` — dibatasi hanya ke Sub Jenis Data ILAP tempat pengguna menjadi **PIC P3DE aktif** (`get_active_p3de_jenis_data_ilap_ids`).

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| ILAP | Nama & kode ILAP |
| Jenis Data | Sub Jenis Data ILAP |
| Periode | Label periode yang dibangkitkan (mis. "Januari", "Triwulan 1") |
| Tahun | Tahun periode |
| Batas Waktu Penyampaian | Akhir periode + hari toleransi penyampaian |
| Status Penyampaian | "Sudah Menyampaikan" (ada tiket `penyampaian=1`) atau "Belum Menyampaikan" |
| Terlambat | "Ya"/"Tidak" — dibandingkan terhadap batas waktu, memakai `tgl_terima_vertikal` untuk ILAP Regional atau `tgl_terima_dip` untuk lainnya bila tiket sudah ada, atau tanggal hari ini bila tiket belum ada |
| Sisa Hari | Selisih hari ke batas waktu (bisa negatif bila sudah lewat) |

#### Filter/Pencarian

Panel filter dapat dilipat, berisi 14 dropdown multi-pilih: Tahun, PIC P3DE, Kategori ILAP, ILAP, Jenis Data, Sub Jenis Data, Kanwil, KPP, Kategori Wilayah, Jenis Tabel, Dasar Hukum, Periode Pengiriman, Status Penyampaian, dan Terlambat. Filter bersifat dinamis/berantai: memilih satu nilai mempersempit pilihan yang tersedia di dropdown lain (dihitung ulang di server, mengecualikan dropdown itu sendiri agar tidak mempersempit dirinya sendiri). Untuk pengguna non-admin, dropdown PIC P3DE hanya berisi dirinya sendiri.

#### Aksi

- **Lihat Tiket** (ikon mata) — membuka Daftar Tiket dengan filter ILAP/Jenis Data/Periode/Tahun sesuai baris, untuk baris yang tiketnya sudah ada.
- **Rekam Penerimaan Data** (ikon file-plus) — pintasan ke form Rekam Penerimaan Data (menu berikutnya) dengan ILAP, Jenis Data ILAP, Periode, dan Tahun **terisi otomatis** dari baris terkait (lewat parameter URL `ilap_id`, `periode_data_id`, `periode`, `tahun` yang dibaca dan diterapkan oleh JavaScript form Rekam Tiket).

Menu ini murni pemantauan/navigasi — tidak ada aksi yang mengubah status tiket atau data lain.

#### Akses

- Halaman (list view): `MonitoringPenyampaianDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView)` → grup `admin`, `admin_p3de`, atau `user_p3de`.
- **Catatan teknis:** endpoint data AJAX (`monitoring_penyampaian_data_data`, yang memuat tabel dan opsi filter) memakai dekorator `@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())` — **tidak termasuk `admin_p3de`**. Akibatnya pengguna yang murni `admin_p3de` (bukan superuser, bukan anggota grup `admin` global, bukan `user_p3de`) dapat membuka halaman ini dari navbar, tetapi tabel dan seluruh dropdown filternya akan gagal dimuat (ditolak) karena endpoint data lebih ketat daripada halaman itu sendiri.
- Hanya P3DE (`admin_p3de`/`user_p3de`) dan admin global yang memiliki akses — bukan PIDE maupun PMDE. `RBAC_MATRIX.md` sudah diperbarui untuk mencerminkan ini.
- Pengguna `kasi_p3de` juga **tidak** mendapat menu ini: blok navbar P3DE tidak mengenali `kasi_p3de`, dan `UserP3DERequiredMixin` juga tidak — berbeda dari `kasi_pide` (mendapat menu Identifikasi) dan `kasi_pmde` (mendapat menu Quality Control), P3DE tidak memiliki padanan halaman antrean unit untuk kasi-nya.

---

### Rekam Penerimaan Data

Ini adalah **Langkah 1** alur kerja tiket: PIC P3DE mencatat data yang baru diterima dari suatu ILAP sebagai Tiket baru berstatus **Direkam (1)** — atau langsung **Selesai (8)** bila data ternyata tidak tersedia sama sekali. Diakses dari menu "Rekam Penerimaan Data", dari tombol "+ Rekam Tiket" di navbar (selalu tampil untuk P3DE), maupun dari tombol "Rekam Penerimaan Data" pada baris Monitoring yang belum menyampaikan data (lihat menu sebelumnya). Formulir ini terdiri dari tiga bagian pada satu halaman.

#### Bagian A — Data Utama

| Field | Keterangan |
|---|---|
| Status Ketersediaan Data | Radio: **Data Tersedia** / **Data Tidak Tersedia**. Memilih "Tidak Tersedia" mewajibkan Alasan Ketidaktersediaan dan membuat tiket **langsung berstatus Selesai (8)** tanpa melalui sisa alur kerja (dua `TiketAction` tercatat sekaligus: Direkam lalu Selesai) — sesuai "Alur Langsung Selesai" pada `status_tiket_flow.md`. |
| Permintaan Khusus & Jatuh Tempo | Switch penanda prioritas tinggi, sama seperti dijelaskan pada `status_tiket_flow.md` bagian *Special Request*: jatuh tempo hanya wajib dan tersimpan selama switch aktif; mematikan switch mengosongkan jatuh temponya. |
| ILAP | Dropdown pencarian. Daftar dibatasi ke ILAP yang: (a) punya PIC P3DE aktif untuk pengguna — kecuali `admin`/`admin_p3de`/`kasi_p3de` yang melihat semua ILAP — dan (b) punya minimal satu Jenis Data ILAP dengan Periode Data yang valid. |
| Jenis Data ILAP (Periode Data) | Dropdown yang terisi setelah ILAP dipilih (via `api/ilap/<id>/periode-jenis-data/`); untuk pengguna biasa dipersempit lagi hanya ke Jenis Data tempat ia PIC P3DE aktif. Kartu info "Informasi Jenis Data ILAP" menampilkan detail ILAP/kategori/jenis tabel/periode/PIC secara otomatis begitu dipilih. |
| Periode & Tahun | Opsi Periode mengikuti pola frekuensi ILAP (mis. Bulanan → Januari–Desember; Triwulanan → Triwulan 1–4). Tahun berupa dropdown (20 tahun ke belakang s.d. tahun berjalan, default tahun berjalan). |
| Penyampaian ke- | **Otomatis dihitung** (readonly), lewat API `check_tiket_exists`: nilainya = jumlah tiket lain yang sudah ada dengan Jenis Data + Periode + Tahun sama, ditambah 1 — mendukung ILAP yang mengirim data yang sama berkali-kali dalam satu periode. Bila kombinasi sudah pernah ada, modal "Peringatan Duplikasi" tampil menampilkan daftar tiket-tiket sebelumnya (dapat diklik untuk dibuka) — ini **hanya peringatan**, tidak memblokir penyimpanan. |
| Data Prioritas | Badge informasi saja (bukan field yang diisi pengguna) — terisi otomatis lewat API `check-jenis-prioritas` bila Sub Jenis Data tsb punya penetapan Data Prioritas yang **masa berlakunya mencakup Tanggal Terima DIP** yang diisi; ditetapkan otomatis ke tiket saat disimpan dengan aturan yang sama persis. Badge baru muncul setelah Tanggal Terima DIP diisi, dan ikut berubah bila tanggal itu diubah. Tahun Data tidak ikut menentukan. |

#### Bagian B — Surat Pengantar & Penerimaan Data

| Field | Keterangan |
|---|---|
| Nomor/Tanggal Surat Pengantar, Nama Pengirim | Opsional. Ini surat resmi dari ILAP yang menyertai pengiriman data — **berbeda** dari "ND Pengantar PIDE" yang baru dibuat P3DE sendiri nanti pada langkah Kirim ke PIDE. |
| Bentuk Data, Cara Penyampaian | Dropdown data referensi (dikelola di menu Admin P3DE). |
| Baris Diterima | Jumlah baris/record data yang diterima. Wajib lebih dari 0 bila Data Tersedia — **divalidasi di sisi tampilan (JavaScript)**, bukan di `clean()` Python. |
| Satuan Data | Tetap "Baris" (satu-satunya pilihan saat ini). |
| Tanggal Terima Vertikal | **Wajib diisi hanya untuk ILAP berkategori wilayah Regional**; untuk ILAP non-Regional field ini dikunci/tidak berlaku. Catatan: pembatasan ini **hanya diterapkan di sisi tampilan** — form Python (`TiketForm`) sendiri tidak mewajibkan ulang aturan ini di server, hanya memvalidasi bahwa tanggalnya tidak di masa depan. |
| Tanggal Terima DIP | Wajib. Tanggal data diterima di Direktorat/DIP. |

#### Bagian C — Rekam Backup Data (opsional)

Switch "Rekam Backup Data Sekarang". Bila diaktifkan, field Lokasi Backup, Nama File, dan Media Backup wajib diisi; sistem otomatis membuat satu baris `BackupData` terkait tiket ini pada saat tiket disimpan — setara dengan membuka menu **Kelola Backup Data → Tambah** secara terpisah, sekaligus menandai `Tiket.backup = True`. Tombol **Auto-format** mengisi Nama File otomatis dari nomor tiket + nama ILAP + jenis data + periode (memakai preview nomor tiket dari API `preview-nomor-tiket`).

#### Validasi (`TiketForm`, `forms/tiket.py`)

- `clean_tgl_terima_vertikal`, `clean_tgl_terima_dip`, `clean_tanggal_surat_pengantar`: ketiganya tidak boleh tanggal di masa depan.
- `clean()`: Tanggal Terima DIP tidak boleh lebih awal dari Tanggal Terima Vertikal.
- `clean()`: Tanggal Terima DIP tidak boleh melebihi `end_date` Periode Data terpilih (bila periode itu punya tanggal akhir).
- `clean_tgl_special_request`: jatuh tempo otomatis dianggap berlaku sampai pukul 23:59:59 pada tanggal yang dipilih; `clean()` mengosongkannya otomatis bila switch Permintaan Khusus tidak aktif.
- `clean_status_ketersediaan_data`: nilai radio "1"/"0" dipetakan eksplisit ke True/False (menghindari bug Django yang menganggap string "0" tetap `True` pada `CheckboxInput`).

#### Nomor Tiket

Dibuat otomatis dengan format `<ID Sub Jenis Data><YYMMDD><urutan 2 digit>` — contoh: `KM0330101` + `260211` (11 Feb 2026) + `01` → `KM033010126021101`. Preview-nya ditampilkan lewat API `preview-nomor-tiket` (dipakai untuk auto-format nama file backup); nomor final tetap **dihitung ulang** saat tiket benar-benar disimpan memakai algoritma yang sama (`TiketRekamCreateView._generate_nomor_tiket`), sehingga secara teori bisa berbeda dari preview apabila ada tiket lain yang keburu tersimpan lebih dulu dengan prefiks yang sama.

#### Aksi

**Simpan** — satu-satunya aksi pada halaman ini. Selain membuat baris Tiket, sistem dalam satu transaksi juga:
- Menugaskan PIC: pengguna yang merekam otomatis menjadi PIC P3DE (bila belum tercatat sebagai PIC di Jenis Data tsb), ditambah seluruh PIC P3DE/PIDE/PMDE **aktif** lain untuk Jenis Data terkait — sehingga PIC PIDE/PMDE sudah "menunggu" tiket ini sejak awal, jauh sebelum tiket benar-benar dikirim ke divisi mereka.
- Mengisi `id_durasi_jatuh_tempo_pide`/`_pmde` dari Durasi Jatuh Tempo yang sedang aktif untuk Jenis Data tsb (dikosongkan bila tidak ada yang aktif — tidak menghalangi penyimpanan).
- Mencatat riwayat aksi (`TiketAction`) "Direkam" dan "Ditambahkan" untuk tiap PIC yang ditugaskan.

#### Akses

`TiketRekamCreateView(LoginRequiredMixin, UserP3DERequiredMixin, UserFormKwargsMixin, CreateView)` → grup `admin`, `admin_p3de`, atau `user_p3de`. Sesuai RBAC_MATRIX.md (Rekam Penerimaan Data: P3DE ✅, PIDE ❌, PMDE ❌, Admin ✅). API pendukung (`preview_nomor_tiket`, `check_tiket_exists`, `api_ilap_periode_jenis_data`, `check_jenis_prioritas`) hanya mensyaratkan login, tanpa pembatasan grup tambahan — namun secara praktis hanya dipakai dari form ini.

---

### Kelola Tanda Terima

Tanda Terima adalah bukti formal bahwa P3DE telah menerima data dari suatu ILAP — direkam per Kanwil untuk ILAP berkategori Regional, atau per ILAP untuk Nasional/Internasional. Statusnya menjadi salah satu syarat sebuah tiket boleh dikirim ke PIDE (lihat Langkah 3 pada `status_tiket_flow.md`: PIDE hanya menerima tiket dengan `tanda_terima=True`). Menu ini mengelola penerbitan, koreksi, dan pembatalan tanda terima.

#### Kriteria/Data yang Ditampilkan

Seluruh `TandaTerimaData`, dengan pembatasan untuk pengguna non-admin (bukan superuser/anggota grup `admin`): hanya tanda terima yang mencakup minimal satu tiket di mana pengguna adalah **PIC P3DE aktif**.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nomor Tanda Terima | Format otomatis, bernomor urut ulang tiap tahun. |
| Tanggal | Tanggal tanda terima diterbitkan. |
| Kanwil / ILAP | Nama Kanwil (lingkup Regional) atau nama ILAP (lingkup Nasional/Internasional), dengan label lingkup ditampilkan di bawahnya. |
| Perekam | Pengguna yang menerbitkan; tertaut ke Profil PIC bila yang melihat berhak. |
| Status | Aktif / Dibatalkan. |
| Aksi | Tombol kontekstual, lihat di bawah. |

#### Filter/Pencarian

Kotak pencarian per kolom (Nomor, Tanggal, Kanwil/ILAP, Perekam, Status) di bawah header tabel, plus tombol **Reset Pencarian**.

#### Aksi

**Tambah — dua jalur pembuatan:**

1. **Standalone** (`tanda_terima_data_create`, tombol "Tambah" pada halaman ini): pengguna memilih Lingkup (Regional / Nasional-Internasional), lalu Kanwil atau ILAP, opsional ND Pengantar (nomor surat pengantar ILAP) untuk mempersempit pilihan, lalu mencentang satu atau beberapa Tiket berstatus di bawah Dikirim ke PIDE yang belum terikat tanda terima aktif lain dalam lingkup yang sama. Nomor Tanda Terima dan Tanggal Tanda Terima (default hari ini) dibuat/diisi otomatis.
2. **Dari halaman detail tiket** (`tanda_terima_data_from_tiket_create`): sama, namun lingkup dan tiketnya sudah ditentukan dari tiket asal (tanpa pemilihan tiket manual) — hanya tersedia untuk PIC P3DE aktif tiket tersebut.

Setelah tersimpan, setiap tiket tercakup ditandai `tanda_terima=True` dan dicatat `TiketAction` "Tanda terima dibuat".

**Tidak Diterbitkan** (`tidak_terbit_tanda_terima`) — tombol di dalam form Tambah (bukan di tabel utama, hanya muncul saat membuat tanda terima baru): menandai tiket-tiket yang dicentang sebagai `tanda_terima=True` **tanpa** membuat baris `TandaTerimaData` — dipakai ketika P3DE memutuskan tidak menerbitkan tanda terima formal untuk tiket tsb namun tetap perlu melanjutkan alur kerja. Tercatat sebagai aksi tersendiri di riwayat tiket ("Tidak diterbitkan Tanda Terima"); ditolak bila tiket sudah punya tanda terima.

**Edit** — hanya dapat dilakukan bila tanda terima masih **Aktif** dan seluruh tiket di dalamnya masih berstatus **di bawah Dikirim ke PIDE (4)**; begitu salah satu tiketnya sudah dikirim ke PIDE, tanda terima terkunci sepenuhnya. Field Lingkup/Kanwil/ILAP/ND Pengantar/Tanggal tidak dapat diubah — hanya daftar tiket yang tercakup yang bisa ditambah/dilepas.

**Batalkan** (soft delete, ikon "x-circle") — mengubah `active=False` (data tidak dihapus permanen), lalu mengembalikan **semua** tiket dalam tanda terima itu ke `tanda_terima=False` **dan status Direkam (1)** — meskipun tiket tadinya sudah berstatus Diteliti (2). Dicatat `TiketAction` "Tanda terima dibatalkan" pada tiap tiket yang terdampak.

**Download** (ikon dokumen) — mengunduh dokumen Tanda Terima beserta lampirannya (DOCX).

**Lihat Detail** (ikon mata, hanya untuk PIC aktif) — menampilkan tanda terima beserta daftar tiketnya secara baca-saja.

#### Validasi (`TandaTerimaDataForm`, `forms/tanda_terima_data.py`)

- Lingkup **Regional** wajib memilih Kanwil; lingkup **Nasional/Internasional** wajib memilih ILAP — keduanya saling eksklusif (memilih salah satu mengosongkan field yang lain saat disimpan).
- Minimal satu tiket harus dipilih (`clean_tiket_ids`), dan tiap tiket yang dipilih harus benar-benar berada dalam cakupan (Kanwil/ILAP/ND Pengantar) yang dipilih serta belum terikat tanda terima aktif lain di cakupan yang sama.
- Tanggal Tanda Terima tidak boleh **lebih awal** dari Tanggal Terima DIP milik tiket manapun yang tercakup di dalamnya; bila selisihnya hanya jam pada hari yang sama, sistem otomatis menyesuaikan jamnya alih-alih menolak — hanya selisih hari (tanggal) yang benar-benar dianggap konflik.
- Nomor Tanda Terima dialokasikan ulang otomatis saat form disimpan (bukan sekadar memakai nilai preview yang ditampilkan) untuk menghindari duplikasi bila dua pengguna menyimpan hampir bersamaan.

#### Akses

- Halaman & create/update/delete: `UserP3DERequiredMixin` → grup `admin`, `admin_p3de`, `user_p3de`. Aksi per-tiket (create-dari-tiket, update, delete, lihat detail) menambahkan syarat `ActiveTiketP3DERequiredForEditMixin` / pemeriksaan manual — pengguna harus PIC P3DE **aktif** pada tiket-tiket yang tercakup.
- **Catatan teknis:** endpoint data AJAX (`tanda_terima_data_data`, `tanda_terima_next_number`, `tanda_terima_tikets_by_ilap`, `tanda_terima_nd_pengantar_options`) memakai dekorator `['admin', 'user_p3de']` — **tidak termasuk `admin_p3de`**, pola yang sama seperti pada menu Monitoring: pengguna `admin_p3de` murni bisa membuka halaman ini tetapi tabelnya gagal dimuat.
- Sesuai RBAC_MATRIX.md untuk akses menu itu sendiri (Tanda Terima Data: P3DE ✅, PIDE ❌, PMDE ❌, Admin ✅).

---

### Register Penerimaan Data

Laporan rekapitulasi seluruh penerimaan data pada suatu bulan/tahun tertentu — register administratif (siapa mengirim apa, kapan, tanda terima bernomor berapa) yang biasa dipakai untuk pelaporan atau arsip bulanan P3DE. Menu ini murni pelaporan; tidak terkait langsung dengan perubahan status tiket.

#### Kriteria/Data yang Ditampilkan

Seluruh Tiket dengan `tgl_terima_dip` jatuh pada bulan & tahun yang dipilih pengguna — **tanpa pembatasan PIC/kepemilikan**. Berbeda dari Monitoring, Tanda Terima, dan Backup Data, laporan ini menampilkan seluruh ILAP tanpa disaring ke PIC aktif pengguna. Tabel tetap kosong sampai pengguna memilih Bulan **dan** Tahun (keduanya wajib).

#### Kolom/Field

No; Nama ILAP; Dasar Hukum (gabungan deskripsi klasifikasi jenis data terkait, dipisah koma); Jenis Data ILAP; Bentuk Data; Periode / Tahun Data; Jumlah Data Diterima (`baris_diterima`); Nomor Surat Pengantar; Tanggal Surat Pengantar; Nomor Tanda Terima; Tanggal Tanda Terima (tanda terima **pertama** yang tercatat untuk tiket itu bila ada, "-" bila belum ada tanda terima).

#### Filter/Pencarian

Dropdown **Bulan** (Januari–Desember) dan **Tahun** (10 tahun terakhir, default tahun berjalan) pada header tabel — keduanya wajib dipilih sebelum data ditampilkan.

#### Aksi

**Ekspor ke Excel** (tombol "EKSPOR KE EXCEL", aktif setelah data tampil) — mengunduh berkas .xlsx dengan kolom yang sama, judul "Register Penerimaan Data - `<Bulan Tahun>`", dan baris berwarna selang-seling. Tidak ada aksi lain — laporan ini tidak mengubah data apa pun.

#### Akses

Fungsi `_is_p3de_user` di `views/laporan_register_penerimaan.py` → `is_superuser`, `is_staff`, atau anggota grup `user_p3de`/`admin`/`admin_p3de`. Perlu dicatat: `is_staff` (atribut akun Django, bukan grup) ikut meloloskan akses — siapa pun akun dengan flag staff Django aktif bisa membuka laporan ini terlepas dari keanggotaan grupnya. Sesuai RBAC_MATRIX.md (Register Penerimaan Data: P3DE ✅, PIDE ❌, PMDE ❌, Admin ✅).

---

### Kelola Backup Data

Mencatat lokasi & media penyimpanan cadangan (backup) untuk data mentah yang diterima per tiket — bagian dari kewajiban pengarsipan P3DE agar data sumber tidak hilang. Status backup tiket (`Tiket.backup`) juga menjadi salah satu syarat sebuah tiket boleh dikirim ke PIDE (lihat pemeriksaan "belum backup" pada menu Kirim Tiket ke PIDE).

#### Kriteria/Data yang Ditampilkan

Pengguna non-admin (bukan superuser/anggota grup `admin`) hanya melihat `BackupData` milik tiket tempat ia PIC P3DE **aktif**; admin/superuser melihat semua.

#### Kolom/Field

Kategori ILAP; Nama ILAP; Jenis Data; Subjenis Data; Periode Data; Nomor Tiket; Media Backup (referensi, mis. Hardisk Eksternal/Cloud); Lokasi Penyimpanan (path/tautan bebas teks yang diinput pengguna); PIC P3DE (nama PIC aktif tiket tsb, dapat tertaut ke Profil PIC); Jumlah Data (`baris_diterima` tiket); Aksi.

#### Filter/Pencarian

Filter Tahun (memengaruhi ringkasan jumlah backup per Media Backup) serta filter lanjutan yang saling berantai secara dinamis (ILAP, Jenis Data, Subjenis Data, Kategori ILAP, Periode Data, Periode Pengiriman, Media Backup, PIC P3DE) — memilih ILAP memuat opsi Jenis Data yang relevan, dan seterusnya, mirip pola pada menu Monitoring. Tabel juga menyediakan kotak pencarian per kolom.

#### Aksi

**Tambah** — dua jalur seperti pada Kelola Tanda Terima: standalone (memilih Tiket dari dropdown, dibatasi ke tiket tempat pengguna PIC P3DE aktif **dan** berstatus **sebelum Dikirim ke PIDE**, yaitu status < 4) atau dari halaman detail tiket (tiket sudah ditentukan). Menyimpan menandai `Tiket.backup = True` dan mencatat `TiketAction` "backup data direkam".

**Edit** — field Tiket dikunci (tidak dapat dipindah ke tiket lain); hanya Lokasi Backup, Nama File, dan Media Backup yang dapat diubah. Tombol Edit hanya muncul bila status tiket < Dikirim ke PIDE (4) **dan** pengguna adalah PIC aktif tiket tsb.

**Hapus** — menghapus baris backup. **Bila itu satu-satunya backup milik tiket tersebut**, sistem otomatis mengosongkan `Tiket.backup` (menjadi `False`) **dan mengembalikan status tiket ke Direkam (1)** — walaupun tiket sudah berstatus Diteliti (2) sebelumnya. Ini efek samping yang perlu diperhatikan pengguna: menghapus satu-satunya backup pada tiket dapat memundurkan status tiket tersebut.

**Ekspor Excel / PDF** — mengunduh hasil filter saat ini dalam format .xlsx atau .pdf (PDF dibuat manual tanpa pustaka pihak ketiga, berupa tabel sederhana).

#### Akses

- Halaman & create/update/delete: `UserP3DERequiredMixin` (+ `ActiveTiketP3DERequiredForEditMixin` untuk create-dari-tiket/update/delete) → grup `admin`, `admin_p3de`, `user_p3de`.
- **Catatan teknis:** endpoint data AJAX (`backup_data_data`, `backup_data_filter_options`, `backup_data_export_excel`, `backup_data_export_pdf`) memakai dekorator `['admin', 'user_p3de']` — **tidak termasuk `admin_p3de`** — pola yang sama seperti pada Monitoring dan Kelola Tanda Terima.
- Sesuai RBAC_MATRIX.md (Backup Data: P3DE ✅, PIDE ❌, PMDE ❌, Admin ✅).

---

### Kirim Tiket ke PIDE

Ini adalah **Langkah 3** alur kerja tiket (`status_tiket_flow.md` bagian 3): P3DE mengirimkan tiket yang sudah diteliti ke PIDE melalui dua tahap terpisah — **Generate ND Pengantar PIDE**, lalu **Kirim ke PIDE**. Halaman ini menyatukan kedua tahap dalam dua tab.

#### Tab 1 — Generate ND Pengantar PIDE

**Kriteria/Data yang Ditampilkan:** Tiket dengan status **Diteliti (2)** atau **Dikembalikan (3)** — meskipun menurut `status_tiket_flow.md` status Dikembalikan tidak pernah benar-benar ditetapkan pada tiket manapun, sehingga dalam praktiknya daftar ini hanya berisi tiket Diteliti — **dan** `backup=True` **dan** `tanda_terima=True` **dan** status penelitian bukan "Tidak Lengkap" **dan** pengguna adalah PIC P3DE aktif tiket tsb **dan** tiket itu belum masuk batch `KirimPideTemp` manapun. Catatan: syarat `backup=True` (Backup Data sudah direkam) ini tidak disebutkan secara eksplisit pada `status_tiket_flow.md` namun ditegakkan di kode. Daftar dapat difilter per ILAP.

**Kolom/Field:** checkbox pilih; No; Nomor Tiket; Nama ILAP; Jenis/Subjenis Data; Periode Data; Jumlah Rows Lengkap (`baris_lengkap`); Status Tiket.

**Aksi:** mencentang satu/beberapa tiket (atau tombol "Pilih semua N tiket" lintas halaman) lalu **Generate ND Pengantar**. Sistem menyimpan tiap tiket terpilih sebagai baris `KirimPideTemp` dengan `id_temp` baru (nomor batch bersama), lalu men-generate dan mengunduh dokumen **ND Pengantar PIDE** (.docx — dari template `nd_pengantar_pide` di menu Template Dokumen bila tersedia, atau tabel sederhana sebagai cadangan). Tiket yang sudah masuk batch `KirimPideTemp` lain tidak bisa digenerate ulang sebelum batch lamanya dihapus/diproses.

#### Tab 2 — Kirim ke PIDE (Daftar Template Kirim PIDE)

**Kriteria/Data:** seluruh batch `KirimPideTemp` **milik pengguna yang sedang login** (dikelompokkan per `id_temp`), tidak difilter ILAP.

**Kolom/Field:** ID Temp; Jumlah Tiket (beserta daftar nomor tiket di dalamnya); Aksi.

**Aksi per batch:**

- **Update Template** (ikon pensil) — modal menampilkan seluruh tiket yang **masih memenuhi syarat** (kriteria sama seperti Tab 1) ditambah tiket yang sudah ada di batch ini, dengan checkbox; menyimpan menambah/menghapus tiket dari batch sesuai centang yang berubah.
- **Hapus Template** (ikon tempat sampah) — menghapus seluruh baris `KirimPideTemp` batch ini; tiket-tiketnya kembali tersedia di Tab 1.
- **Kirim ke PIDE** (ikon kirim) — modal konfirmasi meminta data **ND Nadine**: Nomor ND Nadine, Tanggal Nadine, dan Tanggal Kirim PIDE. Setelah dikonfirmasi:
  - Sistem memeriksa ulang syarat tiap tiket (status Diteliti/Dikembalikan, sudah backup, sudah tanda terima, sudah punya `tgl_teliti`, status penelitian bukan Tidak Lengkap) — bila ada tiket yang tidak lagi memenuhi syarat (mis. berubah sejak Tab 1 dijalankan), seluruh pengiriman ditolak dengan pesan rinci per tiket bermasalah.
  - Tiap tiket diubah menjadi status **Dikirim ke PIDE (4)**; field `tgl_nadine`, `nomor_nd_nadine`, `tgl_kirim_pide` diisi; `TiketAction` "Dikirim ke PIDE" dicatat; notifikasi dikirim ke setiap PIC PIDE aktif tiket tsb.
  - Baris `KirimPideTemp` batch ini dihapus (dianggap selesai diproses).

#### Validasi ND Nadine (`KirimKePideForm`, `forms/kirim_ke_pide.py`)

- Nomor ND Nadine, Tanggal Nadine, dan Tanggal Kirim PIDE ketiganya **wajib** diisi.
- Tanggal Nadine dan Tanggal Kirim PIDE tidak boleh tanggal di masa depan.
- Untuk **setiap** tiket dalam batch: Tanggal Nadine dan Tanggal Kirim PIDE tidak boleh lebih awal dari `tgl_teliti` tiket tersebut.
- Tanggal Kirim PIDE tidak boleh lebih awal dari Tanggal Nadine.

#### Akses

Seluruh view terkait (`KirimTiketView`, `DownloadNDPengantarView`, `KirimPideTempUpdateView`, `KirimPideTempDeleteView`, `KirimKePIDEView`) memakai `UserP3DERequiredMixin` → grup `admin`, `admin_p3de`, `user_p3de`. Setiap aksi pada suatu batch (`id_temp`) juga memverifikasi **kepemilikan**: hanya pengguna yang membuat batch tersebut yang boleh mengedit/menghapus/mengirimkannya — bukan sekadar PIC aktif tiket-tiket di dalamnya. Sesuai RBAC_MATRIX.md (Kirim Tiket ke PIDE: P3DE ✅, PIDE ❌, PMDE ❌, Admin ✅).

---

### Generate PKDI/Klarifikasi (Bulk)

Alat pembuatan dokumen massal untuk mencetak **PKDI** (Lengkap atau Sebagian) atau **Surat Klarifikasi** sekaligus untuk banyak tiket yang diterima pada tanggal yang sama — menghindari proses generate satu per satu dari halaman detail tiket. Dokumen yang dihasilkan sama secara fungsi dengan yang bisa dibuat dari detail tiket; bedanya di sini prosesnya dikelompokkan berdasarkan Tanggal Terima DIP dan (opsional) ILAP.

#### Kriteria/Data yang Ditampilkan

Tiket dengan `tgl_terima_dip` = tanggal yang dipilih **dan** `tanda_terima=True`, disaring lagi menurut Jenis Dokumen yang dipilih:

| Jenis Dokumen | Syarat Status Penelitian |
|---|---|
| PKDI (Lengkap) | "Lengkap" |
| PKDI Sebagian | "Lengkap Sebagian" |
| Klarifikasi | "Lengkap Sebagian" atau "Tidak Lengkap" |

Tidak ada pembatasan tiket ke PIC aktif pengguna pada query tiketnya sendiri (berbeda dari kebanyakan menu lain) — yang dibatasi hanya daftar ILAP yang muncul pada dropdown filter (lihat bagian Akses).

#### Kolom/Field

Checkbox pilih; Nomor Tiket; Kategori Wilayah; ILAP; Jenis Data; Periode Data; Baris Diterima; Status Penelitian (badge berwarna); Tanggal Terima DIP.

#### Filter/Pencarian

**Tanggal Terima DIP** (wajib, tanggal tunggal); **ILAP** (opsional — kosongkan untuk mencakup semua ILAP pada tanggal tsb); **Jenis Dokumen** (PKDI / PKDI Sebagian / Klarifikasi).

#### Aksi

Centang tiket yang diinginkan lalu **Generate DOCX** — mengunduh satu berkas .docx berisi seluruh tiket terpilih, memakai template dari menu Template Dokumen sesuai kombinasi jenis dokumen + kategori wilayah ILAP (Regional vs Nasional/Internasional memakai template berbeda), atau jatuh ke tabel sederhana bila template tidak ditemukan. Aksi ini tidak mengubah status tiket maupun data lain — murni menghasilkan dokumen.

> Kode juga menyediakan halaman serupa **Generate ND Pengantar PIDE (Bulk)** (`bulk_nd_pengantar_pide`, template `bulk_documents/nd_pengantar_pide.html`) dengan mekanisme sama namun disaring dari Tanggal Kirim PIDE; link-nya ada di `navbar.html` tetapi dikomentari (`<!-- ... -->`) sehingga saat ini tidak muncul di menu manapun.

#### Akses

Fungsi `_is_p3de_user` di `views/bulk_document_generation.py` → `is_superuser`, grup `admin`, atau grup `user_p3de` — **`admin_p3de` tidak termasuk**. Artinya seorang pengguna yang murni `admin_p3de` (bukan juga `user_p3de`, bukan anggota grup `admin` global, bukan superuser) akan **melihat link "Generate PKDI/Klarifikasi (Bulk)" di navbar-nya** (karena blok navbar P3DE terbuka untuk `admin_p3de` ATAU `user_p3de`) **namun ditolak akses begitu mengkliknya**. RBAC_MATRIX.md mencantumkan baris generik "Bulk Generate Dokumen" (P3DE ✅, PIDE ✅, PMDE ❌, Admin ✅) yang tidak merinci hal ini — sebaiknya diperjelas bahwa akses "P3DE" di sini secara spesifik berarti `user_p3de`, bukan `admin_p3de`.

---

### Laporan Rekap Himpun Olah Data

Laporan ringkasan tingkat ILAP yang membandingkan jumlah Jenis Data "wajib" dimiliki suatu ILAP terhadap berapa yang benar-benar sudah dikirim (punya tiket), tepat waktu (`tgl_kirim_pide` terisi), dan lengkap (`baris_lengkap > 0`) — kartu skor kepatuhan ILAP untuk kebutuhan pengendalian mutu data.

#### Kriteria/Data yang Ditampilkan

Satu baris per ILAP, mencakup **seluruh ILAP di sistem** (tidak dibatasi PIC). Untuk tiap ILAP dihitung: Jenis Data Wajib (total Jenis Data ILAP miliknya), Jenis Data Kirim (jumlah Jenis Data yang punya minimal satu tiket), Jenis Data Tepat Waktu (jumlah Jenis Data dengan minimal satu tiket ber-`tgl_kirim_pide` terisi), Jenis Data Lengkap (jumlah Jenis Data dengan minimal satu tiket ber-`baris_lengkap > 0`), beserta persentase masing-masing serta jumlah data (baris) terkirim/lengkap secara total.

#### Kolom/Field

Kategori ILAP; Nama ILAP; Jenis Data Wajib; Jenis Data Kirim; Jenis Data Tepat Waktu; Jenis Data Lengkap; Persentase Kirim; Persentase Tepat Waktu; Persentase Lengkap; Jumlah Data Kirim; Jumlah Data Lengkap.

#### Filter/Pencarian

Form filter menampilkan tujuh dropdown (Kategori ILAP, Nama ILAP, Jenis Data, Subjenis Data, Dasar Hukum, serta dua dropdown berlabel "Tanggal Mulai" dan "Tanggal Selesai", dan "Nama Tabel"). **Hanya "Nama ILAP" yang benar-benar berfungsi** — enam dropdown lainnya dirender `disabled` di HTML dan tidak pernah diisi maupun diaktifkan oleh JavaScript (tampaknya sisa dari templat Kelola Backup Data yang labelnya belum disesuaikan dan logikanya belum diimplementasikan untuk laporan ini). Dalam praktiknya pengguna hanya bisa menyaring berdasarkan ILAP, lalu klik **Cari**.

#### Aksi

**Cari** (menjalankan ulang query dengan filter terpilih); **Excel** dan **PDF** (mengunduh hasil filter saat ini — PDF memakai pustaka `reportlab` bila terpasang di server, jatuh otomatis ke Excel bila tidak). Murni laporan baca-saja, tidak mengubah data apa pun.

#### Akses

Fungsi `is_pmde_user` di `views/laporan_rekap_himpun_olah_data.py` → `is_superuser`, `is_staff`, atau anggota grup `user_pmde`/`admin`/`admin_pmde`/`user_p3de`/`admin_p3de`.

> **Riwayat perbaikan:** menu ini semula hanya mengizinkan PMDE di kode, padahal `navbar.html` sudah lama menampilkan tautannya di blok P3DE — pengguna P3DE melihat link ini tapi ditolak begitu mengklik. Aturan akses kini sudah diperluas agar sesuai dengan penempatan link tersebut (P3DE dan PMDE sama-sama berhak, karena laporan ini merekap tahap Penghimpunan P3DE sekaligus Pengolahan yang berlanjut ke PIDE/PMDE). `RBAC_MATRIX.md` sudah diperbarui mengikuti perubahan ini.

---

### Laporan Detail Penghimpunan dan Pengolahan Data

Versi rinci dari laporan sebelumnya — bukan agregat per ILAP, melainkan satu baris per Jenis Data ILAP, menampilkan dasar hukum, klasifikasi, dan periode pengiriman masing-masing. Dipakai untuk menelusuri Jenis Data ILAP mana saja yang mendasari angka pada Laporan Rekap Himpun Olah Data.

#### Kriteria/Data yang Ditampilkan

Satu baris per Jenis Data ILAP (bukan per ILAP maupun per tiket) — mencakup **seluruh Jenis Data ILAP di sistem**, tanpa pembatasan PIC.

#### Kolom/Field

Kategori ILAP; Nama ILAP; Nama Jenis Data; Nama Sub Jenis Data; Nama Tabel (Jenis Tabel); Klasifikasi (gabungan kategori klasifikasi jenis data terkait); Dasar Hukum (gabungan deskripsi dasar hukum terkait); Periode Pengiriman (gabungan periode penyampaian yang berlaku).

#### Filter/Pencarian

Sama persis strukturnya dengan Laporan Rekap Himpun Olah Data — form filter menyalin susunan dropdown yang sama (Kategori ILAP, Nama ILAP, Jenis Data, Subjenis Data, Dasar Hukum, "Tanggal Mulai"/"Tanggal Selesai", Nama Tabel), dan hanya **Nama ILAP** yang aktif; sisanya `disabled` dan tidak fungsional (lihat catatan pada menu sebelumnya).

#### Aksi

**Cari**; **Excel** (ekspor .xlsx lengkap). Tombol **PDF** tersedia di tampilan namun **belum benar-benar diimplementasikan** untuk laporan ini — fungsi `_export_detail_to_pdf()` di kode selalu memanggil `_export_detail_to_excel()`, sehingga klik "PDF" tetap menghasilkan berkas Excel. Murni laporan baca-saja.

#### Akses

Sama persis dengan Laporan Rekap Himpun Olah Data — fungsi `is_pmde_user` di `views/laporan_detail_himpun_olah_data.py` (definisi identik) → superuser/`is_staff`/grup `user_pmde`/`admin`/`admin_pmde`/`user_p3de`/`admin_p3de`.

> **Riwayat perbaikan:** sama seperti menu sebelumnya, akses kini sudah diperluas ke P3DE agar sesuai dengan penempatan link-nya di blok P3DE pada `navbar.html`. `RBAC_MATRIX.md` sudah diperbarui mengikuti perubahan ini.

---

## Menu PIDE


Dokumen ini menjelaskan menu-menu yang muncul pada blok **PIDE** di navbar (`navbar.html`) untuk role `admin_pide`, `user_pide`, dan (untuk menu Identifikasi) `kasi_pide` — yaitu Identifikasi, Laporan SLA Perekaman, Laporan SLA Identifikasi, Laporan Transfer, dan Laporan Metrik Data Eksternal. Menu **PIC PIDE** sengaja tidak dibahas di sini karena sudah didokumentasikan lengkap di `ADMIN_MENU_GUIDE.md`.

---

### Identifikasi

Halaman **Identifikasi** adalah antrian kerja utama PIDE: daftar tiket yang statusnya sudah **Identifikasi (5)** — tiket yang sedang dikerjakan PIDE untuk memilah data menjadi baris I (Identifikasi), U (Update), Res (Residual), dan CDE, sebelum diteruskan ke PMDE (lihat `status_tiket_flow.md` bagian 4 dan 6). Halaman ini murni berfungsi sebagai **antrian dan alat pemantauan beban kerja**; aksi yang benar-benar memindahkan status tiket — **Proses Identifikasi** (Dikirim ke PIDE → Identifikasi), **Kembalikan ke P3DE** (→ Dibatalkan), dan **Transfer ke PMDE** (Identifikasi → Pengendalian Mutu) — semuanya dijalankan lewat modal di halaman **Detail Tiket**, bukan di halaman ini.

Menu ini dipakai bersama oleh `admin_pide`, `user_pide`, dan `kasi_pide` — ketiganya membuka **halaman yang sama** (tidak ada versi terpisah untuk kasi), namun isi datanya berbeda menurut cakupan masing-masing (lihat di bawah).

#### Kriteria/Data yang Ditampilkan

- Tabel utama ("Daftar Tiket Identifikasi") hanya berisi tiket yang **statusnya persis Identifikasi (5)**. Tiket yang baru berstatus "Dikirim ke PIDE" dan belum mulai diproses **tidak** muncul di tabel ini — tiket tersebut hanya terhitung pada kartu ringkasan "Belum Mulai Identifikasi".
- Di atas tabel dan grafik terdapat **tiga kartu ringkasan** yang saling melengkapi, dihitung dari kumpulan tiket yang sama dan mengikuti filter yang sedang aktif:

  | Kartu | Cakupan status tiket | Arti |
  |---|---|---|
  | **Dalam Proses Identifikasi** | Identifikasi (5) | Beban kerja saat ini — tiket yang sama dengan isi tabel, dihitung dari sisa baris yang belum diidentifikasi |
  | **Belum Mulai Identifikasi** | Dikirim ke PIDE (4) | Tiket yang sudah diterima dari P3DE tapi belum dibuka untuk diidentifikasi — antrian yang akan masuk ke tabel begitu diproses |
  | **Masih di P3DE** | Direkam (1), Diteliti (2), Dikembalikan (3) | Tiket yang belum sampai ke PIDE sama sekali — gambaran beban yang akan datang |

  Karena PIC PIDE sudah ditugaskan sejak tahap perekaman tiket di P3DE (bukan baru saat tiket dikirim ke PIDE), seorang pelaksana PIDE biasanya **sudah** mempunyai tiket pada kartu "Belum Mulai Identifikasi" dan "Masih di P3DE" meski tiket itu belum sampai ke mejanya.
- **Cakupan menurut role** (berlaku sekaligus ke tabel, ketiga kartu, dan grafik):

  | Role | Tiket yang terlihat |
  |---|---|
  | `kasi_pide` | **Semua** tiket unit PIDE, tanpa memandang siapa PIC-nya — kasi mengawasi seluruh unit |
  | `user_pide`, `admin_pide`, `admin` (global), superuser, staff | Hanya tiket yang **PIC PIDE aktifnya** adalah pengguna itu sendiri |

  Berdasarkan kode saat ini (`views/identifikasi.py` bersama `pic_scope()` di `views/seksi_queue.py`), **hanya keanggotaan grup `kasi_pide`** yang diperlakukan sebagai "lihat semua tiket". Grup `admin`/`admin_pide` maupun status superuser/staff **tidak** memberi keleluasaan yang sama pada cakupan data ini — seorang admin yang bukan `kasi_pide` dan sedang tidak menjadi PIC PIDE aktif pada tiket manapun akan melihat tabel, ketiga kartu, dan grafik dalam keadaan **kosong**, walau ia tetap bisa membuka halamannya (lihat bagian Akses).
- Baris tabel diwarnai menurut kolom Jatuh Tempo: **merah** bila sisa hari < 7 (termasuk yang sudah lewat tempo), **kuning** bila 7–29 hari, **hijau** bila ≥ 30 hari; tiket tanpa Deadline tidak diberi warna.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama Tabel | Nama tabel bank data dari sub jenis data tiket |
| PIC PIDE | Nama PIC PIDE yang aktif menangani tiket; menjadi tautan ke halaman Profil PIC bila pengguna yang membuka berhak melihatnya |
| Nomor Tiket / Sub Jenis Data | Dua baris dalam satu sel: nomor tiket di atas, nama sub jenis data di bawah |
| Nama ILAP / Jenis Tabel | Dua baris: nama ILAP pengirim data, dan klasifikasi Jenis Tabel dari sub jenis data tersebut |
| Tgl Kirim PIDE / Tgl Rekam PIDE | Dua baris: tanggal P3DE mengirim tiket ke PIDE, dan tanggal PIDE mulai mencatat/memproses identifikasi (terisi begitu aksi Proses Identifikasi dijalankan di halaman detail) |
| Deadline | Tanggal jatuh tempo = tanggal dasar (Tgl Rekam PIDE bila sudah terisi, kalau belum memakai Tgl Kirim PIDE) ditambah durasi SLA yang berlaku untuk sub jenis data tersebut pada tanggal itu (diatur lewat menu admin **Durasi Jatuh Tempo PIDE**, lihat ADMIN_MENU_GUIDE.md). Tampil "-" bila tidak ada durasi SLA yang berlaku pada tanggal itu |
| Jatuh Tempo | Selisih hari dari hari ini ke Deadline; angka negatif berarti sudah lewat tempo |
| Prioritas | Ya/Tidak — apakah data ini termasuk jendela waktu "Data Prioritas" yang berlaku pada tanggal tiket diterima |
| Jml Baris Lengkap | Jumlah baris data yang dinyatakan lengkap pada hasil penelitian P3DE |
| Jml Selesai | Jumlah baris yang sudah dipilah PIDE ke dalam I/U/CDE/Res |
| Jml Progress | Sisa baris yang belum dipilah/diidentifikasi (Jml Baris Lengkap dikurangi Jml Selesai; tidak pernah ditampilkan negatif) |
| Aksi | Tombol "Lihat Detail" menuju halaman Detail Tiket — tempat seluruh aksi alur kerja (Proses Identifikasi, Kembalikan ke P3DE, Transfer ke PMDE) sebenarnya dijalankan |

#### Filter/Pencarian

Panel filter (dapat dilipat/dibuka, otomatis tertutup bila tidak ada filter aktif) menyediakan dropdown berikut, dan semuanya saling menyempitkan satu sama lain — memilih satu nilai otomatis mempersempit pilihan yang tersedia pada dropdown lainnya:

Nomor Tiket, Tahun, Periode, Periode Pengiriman, Periode Penerimaan, PIC P3DE, PIC PIDE, PIC PMDE, Kategori ILAP, ILAP, Jenis Data, Sub Jenis Data, Nama Tabel, Kanwil, KPP, Kategori Wilayah, Jenis Tabel, Dasar Hukum, Status Penelitian, Status Ketersediaan Data, Permintaan Khusus, Prioritas, dan **Jatuh Tempo** (tiga ambang tetap: < 10 hari, < 30 hari, < 60 hari).

Filter berlaku serentak ke tabel, ke tiga kartu ringkasan, dan ke grafik "Jml Progress per Jatuh Tempo". Khusus filter Jatuh Tempo, hanya berpengaruh ke kartu/tabel "Dalam Proses Identifikasi" — tidak relevan untuk dua kartu upstream karena hitungan mundurnya memang belum dimulai untuk tiket yang belum sampai/dibuka PIDE.

#### Aksi

- **Lihat Detail** (ikon mata) — satu-satunya aksi per baris, membuka halaman Detail Tiket.
- Grafik **"Jml Progress per Jatuh Tempo"** menampilkan sisa baris yang belum diidentifikasi, dikelompokkan per hari-jatuh-tempo dan per PIC PIDE (satu garis per PIC, warna tetap per orang) — alat pemantauan, bukan aksi yang mengubah data.
- Tidak ada tombol ekspor Excel/PDF di halaman ini.
- Aksi yang mengubah status tiket (Proses Identifikasi, Kembalikan ke P3DE, Transfer ke PMDE) **tidak** tersedia di halaman ini — lihat `status_tiket_flow.md` dan panduan Detail Tiket.

#### Akses

Diverifikasi dari `views/identifikasi.py`. Akses halaman (`IdentifikasiView.test_func`) dan endpoint data tabel (`identifikasi_data`, lewat `@user_passes_test`) memakai fungsi lokal `_is_pide_user` yang sama: **superuser, staff (`is_staff`), atau anggota grup `user_pide`, `admin`, `admin_pide`, atau `kasi_pide`.** View ini tidak memakai mixin bersama `UserPIDERequiredMixin`/`AdminPIDERequiredMixin` dari `views/mixins.py` — ia mendefinisikan pengecekannya sendiri, yang cakupan grupnya lebih luas (menambahkan `kasi_pide`, `is_staff`, dan `is_superuser` yang tidak ada pada mixin bersama tersebut).

Ini sejalan dengan navbar (`admin_pide`, `user_pide`, `kasi_pide` melihat tautannya) dan dengan RBAC_MATRIX.md, yang mencatat menu "Identifikasi" sebagai PIDE ✅ / P3DE ❌ / PMDE ❌ — tidak ada perbedaan untuk **akses halaman**.

> **Catatan tambahan (tidak disebutkan RBAC_MATRIX.md):** akses halaman berbeda dari cakupan **data** yang terlihat. RBAC_MATRIX.md hanya menyebut kasi secara umum ("kasi tidak dibatasi pada tiket tempat mereka menjadi PIC aktif") tanpa merinci menu Identifikasi secara khusus. Dari kode, cakupan "lihat semua" pada menu ini benar-benar hanya diberikan ke grup `kasi_pide`, sebagaimana dijelaskan pada bagian Kriteria di atas.

---

### Laporan SLA Perekaman

Laporan ini mengukur **kecepatan PIDE membuka tiket yang sudah dikirim P3DE** — selisih hari antara tiket dikirim ke PIDE dan PIDE mulai mencatat/memproses identifikasinya (aksi Proses Identifikasi, lihat `status_tiket_flow.md` bagian 4). Istilah "Perekaman" di judul menu ini merujuk ke PIDE merekam mulainya identifikasi, **bukan** ke P3DE merekam penerimaan data — jangan tertukar dengan menu "Rekam Penerimaan Data" milik P3DE. Berbeda dari halaman Identifikasi yang berupa antrian kerja real-time, laporan ini adalah **rekapitulasi historis** atas rentang tanggal pilihan pengguna, dan bisa diekspor ke Excel.

#### Kriteria/Data yang Ditampilkan

- Satu baris = satu tiket. Sumber datanya adalah **seluruh tiket di sistem**, tidak dipersempit berdasarkan siapa PIC-nya maupun apakah pengguna kasi/pelaksana — berbeda dari halaman Identifikasi, laporan ini **tidak** menerapkan pembatasan "hanya tiket saya" untuk siapa pun yang berhak membukanya.
- Baris hanya muncul bila tanggal tiket dikirim ke PIDE berada pada rentang **Tanggal Mulai – Tanggal Akhir** yang dipilih (lihat Filter). Tiket yang belum pernah dikirim ke PIDE otomatis tidak pernah muncul, tanpa perlu filter status terpisah.
- Diurutkan berdasarkan tanggal kirim ke PIDE, dari yang paling lama.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP sumber data |
| Jenis Data | Jenis data ILAP dari sub jenis data tiket |
| Subjenis Data | Nama sub jenis data tiket |
| Tabel Bank Data | Nama tabel dari sub jenis data tiket |
| Nomor Tiket | Nomor tiket |
| Tanggal Terima PIDE | Tanggal P3DE mengirim tiket ke PIDE |
| Tanggal Mulai Identifikasi | Tanggal PIDE mulai mencatat/memproses identifikasi |
| SLA Perekaman | Selisih hari dari Tanggal Terima PIDE ke Tanggal Mulai Identifikasi, dihitung inklusif (hari yang sama dihitung 1 hari); kosong bila salah satu tanggal belum terisi |

#### Filter/Pencarian

- **Tanggal Mulai** dan **Tanggal Akhir** — wajib diisi, default ke rentang bulan berjalan saat halaman dibuka; menyaring berdasarkan tanggal tiket dikirim ke PIDE.
- **Nama ILAP**, **Jenis Data**, **Subjenis Data**, **Nama Tabel** — empat dropdown berjenjang yang saling menyempitkan (didukung endpoint bersama `laporan_pide_filter_options`, dipakai oleh keempat laporan PIDE ini). Catatan: dropdown *Jenis Data* memilih satu baris Jenis Data ILAP yang spesifik (pilihannya ditampilkan memakai nama sub jenis data agar mudah dikenali), sedangkan dropdown *Subjenis Data* mencocokkan berdasarkan teks nama sub jenis data sehingga bisa mencakup lebih dari satu ILAP yang kebetulan memakai nama sub jenis data yang sama.

#### Aksi

- **Ekspor ke Excel** — mengunduh seluruh baris yang sesuai filter aktif (tidak dibatasi oleh paginasi tabel di layar) sebagai berkas .xlsx dengan kolom yang sama seperti tabel. Tombol baru aktif setelah tabel menampilkan minimal satu baris hasil filter.

#### Akses

Diverifikasi dari `views/laporan_sla_perekaman.py`. Fungsi lokal `_is_pide_user` dipakai konsisten oleh halaman (`LaporanSLAPerekamanView.test_func`), endpoint data (`laporan_sla_perekaman_data`), dan endpoint ekspor (`laporan_sla_perekaman_export`): **superuser, staff, atau anggota grup `user_pide`, `admin`, atau `admin_pide`.** Grup `user_p3de` **tidak** termasuk di kode manapun pada file ini — juga tidak ada pengecualian untuk `kasi_pide`.

> Meskipun namanya menyebut "Perekaman" — istilah yang biasanya identik dengan P3DE — menu ini murni milik PIDE: `navbar.html` menaruh tautannya di blok menu PIDE, dan `RBAC_MATRIX.md` mencantumkannya sebagai PIDE ✅ / P3DE ❌. "Perekaman" di sini merujuk ke PIDE mencatat mulainya identifikasi, bukan ke P3DE merekam penerimaan data — lihat penjelasan di paragraf pembuka di atas.

---

### Laporan SLA Identifikasi

Laporan ini mengukur **lama waktu PIDE benar-benar mengidentifikasi data**, yaitu selisih hari sejak PIDE mulai mencatat/memproses identifikasi hingga tiket ditransfer ke PMDE (aksi Transfer ke PMDE, lihat `status_tiket_flow.md` bagian 6). Bila Laporan SLA Perekaman mengukur waktu tunggu sebelum PIDE membuka tiket, laporan ini mengukur waktu pengerjaan identifikasinya sendiri.

#### Kriteria/Data yang Ditampilkan

- Sama seperti Laporan SLA Perekaman: satu baris = satu tiket, sumber data seluruh tiket di sistem, tidak dibatasi berdasarkan PIC/kasi/pelaksana.
- Baris hanya muncul bila tanggal PIDE mulai mencatat/memproses identifikasi berada pada rentang **Tanggal Mulai – Tanggal Akhir** yang dipilih — tiket yang belum mulai diidentifikasi tidak pernah muncul.
- Diurutkan berdasarkan Tanggal Mulai Identifikasi, sama seperti kolom yang dipakai untuk menyaring rentang tanggal di atas.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP sumber data |
| Jenis Data | Jenis data ILAP dari sub jenis data tiket |
| Subjenis Data | Nama sub jenis data tiket |
| Tabel Bank Data | Nama tabel dari sub jenis data tiket |
| Nomor Tiket | Nomor tiket |
| Tanggal Mulai Identifikasi | Tanggal PIDE mulai mencatat/memproses identifikasi |
| Tanggal Transfer | Tanggal tiket ditransfer ke PMDE |
| SLA Identifikasi | Selisih hari dari Tanggal Mulai Identifikasi ke Tanggal Transfer, dihitung inklusif; kosong bila salah satu tanggal belum terisi |

#### Filter/Pencarian

Sama persis dengan Laporan SLA Perekaman: **Tanggal Mulai/Tanggal Akhir** (wajib diisi, default bulan berjalan, kali ini menyaring berdasarkan tanggal mulai identifikasi), ditambah **Nama ILAP, Jenis Data, Subjenis Data, Nama Tabel** yang berjenjang lewat endpoint bersama `laporan_pide_filter_options`.

#### Aksi

Sama seperti Laporan SLA Perekaman: **Ekspor ke Excel** atas baris sesuai filter aktif, tombol aktif setelah ada minimal satu baris hasil.

#### Akses

Diverifikasi dari `views/laporan_sla_identifikasi.py` — fungsi lokal `_is_pide_user` identik dengan Laporan SLA Perekaman: superuser, staff, atau grup `user_pide`/`admin`/`admin_pide` (dipakai konsisten di halaman, endpoint data, dan endpoint ekspor). Grup `kasi_pide` dan `user_p3de` tidak termasuk.

Ini **sesuai** dengan RBAC_MATRIX.md, yang mencatat menu ini sebagai PIDE ✅ / P3DE ❌ / PMDE ❌ — tidak ditemukan perbedaan untuk menu ini.

---

### Laporan Transfer

Laporan ini merekap **hasil identifikasi pada saat tiket ditransfer ke PMDE** — berapa banyak baris data yang berhasil diidentifikasi dibanding yang tidak, per tiket (data yang sama dengan yang dicatat PIC PIDE saat menjalankan aksi Transfer ke PMDE, lihat `status_tiket_flow.md` bagian 6). Laporan ini menjawab "dari data yang diterima P3DE, berapa persen yang berhasil diidentifikasi PIDE" untuk setiap tiket yang sudah melewati tahap transfer.

#### Kriteria/Data yang Ditampilkan

- Satu baris = satu tiket; sumber data seluruh tiket di sistem, tidak dibatasi PIC/kasi/pelaksana (sama seperti kedua laporan SLA di atas).
- Baris hanya muncul bila tanggal tiket ditransfer ke PMDE berada pada rentang **Tanggal Mulai – Tanggal Akhir** yang dipilih — dengan kata lain, hanya tiket yang sudah pernah ditransfer ke PMDE (status Pengendalian Mutu atau lebih lanjut) yang bisa tampil.
- Diurutkan berdasarkan tanggal transfer, dari yang paling lama.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP sumber data |
| Jenis Data | Jenis data ILAP dari sub jenis data tiket |
| Subjenis Data | Nama sub jenis data tiket |
| Tabel Bank Data | Nama tabel dari sub jenis data tiket |
| Nomor Tiket | Nomor tiket |
| Tanggal Transfer | Tanggal tiket ditransfer ke PMDE |
| Jumlah Data Teridentifikasi | Baris I (hasil identifikasi) — **hanya dihitung** bila Jenis Tabel dari sub jenis data tiket tergolong "Diidentifikasi"; untuk jenis tabel lain, kolom ini bernilai 0 |
| Jumlah Data Tidak Teridentifikasi | Baris U (Update) — selalu ditampilkan apa adanya, tidak bergantung Jenis Tabel |
| Jumlah Data Tidak Diidentifikasi | Baris I juga, tapi **hanya dihitung** bila Jenis Tabel dari sub jenis data tiket tergolong "Tidak Diidentifikasi"; untuk jenis tabel lain, kolom ini bernilai 0 |
| Jumlah Data Masuk | Jumlah baris data lengkap hasil penelitian P3DE |
| Persentase | Baris I dibagi Jumlah Data Masuk, dikali 100%; kosong bila Jumlah Data Masuk sama dengan 0 |
| Keterangan | Kolom ini selalu kosong pada versi sistem saat ini — tidak diisi otomatis oleh proses apa pun (tampaknya disediakan untuk anotasi manual di masa depan) |

> Karena "Jumlah Data Teridentifikasi" dan "Jumlah Data Tidak Diidentifikasi" ditentukan oleh Jenis Tabel sub jenis data (bukan oleh isi barisnya sendiri), tiket yang sub jenis datanya tergolong Jenis Tabel selain "Diidentifikasi"/"Tidak Diidentifikasi" (mis. "Tidak Terstruktur") akan menampilkan 0 pada **kedua** kolom tersebut sekaligus, walau baris identifikasinya sebenarnya terisi.

#### Filter/Pencarian

Sama seperti dua laporan SLA — **Tanggal Mulai/Tanggal Akhir** (menyaring tanggal transfer, wajib diisi, default bulan berjalan), ditambah **Nama ILAP, Jenis Data, Subjenis Data, Nama Tabel** berjenjang.

#### Aksi

**Ekspor ke Excel** atas baris sesuai filter aktif (nama berkas hasil unduhan memakai stempel waktu saat diunduh, bukan rentang tanggal filter yang dipilih).

#### Akses

Diverifikasi dari `views/laporan_transfer.py` — fungsi lokal `_is_pide_user` identik dengan dua laporan SLA: superuser, staff, atau grup `user_pide`/`admin`/`admin_pide`. Grup `kasi_pide` dan `user_p3de` tidak termasuk.

Ini **sesuai** dengan RBAC_MATRIX.md (Laporan Transfer: PIDE ✅ / P3DE ❌ / PMDE ❌) — tidak ditemukan perbedaan untuk menu ini.

---

### Laporan Metrik Data Eksternal

Laporan ini adalah "saudara dekat" Laporan Transfer — sumber data dan tanggal penyaringnya sama (tanggal transfer ke PMDE) — tetapi disajikan sebagai **rekap metrik hasil pengolahan** per tiket: seberapa besar data yang teridentifikasi, tidak teridentifikasi, tidak diidentifikasi, dan residu, tanpa menonjolkan tanggal transfer maupun kolom catatan manual.

#### Kriteria/Data yang Ditampilkan

- Satu baris = satu tiket; sumber data seluruh tiket di sistem, tidak dibatasi PIC/kasi/pelaksana.
- Baris hanya muncul bila tanggal tiket ditransfer ke PMDE berada pada rentang **Tanggal Mulai – Tanggal Akhir** yang dipilih — sama seperti Laporan Transfer, walaupun tanggal transfer itu sendiri tidak ditampilkan sebagai kolom pada tabel ini.
- Diurutkan berdasarkan tanggal transfer, dari yang paling lama.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP sumber data |
| Jenis Data | Jenis data ILAP dari sub jenis data tiket |
| Subjenis Data | Nama sub jenis data tiket |
| Tabel Bank Data | Nama tabel dari sub jenis data tiket |
| Nomor Tiket | Nomor tiket |
| Jumlah Data Masuk | Jumlah baris data lengkap hasil penelitian P3DE |
| Jumlah Data Teridentifikasi | Baris I — hanya dihitung bila Jenis Tabel sub jenis data tergolong "Diidentifikasi"; selain itu 0 (aturan sama seperti Laporan Transfer) |
| Jumlah Data Tidak Teridentifikasi | Baris U (Update), selalu ditampilkan apa adanya |
| Jumlah Data Tidak Diidentifikasi | Baris I — hanya dihitung bila Jenis Tabel tergolong "Tidak Diidentifikasi"; selain itu 0 |
| Jumlah Data Res | Baris Res (Residual) hasil identifikasi |
| Persentase | Baris I dibagi Jumlah Data Masuk, dikali 100%; kosong bila Jumlah Data Masuk sama dengan 0 |

Dibanding Laporan Transfer, laporan ini menambahkan kolom **Jumlah Data Res** tetapi tidak menampilkan Tanggal Transfer maupun Keterangan — lebih berorientasi ke metrik hasil pengolahan per tiket daripada catatan waktu transfernya.

#### Filter/Pencarian

Sama seperti Laporan Transfer — **Tanggal Mulai/Tanggal Akhir** (menyaring tanggal transfer meski tidak ditampilkan sebagai kolom, wajib diisi, default bulan berjalan), ditambah **Nama ILAP, Jenis Data, Subjenis Data, Nama Tabel** berjenjang.

#### Aksi

**Ekspor ke Excel** atas baris sesuai filter aktif — berkas berjudul sheet "Laporan Metrik Data Eksternal" dan nama berkas diawali `Laporan_Metrik_Data_Eksternal_...`.

#### Akses

Diverifikasi dari `views/laporan_metrik_data_eksternal.py` — fungsi lokal `_is_pide_user` identik dengan tiga laporan PIDE lainnya: superuser, staff, atau grup `user_pide`/`admin`/`admin_pide`. Grup `kasi_pide` dan `user_p3de` tidak termasuk.

Ini **sesuai** dengan RBAC_MATRIX.md (Metrik Data Eksternal: PIDE ✅ / P3DE ❌ / PMDE ❌) — tidak ditemukan perbedaan untuk menu ini.

---

### Catatan Umum Lintas Menu

- **Filter kaskade bersama:** keempat laporan PIDE di atas (SLA Perekaman, SLA Identifikasi, Transfer, Metrik Data Eksternal) berbagi satu endpoint (`laporan_pide_filter_options`) untuk mengisi ulang pilihan dropdown ILAP/Jenis Data/Subjenis Data/Nama Tabel setiap kali salah satunya diubah. Endpoint ini memakai pengecekan akses yang sama (`user_pide`/`admin`/`admin_pide`, plus staff/superuser) seperti keempat laporan tersebut.
- **Tidak ada mixin bersama yang dipakai:** kelima menu PIDE di atas (termasuk Identifikasi) tidak memakai mixin siap pakai `UserPIDERequiredMixin`/`AdminPIDERequiredMixin` dari `views/mixins.py`. Masing-masing view mendefinisikan fungsi `_is_pide_user` sendiri secara lokal — hampir sama isinya di keempat laporan, tetapi khusus halaman Identifikasi cakupan grupnya sedikit lebih luas (menambahkan `kasi_pide`).
- **`kasi_pide` hanya diistimewakan di halaman Identifikasi.** Baik untuk *akses membuka halaman* maupun *cakupan data*, grup `kasi_pide` hanya disebutkan secara eksplisit pada `views/identifikasi.py`. Keempat laporan PIDE tidak mencantumkan `kasi_pide` sama sekali pada pengecekan aksesnya — seorang kasi PIDE yang tidak juga menjadi anggota `admin`/`admin_pide`/`user_pide` (atau staff/superuser) akan ditolak (403) saat mencoba membuka keempat laporan tersebut.

## Menu PMDE

Menu-menu berikut muncul pada blok **PMDE** di navbar, untuk role `admin_pmde`, `user_pmde`, dan (khusus menu Quality Control) `kasi_pmde`. PMDE (Pengendalian Mutu Data Eksternal) memeriksa kualitas data yang sudah diidentifikasi PIDE — tahap akhir alur kerja tiket. Menu **PIC PMDE** dan **Durasi Jatuh Tempo PMDE** tidak dibahas di sini karena sudah didokumentasikan lengkap di [Panduan Menu Admin](ADMIN_MENU_GUIDE.md).

---


### Quality Control

Quality Control adalah halaman kerja utama PMDE: daftar antrean seluruh tiket yang sedang berada pada status **Pengendalian Mutu (6)** — yaitu tiket yang sudah selesai diidentifikasi PIDE dan ditransfer ke PMDE untuk diperiksa kualitasnya (lihat `status_tiket_flow.md` bagian 6 dan 7). Halaman ini dibangun di atas komponen "seksi queue" yang sama dengan halaman **Identifikasi** milik PIDE — filter panel, ringkasan beban kerja, grafik, dan tabel tiket mengikuti pola yang identik, hanya datanya yang berbeda (antrean PMDE, PIC PMDE, dan tenggat dihitung dari tanggal transfer PMDE, bukan tanggal kirim ke PIDE). Halaman ini adalah titik pantau sebelum PIC benar-benar menuntaskan tiket: aksi penyelesaian tiket sendiri (**Selesaikan Tiket**) tidak dilakukan di sini, melainkan lewat modal pada halaman Detail Tiket (lihat `status_tiket_flow.md` bagian 7).

#### Kriteria/Data yang Ditampilkan

- Baris default: seluruh tiket berstatus **Pengendalian Mutu (6)**.
- Cakupan (scope) tiket yang terlihat, diverifikasi dari `_pmde_scope()` di `views/quality_control.py` (memanggil `seksi_queue.pic_scope` dengan helper `is_kasi_pmde`):
  - **Kasi PMDE** (grup `kasi_pmde`), serta anggota `admin`/`admin_pmde`/superuser, melihat **seluruh** tiket Pengendalian Mutu tanpa batas — tidak harus menjadi PIC.
  - **Pelaksana PMDE** (grup `user_pmde` yang bukan kasi/admin) hanya melihat tiket yang penugasan **PIC PMDE aktif**-nya adalah dirinya sendiri.
- Tabel diurutkan **naik menurut kolom Jatuh Tempo** secara default, sehingga tiket paling mendesak (tenggat paling dekat, atau sudah lewat) tampil paling atas.
- **Konsep "Jatuh Tempo" (tenggat) tiket** — ini definisi acuan yang juga dipakai kartu "Dalam Proses Pengendalian Mutu" di halaman Home (tombol filter *&lt;10 hari* dan *&lt;30 hari*) lewat fungsi `jatuh_tempo_ids()` yang diekspor modul ini, sehingga angka pada kedua halaman tidak pernah berbeda. Cara hitungnya:
  1. **Tanggal dasar** — tanggal Transfer (`tgl_transfer`, saat PIDE mentransfer tiket ke PMDE); apabila tiket punya **tanggal Rematch** (`tgl_rematch`) yang terisi, tanggal dasar berpindah ke tanggal rematch tersebut, seakan hitung mundur dimulai ulang. Rematch adalah kejadian dari data sinkronisasi (Oracle), bukan aksi yang dijalankan pengguna di aplikasi ini.
  2. **Durasi** — durasi hari yang berlaku diambil dari tabel referensi **Durasi Jatuh Tempo PMDE** (dikelola admin PMDE, lihat `ADMIN_MENU_GUIDE.md`) untuk Sub Jenis Data tiket tersebut, yang masa berlakunya (`start_date`–`end_date`) mencakup tanggal dasar di atas.
  3. **Deadline** = tanggal dasar + durasi. **Jatuh Tempo** = Deadline − hari ini (bisa negatif, artinya sudah lewat tenggat).
  4. Bila tidak ada baris Durasi Jatuh Tempo PMDE yang berlaku pada tanggal dasar tiket, Deadline dan Jatuh Tempo ditampilkan **"-"** (bukan dianggap "jatuh tempo hari ini").
  - Home hanya memakai dua dari tiga ambang yang tersedia pada filter halaman ini (10 dan 30 hari); ambang 60 hari hanya ada di sini.
  - **Catatan:** ambang pewarnaan baris tabel (lihat bagian Aksi/tampilan di bawah) memakai batas 7/30 hari, sedikit berbeda dari pilihan filter dropdown Jatuh Tempo (10/30/60 hari) — keduanya independen, jangan disamakan.
- **Ringkasan "Beban Kerja"** di atas grafik bukan bagian dari tabel utama, melainkan rekap terpisah per PIC PMDE, mengikuti filter yang sama dengan tabel. Satu baris per PIC (termasuk baris "Tanpa PIC PMDE" untuk tiket yang belum ditugaskan), dengan lima kelompok kolom:
  - **Proses QC** — baris data tiket yang sedang ada di antrean ini (`belum_qc`).
  - **Masih di P3DE** dan **Masih di PIDE** — pekerjaan yang belum sampai ke PMDE tetapi sudah menjadi tanggung jawab PIC PMDE tersebut (PIC PMDE ditugaskan sejak tiket direkam, bukan baru saat transfer), supaya terlihat beban yang akan datang.
  - **Selesai QC 90 Hari Terakhir** dan **Selesai QC 1 Tahun Terakhir** — tiket yang PIC tersebut selesaikan QC-nya dalam jendela waktu tersebut (dihitung dari riwayat aksi Selesai, bukan kolom tanggal), sebagai gambaran kecepatan kerja. Jendela 90 hari bersarang di dalam jendela 1 tahun (tiket yang baru selesai dihitung di kedua kolom).
  - Setiap kelompok dapat dipecah lebih lanjut menurut **Jenis Tabel** dan **Kategori Wilayah** lewat tombol **Tampilkan Detail** pada judul kartu.
  - Kolom **Indeks Beban** adalah skor komposit (bukan sekadar jumlah baris) dengan rumus yang ditampilkan langsung di halaman lewat tombol ⓘ: `Indeks Beban = Σ (baris data × bobot jenis tabel × bobot kategori wilayah × bobot prioritas × bobot jatuh tempo × bobot antrean)`. Secara umum: data yang **Diidentifikasi** dibobot lebih berat daripada yang **Tidak Diidentifikasi/Tidak Terstruktur**; ILAP **Regional** dibobot lebih berat dari **Nasional/Internasional**; data yang berstatus **prioritas** saat diterima dibobot 1,5×; baris yang tenggatnya makin dekat dibobot makin berat; dan kelima kelompok kolom di atas dibobot berbeda menurut seberapa dekat pekerjaan itu ke tangan PIC (Proses QC terberat, lalu Masih di PIDE, Masih di P3DE, dan kedua kolom Selesai paling ringan). Tabel dibuka terurut menurun berdasarkan Indeks Beban ini (kolom lain juga bisa diklik untuk mengurutkan ulang).
  - Baris ringkasan selalu dikelompokkan **per PIC PMDE pelaksana**, bukan per penampil — kasi PMDE yang membuka halaman ini tetap melihat rincian per-pelaksana, bukan hanya total unit.

#### Kolom/Field

Tabel utama (kartu "Daftar Tiket Pengendalian Mutu") memiliki 12 kolom:

| Kolom | Keterangan |
|---|---|
| Nama Tabel | Nama tabel data pada Sub Jenis Data tiket (field "Nama Tabel I"). |
| PIC PMDE | Nama pelaksana PMDE yang aktif ditugaskan pada tiket; ditautkan ke halaman Profil PIC bila pengguna yang membuka berhak melihatnya (admin, atau kasi/anggota unit yang sama, atau dirinya sendiri), teks biasa jika tidak; kosong bila belum ada PIC aktif. |
| Nomor Tiket / Sub Jenis Data | Dua baris dalam satu sel: nomor tiket di atas, nama Sub Jenis Data di bawah. |
| Nama ILAP / Jenis Tabel | Nama ILAP di atas, Jenis Tabel (Diidentifikasi/Tidak Diidentifikasi/Tidak Terstruktur) di bawah. |
| Tgl Transfer / Tgl Rematch | Tanggal PIDE mentransfer tiket ke PMDE, dan tanggal rematch bila ada (lihat penjelasan Jatuh Tempo di atas). |
| Deadline | Tanggal jatuh tempo hasil perhitungan (tanggal dasar + durasi); "-" bila tidak ada Durasi Jatuh Tempo PMDE yang berlaku. |
| Jatuh Tempo | Sisa hari sampai Deadline, dihitung dari hari ini; bisa negatif (sudah lewat tenggat). Baris tabel diwarnai menurut nilai ini: **merah** jika kurang dari 7 hari (termasuk yang sudah lewat), **kuning** jika 7–29 hari, **hijau** jika 30 hari atau lebih. |
| Prioritas | Ya/Tidak — Ya apabila Sub Jenis Data tiket tercatat sebagai Data Prioritas (referensi P3DE) yang masa berlakunya mencakup tanggal terima DIP tiket tersebut. |
| Jml Baris I | Jumlah baris hasil identifikasi (baris I) yang perlu diperiksa QC, dicatat PIDE saat Transfer ke PMDE. |
| Jml Selesai | Jumlah baris yang sudah diperiksa QC sejauh ini. |
| Jml Progress | Sisa baris yang belum diperiksa QC — inilah angka yang dipakai kartu Home "Dalam Proses Pengendalian Mutu" dan grafik di halaman ini. |
| Aksi | Tombol "Lihat Detail" menuju halaman Detail Tiket. |

Nilai Jml Selesai/Jml Progress diperbarui melalui proses back-end (rekonsiliasi/sinkronisasi data), bukan diisi manual dari halaman ini; penyelesaian akhirnya tetap dikonfirmasi lewat aksi **Selesaikan Tiket** pada Detail Tiket, yang mewajibkan `Lolos QC + Tidak Lolos QC = Jml Baris I`.

#### Filter/Pencarian

Panel filter (accordion, terlipat secara default, otomatis terbuka bila datang dari tautan berisi filter atau bila ada filter aktif) menyediakan dropdown multi-pilih berikut, saling menyempitkan pilihan satu sama lain: Nomor Tiket, Tahun, Periode, Periode Pengiriman, Periode Penerimaan, PIC P3DE, PIC PIDE, PIC PMDE, Kategori ILAP, ILAP, Jenis Data, Sub Jenis Data, Nama Tabel, Kanwil, KPP, Kategori Wilayah, Jenis Tabel, Dasar Hukum, Status Penelitian, Status Ketersediaan Data, Permintaan Khusus (Special Request), Prioritas, dan **Jatuh Tempo** (opsi tetap: &lt;10 hari, &lt;30 hari, &lt;60 hari — tidak dibaca dari data karena selalu relevan ditanyakan meski hasilnya kosong).

Halaman ini **tidak** memiliki kotak pencarian bebas (fitur pencarian bawaan DataTables dimatikan) — semua penyaringan dilakukan lewat panel filter di atas. Pilihan filter tersimpan di penyimpanan lokal peramban sehingga bertahan antar-kunjungan.

#### Aksi

- **Lihat Detail** (ikon mata) pada setiap baris — membuka halaman Detail Tiket. Aksi yang mengubah status tiket (**Selesaikan Tiket**, memindahkan status dari Pengendalian Mutu (6) ke Selesai (8)) dilakukan di sana lewat modal, bukan di halaman daftar ini.
- Tombol **Tampilkan/Sembunyikan Detail** pada kartu Beban Kerja — memperluas/melipat rincian per Jenis Tabel dan Kategori Wilayah di bawah setiap baris PIC.
- Tombol ⓘ di header kolom Indeks Beban — membuka panel penjelasan rumus dan bobot (lihat bagian Kriteria di atas), bersifat informatif saja.
- Grafik "Jml Progress per Jatuh Tempo" — satu garis per PIC PMDE (plus garis abu-abu putus-putus untuk "Tanpa PIC PMDE"), menunjukkan total baris yang masih harus diperiksa (Jml Progress) pada tiap nilai Jatuh Tempo; ikut menyesuaikan saat filter diubah.
- **Tidak ada** ekspor Excel/PDF pada halaman ini.

#### Akses

Diverifikasi dari `QualityControlView.test_func()` di `views/quality_control.py`, yang memanggil `_is_pmde_user()`:

```python
def _is_pmde_user(user):
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde', 'kasi_pmde']
    ).exists()
```

Jadi akses sebenarnya: superuser, pengguna dengan flag `is_staff` (flag bawaan Django, lepas dari grup), atau anggota grup `user_pmde`, `admin`, `admin_pmde`, **atau `kasi_pmde`**. Endpoint data (`quality_control_data`) memakai pemeriksaan yang sama lewat `@user_passes_test(_is_pmde_user)`. Ini sejalan dengan `navbar.html` (baris ~134–143), yang menampilkan tautan Quality Control untuk `admin_pmde`, `user_pmde`, maupun `kasi_pmde` — sesuai komentar navbar bahwa Kasi PMDE mendapat halaman ini tanpa batas cakupan, bukan menu-menu lain di bawahnya (PIC PMDE, Laporan).

> Hanya PMDE dan admin global yang diizinkan — bukan PIDE, meskipun keduanya bertetangga langsung dalam alur kerja (PIDE mengidentifikasi, lalu mentransfer ke PMDE untuk QC). `RBAC_MATRIX.md` sudah diperbarui agar tidak lagi mencantumkan PIDE pada baris Quality Control.

---

### Laporan Pengendalian Mutu

Laporan ini adalah rekap periodik seluruh tiket yang **pernah ditransfer ke PMDE** pada suatu rentang waktu, lengkap dengan rincian hasil QC-nya per kode klasifikasi. Berbeda dari halaman Quality Control (yang menampilkan antrean kerja yang *sedang* berjalan dan dibatasi ke PIC aktif), laporan ini adalah alat pelaporan: cakupannya seluruh tiket unit PMDE pada periode terpilih, tanpa membatasi berdasarkan siapa PIC-nya, dan tanpa membatasi status tiket saat ini (tiket yang sudah Selesai (8) pun tetap muncul selama tanggal transfer-nya masuk periode yang dipilih).

#### Kriteria/Data yang Ditampilkan

- Tabel tetap kosong sampai pengguna memilih **ketiga** filter (Jenis Periode, Periode, dan Tahun) — data baru dimuat setelah semuanya terisi.
- Baris yang ditampilkan: tiket dengan **Tanggal Transfer** (`tgl_transfer`, tanggal PIDE mentransfer ke PMDE) yang jatuh pada rentang tanggal hasil perhitungan Jenis Periode + Periode + Tahun. Empat jenis periode yang bisa dipilih: **Bulanan** (1 bulan), **Triwulanan** (3 bulan), **Semester** (6 bulan), **Tahunan** (1 tahun penuh).
- **Tidak dibatasi PIC** — setiap pengguna yang berhak membuka laporan ini melihat seluruh tiket PMDE pada periode tersebut, bukan hanya tiket miliknya.
- **Tidak dibatasi status tiket** — status tiket saat ini ditampilkan sebagai kolom informasi, bukan sebagai filter.
- Urutan default: menurut Nomor Tiket menaik (kolom lain tetap bisa diklik untuk mengurutkan ulang).

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP asal data. |
| Nama Sub Jenis Data | Sub Jenis Data ILAP tiket. |
| Nama Tabel | Nama tabel (field "Nama Tabel I" pada Sub Jenis Data). |
| Nomor Tiket | Nomor tiket. |
| Status Tiket | Status tiket **saat laporan dibuka** (bisa berbeda dari status ketika tiket ditransfer — mis. tiket yang sudah Selesai tetap tercatat di sini karena transfer-nya jatuh pada periode terpilih). |
| Data Diterima | Jumlah baris diterima P3DE (`baris_diterima`). |
| Data Direkam (I+U) | Total baris I + baris U hasil rekam PIDE. |
| Data Teridentifikasi (I) | Jumlah baris I (hasil identifikasi). |
| Data Tidak Teridentifikasi (U) | Jumlah baris U (update/tidak teridentifikasi). |
| Lolos QC / Tidak Lolos QC | Hasil akhir QC yang direkam lewat aksi Selesaikan Tiket. |
| QC P, QC X, QC W, QC V, QC A, QC N, QC Y, QC Z, QC D, QC U, QC C | Sebelas kolom jumlah baris menurut kode klasifikasi hasil QC yang tercatat pada tiket. |

**Catatan tentang kolom klasifikasi QC:** dari sebelas kode di atas, hanya **QC C** yang diisi lewat aksi Selesaikan Tiket di aplikasi ini (bersama Sudah QC/Lolos QC/Tidak Lolos QC — lihat `forms/selesaikan_tiket.py`). Sepuluh kode lainnya (P, X, W, V, A, N, Y, Z, D, U) bukan bagian dari form aksi tersebut, sehingga nilainya berasal dari sumber data lain (migrasi/sinkronisasi), bukan diisi manual dari halaman PMDE mana pun yang dibahas dalam dokumen ini.

#### Filter/Pencarian

- **Jenis Periode** — Bulanan/Triwulanan/Semester/Tahunan.
- **Periode** — pilihannya menyesuaikan Jenis Periode (nama bulan; Triwulan 1–4; Semester 1–2; atau "Seluruh Tahun" untuk Tahunan).
- **Tahun** — daftar tahun yang benar-benar ada pada data tiket, ditambah tahun berjalan.
- Ketiganya **wajib** diisi sebelum tabel memuat data.
- Kotak pencarian umum ("Cari:") tetap tampil di atas tabel (bawaan komponen tabel aplikasi), namun **tidak berfungsi** pada laporan ini — kata kunci yang diketik di sana tidak diteruskan ke server dan tidak memengaruhi hasil. Penyaringan hanya berlaku lewat tiga dropdown periode di atas.

#### Aksi

- **EKSPOR KE EXCEL** — tombol di kartu filter, aktif hanya setelah tabel berisi data untuk periode terpilih. Mengunduh berkas `.xlsx` berisi seluruh baris hasil (bukan hanya halaman yang sedang tampil) dengan kolom yang sama seperti tabel, dengan nama berkas `Laporan_Pengendalian_Mutu_<Periode>.xlsx`.
- Tidak ada tombol aksi per baris (tidak ada tautan "Lihat Detail" pada laporan ini).
- Tidak ada ekspor PDF.

#### Akses

Diverifikasi dari `LaporanPengendalianMutuView.test_func()` di `views/laporan_pengendalian_mutu.py`, memanggil `_is_pmde_user()`:

```python
def _is_pmde_user(user):
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde']
    ).exists()
```

Akses: superuser, `is_staff`, atau anggota `user_pmde`/`admin`/`admin_pmde`. **`kasi_pmde` tidak termasuk** — berbeda dari halaman Quality Control. Ini konsisten dengan `navbar.html`: submenu "Laporan" yang memuat tautan ini (baris ~145–165) hanya dirender untuk `admin_pmde` atau `user_pmde`, tidak untuk `kasi_pmde` (lihat komentar navbar di atasnya: kasi PMDE hanya mendapat Quality Control). Baris "Pengendalian Mutu" pada tabel Laporan di `RBAC_MATRIX.md` (PMDE ✅, P3DE/PIDE ❌) sudah sesuai dengan temuan ini — **tidak ada ketidaksesuaian** untuk menu ini.

---

### Laporan Kelengkapan Data

Laporan ini adalah versi ringkas dari Laporan Pengendalian Mutu, difokuskan pada satu angka saja per tiket: jumlah baris dengan klasifikasi **QC C ("Kelengkapan")**. Kegunaannya melengkapi Laporan Pengendalian Mutu dengan tampilan yang lebih sederhana ketika yang ingin dipantau hanya kelengkapan data hasil QC, bukan seluruh sebelas kode klasifikasi.

#### Kriteria/Data yang Ditampilkan

- Sama seperti Laporan Pengendalian Mutu: baris adalah tiket dengan **Tanggal Transfer** (`tgl_transfer`) pada rentang Jenis Periode + Periode + Tahun yang dipilih; ketiganya wajib diisi lebih dulu.
- **Tidak dibatasi PIC** dan **tidak dibatasi status tiket saat ini** — sama seperti Laporan Pengendalian Mutu.
- Urutan default: menurut Data Diterima menurun (terbesar lebih dulu).

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| Nama ILAP | ILAP asal data. |
| Nama Sub Jenis Data | Sub Jenis Data ILAP tiket. |
| Nama Tabel | **Berbeda dari kolom "Nama Tabel" di Quality Control maupun Laporan Pengendalian Mutu** — di laporan ini kolom tersebut bersumber dari deskripsi **Jenis Tabel** (Diidentifikasi/Tidak Diidentifikasi/Tidak Terstruktur), bukan dari field "Nama Tabel I" pada Sub Jenis Data. |
| Nomor Tiket | Nomor tiket. |
| Status Tiket | Status tiket saat laporan dibuka. |
| Data Diterima | Jumlah baris diterima P3DE (`baris_diterima`). |
| QC C (Kelengkapan) | Jumlah baris dengan klasifikasi QC C — satu-satunya kode klasifikasi QC yang diisi lewat aksi Selesaikan Tiket di aplikasi ini. |

#### Filter/Pencarian

- **Jenis Periode**, **Periode**, **Tahun** — sama seperti Laporan Pengendalian Mutu (ketiganya wajib diisi lebih dulu).
- **Kotak pencarian umum berfungsi pada laporan ini** (berbeda dari Laporan Pengendalian Mutu dan Laporan Hasil Pengolahan Data Prioritas): kata kunci dicocokkan terhadap Nama ILAP, Nama Sub Jenis Data, dan Nomor Tiket, diterapkan di atas hasil filter periode.

#### Aksi

- **EKSPOR KE EXCEL** — sama seperti Laporan Pengendalian Mutu: aktif setelah ada data, mengunduh seluruh hasil (bukan hanya halaman tampil) sebagai `.xlsx` dengan nama `laporan_kelengkapan_data_<Periode>.xlsx`.
- Tidak ada tombol aksi per baris, tidak ada ekspor PDF.

#### Akses

Diverifikasi dari `LaporanKelengkapanDataView.test_func()` di `views/laporan_kelengkapan_data.py`, memanggil fungsi `is_pmde_user()` (perhatikan: nama fungsi ini tanpa garis bawah di depan, berbeda dari modul laporan lain, tetapi isinya identik):

```python
def is_pmde_user(user):
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde']
    ).exists()
```

Akses: superuser, `is_staff`, atau anggota `user_pmde`/`admin`/`admin_pmde`. Sama seperti Laporan Pengendalian Mutu, **`kasi_pmde` tidak termasuk**, dan ini konsisten dengan `navbar.html` (tautan ini berada dalam submenu Laporan yang sama, hanya dirender untuk `admin_pmde`/`user_pmde`). Baris "Kelengkapan Data" pada `RBAC_MATRIX.md` (PMDE ✅, P3DE/PIDE ❌) sudah sesuai — **tidak ada ketidaksesuaian** untuk menu ini.

---

### Laporan Hasil Pengolahan Data Prioritas

Laporan ini adalah rekap paling rinci di antara ketiga laporan PMDE: menggabungkan angka-angka dari tahap P3DE, PIDE, dan PMDE untuk setiap tiket dalam satu baris lebar (23 kolom), mengikuti format laporan gabungan lintas-seksi. Meskipun namanya menyebut "Data Prioritas", **kriteria tampilannya tidak membatasi hanya tiket dengan penanda prioritas** — seluruh tiket pada periode terpilih ikut tampil, prioritas maupun bukan (lihat detail di bawah).

#### Kriteria/Data yang Ditampilkan

- Tabel tetap kosong sampai Jenis Periode, Periode, dan Tahun dipilih semua.
- Baris yang ditampilkan: tiket dengan **Tanggal Kirim ke PIDE** (`tgl_kirim_pide`) pada rentang periode terpilih — **dasar tanggalnya berbeda** dari dua laporan PMDE lainnya, yang memakai Tanggal Transfer (PIDE→PMDE). Laporan ini memakai tanggal P3DE mengirim tiket ke PIDE, sesuai komentar pada kode: "tgl_kirim_pide sebagai tanggal yang relevan untuk 'pengolahan data'".
- **Tidak difilter berdasarkan penanda prioritas** — walau judul menunya "Data Prioritas", query yang menyusun laporan ini (`views/laporan_hasil_pengolahan_data_prioritas.py`) tidak menambahkan syarat apa pun terkait `id_jenis_prioritas_data`/Data Prioritas; tiket biasa maupun prioritas sama-sama muncul selama tanggal kirim ke PIDE-nya masuk periode.
- **Tidak dibatasi PIC** dan **tidak dibatasi status tiket saat ini**, sama seperti dua laporan lainnya.
- Urutan default: menurut Nama ILAP menaik.

#### Kolom/Field

| Kolom | Keterangan |
|---|---|
| No | Nomor urut baris pada halaman & urutan saat ini (bukan id tiket). |
| Nama ILAP | ILAP asal data. |
| Nama Jenis Data | Nama Sub Jenis Data ILAP. |
| Nama Tabel KPDE | Field "Nama Tabel I" pada Sub Jenis Data. |
| Nama Tabel Bank Data | Sumbernya **sama persis** dengan "Nama Tabel KPDE" (field "Nama Tabel I" yang sama) — kedua kolom akan selalu menampilkan nilai yang identik. |
| Nama Tabel Bank Data U | Field "Nama Tabel U" pada Sub Jenis Data — nama tabel untuk data hasil Update, berbeda dari dua kolom sebelumnya. |
| Periode Data | Label periode penyampaian pada Sub Jenis Data ILAP (mis. Bulanan/Triwulanan) — bukan periode/tahun tiket. |
| ID Tiket | Nomor tiket. |
| Periode Tiket | Periode pelaporan data tiket itu sendiri dalam format terbaca (mis. "Maret 2026", "Triwulan III 2026") — berbeda dari filter Jenis Periode/Periode/Tahun di atas, yang mengacu pada tanggal kirim ke PIDE. |
| Data Diterima (P3DE) | Jumlah baris diterima (`baris_diterima`). |
| Data Lengkap (P3DE) | Jumlah baris lengkap hasil penelitian P3DE (`baris_lengkap`). |
| Data Klarifikasi (P3DE) | Jumlah baris tidak lengkap/perlu diklarifikasi (`baris_tidak_lengkap`). |
| Data Diterima (PIDE) | Sumbernya **sama persis** dengan "Data Diterima (P3DE)" — kolom ini sengaja diulang sesuai format laporan yang diminta, bukan angka yang berbeda. |
| Data Direkam | Total baris I + baris U hasil rekam PIDE. |
| Data Teridentifikasi (PIDE) | Baris I, **hanya diisi bila Jenis Tabel data tersebut "Diidentifikasi"**; bernilai 0 untuk Jenis Tabel lain. |
| Data Tidak Teridentifikasi (PIDE) | Baris U, tanpa syarat Jenis Tabel. |
| Data Belum Diidentifikasi (PIDE) | Selisih antara Data Diterima dan (baris I + baris U); **hanya dihitung untuk Jenis Tabel "Diidentifikasi"**, bernilai 0 untuk Jenis Tabel lain. |
| Data Tidak Diidentifikasi (PIDE) | Baris I, **hanya diisi bila Jenis Tabel data tersebut "Tidak Diidentifikasi"**; bernilai 0 untuk Jenis Tabel lain. |
| Data Diterima Tabel I (QC) | Alias/salinan persis dari kolom "Data Teridentifikasi (PIDE)". |
| Data Lolos QC / Data Tidak Lolos QC | Hasil akhir QC dari aksi Selesaikan Tiket. |
| Data Belum QC | Bersumber dari field `qc_c` — field yang sama yang tampil sebagai "QC C (Kelengkapan)" pada Laporan Kelengkapan Data. Perlu diperhatikan: meski judul kolomnya "Belum QC", isinya adalah angka klasifikasi QC C, bukan sisa baris yang belum diperiksa (Jml Progress pada halaman Quality Control adalah angka yang berbeda). |
| Keterangan | Selalu kosong — kolom disediakan tetapi tidak diisi otomatis oleh sistem. |

#### Filter/Pencarian

- **Jenis Periode**, **Periode**, **Tahun** — sama seperti dua laporan lainnya (mengacu ke Tanggal Kirim ke PIDE), wajib diisi lebih dulu.
- Kotak pencarian umum tampil tetapi **tidak berfungsi** (sama seperti Laporan Pengendalian Mutu) — tidak ada penanganan kata kunci pencarian di sisi server.

#### Aksi

- **EKSPOR KE EXCEL** — aktif setelah ada data, mengunduh seluruh hasil periode terpilih (bukan hanya halaman tampil) sebagai `.xlsx` dengan nama `Laporan_Hasil_Pengolahan_Data_Prioritas_<Periode>.xlsx`, kolom sama seperti tabel.
- Tidak ada tombol aksi per baris, tidak ada ekspor PDF.

#### Akses

Diverifikasi dari `LaporanHasilPengolahanDataPrioritasView.test_func()` di `views/laporan_hasil_pengolahan_data_prioritas.py`, memanggil `_is_pmde_user()` (dipakai juga oleh kedua endpoint data dan ekspor lewat `@user_passes_test`):

```python
def _is_pmde_user(user):
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde']
    ).exists()
```

Akses: superuser, `is_staff`, atau anggota `user_pmde`/`admin`/`admin_pmde`. **Tidak ada grup PIDE (`user_pide`/`admin_pide`/`kasi_pide`) yang disebut sama sekali**, dan `kasi_pmde` juga tidak termasuk. `navbar.html` menaruh tautan menu ini di blok PMDE (baris ~145–165, di dalam submenu "Laporan" yang sama dengan dua laporan di atas), **bukan** di blok PIDE (baris ~111–132).

> Meskipun namanya menyebut "Data Prioritas" tanpa embel-embel divisi, menu ini adalah milik PMDE, bukan PIDE — sesuai penempatan tautannya di navbar. `RBAC_MATRIX.md` sudah diperbarui untuk mencerminkan ini (PMDE ✅ / PIDE ❌).

---

## Lihat Juga

- **PIC P3DE, PIC PIDE, PIC PMDE** (pengelolaan penanggung jawab per Sub Jenis Data, dan efek berantainya ke tiket berjalan) → [Panduan Menu Admin](ADMIN_MENU_GUIDE.md)
- **Data referensi/master** (Kategori ILAP, Jenis Tabel, Dasar Hukum, Durasi Jatuh Tempo PIDE/PMDE, Template Dokumen, Sequence Tanda Terima, dst.) → [Panduan Menu Admin](ADMIN_MENU_GUIDE.md)
- **Sinkronisasi data Oracle** (referensi, tiket, dan status tiket) → [Panduan Menu Admin](ADMIN_MENU_GUIDE.md)
- **Alur & status tiket secara lengkap**, termasuk diagram dan aturan validasi tiap aksi → [Diagram Alur Status Tiket](status_tiket_flow.md)
- **Matriks akses per role** (ringkasan menu × role dalam satu tabel) → [Matriks RBAC & Hak Akses Menu](RBAC_MATRIX.md) — perlu diperbarui pada beberapa baris, lihat catatan-catatan di dokumen ini
