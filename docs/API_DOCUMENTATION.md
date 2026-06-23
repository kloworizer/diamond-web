# API Documentation

> **Last Updated:** June 23, 2026  
> **Base URL:** `https://diamond.pajak.go.id` (production) or `http://localhost:8000` (development)

---

## Table of Contents

- [Authentication](#authentication)
- [API Endpoints Overview](#api-endpoints-overview)
- [AJAX DataTables Endpoints](#ajax-datatables-endpoints)
- [CRUD Master Data Endpoints](#crud-master-data-endpoints)
- [Tiket Workflow Endpoints](#tiket-workflow-endpoints)
- [Report & Export Endpoints](#report--export-endpoints)
- [Document Generation Endpoints](#document-generation-endpoints)
- [Oracle Sync Endpoints](#oracle-sync-endpoints)
- [Notification Endpoints](#notification-endpoints)
- [Utility Endpoints](#utility-endpoints)
- [Error Handling](#error-handling)

---

## Authentication

This application uses Django's built-in session-based authentication. All authenticated endpoints require an active session.

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/login/` | Login form submission (CSRF protected) |
| `POST` | `/logout/` | Logout (POST required) |
| `GET` | `/accounts/password_change/` | Change password form |
| `POST` | `/accounts/password_change/` | Submit password change |

### Session Configuration
- Session timeout: **30 minutes** (`SESSION_COOKIE_AGE = 1800`)
- Session expires at browser close: **No**
- Cookie secure: **Yes** (production only)

---

## API Endpoints Overview

### JSON API Endpoints (used by frontend AJAX)

| Method | URL | Description | Auth |
|--------|-----|-------------|------|
| `GET` | `/api/ilap/<ilap_id>/periode-jenis-data/` | Get period data for an ILAP | ✓ |
| `GET` | `/api/check-jenis-prioritas/<jenis_data_id>/<tahun>/` | Check data priority status | ✓ |
| `GET` | `/api/check-tiket-exists/` | Check if a ticket already exists | ✓ |
| `GET` | `/api/preview-nomor-tiket/` | Preview auto-generated ticket number | ✓ |
| `GET` | `/api/ilap/<ilap_id>/periode-jenis-data/` | Get ILAP period data types | ✓ |

### General Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/` | Home page (role-based dashboard) |
| `GET` | `/home/data/` | Home page data (AJAX) |
| `GET` | `/keep-alive/` | Health check / session keep-alive |
| `GET` | `/session-expired/` | Session expired notification page |
| `GET` | `/profil/` | User profile page |
| `GET` | `/docs/` | Internal documentation index |
| `GET` | `/docs/<slug>/` | Internal documentation detail |

---

## AJAX DataTables Endpoints

All master data list views provide server-side DataTables JSON endpoints (via `GET` with DataTables query parameters).

### Parameters (sent by DataTables automatically)
| Parameter | Description |
|-----------|-------------|
| `draw` | Draw counter (echoed back) |
| `start` | Offset for pagination |
| `length` | Number of records per page |
| `order[0][column]` | Column index to sort by |
| `order[0][dir]` | Sort direction (`asc`/`desc`) |
| `search[value]` | Global search value |
| `columns[0][search][value]` | Column-specific search |

### Response Format
```json
{
    "draw": 1,
    "recordsTotal": 100,
    "recordsFiltered": 50,
    "data": [ ... ]
}
```

### DataTables Endpoints

| URL | Model |
|-----|-------|
| `/ilap/data/` | ILAP |
| `/kategori-ilap/data/` | Kategori ILAP |
| `/jenis-data-ilap/data/` | Jenis Data ILAP |
| `/jenis-tabel/data/` | Jenis Tabel |
| `/kategori-wilayah/data/` | Kategori Wilayah |
| `/kanwil/data/` | Kanwil |
| `/kpp/data/` | KPP |
| `/status-data/data/` | Status Data |
| `/status-penelitian/data/` | Status Penelitian |
| `/bentuk-data/data/` | Bentuk Data |
| `/cara-penyampaian/data/` | Cara Penyampaian |
| `/dasar-hukum/data/` | Dasar Hukum |
| `/media-backup/data/` | Media Backup |
| `/periode-pengiriman/data/` | Periode Pengiriman |
| `/periode-jenis-data/data/` | Periode Jenis Data |
| `/jenis-prioritas-data/data/` | Jenis Prioritas Data |
| `/pic-p3de/data/` | PIC P3DE |
| `/pic-pide/data/` | PIC PIDE |
| `/pic-pmde/data/` | PIC PMDE |
| `/nama-tabel/data/` | Nama Tabel |
| `/docx-template/data/` | Docx Template |
| `/klasifikasi-jenis-data/data/` | Klasifikasi Jenis Data |
| `/durasi-jatuh-tempo-pide/data/` | Durasi Jatuh Tempo PIDE |
| `/durasi-jatuh-tempo-pmde/data/` | Durasi Jatuh Tempo PMDE |

---

## CRUD Master Data Endpoints

Each master data module follows a consistent URL pattern:

| Method | URL Pattern | Description |
|--------|-------------|-------------|
| `GET` | `/{module}/` | List view (renders HTML) |
| `GET` | `/{module}/data/` | DataTables JSON data |
| `GET` | `/{module}/create/` | Create form (HTML) |
| `POST` | `/{module}/create/` | Submit create form |
| `GET` | `/{module}/<pk>/update/` | Update form (HTML) |
| `POST` | `/{module}/<pk>/update/` | Submit update form |
| `POST` | `/{module}/<pk>/delete/` | Delete record |

### Available CRUD Modules

| Module | URL Prefix | Model |
|--------|-----------|-------|
| ILAP | `/ilap/` | `ILAP` |
| Kategori ILAP | `/kategori-ilap/` | `KategoriILAP` |
| Jenis Data ILAP | `/jenis-data-ilap/` | `JenisDataILAP` |
| Jenis Tabel | `/jenis-tabel/` | `JenisTabel` |
| Kategori Wilayah | `/kategori-wilayah/` | `KategoriWilayah` |
| Kanwil | `/kanwil/` | `Kanwil` |
| KPP | `/kpp/` | `KPP` |
| Status Data | `/status-data/` | `StatusData` |
| Status Penelitian | `/status-penelitian/` | `StatusPenelitian` |
| Bentuk Data | `/bentuk-data/` | `BentukData` |
| Cara Penyampaian | `/cara-penyampaian/` | `CaraPenyampaian` |
| Dasar Hukum | `/dasar-hukum/` | `DasarHukum` |
| Media Backup | `/media-backup/` | `MediaBackup` |
| Periode Pengiriman | `/periode-pengiriman/` | `PeriodePengiriman` |
| Periode Jenis Data | `/periode-jenis-data/` | `PeriodeJenisData` |
| Jenis Prioritas Data | `/jenis-prioritas-data/` | `JenisPrioritasData` |
| PIC P3DE | `/pic-p3de/` | `PIC` (tipe=P3DE) |
| PIC PIDE | `/pic-pide/` | `PIC` (tipe=PIDE) |
| PIC PMDE | `/pic-pmde/` | `PIC` (tipe=PMDE) |
| Nama Tabel | `/nama-tabel/` | `NamaTabel` |
| Docx Template | `/docx-template/` | `DocxTemplate` |
| Klasifikasi Jenis Data | `/klasifikasi-jenis-data/` | `KlasifikasiJenisData` |
| Durasi Jatuh Tempo PIDE | `/durasi-jatuh-tempo-pide/` | `DurasiJatuhTempo` (seksi=PIDE) |
| Durasi Jatuh Tempo PMDE | `/durasi-jatuh-tempo-pmde/` | `DurasiJatuhTempo` (seksi=PMDE) |

### Special Endpoints (non-standard CRUD)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/ilap/next-id/` | Get next available ILAP ID |
| `GET` | `/jenis-data/get-next-id/` | Get next Jenis Data ID |
| `GET` | `/jenis-data/existing/` | Get existing Jenis Data list |
| `GET` | `/jenis-data/sub/existing/` | Get existing Sub Jenis Data list |
| `GET` | `/jenis-data/sub/next/` | Get next Sub Jenis Data ID |
| `GET` | `/tanda-terima-data/next-number/` | Get next tanda terima number |
| `GET` | `/tanda-terima-data/tikets-by-ilap/` | Get tikets grouped by ILAP |

---

## Tiket Workflow Endpoints

### List & Detail

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/tiket/` | Tiket list view (HTML) |
| `GET` | `/tiket/data/` | Tiket DataTables JSON |
| `GET` | `/tiket/<pk>/` | Tiket detail view (HTML) |
| `GET` | `/tiket/<pk>/documents/download/` | Download all tiket documents (ZIP) |

### Workflow Steps

| Method | URL | Description | Status Change |
|--------|-----|-------------|---------------|
| `GET/POST` | `/tiket/rekam/` | Record new tiket | → **Direkam (1)** |
| `GET/POST` | `/tiket/identifikasi/create/` | Record new tiket (identifikasi flow) | → **Direkam (1)** |
| `GET/POST` | `/tiket/<pk>/rekam-hasil-penelitian/` | Record research results (modal) | → **Diteliti (2)** |
| `GET/POST` | `/tiket/kirim-tiket/` | Send tiket to PIDE | → **Dikirim ke PIDE (4)** |
| `GET/POST` | `/tiket/<pk>/kirim-pide/` | Send specific tiket to PIDE | → **Dikirim ke PIDE (4)** |
| `GET/POST` | `/tiket/<pk>/identifikasi/` | Identify tiket data | → **Identifikasi (5)** |
| `GET/POST` | `/tiket/<pk>/batalkan/` | Cancel tiket (modal) | → **Dibatalkan (7)** |
| `GET/POST` | `/tiket/<pk>/dikembalikan/` | Return tiket to P3DE (modal) | → **Dikembalikan (3)** |
| `GET/POST` | `/tiket/<pk>/transfer-ke-pmde/` | Transfer tiket to PMDE (modal) | → **Pengendalian Mutu (6)** |
| `GET/POST` | `/tiket/<pk>/selesaikan/` | Complete tiket (modal) | → **Selesai (8)** |

### Kirim Tiket Sub-endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/tiket/kirim-tiket/download/<id_temp>/` | Download ND Pengantar DOCX |
| `POST` | `/tiket/kirim-tiket/temp-update/<id_temp>/` | Update temporary kirim data |
| `POST` | `/tiket/kirim-tiket/temp-delete/<id_temp>/` | Delete temporary kirim data |
| `POST` | `/tiket/kirim-tiket/kirim-ke-pide/<id_temp>/` | Confirm send to PIDE |

### Filtered List Views

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/tiket/identifikasi/` | Tiket list filtered for identification |
| `GET` | `/tiket/kirim/` | Tiket list filtered for sending |
| `GET` | `/backup-data/filter-options/` | Filter options for backup data |

---

## Report & Export Endpoints

### Laporan (Reports)

Each report follows a consistent pattern:

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/laporan-{nama}/` | Report page (HTML with filter form) |
| `GET` | `/laporan-{nama}/data/` | Report data (DataTables JSON) |
| `GET` | `/laporan-{nama}/export/` | Export to Excel (.xlsx) |

### Available Reports

| Report | URL Prefix | Description |
|--------|-----------|-------------|
| Register Penerimaan Data | `/register-penerimaan-data/` | Data receipt register |
| Laporan Transfer | `/laporan-transfer/` | Transfer report |
| SLA Perekaman | `/laporan-sla-perekaman/` | SLA recording report |
| SLA Identifikasi | `/laporan-sla-identifikasi/` | SLA identification report |
| Metrik Data Eksternal | `/laporan-metrik-data-eksternal/` | External data metrics |
| Pengendalian Mutu | `/laporan-pengendalian-mutu/` | Quality control report |
| Hasil Pengolahan Data Prioritas | `/laporan-hasil-pengolahan-data-prioritas/` | Priority data processing |
| Kelengkapan Data | `/laporan-kelengkapan-data/` | Data completeness report |
| Rekap Himpun Olah Data | `/laporan-rekap-himpun-olah-data/` | Data compilation recap |
| Detail Himpun Olah Data | `/laporan-detail-himpun-olah-data/` | Detailed compilation report |

### Other Reports & Exports

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/backup-data/export/excel/` | Backup data export (Excel) |
| `GET` | `/backup-data/export/pdf/` | Backup data export (PDF) |
| `GET` | `/laporan-pide/filter-options/` | PIDE report filter options (AJAX) |

---

## Document Generation Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/bulk-generate/pkdi-klarifikasi/` | Bulk generate PKDI/Klarifikasi letters |
| `POST` | `/bulk-generate/nd-pengantar-pide/` | Bulk generate ND Pengantar PIDE |
| `GET` | `/docx-template/<pk>/download/` | Download specific DOCX template |

### Generated Document Types

1. **Tanda Terima** (Receipt) — Nasional/Internasional & Regional (with attachment)
2. **ND Pengantar PIDE** — Cover letter to PIDE
3. **Surat Klarifikasi** — Clarification letter
4. **Surat PKDI** — Incomplete Data Notification (full/partial)
5. **Register Penerimaan Data** — Data receipt register

### Document Generation Flow

```
User clicks "Generate" → System selects template based on:
  1. Document type
  2. Region type (Regional vs Nasional/Internasional) from tiket
  3. Fills placeholders {{variable}} with tiket data
  4. Returns generated DOCX file for download
```

---

## Oracle Sync Endpoints

### Sync Data Referensi

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/sync-data-referensi/` | Sync page (HTML) |
| `POST` | `/sync-data-referensi/test/` | Test Oracle connection |
| `POST` | `/sync-data-referensi/check/` | Check for data changes (dry-run) |
| `POST` | `/sync-data-referensi/run/` | Run full data synchronization |
| `POST` | `/sync-data-referensi/stop/` | Stop running sync |
| `GET` | `/sync-data-referensi/stop-check/` | Check if stop requested |
| `GET` | `/sync-data-referensi/progress/` | Get sync progress (AJAX poll) |
| `POST` | `/sync-data-referensi/truncate/` | Truncate synced tables |
| `GET` | `/sync-data-referensi/download-errors/<sync_id>/` | Download error log |
| `POST` | `/sync-data-referensi/clear-session/` | Clear sync session data |

### Sync Tiket

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/sync-tiket/` | Sync tiket page (HTML) |
| `POST` | `/sync-tiket/test/` | Test Oracle connection |
| `POST` | `/sync-tiket/check/` | Check for tiket changes (dry-run) |
| `POST` | `/sync-tiket/run/` | Run tiket synchronization |
| `POST` | `/sync-tiket/stop/` | Stop running sync |
| `GET` | `/sync-tiket/stop-check/` | Check if stop requested |
| `GET` | `/sync-tiket/progress/` | Get sync progress (AJAX poll) |
| `POST` | `/sync-tiket/truncate/` | Truncate synced tiket tables |
| `GET` | `/sync-tiket/download-errors/<sync_id>/` | Download error log |

### Sync Progress Response Format

```json
{
    "current": 5,
    "total": 12,
    "percentage": 41,
    "table_name": "REF_ILAP",
    "inserts": 10,
    "updates": 3,
    "errors": 0
}
```

---

## Notification Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/notifications/` | Notification list |
| `POST` | `/notifications/read/<pk>/` | Mark single notification as read |
| `POST` | `/notifications/read-all/` | Mark all notifications as read |

---

## Utility Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/dashboard/` | Power BI embedded dashboard |
| `GET` | `/quality-control/` | Quality control page |
| `GET` | `/quality-control/data/` | Quality control DataTables JSON |
| `GET` | `/profil-ilap/` | ILAP profile list |
| `GET` | `/profil-ilap/<pk>/` | ILAP profile detail |
| `GET` | `/monitoring-penyampaian-data/` | Data delivery monitoring |
| `GET` | `/monitoring-penyampaian-data/data/` | Monitoring DataTables JSON |

### Django Admin

| Method | URL | Description |
|--------|-----|-------------|
| `GET/POST` | `/admin/` | Django admin interface (superuser only) |

### Development-only Endpoints (DEBUG=True)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/schema/` | Interactive ERD diagram (django-schema-graph) |

---

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| `200` | Success |
| `302` | Redirect (login required, etc.) |
| `400` | Bad request (invalid form data) |
| `403` | Forbidden (permission denied) |
| `404` | Not found |
| `405` | Method not allowed |
| `500` | Internal server error |

### Error Response Format (JSON)

```json
{
    "error": "Error message description",
    "details": {}
}
```

### CSRF Protection

All `POST` requests require a CSRF token. Include in forms:

```html
{% csrf_token %}
```

For AJAX POST requests, include the CSRF header:

```javascript
// From Django docs - get CSRF token from cookie
const csrftoken = getCookie('csrftoken');

fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
});
```
