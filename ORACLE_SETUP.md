# Oracle Database Setup Guide for python-oracledb (Thick Mode)

## Problem
If you encounter the error:
```
DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode
```

This means python-oracledb is running in **thin mode** which doesn't support your Oracle database version. You need to enable **thick mode**.

## Solution: Enable Thick Mode

Thick mode requires Oracle Client libraries to be installed on your system.

### Prerequisites

#### Windows
- **Oracle Instant Client Basic** or **Oracle Database Client** installed
- Download from: https://www.oracle.com/database/technologies/instant-client/downloads.html
- Extract to a folder, e.g., `C:\oracle\instantclient_21_9`

#### Linux/Unix
- Install Oracle Client libraries
- Set `LD_LIBRARY_PATH` environment variable

#### macOS
- Install Oracle Instant Client
- May require additional configuration

### Setup Instructions

#### Windows

1. **Download Oracle Instant Client Basic**
   - Visit: https://www.oracle.com/database/technologies/instant-client/downloads.html
   - Select your OS (Windows) and download the Basic package
   - Extract to a location like `C:\oracle\instantclient_21_9`

2. **Set Environment Variables**
   ```batch
   setx ORACLE_CLIENT_HOME "C:\oracle\instantclient_21_9"
   setx PATH "%PATH%;C:\oracle\instantclient_21_9"
   ```
   
   Or add via Python:
   ```python
   import os
   os.environ['ORACLE_CLIENT_HOME'] = r'C:\oracle\instantclient_21_9'
   ```

3. **Test Connection**
   ```bash
   python -m diamond_web.utils.oracle_sync --check
   ```

#### Linux

1. **Install Oracle Client**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install oracle-instantclient-basic
   
   # Or download and install manually from Oracle
   ```

2. **Set LD_LIBRARY_PATH**
   ```bash
   export LD_LIBRARY_PATH=/usr/lib/oracle/21/client64/lib:$LD_LIBRARY_PATH
   ```
   
   Add to `.bashrc` or `.bash_profile`:
   ```bash
   echo 'export LD_LIBRARY_PATH=/usr/lib/oracle/21/client64/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
   source ~/.bashrc
   ```

#### macOS

1. **Install Oracle Instant Client**
   ```bash
   brew install oracle-instantclient
   ```

2. **Set Environment Variables**
   ```bash
   export DYLD_LIBRARY_PATH=/usr/local/lib/oracle/instantclient_21_9:$DYLD_LIBRARY_PATH
   ```

### Configuration in Django

The code automatically initializes thick mode when `OracleDataSyncService` is instantiated:

```python
from diamond_web.utils.oracle_sync import OracleDataSyncService

# This will initialize thick mode automatically
service = OracleDataSyncService()
```

If initialization fails, check:
1. Oracle Client is installed
2. `ORACLE_CLIENT_HOME` is set correctly (Windows)
3. `LD_LIBRARY_PATH` is set correctly (Linux)

### Environment Variables Required

Set these in your `.env` file:

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

### Troubleshooting

#### Error: "Oracle Client is not found"
- Ensure Oracle Instant Client is installed
- Verify `ORACLE_CLIENT_HOME` or `LD_LIBRARY_PATH` is set correctly
- Restart your terminal/IDE after setting environment variables

#### Error: "cannot connect to database"
- Verify Oracle credentials and connection string
- Test with `sqlplus` or other Oracle client tools first
- Check firewall/network connectivity to Oracle server

#### Error: "DPY-3010" still occurring
- Make sure you've restarted your Python process/IDE
- Environment variables must be set BEFORE Python starts
- Try setting them programmatically as first import:
  ```python
  import os
  os.environ['ORACLE_CLIENT_HOME'] = r'C:\oracle\instantclient_21_9'
  import oracledb
  oracledb.init_oracle_client()
  ```

### Testing the Connection

```bash
cd diamond-web
python manage.py shell
```

Then in the Python shell:
```python
from diamond_web.utils.oracle_sync import OracleDataSyncService
service = OracleDataSyncService()
print("Oracle connection successful!")
```

### More Information

- [python-oracledb Documentation](https://python-oracledb.readthedocs.io/)
- [Oracle Instant Client Setup](https://www.oracle.com/database/technologies/instant-client/downloads.html)
- [Thick Mode Guide](https://python-oracledb.readthedocs.io/en/latest/user_guide/initialization.html#thick-mode)
