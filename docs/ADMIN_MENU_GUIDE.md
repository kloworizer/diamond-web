# Panduan Menu Admin (P3DE, PIDE, PMDE)

> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE
> **Untuk:** Pengguna dengan role `admin`, `admin_p3de`, `admin_pide`, dan `admin_pmde`

Dokumen ini menjelaskan seluruh menu yang muncul di navbar untuk role admin, apa fungsinya, serta **perilaku sistem** di balik setiap aksi — terutama pada menu **PIC** (Person In Charge), yang memiliki efek samping penting terhadap tiket yang sedang berjalan.

---

## Daftar Isi

- [Peran Admin & Visibilitas Menu](#peran-admin--visibilitas-menu)
- [Menu Admin P3DE](#menu-admin-p3de)
- [Menu Admin PIDE](#menu-admin-pide)
- [Menu Admin PMDE](#menu-admin-pmde)
- [Menu Sinkronisasi Data (Admin Global)](#menu-sinkronisasi-data-admin-global)
- [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic)
- [Fokus: Cara Kerja Menu Periode Jenis Data](#fokus-cara-kerja-menu-periode-jenis-data)
- [Fokus: Cara Kerja Menu Data Prioritas](#fokus-cara-kerja-menu-data-prioritas)

---

## Peran Admin & Visibilitas Menu

Menu pada navbar muncul secara kondisional berdasarkan grup (role) pengguna. Terdapat tiga role admin per-divisi, ditambah satu role `admin` global:

| Role | Caption Navbar yang Muncul | Cakupan |
|------|----------------------------|---------|
| `admin_p3de` | **Admin P3DE** | Referensi & ILAP P3DE, Data Prioritas, PIC P3DE, Template, Sequence |
| `admin_pide` | **Admin PIDE** | Durasi Jatuh Tempo PIDE, Nama Tabel, PIC PIDE, Data Prioritas |
| `admin_pmde` | **Admin PMDE** | Durasi Jatuh Tempo PMDE, PIC PMDE, Data Prioritas |
| `admin` (global) | **Semua caption Admin + Sinkronisasi Data** | Akses penuh seluruh menu admin dan sinkronisasi Oracle |

> **Catatan:** Role `admin` global melihat **semua** blok menu admin (P3DE, PIDE, PMDE) sekaligus, plus blok **Sinkronisasi Data** yang eksklusif untuk `admin`. Admin per-divisi hanya melihat blok divisinya sendiri.

> **Menu bersama:** **Data Prioritas** adalah satu-satunya menu admin yang dikelola bersama oleh ketiga seksi — tautannya muncul di akar blok Admin P3DE, Admin PIDE, maupun Admin PMDE, dan ketiganya menunjuk halaman yang sama persis. Pengguna yang melihat lebih dari satu blok (mis. `admin` global melihat ketiganya) akan menjumpai tautan ini berulang di tiap blok; itu memang disengaja, agar setiap seksi menemukannya di tempat yang sama. Lihat [Fokus: Cara Kerja Menu Data Prioritas](#fokus-cara-kerja-menu-data-prioritas).

---

## Menu Admin P3DE

Muncul untuk role `admin` atau `admin_p3de`. Berisi pengelolaan data referensi/master untuk divisi Penghimpunan Data Eksternal.

### 1. Kelola Referensi P3DE (submenu)

Data master dasar yang menjadi acuan proses penerimaan data. Semua bersifat CRUD (Tambah / Ubah / Hapus) melalui tabel dan modal:

- **Kategori ILAP** — pengelompokan Instansi/Lembaga/Asosiasi/Pihak lain.
- **Kategori Wilayah** — pengelompokan wilayah.
- **Kanwil** — Kantor Wilayah.
- **KPP** — Kantor Pelayanan Pajak.
- **Jenis Tabel** — jenis tabel data.
- **Dasar Hukum** — dasar hukum penerimaan data.
- **Periode Pengiriman** — periode pengiriman data (mis. bulanan, triwulanan).
- **Status Data** — status kondisi data.
- **Bentuk Data** — bentuk/format data.
- **Cara Penyampaian** — metode penyampaian data.
- **Media Backup** — media penyimpanan cadangan.
- **Status Penelitian** — status hasil penelitian data.

### 2. Kelola ILAP (submenu)

Pengelolaan entitas ILAP dan struktur jenis datanya:

- **ILAP** — daftar Instansi/Lembaga/Asosiasi/Pihak lain sumber data.
- **Jenis Data ILAP** — jenis data yang dimiliki tiap ILAP (menjadi acuan **Sub Jenis Data** pada PIC dan tiket).
- **Klasifikasi Jenis Data** — klasifikasi atas jenis data.
- **Periode Jenis Data** — periode yang berlaku untuk tiap jenis data.

### 3. Data Prioritas

Penandaan Sub Jenis Data ILAP sebagai data prioritas selama suatu rentang waktu. Menu ini **dikelola bersama** oleh Admin P3DE, PIDE, dan PMDE — tautannya juga muncul di blok Admin PIDE dan Admin PMDE. **Lihat [Fokus: Cara Kerja Menu Data Prioritas](#fokus-cara-kerja-menu-data-prioritas)** untuk detail perilakunya, terutama arti Start Date/End Date dan kapan penandaan ini menempel ke tiket.

### 4. PIC P3DE

Pengelolaan penanggung jawab (Person In Charge) untuk divisi P3DE. **Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic)** untuk detail perilakunya.

### 5. Template Dokumen

Pengelolaan template dokumen `.docx` (mis. PKDI/Klarifikasi, ND Pengantar) yang dipakai untuk generate dokumen otomatis.

### 6. Sequence Tanda Terima

Pengelolaan nomor urut (sequence) tanda terima data, agar penomoran tanda terima konsisten dan tidak duplikat.

---

## Menu Admin PIDE

Muncul untuk role `admin` atau `admin_pide`. Berisi pengelolaan referensi divisi Pengolahan Informasi Data Eksternal.

- **Durasi Jatuh Tempo PIDE** — pengaturan durasi SLA/jatuh tempo untuk proses identifikasi & perekaman di PIDE.
- **Nama Tabel** — pengelolaan nama tabel data yang diproses PIDE.
- **PIC PIDE** — pengelolaan penanggung jawab divisi PIDE. Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic).
- **Data Prioritas** — menu bersama dengan P3DE dan PMDE; halaman yang sama seperti pada blok Admin P3DE. Lihat [Fokus: Cara Kerja Menu Data Prioritas](#fokus-cara-kerja-menu-data-prioritas).

---

## Menu Admin PMDE

Muncul untuk role `admin` atau `admin_pmde`. Berisi pengelolaan referensi divisi Pengendalian Mutu Data Eksternal.

- **Durasi Jatuh Tempo PMDE** — pengaturan durasi SLA/jatuh tempo untuk proses quality control di PMDE.
- **PIC PMDE** — pengelolaan penanggung jawab divisi PMDE. Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic).
- **Data Prioritas** — menu bersama dengan P3DE dan PIDE; halaman yang sama seperti pada blok Admin P3DE. Lihat [Fokus: Cara Kerja Menu Data Prioritas](#fokus-cara-kerja-menu-data-prioritas).

---

## Menu Sinkronisasi Data (Admin Global)

Hanya muncul untuk role `admin` global. Digunakan untuk menyelaraskan data lokal dengan sumber data Oracle:

- **Sinkronisasi Data Referensi** — menarik/menyelaraskan data master referensi dari Oracle.
- **Sinkronisasi Data Tiket** — menyelaraskan data tiket dari Oracle.
- **Sinkronisasi Tarikan Tiket** — menarik pembaruan status tiket (lihat *Aturan Sinkronisasi Status Tiket*).
- **Status Sinkronisasi** — memantau riwayat & status proses sinkronisasi.

---

## Fokus: Cara Kerja Menu PIC

Menu **PIC** (PIC P3DE, PIC PIDE, PIC PMDE) memakai satu model dan logika yang sama, hanya berbeda `tipe` (P3DE/PIDE/PMDE). Bagian ini menjelaskan secara detail apa yang terjadi di balik layar pada setiap aksi.

### Apa itu PIC?

PIC adalah penugasan seorang **user** sebagai penanggung jawab atas suatu **Sub Jenis Data ILAP** untuk divisi tertentu. Satu record PIC memiliki field:

| Field | Keterangan |
|-------|-----------|
| **Tipe** | P3DE / PIDE / PMDE (otomatis sesuai menu, tersembunyi saat tambah). |
| **Sub Jenis Data ILAP** | Data yang menjadi tanggung jawab PIC. |
| **User** | Pengguna yang ditugaskan. Pilihan dibatasi hanya user pada grup terkait (`user_p3de` / `user_pide` / `user_pmde`). |
| **Start Date** | Tanggal mulai bertugas. **Wajib.** |
| **End Date** | Tanggal berakhir bertugas. **Opsional.** Jika kosong → PIC dianggap **aktif**. |

> **Definisi aktif:** Sebuah PIC dianggap **aktif** selama **End Date masih kosong**. Begitu End Date diisi, PIC dianggap sudah tidak aktif.

### Prinsip Penting: Efek Berantai ke Tiket

Setiap perubahan pada data PIC **tidak hanya** mengubah tabel PIC, tetapi juga otomatis menyesuaikan penugasan pada **tiket yang sedang berjalan** (`TiketPIC`) dan mencatat jejaknya pada **riwayat aksi tiket** (`TiketAction`).

Yang dimaksud "tiket yang sedang berjalan" adalah tiket yang:

- Menggunakan **Sub Jenis Data ILAP yang sama** dengan PIC, **dan**
- Statusnya **belum dibatalkan/selesai** (status di bawah "Dibatalkan").

Setiap perubahan penugasan dicatat pada riwayat tiket dengan aksi: **Ditambahkan**, **Diaktifkan Kembali**, atau **Tidak Aktif**.

---

### Skenario 1 — Menambahkan PIC Baru

Saat admin menekan **Tambah** dan menyimpan PIC baru:

1. Record PIC baru dibuat.
2. Sistem mencari **semua tiket berjalan** yang memakai Sub Jenis Data yang sama.
3. Untuk setiap tiket tersebut:
   - Jika user **belum** pernah menjadi PIC pada tiket itu → dibuat penugasan `TiketPIC` baru (aktif) dan dicatat riwayat **"Ditambahkan"**.
   - Jika user **sudah pernah** menjadi PIC tapi statusnya nonaktif → penugasan **diaktifkan kembali**, dicatat riwayat **"Diaktifkan Kembali"**.

**Efeknya:** user langsung menjadi penanggung jawab pada semua tiket berjalan untuk data tersebut, tanpa perlu penugasan manual per tiket.

### Skenario 2 — Mengganti User (Serah Terima PIC)

Saat admin mengubah PIC dan **mengganti field User** dengan orang lain, sistem memperlakukannya sebagai **serah terima**: dalam satu penyimpanan, PIC lama dilepas dan PIC baru langsung memegang tiket, sehingga tiket tidak pernah tertinggal tanpa penanggung jawab.

1. Record PIC diperbarui ke user yang baru.
2. Sistem mencari **semua tiket berjalan** yang memakai Sub Jenis Data yang sama.
3. Pada tiket-tiket tersebut, penugasan **user lama dinonaktifkan** dan dicatat riwayat **"Tidak Aktif"** dengan catatan *"… diganti oleh &lt;user baru&gt;"*.
4. Pada tiket yang sama, **user baru ditugaskan persis seperti Skenario 1**: dibuat penugasan baru (riwayat **"Ditambahkan"**), atau bila ia pernah menjadi PIC pada tiket itu dan statusnya nonaktif → **diaktifkan kembali** (riwayat **"Diaktifkan Kembali"**). Penugasan tidak digandakan bila user baru sudah aktif di tiket tersebut.

**Efeknya:** pergantian penanggung jawab cukup dilakukan sekali di menu PIC dan langsung tercermin pada seluruh tiket berjalan.

> **Cakupan hanya tiket berjalan.** Tiket yang sudah **dibatalkan/selesai** sengaja tidak disentuh — tiket tersebut tetap mencatat orang yang benar-benar mengerjakannya.

> **Jika User diganti sekaligus End Date diisi**, edit tersebut **bukan** serah terima melainkan pemberhentian: user lama dinonaktifkan dan **tidak ada** yang menggantikan (PIC-nya memang sudah tidak aktif).

### Skenario 3 — Mengisi End Date (Menonaktifkan PIC)

Saat admin mengubah PIC dan **mengisi End Date** yang sebelumnya kosong:

1. Sistem mencari semua penugasan `TiketPIC` yang **masih aktif** untuk user + divisi + Sub Jenis Data tersebut.
2. Setiap penugasan itu **dinonaktifkan** (bukan dihapus — datanya tetap ada untuk histori).
3. Dicatat riwayat **"Tidak Aktif"** pada masing-masing tiket.

**Efeknya:** user tidak lagi tercatat sebagai penanggung jawab aktif pada tiket-tiket berjalan, tetapi jejak penugasannya tetap tersimpan.

> **Penting:** Menonaktifkan PIC dilakukan dengan **mengisi End Date**, bukan menghapus record. Ini cara yang benar untuk "memberhentikan" seorang PIC sambil menjaga histori.

### Skenario 4 — Menghapus (Mengosongkan) End Date (Mengaktifkan Kembali)

Saat admin mengubah PIC dan **mengosongkan kembali End Date** yang sebelumnya terisi:

1. Sistem mencari semua tiket berjalan dengan Sub Jenis Data yang sama.
2. Untuk setiap tiket:
   - Jika penugasan lama masih ada (nonaktif) → **diaktifkan kembali**, dicatat riwayat **"Diaktifkan Kembali"**.
   - Jika belum ada penugasan → dibuat penugasan baru, dicatat riwayat **"Ditambahkan"**.

**Efeknya:** PIC kembali aktif dan otomatis dipasang lagi pada tiket-tiket berjalan.

### Skenario 5 — Menghapus Record PIC

Saat admin menekan **Hapus** pada sebuah PIC:

1. Sistem mencari **semua** penugasan `TiketPIC` (aktif maupun tidak) untuk user + divisi + Sub Jenis Data tersebut.
2. Seluruh penugasan itu **dihapus**.
3. Dicatat riwayat **"Tidak Aktif"** (dengan catatan bahwa PIC dihapus) pada masing-masing tiket.
4. Terakhir, record PIC itu sendiri dihapus.

> **Perbedaan Hapus vs Isi End Date:**
> - **Isi End Date** → penugasan tiket dinonaktifkan tetapi **tetap tersimpan** (histori terjaga). Bisa diaktifkan kembali dengan mengosongkan End Date.
> - **Hapus** → penugasan tiket **benar-benar dihapus**. Gunakan hanya bila data PIC salah/tidak diperlukan. Untuk pemberhentian normal, **lebih disarankan mengisi End Date**.

### Ringkasan Efek ke Tiket

| Aksi admin | Penugasan pada tiket (`TiketPIC`) | Riwayat tiket (`TiketAction`) | Cakupan tiket |
|---|---|---|---|
| **Tambah** PIC | User baru ditugaskan (dibuat / diaktifkan kembali) | *Ditambahkan* atau *Diaktifkan Kembali* | Tiket berjalan |
| **Edit — ganti User** | User lama dinonaktifkan **dan** user baru ditugaskan | *Tidak Aktif* untuk yang lama + *Ditambahkan*/*Diaktifkan Kembali* untuk yang baru | Tiket berjalan |
| **Edit — isi End Date** | Penugasan user dinonaktifkan (data tetap ada) | *Tidak Aktif* | Semua tiket dengan Sub Jenis Data tsb. |
| **Edit — kosongkan End Date** | Penugasan user diaktifkan kembali / dibuat | *Diaktifkan Kembali* atau *Ditambahkan* | Tiket berjalan |
| **Edit — ganti User + isi End Date** | Hanya user lama dinonaktifkan, tidak ada pengganti | *Tidak Aktif* | Tiket berjalan |
| **Hapus** PIC | Penugasan **dihapus permanen** | *Tidak Aktif* (catatan: dihapus) | Semua tiket dengan Sub Jenis Data tsb. |

> Perubahan **Start Date** saja tidak berpengaruh ke penugasan tiket.

---

### Aturan Validasi Form PIC

Agar data konsisten, form PIC menerapkan aturan berikut:

- **Saat mengubah (Edit):** field **Tipe** dan **Sub Jenis Data** dikunci (tidak bisa diubah). **User**, **Start Date**, dan **End Date** dapat disunting — mengganti User memicu serah terima pada tiket berjalan (lihat Skenario 2). Untuk memindahkan penugasan ke Sub Jenis Data lain, buat record PIC baru.
- **User dibatasi per divisi:** dropdown user hanya menampilkan anggota grup yang sesuai (`user_p3de` / `user_pide` / `user_pmde`).
- **Tidak boleh duplikat:** kombinasi Tipe + Sub Jenis Data + User + Start Date yang sama persis akan ditolak.
- **Tidak boleh tumpang tindih aktif:** bila sudah ada PIC **aktif** (End Date kosong) untuk user & Sub Jenis Data yang sama, penambahan PIC aktif baru ditolak. Isi dulu End Date pada PIC yang lama sebelum membuat yang baru.

### Fitur Tabel PIC

Halaman daftar PIC menampilkan tabel dengan kolom: ILAP, ID Sub Jenis Data, Nama Sub Jenis Data, Username, Full Name, Start Date, dan End Date. Tabel mendukung:

- **Pencarian per kolom** (kotak pencarian di bawah setiap judul kolom) dan tombol **Reset Pencarian**.
- **Pengurutan** kolom serta **paginasi** (server-side).
- Kolom **Aksi** (tombol Edit & Hapus) **hanya muncul untuk admin**. User biasa dapat melihat daftar tetapi tanpa tombol aksi.

---

## Fokus: Cara Kerja Menu Periode Jenis Data

Menu **Periode Jenis Data** (submenu Kelola ILAP) menentukan seberapa sering suatu Sub Jenis Data ILAP wajib dikirim (Bulanan, Triwulanan, Semesteran, Tahunan, dll). Bagian ini menjelaskan efek yang **tidak langsung terlihat** ketika tipe periode pada record yang sudah dipakai tiket diubah — karena tidak ada validasi yang memblokir aksi ini, walau efeknya cukup luas.

### Apa itu Periode Jenis Data?

Satu record `Periode Jenis Data` memiliki field:

| Field | Keterangan |
|-------|-----------|
| **Sub Jenis Data ILAP** | Jenis data yang diatur periodenya. |
| **Periode Pengiriman** | Tipe periode, diambil dari master **Periode Pengiriman** (Harian, Mingguan, Bulanan, Triwulanan, Semesteran, Tahunan, dll). |
| **Start Date** | Tanggal mulai berlakunya aturan periode ini. |
| **End Date** | Tanggal berakhir. **Opsional** — kosong berarti masih berlaku sampai sekarang. |
| **Akhir Penyampaian** | Jumlah hari batas kirim, dihitung sejak **akhir tiap periode** (mis. akhir bulan untuk tipe Bulanan, akhir tahun untuk tipe Tahunan). |

> **Sub Jenis Data + rentang tanggal tidak boleh tumpang tindih.** Form menolak bila Sub Jenis Data yang sama punya dua record dengan rentang `start_date`–`end_date` yang beririsan. Validasi ini otomatis mendukung pola "tutup periode lama, buat periode baru" di bawah.

### Prinsip Penting: Tiket Lama Terkunci Permanen ke Record yang Sama

Setiap **Tiket** menyimpan referensi (`id_periode_data`) ke **satu record** Periode Jenis Data tertentu — bukan ke tipe periodenya secara langsung. Referensi ini bersifat `PROTECT`: record Periode Jenis Data **tidak bisa dihapus** selama masih dipakai tiket. Tapi field-fieldnya, **termasuk tipe Periode Pengiriman, tetap bisa diedit** kapan saja tanpa penolakan sistem — walau sudah dipakai ratusan tiket.

Yang membuat ini berisiko: label tipe periode ("Bulanan"/"Tahunan"/dst) yang tampil di seluruh aplikasi (detail tiket, daftar tiket, dashboard Home, dokumen ND/Surat, Laporan Register Penerimaan, Laporan Hasil Pengolahan Data Prioritas, Tanda Terima, Profil ILAP/PIC, Nama Tabel, Backup Data) **dihitung ulang setiap kali halaman dibuka**, dengan membaca nilai Periode Pengiriman **yang berlaku sekarang** pada record tersebut — bukan nilai yang berlaku saat tiket itu dibuat.

### Skenario — Mengubah Tipe Periode pada Record yang Sudah Dipakai Tiket (bukan menambah baru)

Misalnya admin membuka record Periode Jenis Data yang sudah lama dipakai (tipe **Bulanan**, dipakai tiket-tiket dengan Periode 1–12), lalu mengubah field **Periode Pengiriman** menjadi **Tahunan** pada record yang sama (tanpa mengubah Start Date), dan menyimpan:

1. **Tersimpan tanpa error.** Tidak ada validasi yang memeriksa apakah record ini sudah dipakai tiket sebelum mengizinkan perubahan tipe periode.
2. **Nilai `Periode` dan `Tahun` pada tiket lama tidak berubah** di database (tetap 1–12 apa adanya). Yang berubah hanya **tipe periode yang ditempelkan ke tiket itu saat ditampilkan**.
3. **Tampilan berubah di semua halaman yang memformat periode.** Untuk tipe Tahunan, sistem hanya menampilkan tahunnya saja (mis. "2025") — info bulan (Januari–Desember) yang sebelumnya melekat pada tiket-tiket itu **hilang dari tampilan** (bukan dari data mentah).
4. **Menu Monitoring Penyampaian Data paling terdampak.** Halaman ini membangkitkan ulang jadwal periode wajib dari Start Date sampai hari ini berdasarkan tipe periode yang berlaku *sekarang*. Begitu berubah ke Tahunan, sistem hanya mengharapkan **1 periode wajib per tahun**, lalu mencocokkannya ke tiket lewat kombinasi (record periode, nomor periode, tahun). Akibatnya:
   - Tiket lama dengan Periode = 1 (Januari) akan otomatis cocok dan dianggap **"Sudah Menyampaikan"** mewakili seluruh tahun.
   - **11 tiket bulan lainnya (Februari–Desember) tidak lagi punya slot yang cocok**, sehingga tidak muncul lagi di halaman ini sama sekali — seolah kewajiban tahun tersebut sudah tuntas sejak Januari, padahal aslinya wajib dikirim bulanan. Data tiketnya sendiri tetap ada dan tetap bisa dilihat normal di menu Tiket.
5. **Batas jatuh tempo (`Akhir Penyampaian`) ikut bergeser maknanya.** Nilai hari yang tadinya dihitung dari akhir bulan kini dihitung dari akhir tahun. Bila nilainya tidak disesuaikan ulang, tanggal jatuh tempo yang dihasilkan bisa tidak relevan.
6. **Tiket baru ke depan otomatis mengikuti aturan baru** — form Rekam Tiket membatasi pilihan Periode hanya ke nilai "1" untuk tipe Tahunan, jadi secara operasional pengguna tidak bisa lagi merekam data bulanan pada jenis data tersebut setelah perubahan. Ini bagian yang memang sesuai tujuan mengubah ke tahunan.

> **Inti masalahnya:** mengedit tipe periode pada record lama itu retroaktif — mengubah cara *seluruh* histori tiket pada Sub Jenis Data itu dibaca dan dijadwalkan ulang, bukan hanya berlaku untuk tiket baru ke depan.

### Cara yang Direkomendasikan — Tutup Periode Lama, Buat Periode Baru

Untuk mengganti tipe periode suatu Sub Jenis Data tanpa mengganggu histori tiket yang sudah ada:

1. **Jangan edit** field Periode Pengiriman pada record lama.
2. Buka record lama, isi **End Date** dengan tanggal akhir periode terakhir yang masih memakai aturan lama (mis. 31 Desember tahun terakhir yang masih Bulanan).
3. Buat **record Periode Jenis Data baru**: Sub Jenis Data yang sama, Periode Pengiriman = **Tahunan**, Start Date = awal periode baru berlaku (mis. 1 Januari tahun berikutnya), dan Akhir Penyampaian disesuaikan dengan aturan tahunan yang baru.
4. Sistem otomatis memastikan rentang tanggal kedua record ini tidak tumpang tindih (lihat catatan validasi di atas).
5. **Lakukan cutover tepat di pergantian tahun** (Start Date record Tahunan baru = 1 Januari) — lihat alasannya di bagian *Kolom Penyampaian* di bawah.

Dengan pola ini: tiket-tiket lama tetap terhubung ke record Bulanan yang sudah ditutup (tampilan & Monitoring Penyampaian Data untuk histori tetap benar sebagai bulanan), sementara tiket-tiket baru sejak tanggal cutover otomatis terhubung ke record Tahunan yang baru.

### Kolom Penyampaian pada Tiket — Tidak Ikut Berubah Tampilannya, tapi Ada Risiko Lain

Tiket punya dua field angka yang sering tertukar: **Periode** (1–12, dibahas di atas) dan **Penyampaian** (penghitung pengiriman ulang/resend — 0 untuk kiriman pertama, 1 untuk kiriman kedua, dst., untuk kombinasi Sub Jenis Data + Periode + Tahun yang sama persis).

- **Nilai `Penyampaian` pada tiket lama tidak berubah** bila tipe Periode Pengiriman diedit. Field ini diisi **sekali** saat tiket dibuat — hasil hitung "sudah berapa tiket lain untuk kombinasi ini" — lalu disimpan permanen di baris tiket tersebut.
- **Tampilannya juga tidak ikut terdampak.** Berbeda dari kolom Periode yang diformat ulang lewat `format_periode()` (sehingga label Bulanan/Tahunan-nya bisa berubah saat dibaca), kolom Penyampaian ditampilkan sebagai angka mentah apa adanya.
- **Tapi ada risiko tidak langsung pada tiket baru** bila cutover dilakukan **di tengah tahun**: pengecekan duplikat/penomoran Penyampaian saat merekam tiket baru (lihat `DuplicateCheckAPIView` pada `rekam_tiket.py`) mencari tiket lain berdasarkan **kode Sub Jenis Data + Periode + Tahun yang sama** — pencarian ini **tidak dibatasi ke satu record Periode Jenis Data tertentu**, jadi ia menembus lintas record lama (Bulanan) dan record baru (Tahunan) selama kode Sub Jenis Data-nya sama.

  Contoh: bila record Tahunan baru mulai berlaku Juli 2026 (bukan awal tahun), lalu direkam tiket tahunan untuk Tahun 2026 dengan Periode = 1, sistem akan menemukan tiket Bulanan Januari 2026 (Periode = 1, Tahun = 2026) yang sudah ada lebih dulu — dan menganggap tiket tahunan itu sebagai **kiriman ulang (resend)** dari tiket Januari tersebut. Tiket tahunan baru akan muncul di peringatan duplikat dan `Penyampaian`-nya ikut naik (mis. jadi 1), padahal secara konsep keduanya adalah jenis pelaporan berbeda, bukan resend.
  
  Inilah alasan cutover **sebaiknya persis di 1 Januari**: dengan begitu tidak ada tahun yang memiliki tiket Bulanan maupun tiket Tahunan dengan Periode = 1 yang sama, sehingga tidak ada tabrakan.

---

## Fokus: Cara Kerja Menu Data Prioritas

Menu **Data Prioritas** menandai bahwa suatu **Sub Jenis Data ILAP** merupakan data prioritas selama **suatu rentang waktu**. Penandaan ini dipakai lintas seksi: P3DE melihatnya saat merekam tiket, PIDE memakainya untuk mengurutkan antrean Identifikasi, dan PMDE untuk antrean Quality Control. Karena itu menunya **dikelola bersama ketiga seksi** dan muncul di akar blok Admin P3DE, Admin PIDE, maupun Admin PMDE (bukan lagi submenu *Kelola ILAP*).

### Aturannya: Satu, dan Hanya Satu

> **Sebuah tiket berstatus prioritas apabila Sub Jenis Data-nya punya record Data Prioritas yang masa berlakunya mencakup TANGGAL TERIMA DIP tiket tersebut:**
>
> ```
> Start Date  ≤  Tanggal Terima DIP tiket  ≤  End Date
> ```
>
> **Field Tahun pada record tidak ikut menentukan.** Begitu pula Tahun Data pada tiket.

Aturan ini berlaku sama di **semua** tempat: form Rekam Tiket, badge Data Prioritas di form itu, kolom Prioritas dan sakelar "Hanya Prioritas" di Home, badge di Detail Tiket, antrean Identifikasi (PIDE), antrean Quality Control (PMDE), dan sinkronisasi dari Oracle. Kodenya pun satu berkas — `diamond_web/utils/jenis_prioritas.py` — supaya tidak bisa lagi berbeda antar menu.

### Field pada Satu Record Data Prioritas

| Field | Keterangan |
|-------|-----------|
| **Sub Jenis Data ILAP** | Jenis data yang ditandai prioritas. |
| **Start Date** | **Tanggal mulai berlaku. Wajib.** Bersama End Date, inilah satu-satunya yang menentukan tiket mana yang prioritas. |
| **End Date** | Tanggal berakhir. **Opsional** — kosong berarti masih berlaku sampai seterusnya. |
| **Tahun** | Tahun **penetapan** prioritas, mengikuti Nota Dinas-nya. Hanya keterangan dan pembeda antar record; **tidak dipakai logika mana pun**. |
| **No ND** | Nomor Nota Dinas dasar penetapan. Dokumentasi saja. |

Aturan validasi form:

- **Satu Sub Jenis Data hanya boleh punya satu record per Tahun** (dijaga constraint database `unique_subjenis_tahun`). Ini pembatas administratif, bukan bagian dari aturan prioritas.
- **Start Date tidak boleh sama** dengan record lain pada Sub Jenis Data yang sama.
- **Rentang Start Date–End Date tidak boleh tumpang tindih** dengan record lain pada Sub Jenis Data yang sama. Karena itu, untuk satu tiket paling banyak ada satu record yang cocok.
- **End Date tidak boleh mendahului Start Date.**

### Kapan Kolom Prioritas pada Tiket Terisi

Tiket menyimpan hasil pencocokan itu di kolom `id_jenis_prioritas_data`, **ditulis sekali saja saat tiket direkam**. Yang perlu dipahami:

1. **Saat P3DE menyimpan form Rekam Tiket**, sistem mencari record Data Prioritas untuk Sub Jenis Data tiket yang masa berlakunya mencakup **Tanggal Terima DIP yang diisi di form itu**. Kalau ketemu, kolomnya langsung terisi. Badge "Data Prioritas" di form menampilkan jawaban yang sama persis — badge baru muncul setelah Tanggal Terima DIP diisi, dan ikut berubah bila tanggal itu diubah.
2. **Kolom itu tidak pernah dihitung ulang sendiri.** Menambah, mengubah, atau menutup record Data Prioritas **tidak** menyentuh tiket yang sudah terlanjur direkam.
3. **Menu Identifikasi & Quality Control tidak membaca kolom itu** — keduanya menghitung ulang aturan yang sama setiap kali halaman dibuka, jadi keduanya selalu mengikuti record Data Prioritas yang berlaku *sekarang*.

Konsekuensi praktisnya ada di Skenario 1 di bawah, berikut cara membereskannya.

### Skenario 1 — Menambah Record Data Prioritas Baru Hari Ini

Misalnya hari ini admin menambah record: Sub Jenis Data `KM0330101`, Start Date `1 Januari 2026`, End Date dikosongkan.

1. **Menu Identifikasi & Quality Control langsung berubah**, untuk tiket lama sekaligus tiket baru: semua tiket `KM0330101` yang Tanggal Terima DIP-nya jatuh pada atau setelah 1 Januari 2026 seketika ditandai prioritas di kedua menu itu, tanpa perlu menyentuh data tiketnya.
2. **Tiket baru yang direkam sejak sekarang** otomatis terisi kolom prioritasnya — sepanjang Tanggal Terima DIP-nya masuk rentang tersebut.
3. **Tiket yang sudah terlanjur direkam tidak ikut terisi**, karena kolomnya hanya ditulis sekali. Di Home tiket-tiket itu masih tampil bukan prioritas, sementara di Identifikasi/QC sudah prioritas. **Inilah satu-satunya sumber ketidakcocokan yang tersisa, dan cara membereskannya ada di [Menyelaraskan Tiket yang Sudah Ada](#menyelaraskan-tiket-yang-sudah-ada) di bawah.** Jalankan perintah itu setiap kali selesai menambah atau mengubah record Data Prioritas.

### Skenario 2 — Merekam Tiket Hari Ini untuk Data Tahun Lalu

Contoh yang dulu sering salah dipahami. Hari ini (2026) P3DE merekam tiket untuk data **periode tahun 2025** yang baru diterima, dengan Tanggal Terima DIP hari ini:

- Yang dilihat sistem adalah **Tanggal Terima DIP hari ini (2026)**, dicocokkan dengan masa berlaku record. Tahun Data `2025` pada tiket tidak dilihat sama sekali, begitu pula field Tahun pada record.
- Jadi bila ada record yang berlaku mencakup hari ini, tiket ini **prioritas** — walaupun datanya data tahun 2025.
- Home dan Identifikasi/QC akan menjawab sama. Perbedaan tampilan antar menu untuk tiket yang sama sudah tidak terjadi lagi.

> **Praktik yang disarankan:** set Start Date–End Date menyelimuti rentang **tanggal penerimaan** yang ingin dicakup — bukan tahun datanya. Data tahun 2025 bisa saja baru diterima pada 2026, jadi rentangnya biasanya lebih panjang dan bergeser dibanding tahun datanya sendiri.

### Skenario 3 — Mengosongkan End Date

Mengosongkan End Date berarti **berlaku sampai seterusnya**, dan sekarang seluruh aplikasi membacanya begitu — form admin saat memeriksa tumpang tindih, form Rekam Tiket, Home, maupun Identifikasi & Quality Control.

> **Catatan riwayat:** sebelumnya Identifikasi & Quality Control mensyaratkan `End Date ≥ Tanggal Terima DIP`, syarat yang **tidak pernah bisa dipenuhi record tanpa End Date**, sehingga record terbuka justru tidak pernah dianggap prioritas di kedua menu itu. Ini sudah diperbaiki. Bila Anda pernah menghindari mengosongkan End Date karena alasan itu, sekarang tidak perlu lagi.

Untuk menghentikan penandaan mulai tanggal tertentu, **isi End Date-nya** — jangan hapus recordnya.

### Skenario 4 — Mengubah Tanggal atau Menghapus Record

- **Mengubah Start Date/End Date** pada record yang sudah dipakai: Identifikasi & Quality Control langsung ikut berubah, tapi kolom prioritas pada tiket lama **tidak**. Jalankan perintah penyelarasan di bawah setelah mengubahnya.
- **Mengubah Tahun**: tidak berpengaruh apa pun pada penentuan prioritas — field itu murni keterangan.
- **Menghapus record**: dilindungi `PROTECT` di level database. Selama masih ada tiket yang menunjuk record tersebut, penghapusan **tidak akan pernah berhasil** — datanya aman. Namun `JenisPrioritasDataDeleteView` menimpa penanganan error bawaan (`SafeDeleteMixin`), sehingga penolakan itu muncul sebagai **error server**, bukan pesan yang rapi. Untuk menghentikan penandaan ke depan, **isi End Date-nya, jangan hapus recordnya**.

### Menyelaraskan Tiket yang Sudah Ada

Karena kolom prioritas pada tiket hanya ditulis sekali saat perekaman, kolom itu perlu diselaraskan setiap kali record Data Prioritas ditambah atau diubah. Perbaikannya lewat perintah manajemen (dijalankan operator/administrator sistem di server, bukan lewat UI):

```
# Lihat dulu apa yang akan berubah, tanpa menyentuh database
python manage.py backfill_tiket_jenis_prioritas --dry-run

# Jalankan, sambil menulis catatan perubahan agar bisa dibatalkan
python manage.py backfill_tiket_jenis_prioritas --journal prioritas.jsonl

# Membatalkan kembali bila ternyata keliru
python manage.py backfill_tiket_jenis_prioritas --undo prioritas.jsonl
```

Perilaku perintah ini:

- **Rekonsiliasi penuh terhadap aturan di atas**: mengisi kolom yang kosong, memindahkan yang menunjuk record salah, dan mengosongkan yang tanggal terima DIP-nya sudah di luar masa berlaku record mana pun. Pakai `--fill-only` bila hanya ingin mengisi yang kosong.
- **Sekali jalan juga membetulkan tiket lama peninggalan aturan lama.** Tiket yang direkam sebelum perbaikan ini membawa hasil pencocokan berdasarkan field Tahun, yang sebagian salah; menjalankan perintah ini membereskan semuanya sekaligus.
- Setiap perubahan tercatat di **Riwayat Aksi** tiket sebagai *Isian Tiket Diubah* dengan catatan bertanda `(penyesuaian jenis prioritas data)`.
- Aman dijalankan berulang. Bisa dipersempit dengan `--prioritas-id` (ID record yang baru diubah, terlihat di URL tombol Ubah), `--tiket`, `--status`, atau `--sub-jenis-data`.

Rinciannya ada di docstring `diamond_web/management/commands/backfill_tiket_jenis_prioritas.py`, atau lewat `python manage.py help backfill_tiket_jenis_prioritas`.

#### Opsi `backfill_tiket_jenis_prioritas` selengkapnya

| Opsi | Guna |
|---|---|
| `--dry-run` | Laporkan rencananya, jangan tulis apa pun. Bisa digabung dengan opsi mana pun, termasuk `--undo`. |
| `--fill-only` | Hanya isi kolom yang kosong. Yang sudah terisi tidak dipindah maupun dikosongkan. |
| `--journal PATH` | Tulis catatan perubahan (JSONL) supaya bisa dibatalkan. |
| `--undo PATH` | Kembalikan perubahan dari journal, bukan menjalankan penyesuaian. |
| `--prioritas-id ID` | Batasi ke record Data Prioritas tertentu (ID ada di URL tombol Ubah). Bisa diulang. |
| `--sub-jenis-data KODE` | Batasi ke sub jenis data, mis. `KM0330101`. Bisa diulang. |
| `--tiket NOMOR` | Batasi ke nomor tiket tertentu. Bisa diulang. |
| `--status N` | Batasi ke `status_tiket` tertentu. Bisa diulang. |
| `--tahun N` | Batasi ke Tahun Data tiket. **Penyaring cakupan saja** — tahun tidak menentukan status prioritas. |
| `--only-old-db` / `--skip-old-db` | Hanya / kecuali tiket hasil migrasi. |
| `--limit N` | Proses paling banyak N tiket. |
| `--no-action` | Jangan tulis baris Riwayat Aksi "Isian Tiket Diubah". |
| `--system-user USERNAME` | User yang dicatat di Riwayat Aksi. Default `admin`. |
| `--batch-size N` | Baris per transaksi. Default 2000. |

Beberapa kombinasi yang biasa dipakai:

```
# Sesudah admin menambah satu record Data Prioritas (ID 42)
python manage.py backfill_tiket_jenis_prioritas --prioritas-id 42 --dry-run
python manage.py backfill_tiket_jenis_prioritas --prioritas-id 42 --journal p42.jsonl

# Coba di 50 tiket dulu sebelum semua
python manage.py backfill_tiket_jenis_prioritas --limit 50 --dry-run

# Konservatif: isi yang kosong saja, jangan sentuh yang sudah terisi
python manage.py backfill_tiket_jenis_prioritas --fill-only --journal p.jsonl

# Cek dulu apa yang akan dikembalikan, baru batalkan
python manage.py backfill_tiket_jenis_prioritas --undo p.jsonl --dry-run
python manage.py backfill_tiket_jenis_prioritas --undo p.jsonl
```

### Membangun Ulang Seluruh Tabel dari Data Impor

Bila penetapan prioritas datang sebagai satu berkas besar (mis. rekap dari PMDE berbentuk satu baris per tabel data dengan satu kolom penanda per tahun), tabel Data Prioritas bisa dibangun ulang seluruhnya, bukan diketik satu per satu lewat UI.

Impor dulu berkasnya ke tabel bantu bernama `temp_prioritas` dengan bentuk berikut — kolom tahunnya boleh berapa pun, perintahnya menemukan sendiri pola `PRIORITAS_<4 digit>`:

```sql
CREATE TABLE temp_prioritas (
    TABEL_I         VARCHAR(32),
    ID_TABEL_S      VARCHAR(16),   -- = ID Sub Jenis Data pada Jenis Data ILAP
    PRIORITAS_2022  INTEGER,
    PRIORITAS_2023  INTEGER,
    PRIORITAS_2024  INTEGER,
    PRIORITAS_2025  INTEGER,
    PRIORITAS_2026  INTEGER
);
```

Setiap kolom tahun yang **bernilai 1** menghasilkan satu record Data Prioritas: Sub Jenis Data dari `ID_TABEL_S`, Start Date 1 Januari tahun itu, End Date 31 Desember tahun itu. Nilai 0, kosong, dan NULL tidak dihitung.

**Urutan menjalankannya — dua langkah, jangan dibalik:**

```
# LANGKAH 1 — bangun ulang tabel Data Prioritas
python manage.py rebuild_jenis_prioritas_from_temp --dry-run
python manage.py rebuild_jenis_prioritas_from_temp --dump-existing prioritas-lama.json

# LANGKAH 2 — isi kembali kolom prioritas pada seluruh tiket
python manage.py backfill_tiket_jenis_prioritas --dry-run
python manage.py backfill_tiket_jenis_prioritas --journal prioritas.jsonl
```

Langkah 2 wajib. Langkah 1 mengosongkan kolom prioritas pada **semua** tiket (lihat alasannya di bawah); sampai langkah 2 dijalankan, seluruh tiket tampil bukan prioritas di Home. Menu Identifikasi & Quality Control tidak terpengaruh, keduanya membaca tabel Data Prioritas secara langsung.

Yang perlu diketahui sebelum menjalankan Langkah 1:

- **Seluruh isi tabel Data Prioritas dihapus**, termasuk No ND dan rentang tanggal yang mungkin sudah disunting manual — tabel impor tidak membawa nomor ND. Pakai `--dump-existing PATH` untuk menyimpan salinan JSON isi lama lebih dulu, atau `--no-nd "ND-xx/2026"` untuk memberi nomor ND seragam pada record yang dibuat.
- **FK prioritas pada tiket dikosongkan lebih dulu.** Tiket menunjuk Data Prioritas dengan `on_delete=PROTECT`, jadi selama masih ada tiket yang menunjuknya, penghapusan mustahil. Perintahnya melakukan itu sendiri, di dalam **satu transaksi** bersama penghapusan dan pembuatan record baru — bila gagal di tengah, semuanya kembali seperti semula.
- **Satu `ID_TABEL_S` yang muncul di lebih dari satu baris digabung dengan OR**: tahun itu prioritas bila salah satu barisnya menandainya. Ini bukan pilihan gaya — constraint `unique_subjenis_tahun` memang hanya mengizinkan satu record per pasangan Sub Jenis Data + tahun. Perintahnya melaporkan kode mana saja yang digabung.
- **`ID_TABEL_S` yang tidak ada di Jenis Data ILAP dilewati** dan dilaporkan, bukan membuat perintahnya gagal.
- **Impor yang tidak menandai satu tahun pun akan ditolak.** Mengosongkan tabel tanpa pengganti hampir pasti berarti impornya gagal, bukan yang dimaksud.
- Konfirmasi diminta sebelum menghapus; `--noinput` melewatinya (untuk skrip otomatis).

> ⚠️ **Perhatikan arti tahunnya.** Rentang yang dibangkitkan adalah satu tahun kalender penuh, dan rentang itu dicocokkan ke **tanggal terima DIP**, bukan Tahun Data. Jadi `PRIORITAS_2025` di sini berarti *"prioritas untuk data yang diterima sepanjang 2025"* — bukan *"data tahun 2025 adalah prioritas"*.
>
> Bedanya nyata: pada data yang ada, **sekitar dua pertiga tiket punya tahun terima berbeda dari Tahun Data**, dan sebagian besar di antaranya diterima pada tahun berikutnya. Tiket untuk data 2025 yang baru diterima Februari 2026 akan dinilai oleh penanda tahun **2026**. Bila yang dimaksud rekap sumber justru tahun data, rentangnya perlu diperpanjang sampai menutupi masa penerimaannya — dan rentang antar tahun tidak boleh tumpang tindih, jadi perlu dirancang lebih dulu.

Rinciannya ada di docstring `diamond_web/management/commands/rebuild_jenis_prioritas_from_temp.py`.
