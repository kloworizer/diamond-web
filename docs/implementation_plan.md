# Implementasi UI/UX Polishing (Home, Rekam Tiket, Detail Tiket)

Rencana ini merinci langkah-langkah untuk menyempurnakan UI/UX sesuai dengan prinsip desain modern (UIUX Promax) dan feedback yang telah Anda berikan. 

Mengingat kompleksitas dan pentingnya menjaga stabilitas fitur, eksekusi akan dilakukan secara bertahap (per batch). Setiap batch akan direview bersama sebelum berlanjut ke batch berikutnya.

> [!NOTE]
> Semua pekerjaan dilakukan di branch baru: `alvian-frontend/feat-tiket-ui-ux-polishing`.

---

## Pembagian Batch Eksekusi

### Batch 1: Home Dashboard & Global Fixes
Fokus pada perbaikan di halaman Home dan perbaikan global untuk form ILAP.
1. **Definisi Ulang Summary Jenis Data (Home):** Mengubah `home.py` agar badge di sidebar menu menampilkan jumlah **Jenis Data Unik** (menggunakan `jenis_datas`) bukan total tiket fisik.
2. **Penambahan Kolom Jml Baris Data (Home):** Menyisipkan kolom *Jml Baris Data* setelah kolom *Nama Tabel I* pada datatable di submenu Home yang relevan (misal: antrean P3DE, PIDE, dsb).
3. **Sorting NAMA ILAP (Global):** Memodifikasi form tiket (`diamond_web/forms/tiket.py`) agar Select2 untuk ILAP diurutkan berdasarkan `nama_ilap` (alfabetis), bukan berdasarkan `id_ilap`.

### Batch 2: Form Rekam Tiket (Interaktivitas & Styling)
Fokus pada fungsionalitas dan estetika halaman Rekam Tiket (`rekam_tiket_form.html`).
1. **Interaktivitas Ketersediaan Data:** Menambahkan Javascript agar field *Alasan Ketidaktersediaan* otomatis *hidden* jika radio button "Data Tersedia" dipilih, dan *muncul/required* jika "Data Tidak Tersedia" dipilih.
2. **Restyling Card ILAP & PIC:** Mendesain ulang *Card Informasi Jenis Data ILAP & PIC* agar tampilannya seragam, modern, rapi, dan sesuai dengan mock-up UIUX Promax.
3. **Redesign Switch Permintaan Khusus:** Mempercantik toggle switch *Permintaan Khusus* agar terlihat lebih modern (bukan checkbox/switch default biasa).
4. **Client-side Form Validation:** Menambahkan *mandatory checking* (pengecekan kolom wajib isi) yang memberikan *feedback visual* langsung (highlight merah/pesan error) sebelum user menekan tombol submit (atau memunculkan modal).

### Batch 3: Modal Konfirmasi & Redesign Tambahan
Fokus pada tahap akhir perekaman tiket.
1. **Styling Modal Konfirmasi:** Merapikan dan mendesain ulang layout *Modal Konfirmasi Data* agar informasi lebih mudah dibaca, tipografi lebih baik, dan style tombol (primary/secondary) lebih pas.
2. **General Form Redesign:** Melakukan *touch-up* pada spacing, alignment, dan warna keseluruhan form agar terasa lebih premium.

### Batch 4: Halaman Detail Tiket
Fokus pada penyempurnaan UI/UX di `tiket_detail.html`.
1. **Restyling Card Informasi Utama:** Menyelaraskan layout *Card Informasi Utama (Tiket & ILAP)* dengan hasil diskusi desain terbaru.
2. **Penyesuaian Button Aksi:** Memastikan *Card Aksi* menggunakan hierarki tombol yang benar (Primary untuk aksi utama, Secondary/Tertiary untuk aksi opsional atau kembali).
3. **Visibilitas Semua Metrik Kualitas:** Menyesuaikan *Card Metrik Kualitas & Hasil QC Data* agar selalu menampilkan semua jenis metrik (CDE, baris lengkap, dll) meskipun nilainya `0`, untuk memberikan kepastian kepada user bahwa data tersebut tidak bermasalah.

---

## User Review Required

> [!IMPORTANT]
> **Strategi Eksekusi Batch**
> Apakah Anda setuju dengan pembagian 4 batch di atas? Jika setuju, setelah Anda klik **Proceed**, saya akan mengerjakan **Batch 1** terlebih dahulu, kemudian meminta Anda mengecek hasilnya di browser sebelum saya lanjut ke Batch 2.

## Open Questions

1. **Jml Baris Data di Home:** Untuk kolom "Jml Baris Data" yang akan ditambahkan setelah "NAMA TABEL I", apakah Anda ingin datanya diambil dari `baris_lengkap` atau `baris_diterima`?
2. **Card Detail Tiket:** Ada arahan spesifik/referensi desain untuk layout *Card Informasi Utama (Tiket & ILAP)* di Detail Tiket yang dirasa berbeda dari diskusi sebelumnya? (Misalnya: mau dijadikan 2 kolom, atau dipisahkan sectionnya).
