# Matriks RBAC & Hak Akses Menu

> **Terakhir Diperbarui:** Agustus 20, 2026 (versi 1.2.1)  
> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE

---

## Daftar Isi

- [Grup Pengguna (Role)](#grup-pengguna-role)
- [Matriks Akses Menu Berdasarkan Role](#matriks-akses-menu-berdasarkan-role)
- [Cakupan Data (Row-Level Scope)](#cakupan-data-row-level-scope)
- [Deskripsi Menu](#deskripsi-menu)
- [Implementasi RBAC](#implementasi-rbac)

---

## Grup Pengguna (Role)

Sistem Diamond memiliki **grup pengguna operasional**, **grup pengawas (kasi)**, dan **grup administrator** dengan tingkat akses yang berbeda:

### Grup Operasional

| Grup | Deskripsi | Singkatan |
|------|-----------|-----------|
| `user_p3de` | Penghimpunan Data Eksternal — Tim pengumpul data | P3DE |
| `user_pide` | Pengolahan Informasi Data Eksternal — Tim pengolah data | PIDE |
| `user_pmde` | Pengendalian Mutu Data Eksternal — Tim quality control | PMDE |

### Grup Pengawas (Kasi)

Kasi **bukan** administrator: mereka tidak memperoleh menu admin maupun sinkronisasi Oracle. Yang membedakan kasi dari pengguna biasa adalah **cakupan data** — kasi tidak dibatasi pada tiket tempat mereka menjadi PIC aktif, sehingga dapat memantau seluruh tiket unitnya.

| Grup | Deskripsi |
|------|-----------|
| `kasi_p3de` | Kepala Seksi P3DE — pengawas tim penghimpunan data |
| `kasi_pide` | Kepala Seksi PIDE — pengawas tim pengolahan data |
| `kasi_pmde` | Kepala Seksi PMDE — pengawas tim pengendalian mutu |

### Grup Pengawas Subdit

| Grup | Deskripsi |
|------|-----------|
| `kasubdit_pde` | Kepala Subdirektorat PDE — pengawas ketiga seksi |

`kasubdit_pde` **tidak** memberi hak akses apa pun: grup ini murni aturan navigasi. Anggotanya juga tergabung dalam grup seksi lain (umumnya `kasi_*`), dan grup seksi itulah yang menentukan cakupan data mereka. Yang dilakukan `kasubdit_pde` adalah **menyembunyikan** seluruh seksi menu di navbar — P3DE, PIDE, PMDE, ketiga blok Admin, dan Sinkronisasi Data — sehingga navigasi berhenti pada empat entri teratas: **Home**, **Dashboard**, **Daftar Tiket**, dan **Profil ILAP**. Aturannya berada di `diamond_web/templates/navbar.html`.

> Menyembunyikan menu bukan menutup akses: URL menu yang disembunyikan tetap dapat dibuka bila grup pendamping mengizinkannya.

### Grup Administrator

| Grup | Deskripsi |
|------|-----------|
| `admin` | Administrator global — seluruh menu admin ditambah sinkronisasi Oracle |
| `admin_p3de` | Administrator divisi P3DE — referensi & ILAP P3DE, PIC P3DE, template, sequence |
| `admin_pide` | Administrator divisi PIDE — Durasi Jatuh Tempo PIDE, Nama Tabel, PIC PIDE |
| `admin_pmde` | Administrator divisi PMDE — Durasi Jatuh Tempo PMDE, PIC PMDE |

> Rincian menu per role admin tersedia pada [Panduan Menu Admin](ADMIN_MENU_GUIDE.md).

---

## Matriks Akses Menu Berdasarkan Role

Berikut adalah matriks hak akses setiap menu di navbar untuk masing-masing grup pengguna:

### Navigasi Utama

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Dashboard** | `/` | ✅ | ✅ | ✅ | ✅ |
| **Dokumentasi** | `/docs/` | ✅ | ✅ | ✅ | ✅ |
| **Profil** | `/profil/` | ✅ | ✅ | ✅ | ✅ |

### Tiket Workflow

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Rekam Penerimaan Data** | `/tiket/rekam/` | ✅ | ❌ | ❌ | ✅ |
| **Daftar Tiket** | `/tiket/` | ✅ | ✅ | ✅ | ✅ |
| **Kirim Tiket ke PIDE** | `/tiket/kirim-tiket/` | ✅ | ❌ | ❌ | ✅ |
| **Identifikasi Tiket** | `/tiket/identifikasi/` | ❌ | ✅ | ❌ | ✅ |

### Aksi pada Detail Tiket

Aksi berikut bukan menu navbar melainkan tombol pada halaman detail tiket. Selain grup, aksi ini juga menuntut pengguna berperan sebagai **PIC aktif** yang memiliki tiket pada status berjalan.

| Aksi | URL | Syarat |
|------|-----|--------|
| **Edit Tiket** | `/tiket/<pk>/edit/` | PIC P3DE aktif, hanya selama status *Direkam* dan belum ada tanda terima. Admin P3DE (`admin`, `admin_p3de`, superuser) dikecualikan dan dapat mengedit pada status mana pun |
| **Special Request** | `/tiket/<pk>/special-request/` | PIC aktif pemilik tiket sesuai statusnya: P3DE (status 1–3), PIDE (4–5), PMDE (6). Status 7–8 tidak dapat diubah |

### Tanda Terima

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Tanda Terima Data** | `/tanda-terima-data/` | ✅ | ❌ | ❌ | ✅ |

### Backup Data

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Backup Data** | `/backup-data/` | ✅ | ❌ | ❌ | ✅ |

### Data Master

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **ILAP** | `/ilap/` | ✅ | ✅ | ✅ | ✅ |
| **Kategori ILAP** | `/kategori-ilap/` | ✅ | ✅ | ✅ | ✅ |
| **Jenis Data ILAP** | `/jenis-data-ilap/` | ✅ | ✅ | ✅ | ✅ |
| **KPP** | `/kpp/` | ✅ | ✅ | ✅ | ✅ |
| **Kanwil** | `/kanwil/` | ✅ | ✅ | ✅ | ✅ |
| **Kategori Wilayah** | `/kategori-wilayah/` | ✅ | ✅ | ✅ | ✅ |
| **PIC P3DE** | `/pic-p3de/` | ✅ | ❌ | ❌ | ✅ |
| **PIC PIDE** | `/pic-pide/` | ❌ | ✅ | ❌ | ✅ |
| **PIC PMDE** | `/pic-pmde/` | ❌ | ❌ | ✅ | ✅ |
| **Jenis Tabel** | `/jenis-tabel/` | ✅ | ✅ | ✅ | ✅ |
| **Status Data** | `/status-data/` | ✅ | ✅ | ✅ | ✅ |
| **Status Penelitian** | `/status-penelitian/` | ✅ | ✅ | ✅ | ✅ |
| **Bentuk Data** | `/bentuk-data/` | ✅ | ✅ | ✅ | ✅ |
| **Cara Penyampaian** | `/cara-penyampaian/` | ✅ | ✅ | ✅ | ✅ |
| **Dasar Hukum** | `/dasar-hukum/` | ✅ | ✅ | ✅ | ✅ |
| **Media Backup** | `/media-backup/` | ✅ | ✅ | ✅ | ✅ |
| **Periode Pengiriman** | `/periode-pengiriman/` | ✅ | ✅ | ✅ | ✅ |
| **Periode Jenis Data** | `/periode-jenis-data/` | ✅ | ✅ | ✅ | ✅ |
| **Jenis Prioritas Data** | `/jenis-prioritas-data/` | ✅ | ✅ | ✅ | ✅ |
| **Durasi Jatuh Tempo PIDE** | `/durasi-jatuh-tempo-pide/` | ❌ | ✅ | ❌ | ✅ |
| **Durasi Jatuh Tempo PMDE** | `/durasi-jatuh-tempo-pmde/` | ❌ | ❌ | ✅ | ✅ |
| **Nama Tabel** | `/nama-tabel/` | ✅ | ✅ | ✅ | ✅ |
| **Klasifikasi Jenis Data** | `/klasifikasi-jenis-data/` | ✅ | ✅ | ✅ | ✅ |
| **Template Dokumen** | `/docx-template/` | ✅ | ✅ | ✅ | ✅ |

### Laporan

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Register Penerimaan Data** | `/register-penerimaan-data/` | ✅ | ❌ | ❌ | ✅ |
| **Laporan Transfer** | `/laporan-transfer/` | ❌ | ✅ | ❌ | ✅ |
| **SLA Perekaman** | `/laporan-sla-perekaman/` | ❌ | ✅ | ❌ | ✅ |
| **SLA Identifikasi** | `/laporan-sla-identifikasi/` | ❌ | ✅ | ❌ | ✅ |
| **Metrik Data Eksternal** | `/laporan-metrik-data-eksternal/` | ❌ | ✅ | ❌ | ✅ |
| **Pengendalian Mutu** | `/laporan-pengendalian-mutu/` | ❌ | ❌ | ✅ | ✅ |
| **Hasil Pengolahan Data Prioritas** | `/laporan-hasil-pengolahan-data-prioritas/` | ❌ | ❌ | ✅ | ✅ |
| **Kelengkapan Data** | `/laporan-kelengkapan-data/` | ❌ | ❌ | ✅ | ✅ |
| **Rekap Himpun Olah Data** | `/laporan-rekap-himpun-olah-data/` | ✅ | ❌ | ✅ | ✅ |
| **Detail Himpun Olah Data** | `/laporan-detail-himpun-olah-data/` | ✅ | ❌ | ✅ | ✅ |
| **Profil ILAP (daftar)** | `/profil-ilap/` | ✅ | ✅ | ✅ | ✅ |
| **Profil ILAP (detail)** | `/profil-ilap/<id_ilap>/` | ✅ | ✅ | ✅ | ✅ |
| **Profil Sub Jenis Data** | `/jenis-data-ilap/<id_sub_jenis_data>/` | ✅ | ✅ | ✅ | ✅ |
| **Monitoring Penyampaian Data** | `/monitoring-penyampaian-data/` | ✅ | ❌ | ❌ | ✅ |
| **Quality Control** | `/quality-control/` | ❌ | ❌ | ✅ | ✅ |
| **Identifikasi** | `/identifikasi/` | ❌ | ✅ | ❌ | ✅ |

> Baris di atas mencerminkan pengecekan grup yang benar-benar ada di kode (`test_func`/`@user_passes_test` pada masing-masing view), bukan hanya penempatan tautan di navbar. Riwayat koreksi baris-baris ini — dan detail lebih lanjut tiap menu — ada di [Panduan Menu Pengguna](PANDUAN_MENU_PENGGUNA.md).

### Dashboard & Sinkronisasi

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Dashboard Power BI** | `/dashboard/` | ✅ | ✅ | ✅ | ✅ |
| **Sync Data Referensi** | `/sync-data-referensi/` | ❌ | ❌ | ❌ | ✅ |
| **Sync Tiket** | `/sync-tiket/` | ❌ | ❌ | ❌ | ✅ |

### Admin

| Menu | URL | P3DE | PIDE | PMDE | Admin |
|------|-----|:----:|:----:|:----:|:-----:|
| **Admin Django** | `/admin/` | ❌ | ❌ | ❌ | ✅ (superuser) |
| **Bulk Generate Dokumen** | `/bulk-generate/` | ✅ | ✅ | ❌ | ✅ |

---

## Cakupan Data (Row-Level Scope)

Hak akses menu menentukan halaman mana yang boleh dibuka; **cakupan data** menentukan baris mana yang terlihat di dalamnya. Keduanya terpisah — dua pengguna dengan menu yang sama dapat melihat isi tabel yang berbeda.

| Kelompok | Cakupan tiket yang terlihat |
|----------|-----------------------------|
| Superuser & grup `admin` | Seluruh tiket |
| Grup kasi (`kasi_p3de`, `kasi_pide`, `kasi_pmde`) | Seluruh tiket |
| `user_p3de` / `user_pide` / `user_pmde` | Hanya tiket dengan penugasan `TiketPIC` aktif atas nama pengguna tersebut |

Aturan ini berlaku konsisten pada Daftar Tiket, dashboard Tugas Saya, Monitoring Penyampaian Data, Quality Control, dan endpoint ringkasan tiket pada Backup Data. Endpoint JSON menerapkan cakupan yang sama seperti halamannya, sehingga id tiket tidak dapat ditelusuri secara berurutan untuk membaca data di luar cakupan pengguna.

### Blok "Informasi PIC & Kontak" pada Profil ILAP

Katalog ILAP tidak dibatasi per pengguna: setiap pengguna yang login dapat mencari dan membuka profil ILAP maupun sub jenis data mana pun. Yang dibatasi hanyalah blok **Informasi PIC & Kontak** (nama, jabatan, email, telepon PIC instansi, fax, tujuan surat, tembusan), karena itu adalah data korespondensi dengan instansi.

| Kelompok | Melihat blok Informasi PIC & Kontak |
|----------|--------------------------------------|
| Superuser, `admin`, `admin_p3de` | Seluruh ILAP |
| `kasi_p3de` | Seluruh ILAP |
| `kasi_pide`, `kasi_pmde`, `user_p3de`/`user_pide`/`user_pmde`, lainnya | Hanya ILAP dengan penugasan `PIC` aktif (tipe P3DE, PIDE, atau PMDE) pada minimal satu jenis data milik ILAP tersebut |

Helper terkait berada di `diamond_web/views/mixins.py`: `is_kasi()`, `is_kasi_p3de()`, `is_kasi_pide()`, `is_kasi_pmde()`, `is_admin_p3de()`, `can_access_tiket_list()`, `is_active_ilap_pic()`, dan `can_view_ilap_kontak()`.

---

## Ringkasan Hak Akses per Role

### User P3DE
- ✅ Akses penuh ke tiket workflow (rekam, teliti, kirim)
- ✅ Manajemen backup data dan tanda terima
- ✅ Semua data master (read & write)
- ✅ Laporan P3DE (Register Penerimaan, Monitoring Penyampaian Data, Rekap Himpun Olah Data, Detail Himpun Olah Data)
- ❌ Tidak bisa mengakses halaman identifikasi PIDE
- ❌ Tidak bisa mengakses laporan yang PIDE/PMDE-only (SLA Perekaman, SLA Identifikasi, Metrik Data Eksternal, Pengendalian Mutu, Kelengkapan Data, Hasil Pengolahan Data Prioritas)
- ❌ Tidak bisa mengakses sync Oracle

### User PIDE
- ✅ Akses identifikasi tiket
- ✅ Transfer tiket ke PMDE
- ✅ Semua data master (read & write)
- ✅ Laporan PIDE (Transfer, SLA Perekaman, SLA Identifikasi, Metrik Data Eksternal)
- ❌ Tidak bisa merekam tiket baru
- ❌ Tidak bisa mengakses backup data, tanda terima, maupun Monitoring Penyampaian Data
- ❌ Tidak bisa mengakses Quality Control maupun laporan PMDE
- ❌ Tidak bisa mengakses sync Oracle

### User PMDE
- ✅ Quality control dan penyelesaian tiket
- ✅ Semua data master (read & write)
- ✅ Laporan PMDE (Pengendalian Mutu, Kelengkapan Data, Hasil Pengolahan Data Prioritas)
- ✅ Laporan Rekap & Detail Himpun Olah Data (dipakai bersama P3DE)
- ❌ Tidak bisa merekam atau mengirim tiket
- ❌ Tidak bisa mengakses backup data, tanda terima, maupun Monitoring Penyampaian Data
- ❌ Tidak bisa mengakses halaman identifikasi maupun laporan PIDE
- ❌ Tidak bisa mengakses sync Oracle

### Kasi (kasi_p3de / kasi_pide / kasi_pmde)
- ✅ Melihat seluruh tiket unitnya tanpa harus menjadi PIC aktif — berlaku di Daftar Tiket untuk ketiganya, ditambah halaman antrean unit masing-masing: **Identifikasi** untuk `kasi_pide`, **Quality Control** untuk `kasi_pmde`
- ❌ `kasi_p3de` **tidak** mendapat akses ke menu Monitoring Penyampaian Data — P3DE tidak memiliki padanan halaman antrean unit seperti Identifikasi/Quality Control
- ❌ Ketiga grup kasi juga tidak mendapat akses ke menu Laporan divisinya (Register Penerimaan Data, SLA Perekaman, SLA Identifikasi, Transfer, Metrik Data Eksternal, Pengendalian Mutu, Kelengkapan Data, Hasil Pengolahan Data Prioritas, Rekap/Detail Himpun Olah Data) — laporan-laporan tersebut hanya mengizinkan grup `user_*`/`admin*`, bukan `kasi_*`
- ❌ Tidak memperoleh menu admin (referensi, PIC, template, sequence)
- ❌ Tidak bisa mengakses sync Oracle
- ❌ Tidak memperoleh aksi alur kerja yang menuntut peran PIC aktif

### Kasubdit (kasubdit_pde)
- ✅ Navigasi hanya menampilkan **Home**, **Dashboard**, **Daftar Tiket**, dan **Profil ILAP**
- ✅ Cakupan data keempat halaman tersebut mengikuti grup pendamping (`kasi_*`/`user_*`) yang juga disandang pengguna
- ❌ Seluruh seksi menu P3DE/PIDE/PMDE disembunyikan, termasuk Identifikasi dan Quality Control yang biasanya didapat kasi
- ❌ Blok menu Admin dan Sinkronisasi Data disembunyikan
- ℹ️ Grup ini tidak menambah maupun mengurangi hak akses di sisi view — hanya tampilan menu

### Admin
- ✅ Semua akses termasuk sync Oracle
- ✅ Manajemen user melalui Django Admin
- ✅ Template dokumen dan bulk generate
- ✅ Semua laporan
- ✅ Admin P3DE (`admin`, `admin_p3de`, superuser) dapat mengedit isian tiket pada status mana pun

---

## Implementasi RBAC

RBAC diimplementasikan menggunakan:

1. **Django Group Model** — Grup dibuat melalui Django Admin
2. **Decorator di Views** — Pengecekan grup menggunakan `request.user.groups.filter(name='...').exists()`
3. **Mixin & Helper Terpusat** — `diamond_web/views/mixins.py` menyediakan mixin (`UserP3DERequiredMixin`, `ActiveTiketP3DERequiredForEditMixin`, dll.) dan helper grup (`is_kasi`, `is_admin_p3de`, `can_access_tiket_list`) agar aturan yang sama tidak ditulis ulang per view
4. **Template Tag `has_group`** — Filter UI di template (`diamond_web/templatetags/auth_extras.py`)
5. **Home View** — Dashboard berbeda ditampilkan berdasarkan role (`diamond_web/views/home.py`)

### Contoh Pengecekan di View

```python
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@login_required
def rekam_tiket(request):
    if not request.user.groups.filter(name='user_p3de').exists():
        raise PermissionDenied("Anda tidak memiliki akses ke menu ini.")
    # ... logic view ...
```

### Contoh Filter di Template

```django
{% load auth_extras %}

{% if request.user|has_group:'user_p3de' or request.user|has_group:'admin' %}
<li class="nav-item">
    <a class="nav-link" href="{% url 'rekam_tiket' %}">
        <i class="feather-plus-circle"></i>
        <span>Rekam Penerimaan Data</span>
    </a>
</li>
{% endif %}
```
