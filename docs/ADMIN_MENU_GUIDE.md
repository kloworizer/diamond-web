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

---

## Peran Admin & Visibilitas Menu

Menu pada navbar muncul secara kondisional berdasarkan grup (role) pengguna. Terdapat tiga role admin per-divisi, ditambah satu role `admin` global:

| Role | Caption Navbar yang Muncul | Cakupan |
|------|----------------------------|---------|
| `admin_p3de` | **Admin P3DE** | Referensi & ILAP P3DE, PIC P3DE, Template, Sequence |
| `admin_pide` | **Admin PIDE** | Durasi Jatuh Tempo PIDE, Nama Tabel, PIC PIDE |
| `admin_pmde` | **Admin PMDE** | Durasi Jatuh Tempo PMDE, PIC PMDE |
| `admin` (global) | **Semua caption Admin + Sinkronisasi Data** | Akses penuh seluruh menu admin dan sinkronisasi Oracle |

> **Catatan:** Role `admin` global melihat **semua** blok menu admin (P3DE, PIDE, PMDE) sekaligus, plus blok **Sinkronisasi Data** yang eksklusif untuk `admin`. Admin per-divisi hanya melihat blok divisinya sendiri.

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
- **Data Prioritas** — penandaan jenis data prioritas tinggi.

### 3. PIC P3DE

Pengelolaan penanggung jawab (Person In Charge) untuk divisi P3DE. **Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic)** untuk detail perilakunya.

### 4. Template Dokumen

Pengelolaan template dokumen `.docx` (mis. PKDI/Klarifikasi, ND Pengantar) yang dipakai untuk generate dokumen otomatis.

### 5. Sequence Tanda Terima

Pengelolaan nomor urut (sequence) tanda terima data, agar penomoran tanda terima konsisten dan tidak duplikat.

---

## Menu Admin PIDE

Muncul untuk role `admin` atau `admin_pide`. Berisi pengelolaan referensi divisi Pengolahan Informasi Data Eksternal.

- **Durasi Jatuh Tempo PIDE** — pengaturan durasi SLA/jatuh tempo untuk proses identifikasi & perekaman di PIDE.
- **Nama Tabel** — pengelolaan nama tabel data yang diproses PIDE.
- **PIC PIDE** — pengelolaan penanggung jawab divisi PIDE. Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic).

---

## Menu Admin PMDE

Muncul untuk role `admin` atau `admin_pmde`. Berisi pengelolaan referensi divisi Pengendalian Mutu Data Eksternal.

- **Durasi Jatuh Tempo PMDE** — pengaturan durasi SLA/jatuh tempo untuk proses quality control di PMDE.
- **PIC PMDE** — pengelolaan penanggung jawab divisi PMDE. Lihat [Fokus: Cara Kerja Menu PIC](#fokus-cara-kerja-menu-pic).

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
