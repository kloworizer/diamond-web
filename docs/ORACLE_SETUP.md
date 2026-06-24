# Panduan Setup Database Oracle untuk python-oracledb (Mode Thick)

## Masalah
Jika Anda mengalami error:
```
DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode
```

Ini berarti python-oracledb berjalan dalam **mode thin** yang tidak mendukung versi database Oracle Anda. Anda perlu mengaktifkan **mode thick**.

## Solusi: Aktifkan Mode Thick

Mode thick memerlukan library Oracle Client untuk diinstal di sistem Anda.

### Prasyarat

#### Windows
- **Oracle Instant Client Basic** atau **Oracle Database Client** terinstal
- Unduh dari: https://www.oracle.com/database/technologies/instant-client/downloads.html
- Ekstrak ke folder, misalnya `C:\oracle\instantclient_21_9`

#### Linux/Unix
- Instal library Oracle Client
- Atur variabel lingkungan `LD_LIBRARY_PATH`

#### macOS
- Instal Oracle Instant Client
- Mungkin memerlukan konfigurasi tambahan

### Petunjuk Setup

#### Windows

1. **Unduh Oracle Instant Client Basic**
   - Kunjungi: https://www.oracle.com/database/technologies/instant-client/downloads.html
   - Pilih OS Anda (Windows) dan unduh paket Basic
   - Ekstrak ke lokasi seperti `C:\oracle\instantclient_21_9`

2. **Atur Variabel Lingkungan**
   ```batch
   setx ORACLE_CLIENT_HOME "C:\oracle\instantclient_21_9"
   setx PATH "%PATH%;C:\oracle\instantclient_21_9"
   ```
   
   Atau tambahkan melalui Python:
   ```python
   import os
   os.environ['ORACLE_CLIENT_HOME'] = r'C:\oracle\instantclient_21_9'
   ```

3. **Uji Koneksi**
   ```bash
   python -m diamond_web.utils.oracle_sync --check
   ```

#### Linux

1. **Instal Oracle Client**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install oracle-instantclient-basic
   
   # Atau unduh dan instal secara manual dari Oracle
   ```

2. **Atur LD_LIBRARY_PATH**
   ```bash
   export LD_LIBRARY_PATH=/usr/lib/oracle/21/client64/lib:$LD_LIBRARY_PATH
   ```
   
   Tambahkan ke `.bashrc` atau `.bash_profile`:
   ```bash
   echo 'export LD_LIBRARY_PATH=/usr/lib/oracle/21/client64/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
   source ~/.bashrc
   ```

#### macOS

1. **Instal Oracle Instant Client**
   ```bash
   brew install oracle-instantclient
   ```

2. **Atur Variabel Lingkungan**
   ```bash
   export DYLD_LIBRARY_PATH=/usr/local/lib/oracle/instantclient_21_9:$DYLD_LIBRARY_PATH
   ```

### Konfigurasi di Django

Kode secara otomatis menginisialisasi mode thick ketika `OracleDataSyncService` dipakai (diinstansiasi):

```python
from diamond_web.utils.oracle_sync import OracleDataSyncService

# Ini akan menginisialisasi mode thick secara otomatis
service = OracleDataSyncService()
```

Jika inisialisasi gagal, periksa:
1. Oracle Client sudah terinstal
2. `ORACLE_CLIENT_HOME` sudah diatur dengan benar (Windows)
3. `LD_LIBRARY_PATH` sudah diatur dengan benar (Linux)

### Variabel Lingkungan yang Diperlukan

Atur ini di file `.env` Anda:

```env
# Primary Oracle Connection
ORACLE_USER=your_username
ORACLE_PASSWORD=your_password
ORACLE_HOST=your_host
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=your_service_name  # or use ORACLE_SID instead

# Optional: Secondary Oracle Connection
ORACLE_SECONDARY_USER=
ORACLE_SECONDARY_PASSWORD=
ORACLE_SECONDARY_HOST=
ORACLE_SECONDARY_PORT=1521
ORACLE_SECONDARY_SERVICE_NAME=
```

### Pemecahan Masalah

#### Error: "Oracle Client is not found"
- Pastikan Oracle Instant Client sudah terinstal
- Verifikasi bahwa `ORACLE_CLIENT_HOME` atau `LD_LIBRARY_PATH` sudah diatur dengan benar
- Mulai ulang terminal/IDE Anda setelah mengatur variabel lingkungan

#### Error: "cannot connect to database"
- Verifikasi kredensial Oracle dan string koneksi
- Uji dengan `sqlplus` atau alat Oracle client lainnya terlebih dahulu
- Periksa konektivitas firewall/jaringan ke server Oracle

#### Error: "DPY-3010" masih terjadi
- Pastikan Anda telah memulai ulang proses Python/IDE Anda
- Variabel lingkungan harus diatur SEBELUM Python dimulai
- Coba atur secara terprogram sebagai import pertama:
  ```python
  import os
  os.environ['ORACLE_CLIENT_HOME'] = r'C:\oracle\instantclient_21_9'
  import oracledb
  oracledb.init_oracle_client()
  ```

### Menguji Koneksi

```bash
cd diamond-web
python manage.py shell
```

Kemudian di shell Python:
```python
from diamond_web.utils.oracle_sync import OracleDataSyncService
service = OracleDataSyncService()
print("Oracle connection successful!")
```

### Informasi Lebih Lanjut

- [python-oracledb Documentation](https://python-oracledb.readthedocs.io/)
- [Oracle Instant Client Setup](https://www.oracle.com/database/technologies/instant-client/downloads.html)
- [Thick Mode Guide](https://python-oracledb.readthedocs.io/en/latest/user_guide/initialization.html#thick-mode)
