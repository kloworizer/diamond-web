# Matriks RBAC & Hak Akses Menu

> **Terakhir Diperbarui:** Juni 24, 2026  
> **Proyek:** Diamond — Sistem P3DE/PIDE/PMDE

---

## Daftar Isi

- [Grup Pengguna (Role)](#grup-pengguna-role)
- [Matriks Akses Menu Berdasarkan Role](#matriks-akses-menu-berdasarkan-role)
- [Deskripsi Menu](#deskripsi-menu)
- [Implementasi RBAC](#implementasi-rbac)

---

## Grup Pengguna (Role)

Sistem Diamond memiliki **4 grup pengguna** dengan tingkat akses yang berbeda:

| Grup | Deskripsi | Singkatan |
|------|-----------|-----------|
| `user_p3de` | Penghimpunan Data Eksternal — Tim pengumpul data | P3DE |
| `user_pide` | Pengolahan Informasi Data Eksternal — Tim pengolah data | PIDE |
| `user_pmde` | Pengendalian Mutu Data Eksternal — Tim quality control | PMDE |
| `admin` | Administrator sistem — Akses penuh termasuk sync Oracle | Admin |

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
| **SLA Perekaman** | `/laporan-sla-perekaman/` | ✅ | ❌ | ❌ | ✅ |
| **SLA Identifikasi** | `/laporan-sla-identifikasi/` | ❌ | ✅ | ❌ | ✅ |
| **Metrik Data Eksternal** | `/laporan-metrik-data-eksternal/` | ❌ | ✅ | ❌ | ✅ |
| **Pengendalian Mutu** | `/laporan-pengendalian-mutu/` | ❌ | ❌ | ✅ | ✅ |
| **Hasil Pengolahan Data Prioritas** | `/laporan-hasil-pengolahan-data-prioritas/` | ❌ | ✅ | ❌ | ✅ |
| **Kelengkapan Data** | `/laporan-kelengkapan-data/` | ❌ | ❌ | ✅ | ✅ |
| **Rekap Himpun Olah Data** | `/laporan-rekap-himpun-olah-data/` | ❌ | ❌ | ✅ | ✅ |
| **Detail Himpun Olah Data** | `/laporan-detail-himpun-olah-data/` | ❌ | ❌ | ✅ | ✅ |
| **Profil ILAP** | `/profil-ilap/` | ✅ | ✅ | ✅ | ✅ |
| **Monitoring Penyampaian Data** | `/monitoring-penyampaian-data/` | ✅ | ✅ | ✅ | ✅ |
| **Quality Control** | `/quality-control/` | ❌ | ✅ | ✅ | ✅ |

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

## Ringkasan Hak Akses per Role

### User P3DE
- ✅ Akses penuh ke tiket workflow (rekam, teliti, kirim)
- ✅ Manajemen backup data dan tanda terima
- ✅ Semua data master (read & write)
- ✅ Laporan P3DE (Register Penerimaan, SLA Perekaman)
- ❌ Tidak bisa mengakses halaman identifikasi PIDE
- ❌ Tidak bisa mengakses laporan PMDE
- ❌ Tidak bisa mengakses sync Oracle

### User PIDE
- ✅ Akses identifikasi tiket
- ✅ Transfer tiket ke PMDE
- ✅ Semua data master (read & write)
- ✅ Laporan PIDE (Transfer, SLA Identifikasi, Metrik Data, Hasil Pengolahan)
- ❌ Tidak bisa merekam tiket baru
- ❌ Tidak bisa mengakses backup data
- ❌ Tidak bisa mengakses sync Oracle

### User PMDE
- ✅ Quality control dan penyelesaian tiket
- ✅ Semua data master (read & write)
- ✅ Laporan PMDE (Kelengkapan Data, Rekap Himpun Olah Data, Detail Himpun Olah Data)
- ❌ Tidak bisa merekam atau mengirim tiket
- ❌ Tidak bisa mengakses backup data
- ❌ Tidak bisa mengakses sync Oracle

### Admin
- ✅ Semua akses termasuk sync Oracle
- ✅ Manajemen user melalui Django Admin
- ✅ Template dokumen dan bulk generate
- ✅ Semua laporan

---

## Implementasi RBAC

RBAC diimplementasikan menggunakan:

1. **Django Group Model** — Grup dibuat melalui Django Admin
2. **Decorator di Views** — Pengecekan grup menggunakan `request.user.groups.filter(name='...').exists()`
3. **Template Tag `has_group`** — Filter UI di template (`diamond_web/templatetags/auth_extras.py`)
4. **Home View** — Dashboard berbeda ditampilkan berdasarkan role (`diamond_web/views/home.py`)

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
