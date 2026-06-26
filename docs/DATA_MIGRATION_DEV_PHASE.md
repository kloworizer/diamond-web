# Panduan Migrasi Data

> **Dokumen ini menjelaskan strategi, alur, dan langkah-langkah migrasi data**
> **dari Oracle DB (sistem lama) ke PostgreSQL (sistem baru Diamond Web).**

---

## Daftar Isi

- [1. Ringkasan Strategi Migrasi](#1-ringkasan-strategi-migrasi)
- [2. Arsitektur Migrasi Data](#2-arsitektur-migrasi-data)
- [3. Fase Migrasi](#3-fase-migrasi)
  - [Fase 1: Setup Koneksi Oracle](#fase-1-setup-koneksi-oracle)
  - [Fase 2: Migrasi Data Referensi](#fase-2-migrasi-data-referensi)
  - [Fase 3: Migrasi Data Tiket](#fase-3-migrasi-data-tiket)
  - [Fase 4: Sinkronisasi Harian (Cron)](#fase-4-sinkronisasi-harian-cron)
  - [Fase 5: Pre-Production Cleanup](#fase-5-pre-production-cleanup)
- [4. Dokumentasi Source Code Sync Engine](#4-dokumentasi-source-code-sync-engine)
  - [4.1 OracleSyncService — Class Utama](#41-oraclesyncservice--class-utama)
  - [4.2 HARD_CODED_SYNC_TABLES — Mapping Tabel Referensi](#42-hard_coded_sync_tables--mapping-tabel-referensi)
  - [4.3 Pre-Process & Post-Process Steps](#43-pre-process--post-process-steps)
  - [4.4 View Sync Data Referensi](#44-view-sync-data-referensi)
  - [4.5 View Sync Data Tiket](#45-view-sync-data-tiket)
  - [4.6 Tiket Oracle SQL Query](#46-tiket-oracle-sql-query)
  - [4.7 Status Tiket Mapping](#47-status-tiket-mapping)
  - [4.8 Mapping Field Tiket](#48-mapping-field-tiket)
- [5. Backup Database Harian](#5-backup-database-harian)
- [6. Pre-Production Cleanup](#6-pre-production-cleanup)
- [7. Jadwal Cron](#7-jadwal-cron)
- [8. Manajemen Command](#8-manajemen-command)
  - [8.1 Daftar Management Command](#81-daftar-management-command)
- [9. Verifikasi & Troubleshooting](#9-verifikasi--troubleshooting)
- [10. Rollback Plan](#10-rollback-plan)

---

## 1. Ringkasan Strategi Migrasi

Migrasi data dilakukan secara **bertahap** dengan pendekatan **dual-running**:

1. **Oracle DB (sistem lama)** — tetap berjalan sebagai sumber data utama
2. **PostgreSQL / SQLite (sistem baru)** — menerima data secara periodik melalui sinkronisasi

### Prinsip Migrasi

| Prinsip | Keterangan |
|---------|------------|
| **Bertahap** | Data referensi dimigrasi terlebih dahulu, lalu data tiket |
| **Idempotent** | Proses sinkronisasi aman dijalankan berulang kali |
| **Auditable** | Setiap operasi dicatat dalam log file |
| **Dry-run first** | Estimasi dampak sebelum eksekusi nyata |
| **Rollback ready** | Backup selalu dibuat sebelum perubahan besar |

### Tahapan Utama

```
Oracle DB (Sumber)
    │
    ├── Fase 1: Setup Koneksi ──────────────────────► Konfigurasi .env
    │
    ├── Fase 2: Data Referensi (sekali/sesuai kebutuhan)
    │   └── python manage.py sync_oracle_data
    │
    ├── Fase 3: Data Tiket (sekali/sesuai kebutuhan)
    │   └── python manage.py sync_tiket_data
    │
    ├── Fase 4: Sinkronisasi Harian (otomatis via cron)
    │   └── scripts/sync_daily_cron.sh ───► 09:00 WIB setiap hari
    │
    └── Fase 5: Pre-Production Cleanup (sekali)
        └── scripts/cleanup_pre_production.sh ───► 1 Juli 2026 00:00 WIB
```

---

## 2. Arsitektur Migrasi Data

```
┌──────────────────────────────────────────────────────────────────┐
│                     Oracle Database (Sumber)                      │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Tabel Referensi     │  │ Tabel Tiket                      │   │
│  │ - ILAP              │  │ - Tiket (history data)           │   │
│  │ - JenisDataILAP     │  │ - Data pendukung tiket           │   │
│  │ - KPP               │  │                                  │   │
│  │ - Kanwil            │  │                                  │   │
│  │ - dll (~20 tabel)   │  │                                  │   │
│  └──────────┬──────────┘  └──────────────┬───────────────────┘   │
└─────────────┼────────────────────────────┼───────────────────────┘
              │                            │
              ▼                            ▼
┌────────────────────────────┐ ┌──────────────────────────────────┐
│ 1. sync_oracle_data        │ │ 2. sync_tiket_data               │
│    (management command)    │ │    (management command)          │
│                            │ │                                  │
│ Mode: --check-only (dry)   │ │ Mode: --check-only (dry)         │
│ Mode: normal (execute)     │ │ Mode: normal (execute)           │
└──────────┬─────────────────┘ └───────────┬──────────────────────┘
           │                                │
           └────────────┬───────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Diamond Database (Target)                      │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Tabel Referensi     │  │ Tabel Tiket                      │   │
│  │ (insert/update)     │  │ old_db=True → dari Oracle sync   │   │
│  │                     │  │ old_db=False → input manual      │   │
│  └─────────────────────┘  └──────────────────────────────────┘   │
│                                                                  │
│  Backup: scripts/db_backup_daily.sh (setiap hari 00:00 WIB)     │
│  Cleanup: scripts/cleanup_pre_production.sh (1 Juli 2026)       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Fase Migrasi

### Fase 1: Setup Koneksi Oracle

Sebelum memulai migrasi, pastikan koneksi ke Oracle Database sudah dikonfigurasi.

#### Langkah 1.1 — Konfigurasi Environment Variable

Buka file `.env` dan isi parameter koneksi Oracle:

```bash
# Koneksi Oracle Utama
ORACLE_USER=username_oracle
ORACLE_PASSWORD=password_oracle
ORACLE_HOST=10.x.x.x
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=ORCLPDB1

# Koneksi Oracle Sekunder (optional)
ORACLE_SECONDARY_USER=username_oracle2
ORACLE_SECONDARY_PASSWORD=password_oracle2
ORACLE_SECONDARY_HOST=10.x.x.y
ORACLE_SECONDARY_PORT=1521
ORACLE_SECONDARY_SERVICE_NAME=ORCLPDB2
```

#### Langkah 1.2 — Verifikasi Konfigurasi

Jalankan perintah berikut untuk menguji koneksi:

```bash
# Cek apakah konfigurasi terbaca
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('ORACLE_HOST:', os.getenv('ORACLE_HOST'))
print('ORACLE_PORT:', os.getenv('ORACLE_PORT'))
print('ORACLE_SERVICE_NAME:', os.getenv('ORACLE_SERVICE_NAME'))
"
```

#### Langkah 1.3 — Install Oracle Instant Client (untuk thick mode)

Jika menggunakan **thick mode** (`oracledb`), pastikan Oracle Instant Client terinstall:

```bash
# Ubuntu/Debian
sudo apt install libaio1
wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linuxx64.zip
unzip instantclient-basic-linuxx64.zip
sudo mv instantclient_21_* /usr/local/oracle-instantclient
sudo sh -c "echo /usr/local/oracle-instantclient > /etc/ld.so.conf.d/oracle-instantclient.conf"
sudo ldconfig

# Set environment variable
export LD_LIBRARY_PATH=/usr/local/oracle-instantclient:$LD_LIBRARY_PATH
```

> **Referensi:** Lihat `docs/ORACLE_SETUP.md` untuk panduan setup Oracle yang lebih lengkap.

---

### Fase 2: Migrasi Data Referensi

Data referensi adalah data master yang menjadi acuan bagi data tiket (seperti daftar ILAP, Jenis Data, KPP, Kanwil, dll).

#### Langkah 2.1 — Dry-Run (Cek Perubahan)

Jalankan mode **check-only** untuk melihat apa yang akan diubah tanpa memodifikasi database:

```bash
python manage.py sync_oracle_data --check-only
```

**Output yang diharapkan:**
```
Akan di-insert: 50 record
Akan di-update: 10 record
Tidak ada perubahan: 500 record
```

#### Langkah 2.2 — Eksekusi Sinkronisasi Referensi

Setelah yakin dengan hasil dry-run, jalankan sinkronisasi penuh:

```bash
python manage.py sync_oracle_data
```

Proses ini akan:
- **INSERT** data baru yang belum ada di database target
- **UPDATE** data yang sudah ada jika ada perubahan
- Melewati data yang identik (tidak ada perubahan)

#### Langkah 2.3 — Verifikasi Data Referensi

```bash
# Cek jumlah record yang berhasil disinkronisasi
python manage.py shell_plus -c "
from diamond_web.models.ilap import ILAP
from diamond_web.models.jenis_data_ilap import JenisDataILAP
from diamond_web.models.kpp import KPP
print(f'ILAP: {ILAP.objects.count()} records')
print(f'JenisDataILAP: {JenisDataILAP.objects.count()} records')
print(f'KPP: {KPP.objects.count()} records')
"
```

---

### Fase 3: Migrasi Data Tiket

Data tiket adalah data transaksional yang terdiri dari tiket dan seluruh relasinya (PIC, Action, KirimPideTemp, dll).

#### Langkah 3.1 — Dry-Run Tiket

```bash
python manage.py sync_tiket_data --check-only
```

**Output yang diharapkan:**
```
Akan di-insert: 150 tiket
Akan di-update: 25 tiket
Tidak ada perubahan: 1000 tiket
```

#### Langkah 3.2 — Eksekusi Sinkronisasi Tiket

```bash
python manage.py sync_tiket_data
```

Proses ini akan:
- Meng-sinkronisasi data tiket dari Oracle ke database Diamond
- Menandai tiket hasil sinkronisasi dengan `old_db=True`
- Membuat log aksi untuk setiap tiket yang di-sync

#### Langkah 3.3 — Verifikasi Data Tiket

```bash
# Cek jumlah tiket hasil sinkronisasi
python manage.py shell_plus -c "
from diamond_web.models.tiket import Tiket
total = Tiket.objects.count()
old_db = Tiket.objects.filter(old_db=True).count()
new_db = Tiket.objects.filter(old_db=False).count()
print(f'Total Tiket: {total}')
print(f'old_db=True (dari Oracle): {old_db}')
print(f'old_db=False (input manual): {new_db}')
"
```

---

### Fase 4: Sinkronisasi Harian (Cron)

Setelah migrasi awal selesai, sinkronisasi harian berjalan otomatis melalui cron job untuk menjaga data tetap sinkron dengan Oracle.

#### Langkah 4.1 — Pasang Cron Job

```bash
# Buka crontab
crontab -e

# Tambahkan baris berikut:
0 0 * * * /home/pajak/diamond-web/scripts/db_backup_daily.sh         # Backup harian jam 00:00 WIB
0 9 * * * /home/pajak/diamond-web/scripts/sync_daily_cron.sh          # Sinkronisasi harian jam 09:00 WIB
0 0 1 7 * /home/pajak/diamond-web/scripts/cleanup_pre_production.sh  # Cleanup 1 Juli 2026
```

#### Langkah 4.2 — Verifikasi Cron Berjalan

```bash
# Cek daftar crontab
crontab -l

# Cek log sinkronisasi
ls -la /home/pajak/diamond-web/sync_logs/
cat /home/pajak/diamond-web/sync_logs/daily_sync_$(date +%F)*.log
```

---

### Fase 5: Pre-Production Cleanup

Fase ini adalah langkah terakhir sebelum go-live produksi. Dua kelompok data akan dibersihkan:

1. **Data testing** — seluruh data yang dimasukkan user selama masa pengujian:
   - Semua `BackupData`, `TandaTerimaData`, `DetilTandaTerima` akan di-truncate
   - Semua `TiketAction` kecuali action tipe 301 (PIC Ditambahkan) akan dihapus
2. **Tiket old_db=False** — tiket yang dibuat secara manual (bukan hasil sinkronisasi Oracle)

#### Langkah 5.1 — Dry-Run Cleanup

Jalankan beberapa hari sebelum eksekusi untuk memastikan data yang akan dihapus sudah benar:

```bash
./scripts/cleanup_pre_production.sh --dry-run
```

**Output yang diharapkan (Phase 1 — data testing):**
```
==================================================
PHASE 1: Pembersihan data testing
==================================================
Record testing yang akan dibersihkan:
  - BackupData (semua): 50
  - TandaTerimaData (semua): 30
  - DetilTandaTerima (semua): 80
  - TiketAction (selain action=301): 500
  Total data testing: 660 records

==================================================
PHASE 2: Hapus 45 tiket dengan old_db=False
==================================================
Record terkait yang akan dihapus:
  - TiketPIC: 45
  - TiketAction: 120
  - KirimPideTemp: 10
  - Tiket: 45

Dry-run mode: tidak ada perubahan yang dilakukan.
```

#### Langkah 5.2 — Backup Database (sebelum cleanup)

```bash
# Backup penuh database sebelum cleanup
python manage.py dbbackup --compress
```

#### Langkah 5.3 — Eksekusi Cleanup

> **CATATAN:** Script `cleanup_pre_production.sh` hanya akan berjalan nyata pada **1 Juli 2026**.
> Untuk eksekusi di luar tanggal tersebut, gunakan `./scripts/cleanup_pre_production.sh --dry-run`.

Pada 1 Juli 2026 pukul 00:00 WIB, cron akan menjalankan:

```bash
/home/pajak/diamond-web/scripts/cleanup_pre_production.sh
```

Script akan:
1. **Dry-run otomatis** — melihat estimasi data yang akan dihapus
2. **Phase 1 — Pembersihan data testing** (hapus semua data entry testing user):
   - Truncate `DetilTandaTerima` (semua, harus pertama karena FK ke TandaTerimaData)
   - Truncate `TandaTerimaData` (semua)
   - Truncate `BackupData` (semua)
   - Hapus `TiketAction` (kecuali action=301 / PIC Ditambahkan)
3. **Phase 2 — Hapus tiket old_db=False** (dalam 1 transaksi atomik):
   - `TiketPIC` (id_tiket in tiket_ids)
   - `TiketAction` (id_tiket in tiket_ids)
   - `KirimPideTemp` (id_tiket in tiket_ids)
   - `Tiket` (old_db=False)
4. **Verifikasi** — memastikan tidak ada lagi data testing dan tiket `old_db=False`

#### Langkah 5.4 — Verifikasi Pasca-Cleanup

```bash
# Verifikasi manual
python manage.py cleanup_pre_production --dry-run
# Output: "Tidak ada data testing untuk dibersihkan."
#         "Tidak ada tiket dengan old_db=False untuk dibersihkan."

# Cek sisa data
python manage.py shell_plus -c "
from diamond_web.models.tiket import Tiket
print(f'Tiket tersisa: {Tiket.objects.count()}')
print(f'Semua dari Oracle: {Tiket.objects.filter(old_db=True).count()}')
"
```

> **Catatan:** `DetilTandaTerima` dan `TandaTerimaData` yang ditruncate di Phase 1 adalah data testing secara keseluruhan (tanpa filter id_tiket), karena tabel-tabel tersebut berisi data input pengguna selama masa pengujian dan bukan hasil sinkronisasi Oracle.

---

## 4. Dokumentasi Source Code Sync Engine

### 4.1 OracleSyncService — Class Utama

**File:** `diamond_web/utils/oracle_sync.py`

`OracleDataSyncService` adalah class utama yang menangani seluruh proses sinkronisasi data referensi dari Oracle ke database Diamond.

#### Architecture

```
OracleDataSyncService
│
├── _load_oracle_connections()    → Membaca konfigurasi dari .env
│   ├── primary:   ORACLE_USER/PASSWORD/HOST/PORT/SERVICE_NAME
│   └── secondary: ORACLE_SECONDARY_USER/PASSWORD/HOST/PORT/SERVICE_NAME
│
├── _connect_oracle(conn_name)    → Koneksi ke Oracle via oracledb
│   └── TCP connect timeout: 15 detik (via ORACLE_TCP_CONNECT_TIMEOUT)
│
├── _validate_connection_config() → Validasi kelengkapan konfigurasi
├── _validate_sync_configs()      → Validasi HARD_CODED_SYNC_TABLES
│
├── check()                       → Dry-run (di dalam transaction.atomic, di-rollback)
├── sync()                        → Eksekusi INSERT/UPDATE (transaction.atomic)
│
└── _run_sequential()             → Iterasi semua tabel secara berurutan
    └── Untuk setiap tabel:
        ├── _fetch_oracle_rows()  → Query data dari Oracle
        ├── _calculate_diff()     → Bandingkan dengan DB target
        └── _apply_operations()   → INSERT/UPDATE (jika sync mode)
```

#### Koneksi Oracle

Service mendukung **dua koneksi Oracle**:

| Koneksi | Env Variable | Kegunaan |
|---------|-------------|----------|
| **Primary** | `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME` | Data referensi utama (PROD schema) + data tiket (PVPTD schema) |
| **Secondary** | `ORACLE_SECONDARY_USER`, `ORACLE_SECONDARY_PASSWORD`, `ORACLE_SECONDARY_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME` | Data PMDE (REF_TABEL_PMDE) |

Backward compatibility: `ORACLE_*` dianggap sebagai primary. `ORACLE_PRIMARY_*` dapat override `ORACLE_*`.

#### Mode Thick / Thin

- **Thick mode:** Membutuhkan Oracle Instant Client. Diinisialisasi via `_initialize_oracledb_thick_mode()`.
- **Thin mode:** Fallback jika thick mode gagal (pure Python, tidak perlu Instant Client).

#### PMDE Year Discovery

Sebelum sync, service melakukan discovery tahun-tahun yang memiliki kolom `PRIORITAS_YYYY` di tabel `REF_TABEL_PMDE` (Oracle secondary). Query:

```sql
SELECT COLUMN_NAME
FROM user_tab_columns
WHERE TABLE_NAME = 'REF_TABEL_PMDE'
  AND COLUMN_NAME LIKE 'PRIORITAS_%'
ORDER BY COLUMN_NAME
```

Hasil discovery digunakan untuk membangun query UNION ALL untuk tabel `jenis_prioritas_data` dan `durasi_jatuh_tempo_pmde`.

#### Dataclass Definitions

```python
@dataclass(frozen=True)
class OracleConnectionConfig:
    name: str              # 'primary' atau 'secondary'
    user: str
    password: str
    host: str
    port: int
    service_name: str
    sid: str

@dataclass(frozen=True)
class OracleSyncTableConfig:
    name: str                          # Nama unik konfigurasi
    target_model_label: str            # Label model Django (contoh: 'diamond_web.ILAP')
    target_key_field: str              # Field primary key di model target
    source_key_column: str             # Kolom key di source Oracle
    field_map: dict[str, str]          # Mapping: target_field → source_column
    source_table: str = ""             # Nama tabel Oracle (jika bukan query)
    source_query: str = ""             # SQL query kustom (jika bukan tabel langsung)
    foreign_key_lookup_map: dict = {}  # Mapping: target FK field → lookup field di related model
    derived_field_map: dict = {}       # Mapping: target field → rule name untuk derived values
    match_fields: tuple = ()           # Fields untuk mencocokkan record existing
    where_clause: str = ""             # Filter tambahan WHERE
    source_connection: str = "primary" # 'primary' atau 'secondary'
```

---

### 4.2 HARD_CODED_SYNC_TABLES — Mapping Tabel Referensi

**File:** `diamond_web/utils/oracle_sync.py` (variable `HARD_CODED_SYNC_TABLES`)

Berikut adalah daftar lengkap konfigurasi sinkronisasi untuk setiap tabel referensi, termasuk sumber Oracle, model target Django, dan mapping field.

#### Urutan Sinkronisasi

**PENTING:** Urutan tabel mengikuti dependency (parent sebelum child) untuk menghindari constraint violation.

| No | Nama Config | Oracle Source | Target Model | Key Field |
|----|-------------|---------------|--------------|-----------|
| 1 | `kategori_ilap` | `PROD.APP_KATEGORI_ILAP` | `KategoriILAP` | `id_kategori` |
| 2 | `dasar_hukum` | Query: `P3DE.REF_DTL_DSR_HUKUM` | `DasarHukum` | `deskripsi` |
| 3 | `ilap` | Query UNION ALL: `PROD.APP_ILAP` + `PROD.REF_ILAP` | `ILAP` | `id_ilap` |
| 4 | `jenis_data_ilap` | Query UNION ALL: `PROD.APP_TABEL_DATA_ILAP` + `P3DE.REF_DATA_ILAP` | `JenisDataILAP` | `id_sub_jenis_data` |
| 5 | `jenis_prioritas_data` | Query dinamis: `REF_TABEL_PMDE` (PRIORITAS_YYYY) | `JenisPrioritasData` | `id_sub_jenis_data_ilap` |
| 6 | `klasifikasi_jenis_data` | Query: `P3DE.REF_DSR_HUKUM` + `P3DE.REF_DTL_DSR_HUKUM` | `KlasifikasiJenisData` | `id_sub_jenis_data` |
| 7 | `periode_jenis_data` | Query UNION ALL: `PROD.APP_JENIS_DATA_ILAP` + `P3DE.REF_DATA_ILAP` | `PeriodeJenisData` | `id_sub_jenis_data_ilap` |
| 8 | `pic_p3de` | Query: `PROD.APP_JENIS_DATA_ILAP` (pic_pddo) | `PIC` | `id_sub_jenis_data_ilap` |
| 9 | `pic_pide` | Query: `PVPTD.ZA_REKAP_PEMBAGIAN_PIC_PIDE` + `PVPTD.ZA_REKAP_PIC_PIDE` | `PIC` | `id_sub_jenis_data_ilap` |
| 10 | `pic_pmde` | Query: `REF_TABEL_PMDE` (secondary) | `PIC` | `id_sub_jenis_data_ilap` |
| 11 | `pic_pmde_ref` | Query: `REF_PIC_ILAP_PMDE` (secondary) | `PIC` | `id_sub_jenis_data_ilap` |
| 12 | `durasi_jatuh_tempo_pmde` | Query dinamis: `REF_TABEL_PMDE` (secondary) + default rows | `DurasiJatuhTempo` | `id_sub_jenis_data` |

---

#### Detail Mapping Per Tabel

##### 1. `kategori_ilap` — Kategori ILAP

| Oracle Source | Target Field |
|---------------|-------------|
| `PROD.APP_KATEGORI_ILAP` | |
| `ID_KATEGORI_ILAP` | `id_kategori` |
| `NAMA_KATEGORI` | `nama_kategori` |
| `CREATE_DATE` | `create_date` |
| `CREATE_BY` | `create_by` |

**Dependency:** Tidak ada (independent table).

---

##### 2. `dasar_hukum` — Dasar Hukum

| Oracle Source | Target Field |
|---------------|-------------|
| `P3DE.REF_DTL_DSR_HUKUM` | |
| `KET_DSR_HUKUM` | `deskripsi` |
| Derived: `kategori_from_id_dsr_hukum` | `kategori` |

**Derived Field Rule** (`kategori_from_id_dsr_hukum`):
- Ambil `ID_DSR_HUKUM` dari Oracle
- Jika mengandung karakter `-`, ambil teks sebelum `-` sebagai kategori
- Jika tidak, gunakan seluruh `ID_DSR_HUKUM` sebagai kategori
- Hasil di-uppercase

---

##### 3. `ilap` — Institusi Penerima Data

**Oracle Query:** UNION ALL dari 2 sumber dengan deduplikasi (ROW_NUMBER):

| Source | Priority | Tabel |
|--------|----------|-------|
| `PROD.APP_ILAP` | 1 (higher) | Data utama dengan field lengkap |
| `PROD.REF_ILAP` | 2 (lower) | Data sekunder (beberapa field NULL) |

**Field Mapping:**

| Oracle Column | Target Field | Catatan |
|---------------|-------------|---------|
| `ID_ILAP` | `id_ilap` | Primary key |
| `ID_KATEGORI_ILAP` | `id_kategori` | FK → KategoriILAP (via `foreign_key_lookup_map`) |
| `NAMA_ILAP` | `nama_ilap` | |
| `ALAMAT_ILAP` | `alamat_ilap` | |
| `KOTA_ILAP` | `kota_ilap` | |
| `NAMAPIC_ILAP` | `namapic_ilap` | |
| `TELP_KANTOR` | `telp_kantor` | |
| `FAX_ILAP` | `fax_ilap` | |
| `EMAIL_PICILAP` | `email_picilap` | |
| `CREATE_DATE` | `create_date` | |
| `CREATE_BY` | `create_by` | |
| `JABATAN_PICILAP` | `jabatan_picilap` | |
| `TELP_PIC` | `telp_pic` | |
| `TUJUAN_SURAT` | `tujuan_surat` | |
| `TEMBUSAN` | `tembusan` | |
| `UPDATE_DATE` | `update_date` | |
| `UPDATE_BY` | `update_by` | |

**Derived Field Rule** (`kategori_wilayah_from_id_kategori`):

| ID_KATEGORI_ILAP | Kategori Wilayah |
|------------------|-----------------|
| `PV` atau `PD` | `Regional` |
| `EI` | `Internasional` |
| Lainnya | `Nasional` |

**Match Fields:** `(id_ilap, nama_ilap)` — digunakan untuk mendeteksi apakah record sudah ada.

---

##### 4. `jenis_data_ilap` — Jenis Data ILAP (dengan sub-jenis)

**Oracle Query:** UNION ALL dari 2 sumber dengan deduplikasi:

| Source | Priority | Tabel |
|--------|----------|-------|
| `PROD.APP_TABEL_DATA_ILAP` JOIN `PROD.APP_JENIS_DATA_ILAP` | 1 | Sumber utama dengan field lengkap |
| `P3DE.REF_DATA_ILAP` | 2 | Data referensi tambahan |

**Field Mapping:**

| Oracle Column | Target Field | Catatan |
|---------------|-------------|---------|
| `ID_ILAP` | `id_ilap` | FK → ILAP |
| `ID_JENIS_DATA` | `id_jenis_data` | |
| `ID_SUB_JENIS_DATA` | `id_sub_jenis_data` | Primary key |
| `NAMA_JENIS_DATA` | `nama_jenis_data` | |
| `NAMA_SUB_JENIS_DATA` | `nama_sub_jenis_data` | |
| `NAMA_TABEL_I` | `nama_tabel_I` | Nama tabel untuk identifikasi |
| `NAMA_TABEL_U` | `nama_tabel_U` | Nama tabel untuk update |
| `JENIS_TABEL` | `id_jenis_tabel` | FK → JenisTabel (via deskripsi: `Diidentifikasi`, `Tidak Diidentifikasi`, `Tidak Terstruktur`) |
| `STATUS_DATA` | `id_status_data` | FK → StatusData (via deskripsi) |

**Transformasi JENIS_TABEL:**
- `'Referensi'` → `'Diidentifikasi'`
- `'Transaksi'` → `'Tidak Diidentifikasi'`
- `'Unstructured'` → `'Tidak Terstruktur'`

**Match Fields:** `(id_ilap, id_jenis_data, id_sub_jenis_data)`

---

##### 5. `jenis_prioritas_data` — Prioritas Data PMDE

**Oracle Source:** `REF_TABEL_PMDE` (secondary connection)

Query dibangun secara dinamis berdasarkan hasil discovery kolom `PRIORITAS_YYYY`:

```sql
SELECT DISTINCT
    ID_TABEL_S,
    DATE '<year>-01-01' AS START_DATE,
    DATE '<year>-12-31' AS END_DATE,
    'ND-' AS NO_ND,
    '<year>' AS TAHUN,
    DURASI
FROM REF_TABEL_PMDE
WHERE PRIORITAS_<year> = 1
```
... UNION ALL untuk setiap tahun yang ditemukan.

**Field Mapping:**

| Oracle Column | Target Field |
|---------------|-------------|
| `ID_TABEL_S` | `id_sub_jenis_data_ilap` (FK → JenisDataILAP) |
| `START_DATE` | `start_date` |
| `END_DATE` | `end_date` |
| `NO_ND` | `no_nd` |
| `TAHUN` | `tahun` |

**Match Fields:** `(id_sub_jenis_data_ilap, tahun)`

---

##### 6. `klasifikasi_jenis_data` — Klasifikasi Jenis Data

**Oracle Query:** `P3DE.REF_DSR_HUKUM` JOIN `P3DE.REF_DTL_DSR_HUKUM`

```sql
SELECT
    a.ID_TABEL,
    b.KET_DSR_HUKUM
FROM P3DE.REF_DSR_HUKUM a
JOIN P3DE.REF_DTL_DSR_HUKUM b ON a.ID_DSR_HUKUM = b.ID_DSR_HUKUM
```

**Field Mapping:**

| Oracle Column | Target Field |
|---------------|-------------|
| `ID_TABEL` | `id_sub_jenis_data` (FK → JenisDataILAP) |
| `KET_DSR_HUKUM` | `id_klasifikasi_tabel` (FK → DasarHukum via `deskripsi`) |

**Match Fields:** `(id_sub_jenis_data, id_klasifikasi_tabel)`

---

##### 7. `periode_jenis_data` — Periode Pengiriman Jenis Data

**Oracle Query:** UNION ALL dengan deduplikasi, transformasi nilai periode:

```sql
-- Transformasi: 'Triwulan' → 'Triwulanan'
CASE
    WHEN a.PERIODE_PENGIRIMAN = 'Triwulan' THEN 'Triwulanan'
    ELSE a.PERIODE_PENGIRIMAN
END AS PERIODE_PENGIRIMAN
```

**Field Mapping:**

| Oracle Column | Target Field |
|---------------|-------------|
| `ID_SUB_JENIS_DATA` | `id_sub_jenis_data_ilap` (FK → JenisDataILAP) |
| `PERIODE_PENGIRIMAN` | `id_periode_pengiriman` (FK → PeriodePengiriman via `periode_penyampaian`) |
| `TGL_PENYAMPAIAN_PERTAMA` | `start_date` (NULL → default `2015-01-01`) |
| `JADWAL_PENYAMPAIAN` | `akhir_penyampaian` (NULL → 0) |

**Match Fields:** `(id_sub_jenis_data_ilap, id_periode_pengiriman)`

---

##### 8–10. `pic_p3de`, `pic_pide`, `pic_pmde` — PIC (Person In Charge)

Ketiga konfigurasi ini menyimpan data PIC ke model `PIC` yang sama, dibedakan oleh `derived_field_map`:

| Config | Oracle Source | Tipe PIC |
|--------|---------------|----------|
| `pic_p3de` | `PROD.APP_JENIS_DATA_ILAP` (pic_pddo) | `P3DE` |
| `pic_pide` | `PVPTD.ZA_REKAP_PEMBAGIAN_PIC_PIDE` JOIN `PVPTD.ZA_REKAP_PIC_PIDE` | `PIDE` |
| `pic_pmde` | `REF_TABEL_PMDE` (secondary) — via `nm_tabel` → `nama_tabel_I` lookup | `PMDE` |
| `pic_pmde_ref` | `REF_PIC_ILAP_PMDE` (secondary) — via `id_ilap` → JenisDataILAP lookup | `PMDE` |

**Field Mapping (semua PIC):**

| Oracle Column | Target Field |
|---------------|-------------|
| `ID_SUB_JENIS_DATA` | `id_sub_jenis_data_ilap` (FK → JenisDataILAP) |
| `NIP_MATCH` / `ID_USER` | `id_user` (FK → User via `username`) |
| `START_DATE` | `start_date` |
| Derived: `tipe` | `tipe` (P3DE / PIDE / PMDE) |

**Expansion Logic untuk `pic_pide` dan `pic_pmde`:**
Satu baris Oracle (nm_tabel, nip_match) di-expand menjadi beberapa baris dengan mencocokkan `nm_tabel` dengan `nama_tabel_I` di `JenisDataILAP`. Jika satu `nm_tabel` cocok dengan banyak `JenisDataILAP`, maka semua `id_sub_jenis_data` akan dibuatkan record PIC.

**Expansion Logic untuk `pic_pmde_ref`:**
Satu baris Oracle (`id_ilap`, `username`) di-expand dengan mencari semua `JenisDataILAP` yang memiliki `id_ilap` tersebut. Untuk ILAP dengan prefix PV/PD/PK, dilakukan fallback lookup ke `REF_TABEL_PMDE`.

---

##### 11. `durasi_jatuh_tempo_pmde` — Durasi Jatuh Tempo

**Oracle Source:** `REF_TABEL_PMDE` (secondary) — query dinamis UNION ALL berdasarkan tahun discovery.

**Supplement Default Rows:** Untuk setiap `(id_sub_jenis_data, tahun)` yang tidak tercakup oleh data Oracle, ditambahkan row default dengan `durasi=85`. Ini memastikan semua JenisDataILAP memiliki durasi jatuh tempo untuk semua tahun.

**Field Mapping:**

| Oracle Column | Target Field |
|---------------|-------------|
| `ID_TABEL_S` | `id_sub_jenis_data` (FK → JenisDataILAP) |
| `DURASI` | `durasi` |
| `START_DATE` | `start_date` |
| `END_DATE` | `end_date` |
| Derived: `pmde_group_name` | `seksi` (selalu `user_pmde`) |

**Match Fields:** `(id_sub_jenis_data, seksi, start_date)`

---

### 4.3 Pre-Process & Post-Process Steps

Selain sinkronisasi tabel utama, `OracleDataSyncService` menjalankan beberapa langkah pre-processing dan post-processing:

#### Pre-Process: Insert KategoriILAP 'KW'

**Method:** `_pre_process_kategori_ilap_kw()`

Sebelum sync `kategori_ilap`, pastikan record dengan `id_kategori='KW'` sudah ada. Jika belum, insert secara otomatis.

#### Post-Process 1: Insert Default ILAP

**Method:** `_post_process_ilap_insert_defaults()`

Setelah sync ILAP, insert ILAP tambahan yang tidak ada di Oracle tetapi diperlukan oleh sistem:

| Kode ILAP | Prefix | Kategori Wilayah |
|-----------|--------|-----------------|
| `EI952` | EI | Internasional |
| `KW020`, `KW070`, ..., `KW330` (11 kode) | KW | Nasional |
| `PD908` | PD | Regional |
| `PL801`, `PL807`, ..., `PV908` (5+ kode) | PL/PV | Regional/Internasional |

Total: 24 kode ILAP default.

#### Post-Process 2: Insert AEOI Domestic

**Method:** `_post_process_jenis_data_ilap_aeoi_domestic()`

Insert JenisDataILAP untuk AEOI Domestic (`EI9500102`) berdasarkan referensi dari `EI95001`.

#### Post-Process 3: Insert Additional JenisDataILAP

**Method:** `_post_process_jenis_data_ilap_additional()`

Insert ~400+ additional records dari hardcoded data yang tidak tercakup oleh query Oracle sync. Data ini mencakup berbagai kode ILAP seperti KM, PB, PD, PK, PL, PV, LM, LK, dll.

#### Post-Process 4: Insert Additional PeriodeJenisData

**Method:** `_post_process_periode_jenis_data_additional()`

Insert ~500+ additional periode records untuk sub_jenis_data yang tidak tercakup oleh query Oracle.

#### Post-Process 5: Update `nama_tabel_I` dari DDE

**Method:** `_post_process_update_nama_tabel_I_from_dde()`

Query `PVPTD.ZA_DDE_TABEL_FACT` untuk mendapatkan `nama_tabel_dbbd` dan update `nama_tabel_I` pada `JenisDataILAP` yang cocok.

Transformasi `id_tiket`:
```sql
-- Jika panjang id_tiket = 16 dan dimulai dengan 'E', replace karakter ke-2 dengan 'I'
-- Ambil 9 karakter pertama sebagai id_sub_jenis_data
SUBSTR(CASE
    WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E'
    THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
    ELSE id_tiket
END, 1, 9)
```

#### Post-Process 6: Update `id_jenis_tabel` dari DDE

**Method:** `_post_process_update_id_jenis_tabel_from_dde()`

Sama seperti post-process 5, tetapi untuk mengupdate `id_jenis_tabel` berdasarkan `JENIS_TABEL` dari `PVPTD.ZA_DDE_TABEL_FACT`.

#### Post-Process 7: Set Unstructured JenisTabel

**Method:** `_post_process_set_unstructured_jenis_tabel()`

Update semua `JenisDataILAP` dengan `nama_tabel_I = 'KPDE_DATA_UNSTRUCTURED'` untuk memiliki `id_jenis_tabel = 'Tidak Terstruktur'`.

---

### 4.4 View Sync Data Referensi

**File:** `diamond_web/views/sync_data_referensi.py`

#### Endpoints (HTTP API)

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| `GET` | `/sync/referensi/` | Halaman UI sinkronisasi referensi |
| `POST` | `/sync/referensi/test-connection/` | Test koneksi Oracle primary & secondary |
| `POST` | `/sync/referensi/check/` | Memulai dry-run check (via Celery) |
| `POST` | `/sync/referensi/run/` | Memulai sinkronisasi penuh (via Celery) |
| `POST` | `/sync/referensi/stop/` | Menghentikan sinkronisasi berjalan |
| `POST` | `/sync/referensi/stop-check/` | Menghentikan check berjalan |
| `POST` | `/sync/referensi/clear-session/` | Membersihkan session cache |
| `GET` | `/sync/referensi/progress/` | Polling progress sinkronisasi |
| `POST` | `/sync/referensi/truncate/` | Hapus semua data referensi |
| `GET` | `/sync/referensi/download-errors/<sync_id>/` | Download CSV error log |

#### Alur Progress Tracking

```
Client (Browser)                    Server (Django)                  Celery Worker
      │                                   │                              │
      │  POST /sync/referensi/run/         │                              │
      │──────────────────────────────────►│                              │
      │  { sync_id: "uuid" }              │                              │
      │◄──────────────────────────────────│                              │
      │                                   │  sync_referensi_data_task    │
      │                                   │  .delay(sync_id) ──────────►│
      │                                   │                              │
      │  GET /sync/referensi/progress/    │                              │
      │  ?sync_id=uuid                    │                              │
      │──────────────────────────────────►│                              │
      │  { done: false, progress: {...} } │                              │
      │◄──────────────────────────────────│                              │
      │  (polling setiap 2 detik)         │                              │
      │                                   │                      Cache update
      │                                   │◄─────────────────────────────│
      │  GET /sync/referensi/progress/    │                              │
      │──────────────────────────────────►│                              │
      │  { done: true, result: {...} }    │                              │
      │◄──────────────────────────────────│                              │
```

#### Cache Keys

| Key Pattern | Purpose |
|-------------|---------|
| `sync_referensi_in_progress_{sync_id}` | Flag sedang berjalan |
| `sync_referensi_done_{sync_id}` | Flag selesai |
| `sync_referensi_result_{sync_id}` | Hasil akhir (dict) |
| `sync_referensi_error_{sync_id}` | Pesan error |
| `sync_referensi_progress_{sync_id}` | Progress per tabel |
| `sync_referensi_stop_requested_{sync_id}` | Flag stop |
| `sync_referensi_celery_task_id_{sync_id}` | ID task Celery |
| `sync_referensi_active_sync_id` | Sync ID aktif terakhir (untuk recovery setelah navigasi) |
| `check_referensi_active_check_id` | Check ID aktif terakhir |

#### Error Logging ke CSV

Setiap baris yang gagal di-sync dicatat ke file CSV:

```
sync_logs/sync_referensi_failed_rows_{sync_id}.csv
```

Kolom: `Timestamp, Row Number, Identifier, Category, Error Reason`

#### Truncate All Reference Tables

**Method:** `oracle_sync_truncate()`

Menghapus semua data dari tabel referensi yang terdaftar di `HARD_CODED_SYNC_TABLES` dengan penanganan vendor database:

| Database | Method |
|----------|--------|
| SQLite | `DELETE` + reset `sqlite_sequence` + `PRAGMA foreign_keys = OFF/ON` |
| PostgreSQL | `DELETE` + reset sequence + disable/enable trigger all |
| MySQL | `TRUNCATE TABLE` + reset `AUTO_INCREMENT` + `SET FOREIGN_KEY_CHECKS = 0/1` |

---

### 4.5 View Sync Data Tiket

**File:** `diamond_web/views/sync_tiket.py`

#### Endpoints (HTTP API)

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| `GET` | `/sync/tiket/` | Halaman UI sinkronisasi tiket |
| `POST` | `/sync/tiket/test-connection/` | Test koneksi Oracle |
| `POST` | `/sync/tiket/check/` | Memulai dry-run check tiket (via Celery) |
| `POST` | `/sync/tiket/run/` | Memulai sinkronisasi tiket (via Celery) |
| `POST` | `/sync/tiket/stop/` | Menghentikan sinkronisasi tiket |
| `POST` | `/sync/tiket/stop-check/` | Menghentikan check tiket |
| `GET` | `/sync/tiket/progress/` | Polling progress sinkronisasi |
| `POST` | `/sync/tiket/truncate/` | Hapus semua data tiket |
| `GET` | `/sync/tiket/download-errors/<sync_id>/` | Download CSV error log |

#### Alur Sinkronisasi Tiket

```
1. Query Oracle (bulk)
   └─► Execute _TIKET_ORACLE_SQL → fetchall() → ~N baris

2. Build lookup caches
   ├─► PeriodeJenisData cache (key: id_sub_jenis_data)
   ├─► BentukData cache (key: deskripsi)
   └─► CaraPenyampaian cache (key: deskripsi)

3. Bulk exists pre-fetch
   └─► Deduplicate nomor_tiket → query Tiket.objects.filter(nomor_tiket__in=...)
       → existing_set (chunked per 500 untuk SQLite variable limit)

4. Parse & validate setiap baris
   ├─► Parse nomor_tiket → validasi length >= 9
   ├─► Resolve PeriodeJenisData via lookup cache
   ├─► Map status_tiket dari Oracle → numeric status
   ├─► Parse periode (triwulan, semester, bulan, tahun)
   └──► Klasifikasikan: INSERT (baru) atau UPDATE (existing)

5. Bulk INSERT (batch)
   ├─► BATCH_SIZE = 50 (SQLite), 500 (PostgreSQL), 250 (MySQL)
   └─► Assign PICs via bulk_create untuk setiap tiket baru

6. Bulk UPDATE (batch)
   └─► Update field yang berubah pada tiket existing

7. Auto-settlement
   └─► Tiket dengan JenisTabel='Tidak Diidentifikasi' dan
       tgl_transfer < 2024-05-01 → auto-settle ke status Selesai
```

#### Batch Sizes by Database

| Database Vendor | `BATCH_SIZE` | `LOOKUP_BATCH_SIZE` | Alasan |
|-----------------|-------------|---------------------|--------|
| SQLite | 50 | 50 | Variable limit ~999 |
| PostgreSQL | 500 | 500 | Variable limit ~34,000 |
| MySQL | 250 | 250 | Variable limit ~16,000 |

---

### 4.6 Tiket Oracle SQL Query

**Variable:** `_TIKET_ORACLE_SQL` di `diamond_web/views/sync_tiket.py`

#### Oracle Source Tables

| Schema.Tabel | Alias | Peran |
|-------------|-------|-------|
| `PVPTD.ZA_DDE_TABEL_FACT` | `a` | Tabel utama (source: `LEFT JOIN`) |
| `PVPTD.ZA_REKAP_TARIKAN` | `b` | Data identifikasi & QC (LEFT JOIN, subquery dengan GROUP BY) |
| `PVPTD.ZA_REKAP_TIKET` | `c` | Tanggal rekam PIDE (LEFT JOIN, subquery) |
| `PROD.APP_PENERIMAANBACKUP` | `d` | Data penerimaan tambahan (LEFT JOIN, subquery) |

#### Transformasi ID Tiket

```sql
CASE
    WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E'
    THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
    ELSE id_tiket
END AS id_tiket
```

#### Kolom yang Dihasilkan Query

| Kolom Query | Tipe | Deskripsi |
|-------------|------|-----------|
| `id_tiket` | VARCHAR | Nomor tiket (sudah ditransformasi) |
| `old_db` | INTEGER | Selalu `1` (dari Oracle = old) |
| `status_tiket` | INTEGER (1-8) | Status numerik (lihat mapping di 4.7) |
| `periode_penerimaan` | VARCHAR | `Tahunan` / `Bulanan` / `Triwulanan` / dll |
| `jenis_prioritas_data` | VARCHAR | Format: `{id_sub}_20{yy}` |
| `periode_data` | VARCHAR | Dari Oracle, misal: `Tahun`, `Januari`, `Triwulan I` |
| `tahun_data` | INTEGER | Tahun data (NULL → 2099) |
| `penyampaian` | INTEGER | Row number PARTITION BY (id_tiket, periode_data, tahun_data) ORDER BY TGL_TERIMA |
| `nomor_surat_pengantar` | VARCHAR | NO_SURATPENGANTAR (NULL → '-') |
| `tanggal_surat_pengantar` | DATE | TGL_SURATPENGANTAR → TGL_TERIMA → derived dari id_tiket |
| `nama_pengirim` | VARCHAR | NAMA_PENGIRIM (NULL → '-') |
| `bentuk_data` | VARCHAR | Dari PROD.APP_PENERIMAANBACKUP |
| `cara_penyampaian` | VARCHAR | Dari PROD.APP_PENERIMAANBACKUP |
| `status_ketersediaan_data` | INTEGER | 1 = tersedia, 0 = tiket 0 row |
| `alasan_ketidaktersediaan` | VARCHAR | NULL |
| `baris_diterima` | INTEGER | JML_ROW_P3DE (NULL → 0) |
| `satuan_data` | INTEGER | Selalu 1 |
| `tgl_terima_vertikal` | DATE | NULL |
| `tgl_terima_dip` | DATE | TGL_TERIMA → derived dari id_tiket |
| `backup` | INTEGER | Selalu 0 |
| `tanda_terima` | INTEGER | Selalu 0 |
| `status_penelitian` | VARCHAR | `Lengkap` / `Lengkap Sebagian` / `Tidak Lengkap` |
| `tgl_teliti` | DATE | TGL_TELITI |
| `baris_lengkap` | INTEGER | JML_DATA_TELITI (NULL → 0) |
| `baris_tidak_lengkap` | INTEGER | JML_ROW_P3DE - JML_DATA_TELITI |
| `tgl_nadine` | DATE | TGL_NADINE |
| `no_nadine` | VARCHAR | NO_NADINE |
| `tgl_kirim_pide` | DATE | TGL_NADINE |
| `tgl_rekam_pide` | DATE | Dari PVPTD.ZA_REKAP_TIKET |
| `baris_i` | INTEGER | SUM(JML_LOG) dari ZA_REKAP_TARIKAN |
| `baris_u` | INTEGER | SUM(JML_LOG_U) |
| `baris_res` | INTEGER | SUM(JML_RES) |
| `baris_cde` | INTEGER | SUM(JML_CDE) |
| `tgl_transfer` | DATE | MIN(tgl_transfer) |
| `tgl_rematch` | DATE | MAX(tgl_rematch) |
| `sudah_qc` | INTEGER | SUM(SUDAH_QC) |
| `belum_qc` | INTEGER | SUM(belum_qc) |
| `lolos_qc` | INTEGER | SUM(lolos_qc) |
| `tidak_lolos_qc` | INTEGER | SUM(TIDAK_LOLOS_QC) |
| `qc_p` .. `qc_d` | INTEGER | SUM(QC_P) .. SUM(QC_D) — detail kode QC |
| `tgl_tiket` | DATE | Dari PVPTD.ZA_REKAP_TIKET |

---

### 4.7 Status Tiket Mapping

Mapping dari `status_tiket` Oracle (string) ke status numerik Diamond:

| Status Oracle (String) | Numerik | Nama |
|-----------------------|---------|------|
| `[SELESAI]-Sudah QC` | 8 | Selesai |
| `[SELESAI]-Tidak di QC` | 8 | Selesai |
| `[SELESAI]-Tiket 0 Row` | 8 | Selesai |
| *Tidak Lengkap* (fallback) | 7 | Batal |
| `[P3DE]-Close Tiket` | 7 | Batal |
| `[PIDE]-Close Tiket` | 7 | Batal |
| `[PMDE]-Proses QC` | 6 | Pengendalian Mutu |
| `[PIDE]-Proses Identifikasi` (dengan tgl_tiket) | 5 | Terekam PIDE |
| `[PIDE]-Proses Identifikasi` (tanpa tgl_tiket) | 4 | Dikirim ke PIDE |
| `[P3DE]-Proses Nadine` | 2 | Identifikasi |
| `[P3DE]-Proses Penelitian` | 1 | Penelitian |
| Lainnya (default) | 1 | Penelitian |

**Logika Tambahan untuk Status 7 (Batal):**
- Jika bukan `Lengkap` AND bukan `Lengkap Sebagian` AND `JML_DATA_TELITI IS NOT NULL`
- Maka override ke status 7 (Batal / Tidak Lengkap)

**Logika Tambahan untuk Status 8 (Selesai):**
- Jika `status_tiket` mengandung `[SELESAI]`, maka status 8

---

### 4.8 Mapping Field Tiket

Mapping dari kolom hasil query Oracle ke model Django `Tiket`:

| Field Tiket (Django) | Oracle Column / Source | Tipe |
|----------------------|----------------------|------|
| `nomor_tiket` | `id_tiket` (transformasi E→I) | VARCHAR |
| `old_db` | `old_db` (selalu 1) | Boolean |
| `status_tiket` | `status_tiket` (numerik 1-8) | Integer |
| `id_periode_data` | `periode_jenis_data_obj` (FK via lookup cache) | FK PeriodeJenisData |
| `id_jenis_prioritas_data` | `jenis_prioritas_data` (parsed via _parse_jenis_prioritas_data) | FK JenisPrioritasData |
| `periode` | `periode_data` (parsed via _map_periode_data) | Integer |
| `tahun` | `tahun_data` | Integer |
| `penyampaian` | `penyampaian` (ROW_NUMBER) | Integer |
| `nomor_surat_pengantar` | `nomor_surat_pengantar` (NULL → '-') | VARCHAR |
| `tanggal_surat_pengantar` | `tanggal_surat_pengantar` (NULL → timezone.now()) | DateTime |
| `nama_pengirim` | `nama_pengirim` (NULL → '-') | VARCHAR |
| `id_bentuk_data` | `bentuk_data` (lookup BentukData cache) | FK BentukData |
| `id_cara_penyampaian` | `cara_penyampaian` (lookup CaraPenyampaian cache) | FK CaraPenyampaian |
| `status_ketersediaan_data` | `status_ketersediaan_data` (1/0) | Boolean |
| `alasan_ketidaktersediaan` | `alasan_ketidaktersediaan` | TEXT |
| `baris_diterima` | `baris_diterima` (NULL → 0) | Integer |
| `satuan_data` | `satuan_data` (default 1) | Integer |
| `tgl_terima_vertikal` | `tgl_terima_vertikal` | DateTime |
| `tgl_terima_dip` | `tgl_terima_dip` (NULL → timezone.now()) | DateTime |
| `backup` | `backup` (selalu 0) | Boolean |
| `tanda_terima` | `tanda_terima` (selalu 0) | Boolean |
| `id_status_penelitian` | `status_penelitian` (lookup StatusPenelitian via `deskripsi__icontains`) | FK StatusPenelitian |
| `tgl_teliti` | `tgl_teliti` | DateTime |
| `baris_lengkap` | `baris_lengkap` | Integer |
| `baris_tidak_lengkap` | `baris_tidak_lengkap` | Integer |
| `tgl_nadine` | `tgl_nadine` | DateTime |
| `nomor_nd_nadine` | `no_nadine` | VARCHAR |
| `tgl_kirim_pide` | `tgl_kirim_pide` (= tgl_nadine) | DateTime |
| `tgl_rekam_pide` | `tgl_rekam_pide` | DateTime |
| `baris_i` | `baris_i` (= JML_LOG) | Integer |
| `baris_u` | `baris_u` (= JML_LOG_U) | Integer |
| `baris_res` | `baris_res` (= JML_RES) | Integer |
| `baris_cde` | `baris_cde` (= JML_CDE) | Integer |
| `tgl_transfer` | `tgl_transfer` | DateTime |
| `tgl_rematch` | `tgl_rematch` | DateTime |
| `sudah_qc` .. `qc_d` | `sudah_qc` .. `qc_d` | Integer |

#### Periode Mapping Logic

**Function:** `_map_periode_data()`

| Oracle `periode_data` | `periode_value` | Contoh |
|-----------------------|-----------------|--------|
| `Januari`, `Februari`, ... | 1..12 | `Januari` → 1 |
| `Triwulan I/II/III/IV` | 1..4 | `Triwulan I` → 1 |
| `Semester I/II` | 1..2 | `Semester II` → 2 |
| `Tahun`, `Tahunan` | 1 | `Tahunan` → 1 |
| `Minggu ke-N` | N | `Minggu ke-3` → 3 |
| `Harian` | 1 | `Harian` → 1 |

#### PIC Assignment Logic

**Function:** `_assign_tiket_pics_sync()`

Setelah tiket baru di-insert, sistem meng-assign PIC dengan aturan:
- Query semua `PIC` aktif (`start_date <= today AND end_date IS NULL`)
- Filter berdasarkan `id_sub_jenis_data_ilap` (dari periode_jenis_data)
- Untuk setiap role (P3DE, PIDE, PMDE), assign PIC yang cocok
- Buat `TiketPIC` record + `TiketAction` audit trail via `bulk_create`

#### Auto-Settlement

Setelah sync selesai, sistem melakukan auto-settlement:
```python
Tiket.objects.filter(
    status_tiket=STATUS_PENGENDALIAN_MUTU,  # status 6
    tgl_transfer__lt=cutoff_date,            # sebelum 2024-05-01
    id_periode_data__in=auto_settle_ids,     # JenisTabel = 'Tidak Diidentifikasi'
).update(status_tiket=STATUS_SELESAI)         # → status 8
```

---

## 5. Backup Database Harian

**Script:** `scripts/db_backup_daily.sh`

#### Alur Proses

```
Mulai
  │
  ├─► Pre-flight checks (cek manage.py, venv, dll)
  │
  ├─► STEP 1: Database Backup
  │   └─► python manage.py dbbackup --quiet --compress
  │
  ├─► STEP 2: Media Backup
  │   └─► python manage.py mediabackup --quiet --compress
  │
  ├─► STEP 3: Cleanup Backup Lama (retensi 30 hari)
  │   └─► Hapus file backup > 30 hari
  │
  └─► Ringkasan hasil backup
```

#### Detail Konfigurasi

| Item | Nilai |
|------|-------|
| Jadwal | Setiap hari pukul 00:00 WIB |
| Lokasi backup | `/home/pajak/diamond-web/backups/` |
| Log | `/home/pajak/diamond-web/backups/logs/` |
| Kompresi | Ya (`--compress`) |
| Retensi | 30 hari (dapat diubah via env `BACKUP_RETENTION_DAYS`) |
| Lock file | `/tmp/diamond_dbbackup.lock` (cegah tumpukan proses) |

#### File Backup yang Dihasilkan

```
backups/
├── <namadb>-<timestamp>.dump   # Database dump (kompres)
├── <media>-<timestamp>.tar     # Media archive (kompres)
└── logs/
    └── db_backup_<timestamp>.log
```

---

## 6. Pre-Production Cleanup

**Script:** `scripts/cleanup_pre_production.sh`  
**Management Command:** `python manage.py cleanup_pre_production`

#### Alur Proses

```
Mulai
  │
  ├─► Safety check: hanya jalan jika tanggal = 2026-07-01 (kecuali --dry-run)
  │
  ├─► STEP 1: Dry-Run
  │   ├─► Phase 1: Hitung data testing yang akan dibersihkan
  │   │     (BackupData, TandaTerimaData, DetilTandaTerima, TiketAction selain 301)
  │   └─► Phase 2: Hitung tiket old_db=False & relasinya
  │          (TiketPIC, TiketAction old_db=False, KirimPideTemp, Tiket)
  │
  ├─► STEP 2: Eksekusi Penghapusan (dalam 1 transaksi)
  │   ├─► Phase 1 — Pembersihan Data Testing:
  │   │     ├─ Hapus DetilTandaTerima (semua)
  │   │     ├─ Hapus TandaTerimaData (semua)
  │   │     ├─ Hapus BackupData (semua)
  │   │     └─ Hapus TiketAction (kecuali action=301)
  │   │
  │   └─► Phase 2 — Hapus Tiket old_db=False:
  │         ├─ Hapus TiketPIC (id_tiket in tiket_ids)
  │         ├─ Hapus TiketAction (id_tiket in tiket_ids)
  │         ├─ Hapus KirimPideTemp (id_tiket in tiket_ids)
  │         └─ Hapus Tiket (old_db=False)
  │
  ├─► STEP 3: Verifikasi
  │   └─► Jalankan dry-run → pastikan bersih
  │
  └─► Ringkasan hasil cleanup
```

#### Urutan Penghapusan (Transaction Atomic)

Penghapusan dilakukan dalam urutan tertentu untuk menghindari constraint violation:

**Phase 1 — Data Testing (dihapus semua, tanpa filter id_tiket):**
```
1. DetilTandaTerima ──► child dari TandaTerimaData & Tiket (hapus dulu)
2. TandaTerimaData ───► parent (hapus setelah child-nya habis)
3. BackupData ────────► child dari Tiket (hapus semua)
4. TiketAction ───────► kecuali action=301 (PIC Ditambahkan)
```

**Phase 2 — Tiket old_db=False (filter id_tiket):**
```
5. TiketPIC ──────────► child dari Tiket (hapus dulu)
6. TiketAction ───────► child dari Tiket (sisa action=301 milik old_db=False)
7. KirimPideTemp ─────► child dari Tiket
8. Tiket ─────────────► parent (hapus terakhir)
```

Semua operasi dijalankan dalam `transaction.atomic()` — jika ada kegagalan di tengah jalan, semua perubahan akan di-rollback.

---

## 7. Jadwal Cron

Berikut adalah daftar lengkap cron job yang terpasang di server produksi:

```bash
# ┌───────────── menit (0 - 59)
# │ ┌───────────── jam (0 - 23)
# │ │ ┌───────────── hari (1 - 31)
# │ │ │ ┌───────────── bulan (1 - 12)
# │ │ │ │ ┌───────────── hari dalam minggu (0 - 6) (0 = Minggu)
# │ │ │ │ │
# * * * * * command_to_execute
```

### Crontab Aktif

| Waktu | Ekspresi Cron | Script | Deskripsi |
|-------|--------------|--------|-----------|
| **00:00 WIB setiap hari** | `0 0 * * *` | `/home/pajak/diamond-web/scripts/db_backup_daily.sh` | **Backup Database Harian** — Mencadangkan database dan media, membersihkan backup lama (retensi 30 hari). |
| **09:00 WIB setiap hari** | `0 9 * * *` | `/home/pajak/diamond-web/scripts/sync_daily_cron.sh` | **Sinkronisasi Oracle Harian** — Menjalankan sync referensi dilanjutkan sync tiket dari Oracle. Berhenti otomatis setelah 1 Juli 2026. |
| **1 Juli 2026 00:00 WIB** | `0 0 1 7 *` | `/home/pajak/diamond-web/scripts/cleanup_pre_production.sh` | **Pre-Production Cleanup** — Sekali jalan: (1) truncate data testing (BackupData, TandaTerimaData, DetilTandaTerima, TiketAction selain 301), (2) hapus tiket `old_db=False` dan relasinya. |

### Detail Setiap Cron Job

#### 1. Backup Database Harian — `0 0 * * *`

```bash
# Crontab entry:
0 0 * * * /home/pajak/diamond-web/scripts/db_backup_daily.sh
```

| Atribut | Nilai |
|---------|-------|
| **Frekuensi** | Setiap hari pukul 00:00 WIB |
| **Script** | `/home/pajak/diamond-web/scripts/db_backup_daily.sh` |
| **Fungsi** | Backup database (dbbackup) + backup media (mediabackup) + cleanup backup lama |
| **Log output** | `/home/pajak/diamond-web/backups/logs/db_backup_<timestamp>.log` |
| **Lock file** | `/tmp/diamond_dbbackup.lock` |
| **Retensi** | 30 hari (konfigurabel via `BACKUP_RETENTION_DAYS`) |

---

#### 2. Sinkronisasi Oracle Harian — `0 9 * * *`

```bash
# Crontab entry:
0 9 * * * /home/pajak/diamond-web/scripts/sync_daily_cron.sh
```

| Atribut | Nilai |
|---------|-------|
| **Frekuensi** | Setiap hari pukul 09:00 WIB |
| **Script** | `/home/pajak/diamond-web/scripts/sync_daily_cron.sh` |
| **Fungsi** | Menjalankan 2 langkah sinkronisasi: (1) Referensi sync, (2) Tiket sync |
| **Log output** | `/home/pajak/diamond-web/sync_logs/daily_sync_<timestamp>.log` |
| **Lock file** | `/tmp/diamond_oracle_sync.lock` |
| **Cutoff date** | Berhenti otomatis setelah **1 Juli 2026** (akhir masa kontrak) |

**Tahapan dalam script:**

| Step | Perintah | Log File |
|------|----------|----------|
| 1/2 | `python manage.py sync_oracle_data` | `referensi_sync_<timestamp>.log` |
| 2/2 | `python manage.py sync_tiket_data` | `tiket_sync_<timestamp>.log` |

> **Catatan:** Jika langkah 1 gagal, langkah 2 tetap dijalankan (tidak berhenti di tengah).

---

#### 3. Pre-Production Cleanup — `0 0 1 7 *`

```bash
# Crontab entry:
0 0 1 7 * /home/pajak/diamond-web/scripts/cleanup_pre_production.sh
```

| Atribut | Nilai |
|---------|-------|
| **Frekuensi** | **Sekali saja** — 1 Juli 2026 pukul 00:00 WIB |
| **Script** | `/home/pajak/diamond-web/scripts/cleanup_pre_production.sh` |
| **Fungsi** | **Phase 1:** Truncate data testing (BackupData, TandaTerimaData, DetilTandaTerima); hapus TiketAction selain action=301. **Phase 2:** Hapus tiket `old_db=False` beserta relasinya (TiketPIC, KirimPideTemp). Hanya menyisakan tiket hasil sinkronisasi Oracle. |
| **Log output** | `/home/pajak/diamond-web/sync_logs/cleanup_pre_production_<timestamp>.log` |
| **Lock file** | `/tmp/diamond_cleanup_pre_production.lock` |
| **Safety check** | Hanya berjalan jika tanggal = `2026-07-01` (kecuali dengan flag `--dry-run`) |

**Tahapan dalam script:**

| Step | Aksi | Log |
|------|------|-----|
| 1/3 | Dry-run (estimasi data testing + tiket old_db=False) | `cleanup_dryrun_<timestamp>.log` |
| 2/3 | Eksekusi: Phase 1 (data testing) + Phase 2 (old_db=False) | `cleanup_exec_<timestamp>.log` |
| 3/3 | Verifikasi (dry-run ulang untuk memastikan bersih) | `cleanup_verify_<timestamp>.log` |

---

### Cara Memasang / Memodifikasi Cron Jobs

```bash
# Edit crontab
crontab -e

# Untuk memasang semua cron jobs, tambahkan baris berikut:
# ─────────────────────────────────────────────────────────────
# Diamond Web - Cron Jobs
# ─────────────────────────────────────────────────────────────
# Backup Database Harian - setiap hari jam 00:00 WIB
0 0 * * * /home/pajak/diamond-web/scripts/db_backup_daily.sh

# Sinkronisasi Oracle Harian - setiap hari jam 09:00 WIB
0 9 * * * /home/pajak/diamond-web/scripts/sync_daily_cron.sh

# Pre-Production Cleanup - 1 Juli 2026 jam 00:00 WIB
0 0 1 7 * /home/pajak/diamond-web/scripts/cleanup_pre_production.sh
# ─────────────────────────────────────────────────────────────
```

### Verifikasi Cron

```bash
# Lihat semua cron jobs yang aktif
crontab -l

# Cek log cron (Ubuntu/Debian)
sudo grep CRON /var/log/syslog | grep diamond

# Cek apakah script memiliki execute permission
ls -la /home/pajak/diamond-web/scripts/*.sh
# Output: -rwxr-xr-x ... (pastikan ada x untuk execute)

# Jika tidak ada execute permission, berikan:
chmod +x /home/pajak/diamond-web/scripts/*.sh
```

---

## 8. Manajemen Command

### 8.1 Daftar Management Command

| Command | Deskripsi | Mode |
|---------|-----------|------|
| `sync_oracle_data` | Sinkronisasi data referensi dari Oracle | `--check-only` (dry) / normal (execute) |
| `sync_tiket_data` | Sinkronisasi data tiket dari Oracle | `--check-only` (dry) / normal (execute) |
| `cleanup_pre_production` | Bersihkan data testing + hapus tiket `old_db=False` | `--dry-run` / `--skip-test-data` / normal (execute) |
| `dbbackup` | Backup database (django-dbbackup) | `--compress`, `--database=default` |
| `mediabackup` | Backup media files (django-dbbackup) | `--compress` |
| `dbrestore` | Restore database dari backup | `-i <filename>` (spesifik) / tanpa flag (latest) |

### Alur Eksekusi Lengkap

Berikut adalah alur lengkap dari awal migrasi hingga go-live produksi:

```
MINGGU 1-2              │  Setup koneksi Oracle & instalasi Oracle Instant Client
                        │  python manage.py sync_oracle_data --check-only
                        │  python manage.py sync_oracle_data
                        │
MINGGU 3-4              │  python manage.py sync_tiket_data --check-only
                        │  python manage.py sync_tiket_data
                        │  Verifikasi data tiket
                        │
SETIAP HARI (09:00)     │  Cron: sync_daily_cron.sh
                        │    ├─ sync_oracle_data (referensi)
                        │    └─ sync_tiket_data (tiket)
                        │
SETIAP HARI (00:00)     │  Cron: db_backup_daily.sh
                        │    ├─ dbbackup (database)
                        │    ├─ mediabackup (media)
                        │    └─ cleanup backup > 30 hari
                        │
H-7 BEFORE GO-LIVE      │  ./cleanup_pre_production.sh --dry-run
                        │  Backup database: python manage.py dbbackup --compress
                        │  Review hasil dry-run dengan tim (cek data testing & tiket)
                        │
1 JULI 2026 (00:00)     │  Cron: cleanup_pre_production.sh
                        │    ├─ Dry-run otomatis
                        │    ├─ Phase 1: Truncate data testing
                        │    │     (BackupData, TandaTerimaData, DetilTandaTerima,
                        │    │      TiketAction selain action=301)
                        │    ├─ Phase 2: Hapus tiket old_db=False
                        │    └─ Verifikasi akhir
                        │
GO-LIVE                 │  Sistem siap produksi dengan data Oracle murni
```

---

## 9. Verifikasi & Troubleshooting

### Verifikasi Data

```bash
# 1. Cek jumlah tiket
python manage.py shell_plus -c "
from diamond_web.models.tiket import Tiket
total = Tiket.objects.count()
old = Tiket.objects.filter(old_db=True).count()
new = Tiket.objects.filter(old_db=False).count()
print(f'Total: {total} | old_db=True: {old} | old_db=False: {new}')
"

# 2. Cek integritas relasi
python manage.py shell_plus -c "
from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.models.tiket_action import TiketAction

# Tiket tanpa PIC (orphan?)
tiket_ids = Tiket.objects.values_list('id', flat=True)
pic_ids = TiketPIC.objects.values_list('id_tiket', flat=True)
orphan = set(tiket_ids) - set(pic_ids)
print(f'Tiket tanpa PIC: {len(orphan)}')
"

# 3. Cek log sinkronisasi terakhir
tail -50 /home/pajak/diamond-web/sync_logs/daily_sync_*.log
```

### Daftar Log Files

| Log File | Lokasi | Deskripsi |
|----------|--------|-----------|
| Daily sync master | `sync_logs/daily_sync_<timestamp>.log` | Log utama sinkronisasi harian |
| Referensi sync | `sync_logs/referensi_sync_<timestamp>.log` | Detail sync data referensi |
| Tiket sync | `sync_logs/tiket_sync_<timestamp>.log` | Detail sync data tiket |
| Backup log | `backups/logs/db_backup_<timestamp>.log` | Log backup database |
| Cleanup master | `sync_logs/cleanup_pre_production_<timestamp>.log` | Log utama pre-production cleanup |
| Cleanup dry-run | `sync_logs/cleanup_dryrun_<timestamp>.log` | Estimasi data yang akan dihapus |
| Cleanup exec | `sync_logs/cleanup_exec_<timestamp>.log` | Detail eksekusi penghapusan |
| Cleanup verify | `sync_logs/cleanup_verify_<timestamp>.log` | Verifikasi pasca-cleanup |
| Error log | `sync_logs/*_error.log` | Log error khusus (jika ada kegagalan) |

### Troubleshooting Umum

| Masalah | Penyebab | Solusi |
|---------|----------|--------|
| `ORA-12154: TNS:could not resolve the connect identifier specified` | Konfigurasi Oracle salah | Periksa `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME` di `.env` |
| `DPY-3010: Oracle Client library is not loaded` | Oracle Instant Client tidak terdeteksi | Set `LD_LIBRARY_PATH` atau install ulang instant client |
| `Sync berjalan lambat (>30 menit)` | Dataset besar | Biarkan berjalan async via Celery; cek progress di UI |
| `Lock file error: Sync already running` | Proses sebelumnya masih berjalan atau crash | Hapus lock file: `rm -f /tmp/diamond_oracle_sync.lock` |
| `Backup gagal: disk penuh` | Kapasitas disk tidak mencukupi | Hapus backup lama: `find backups/ -name '*.dump' -mtime +30 -delete` |
| `Cleanup tidak berjalan di tanggal yang salah` | Safety check mencegah eksekusi | Gunakan `--dry-run` untuk simulasi; tunggu tanggal yang benar |
| `IntegrityError saat cleanup` | Ada relasi yang tidak terduga | Periksa manual data yang akan dihapus; pastikan urutan penghapusan benar: DetilTandaTerima → TandaTerimaData → BackupData → TiketAction (phase 1), lalu TiketPIC → TiketAction → KirimPideTemp → Tiket (phase 2) |
| `Data testing tidak ikut terhapus` | Menggunakan `--skip-test-data` | Hapus flag `--skip-test-data` atau jalankan tanpa flag tersebut |

---

## 10. Rollback Plan

### Jika Sinkronisasi Gagal

```bash
# 1. Identifikasi masalah dari log
tail -100 sync_logs/tiket_sync_$(date +%F)*.log

# 2. Perbaiki konfigurasi (jika masalah koneksi)
# 3. Jalankan ulang sinkronisasi
python manage.py sync_tiket_data
```

### Jika Cleanup Gagal

Karena cleanup dijalankan dalam `transaction.atomic()`, jika terjadi kegagalan, semua perubahan akan di-rollback secara otomatis. Tidak perlu tindakan tambahan.

### Jika Cleanup Berhasil tapi Ada Data Hilang yang Seharusnya Tidak Dihapus

```bash
# 1. Hentikan akses pengguna ke sistem
# 2. Restore database dari backup terakhir
python manage.py dbrestore -i <backup_filename>

# 3. Verifikasi data kembali
python manage.py cleanup_pre_production --dry-run

# 4. Identifikasi penyebab (misalnya: ada tiket dengan old_db=False yang seharusnya old_db=True)
# 5. Perbaiki data di Oracle, sync ulang, lalu jalankan cleanup lagi
```

### Praktik Terbaik

1. **Selalu backup sebelum perubahan besar** — `python manage.py dbbackup --compress`
2. **Selalu dry-run sebelum eksekusi** — gunakan `--check-only` atau `--dry-run`
3. **Pantau log secara berkala** — terutama di minggu pertama setelah cron aktif
4. **Dokumentasikan setiap kegagalan** — untuk referensi troubleshooting di masa depan

---

> **Disiapkan oleh:** Tim Pengembangan Diamond Web  
> **Tanggal:** June 25, 2026  
> **Revisi:** 1.0  
> **Pertanyaan?** Hubungi tim pengembangan atau buka issue di repositori.
