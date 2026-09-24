# Catatan Rilis & Perubahan

## [1.2.2] — 2026-09-24

### Ditambahkan
- **Halaman Antrean Seksi: Identifikasi (PIDE) & Quality Control (PMDE)** — Halaman baru `/identifikasi/` untuk PIDE yang berbagi mesin yang sama dengan Quality Control (`seksi_queue`): panel filter Select2 bertingkat, tiga bagian ringkasan (antrean berjalan, pekerjaan selesai 90 hari terakhir, dan rekap per tahun) dengan rincian per jenis tabel dan kategori wilayah, grafik sisa pekerjaan per jatuh tempo, serta tabel antrean. Beban tiket diberi bobot berdasarkan karakteristik dan kedekatan jatuh tempo, dan jatuh tempo **Special Request** didahulukan atas durasi standar.
- **Aturan Durasi Jatuh Tempo (PIDE & PMDE)** — Model `AturanDurasiJatuhTempo` beserta menu CRUD terpisah untuk Admin PIDE dan Admin PMDE. Durasi Jatuh Tempo dapat **di-generate** dari aturan tersebut, disinkronkan dengan periode prioritas, dan di-*backfill* ke tiket; setiap aksi menampilkan pratinjau sebelum dikonfirmasi. Durasi PMDE kini ditentukan per tahun sesuai tumpang-tindih tahun tersebut dengan periode prioritas.
- **Sinkronisasi Prioritas Tiket** — Tombol **Sync Prioritas** pada daftar Data Prioritas untuk menyelaraskan penanda prioritas tiket dengan tabel Data Prioritas, dengan modal pratinjau tiket yang akan berubah dan pencatatan pada riwayat aksi tiket. Menghapus Data Prioritas ikut memperbarui tiket terkait. Menu Data Prioritas kini dapat dikelola oleh seluruh grup admin.
- **Penugasan Otomatis PIC PMDE** — Tombol pada dashboard PMDE untuk menugaskan PIC secara otomatis ke Sub Jenis Data yang berbagi **Nama Tabel I** yang sama, terbatas pada Sub Jenis Data berawalan `PV` dan `PD`. Modal pratinjau menampilkan ringkasan penugasan beserta rincian baris yang dilewati per nama tabel; tanggal mulai penugasan memakai tanggal tetap dan konflik tanggal ditangani.
- **Profil PIC** — Halaman `/profil-pic/<username>/` yang merangkum penugasan seorang PIC: ILAP (dengan wilayah), Sub Jenis Data (tiket aktif dan tidak aktif), Nama Tabel, dan daftar tiketnya, dilengkapi tombol salin daftar ILAP dan Nama Tabel. Nama PIC di seluruh aplikasi ditautkan ke profil ini melalui template tag `pic_name_link` hanya bila pengguna berhak melihatnya.
- **Detail Nama Tabel** — Halaman `/nama-tabel/<nama_tabel>/` yang mengagregasi statistik dan tiket dari seluruh Sub Jenis Data yang memakai nama tabel tersebut, diurutkan dari yang paling sering dipakai, dengan tombol salin. Nama Tabel juga muncul pada saran pencarian global di navbar.
- **Daftar PIC Terpadu** — Halaman `/pic/` yang menyatukan PIC P3DE, PIDE, dan PMDE dengan filter bertingkat dua arah pada modal. Rute `pic-p3de/` lama tetap dipertahankan.
- **ND Pengantar ke PDI untuk Data Adhoc** — Pembuatan massal ND Pengantar ke PDI bagi tiket adhoc (Nama Tabel I kosong) yang dipegang PIC PMDE aktif, dengan template bawaan baru. Pembuatan dokumen tunggal kini juga mendukung tipe `nd_pengantar`, dan field `nama_tabel_i` tersedia pada template DOCX.
- **Rematch pada Sinkronisasi Tiket** — Aksi tiket baru *Rematch* (`action = 11`) yang dicatat oleh proses Sinkronisasi Update Tiket, serta tampilan galat per tiket pada halaman sinkronisasi.
- **Aturan 9: Pembukaan Kembali Tiket Selesai** — Tiket berstatus *Selesai* yang tanggal transfernya direvisi PIDE dikembalikan ke *Pengendalian Mutu*. Perintah `fix_tiket_transfer_ulang` memperbaiki tiket yang terlanjur tertutup; deteksinya memakai dua sidik jari jejak audit dan bersifat idempoten. Lihat `docs/SYNC_TIKET_UPDATE_RULES.md`.
- **Watchlist Tiket Tersimpan di Database** — Tiket yang ditandai bintang (`UserStarredTiket`) kini tersimpan per pengguna sehingga terbawa lintas perangkat; *drawer* watchlist diurutkan berdasarkan status dan waktu penugasan.
- **Aksi Cepat pada Dashboard Home** — Tombol aksi langsung untuk tiket *Belum Diteliti*, *Backup*, *Tanda Terima*, *Rekam Hasil Penelitian*, dan *Proses Identifikasi* yang membuka modalnya di halaman Home tanpa berpindah halaman. Ditambah kolom **Jumlah Baris** (dapat diurutkan), **Jenis Tabel**, dan **Periode Data**, filter prioritas, serta detail tiket yang dibuka di tab baru.
- **Filter Tanggal pada Daftar Tiket & Antrean Seksi** — Filter rentang **Tahun Diterima** dan **Tanggal Terima DIP**, serta filter **Prioritas** pada daftar tiket. Quality Control kini juga dapat difilter berdasarkan jatuh tempo.
- **Pemilihan Kanwil pada Formulir ILAP** — Formulir ILAP kini dapat memetakan ILAP langsung ke Kanwil, sesuai pemetaan ILAP kategori `PV` yang diperkenalkan pada 1.2.0.
- **Grup `kasubdit_pde`** — Grup navigasi untuk Kepala Subdirektorat PDE yang merampingkan navbar menjadi Home, Dashboard, Daftar Tiket, dan Profil ILAP. Grup ini tidak memberi hak akses; cakupan data tetap ditentukan oleh grup seksi anggotanya. Lihat `docs/RBAC_MATRIX.md`.
- **Penyempurnaan Formulir Rekam Tiket** — *Popover* tiket duplikat dengan tautan ke tiket sebelumnya, tombol format otomatis nama file, pemisah ribuan pada Baris Diterima, dan ringkasan isian pada modal konfirmasi.
- **Perintah Manajemen Pemeliharaan Data** — `backfill_old_db_tiket_actions` (rekonstruksi riwayat aksi tiket hasil migrasi `old_db`, termasuk pembersihan tiket dibatalkan), `restore_tiket_pic_dihapus` (mengembalikan penugasan PIC yang terlanjur terhapus, mendukung `--dry-run`, `--tipe`, dan `--user`), `rebuild_jenis_prioritas_from_temp`, dan `backfill_tiket_jenis_prioritas`. Lihat `docs/ADMIN_MENU_GUIDE.md` dan `docs/DATA_MIGRATION_DEV_PHASE.md`.

### Diubah
- **Pembaruan Dependensi** — Django `5.2.14` → `5.2.17` dan sqlparse `0.5.5` → `0.6.0`. Seluruh test suite lolos tanpa kegagalan baru dan tanpa peringatan deprecation dari kedua pustaka.
- **Jatuh Tempo Special Request Opsional pada Rekam Tiket** — Pada formulir Rekam Tiket, `tgl_special_request` kini opsional sesuai proses bisnis. Modal Special Request tetap mewajibkannya selama penanda aktif. Hitungan Special Request pada dashboard tidak lagi menyertakan tiket yang sudah selesai atau dibatalkan.
- **Tambah PIC yang Sudah Aktif** — Mengirim ulang PIC yang sudah aktif kini menyinkronkan penugasannya ke tiket berjalan alih-alih menampilkan galat. PIC P3DE yang End Date-nya sudah lewat tidak lagi muncul pada *dropdown* formulir tiket.
- **Akses Kasi & Profil ILAP** — Kasi memperoleh akses baca-saja ke halaman PIC seksinya, dan navbar menyesuaikan. Profil ILAP kini dapat dibuka oleh semua pengguna yang login.
- **Sesi Lintas Tab** — Logout di satu tab tidak lagi merusak tab lain; muncul modal pemulihan sesi yang memungkinkan pengguna login kembali tanpa kehilangan isian formulir. Respons AJAX kini membedakan 401 (sesi habis) dari 403 (tidak berhak) melalui `AjaxLoginRequiredMixin`.
- **Performa** — Indeks basis data baru pada kolom yang sering di-query, helper `user_group_names` untuk mengurangi query keanggotaan grup berulang, dan filter Monitoring Penyampaian Data yang kini dieksekusi di tingkat database.
- **Tampilan Antarmuka** — Penataan ulang halaman detail tiket dan modal konfirmasi, judul tab browser dinamis sesuai halaman, penomoran baris DataTables, penyeragaman huruf tombol, dan perbaikan label agar lebih jelas.

### Diperbaiki
- Sesi berakhir terlalu cepat akibat konflik antara *keep-alive* sisi klien dan `SlidingSessionMiddleware`, serta kegagalan CSRF saat logout otomatis.
- Baris Diterima tampil sebagai tanda strip pada modal konfirmasi untuk angka besar.
- Jumlah per kategori pada dashboard Home yang keliru, dan *parsing* parameter endpoint `home_data` yang belum aman.
- `TemplateSyntaxError` pada halaman Tanda Terima akibat tag komentar multi-baris.
- Pilihan tiket pada formulir Tanda Terima hilang ketika server menolak submit.
- Endpoint data master Nama Tabel mengalihkan `admin_pide` padahal halamannya dapat mereka buka; kini seluruh view Nama Tabel memakai `AdminPIDERequiredMixin`.
- Format `tgl_terima_dip` pada data tiket kini tanpa komponen jam.
- Salin nomor tiket pada detail tiket kini memiliki *fallback* clipboard dan notifikasi *toast*.

### Catatan Pembaruan
- Jalankan `python manage.py migrate`. Rilis ini menambahkan migrasi `0012`–`0017`, termasuk *seed* Aturan Durasi Jatuh Tempo dan template ND Pengantar ke PDI.
- Instal ulang dependensi agar Django `5.2.17` dan sqlparse `0.6.0` terpasang: `pip install --no-index --find-links=./packages -r requirements/base.txt`.

### Known Issues
- Pemetaan wilayah baru mencakup ILAP kategori `PV` (Pemda Provinsi) yang di-seed langsung ke Kanwil. Data KPP dan pemetaan ILAP kategori `PD` (Pemda Kabupaten/Kota) ke KPP masih perlu dilengkapi.
- Template dokumen (DOCX) belum sempurna — beberapa placeholder masih perlu penyesuaian.
- Flow sinkronisasi ke bankdata untuk tiket baru belum lengkap.

### Rencana
- Pengembangan halaman Dashboard dengan Power BI.
- Penyempurnaan template dokumen (Tanda Terima, ND Pengantar, Surat Klarifikasi, PKDI).
- Penyempurnaan flow sinkronisasi tiket new Diamond dari bankdata.
- Melengkapi data KPP dan pemetaan ILAP kategori `PD` ke KPP.

## [1.2.1] — 2026-08-04

### Ditambahkan
- **Jatuh Tempo Permintaan Khusus** — Field baru `tgl_special_request` pada tiket untuk mencatat batas waktu permintaan khusus. Jatuh tempo **wajib diisi** selama penanda `special_request` aktif dan otomatis dikosongkan saat penanda dimatikan; aturan yang sama berlaku pada formulir Rekam Tiket maupun modal Special Request. Tanggal dipilih sebagai tanggal saja lalu disimpan pada pukul 23:59:59 (helper `end_of_day`) agar batas waktu tetap berlaku sepanjang hari tersebut. Kolom **Jatuh Tempo** ikut tampil pada daftar tiket dan pada kartu Special Request di dashboard.
- **Grafik Jml Progress per Jatuh Tempo (Quality Control)** — Grafik garis pada halaman Quality Control dengan satu garis per PIC PMDE, sumbu-X berupa sisa hari menuju jatuh tempo dan sumbu-Y berupa total Jml Progress. Warna dan pola garis ditetapkan di sisi server atas lingkup penuh sehingga seorang PIC selalu memakai garis yang sama pada filter apa pun; tiket tanpa PIC PMDE aktif memakai garis abu-abu terpisah. Grafik dan tabel dibaca dari parameter filter yang sama melalui endpoint `get_chart_data=1`.
- **Edit Tiket oleh Admin: Hasil Penelitian & Pengiriman ke PIDE** — Modal Edit Tiket kini menampilkan bagian khusus Admin P3DE untuk mengoreksi `tgl_teliti`, `baris_lengkap`, `baris_tidak_lengkap` (dengan `status_penelitian` dihitung ulang otomatis) serta `tgl_nadine`, `nomor_nd_nadine`, dan `tgl_kirim_pide`. Bagian tersebut hanya muncul untuk tahap yang sudah dilalui tiket, dan field-nya dikeluarkan dari form — bukan sekadar disembunyikan — sehingga tidak dapat dikirim lewat POST maupun ikut terkosongkan saat penyimpanan.
- **Pengujian Validasi End-to-End** — Skenario `rule_*` / `val_*` baru yang memverifikasi pesan galat milik masing-masing aturan, mencakup rantai kronologi tanggal penuh (`dip ≤ tanda terima ≤ teliti ≤ nadine ≤ kirim PIDE ≤ rekam PIDE ≤ transfer`), total baris/QC, jatuh tempo permintaan khusus, aturan kata sandi pada Profil, serta aturan form data master (rentang tanggal tumpang tindih, kunci ganda, batas tahun Sequence Tanda Terima, dan lingkup Tanda Terima). Ditambah pengujian unit untuk grafik Quality Control dan bagian khusus admin pada Edit Tiket.

### Diubah
- **Ganti User pada Edit PIC = Serah Terima ke Tiket Berjalan** — Mengganti field **User** pada sebuah PIC kini merambat ke tiket: PIC lama dinonaktifkan (aksi *Tidak Aktif*, dengan catatan *"… diganti oleh &lt;user baru&gt;"*) dan PIC baru langsung ditugaskan pada tiket yang sama persis seperti saat menambah PIC — dibuat baru (*Ditambahkan*) atau diaktifkan kembali (*Diaktifkan Kembali*) bila penugasannya pernah ada. Sebelumnya perubahan user tidak diteruskan sama sekali ke `TiketPIC`. Serah terima hanya menyentuh **tiket berjalan** sehingga tiket yang sudah dibatalkan/selesai tetap mencatat pengerjanya; bila User diganti sekaligus End Date diisi, edit tersebut dianggap pemberhentian dan tidak ada pengganti yang dipasang. Lihat `docs/ADMIN_MENU_GUIDE.md`.
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
