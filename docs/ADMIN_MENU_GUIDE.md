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

### Skenario 2 — Mengisi End Date (Menonaktifkan PIC)

Saat admin mengubah PIC dan **mengisi End Date** yang sebelumnya kosong:

1. Sistem mencari semua penugasan `TiketPIC` yang **masih aktif** untuk user + divisi + Sub Jenis Data tersebut.
2. Setiap penugasan itu **dinonaktifkan** (bukan dihapus — datanya tetap ada untuk histori).
3. Dicatat riwayat **"Tidak Aktif"** pada masing-masing tiket.

**Efeknya:** user tidak lagi tercatat sebagai penanggung jawab aktif pada tiket-tiket berjalan, tetapi jejak penugasannya tetap tersimpan.

> **Penting:** Menonaktifkan PIC dilakukan dengan **mengisi End Date**, bukan menghapus record. Ini cara yang benar untuk "memberhentikan" seorang PIC sambil menjaga histori.

### Skenario 3 — Menghapus (Mengosongkan) End Date (Mengaktifkan Kembali)

Saat admin mengubah PIC dan **mengosongkan kembali End Date** yang sebelumnya terisi:

1. Sistem mencari semua tiket berjalan dengan Sub Jenis Data yang sama.
2. Untuk setiap tiket:
   - Jika penugasan lama masih ada (nonaktif) → **diaktifkan kembali**, dicatat riwayat **"Diaktifkan Kembali"**.
   - Jika belum ada penugasan → dibuat penugasan baru, dicatat riwayat **"Ditambahkan"**.

**Efeknya:** PIC kembali aktif dan otomatis dipasang lagi pada tiket-tiket berjalan.

### Skenario 4 — Menghapus Record PIC

Saat admin menekan **Hapus** pada sebuah PIC:

1. Sistem mencari **semua** penugasan `TiketPIC` (aktif maupun tidak) untuk user + divisi + Sub Jenis Data tersebut.
2. Seluruh penugasan itu **dihapus**.
3. Dicatat riwayat **"Tidak Aktif"** (dengan catatan bahwa PIC dihapus) pada masing-masing tiket.
4. Terakhir, record PIC itu sendiri dihapus.

> **Perbedaan Hapus vs Isi End Date:**
> - **Isi End Date** → penugasan tiket dinonaktifkan tetapi **tetap tersimpan** (histori terjaga). Bisa diaktifkan kembali dengan mengosongkan End Date.
> - **Hapus** → penugasan tiket **benar-benar dihapus**. Gunakan hanya bila data PIC salah/tidak diperlukan. Untuk pemberhentian normal, **lebih disarankan mengisi End Date**.

---

### Aturan Validasi Form PIC

Agar data konsisten, form PIC menerapkan aturan berikut:

- **Saat mengubah (Edit):** field **Tipe**, **Sub Jenis Data**, dan **User** dikunci (tidak bisa diubah). Hanya **Start Date** dan **End Date** yang dapat disunting. Untuk mengganti user/data, buat record PIC baru.
- **User dibatasi per divisi:** dropdown user hanya menampilkan anggota grup yang sesuai (`user_p3de` / `user_pide` / `user_pmde`).
- **Tidak boleh duplikat:** kombinasi Tipe + Sub Jenis Data + User + Start Date yang sama persis akan ditolak.
- **Tidak boleh tumpang tindih aktif:** bila sudah ada PIC **aktif** (End Date kosong) untuk user & Sub Jenis Data yang sama, penambahan PIC aktif baru ditolak. Isi dulu End Date pada PIC yang lama sebelum membuat yang baru.

### Fitur Tabel PIC

Halaman daftar PIC menampilkan tabel dengan kolom: ILAP, ID Sub Jenis Data, Nama Sub Jenis Data, Username, Full Name, Start Date, dan End Date. Tabel mendukung:

- **Pencarian per kolom** (kotak pencarian di bawah setiap judul kolom) dan tombol **Reset Pencarian**.
- **Pengurutan** kolom serta **paginasi** (server-side).
- Kolom **Aksi** (tombol Edit & Hapus) **hanya muncul untuk admin**. User biasa dapat melihat daftar tetapi tanpa tombol aksi.
