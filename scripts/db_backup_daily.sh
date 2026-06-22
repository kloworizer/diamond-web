#!/bin/bash
# =============================================================================
# Daily Database Backup Cron Script
# Runs: django-dbbackup to create database and media backups
# Schedule: every day at 00:00 WIB (GMT+7)
# Logs: /home/pajak/diamond-web/backups/logs/
# Retention: keeps last 30 days of backups by default
# =============================================================================
set -euo pipefail

# ---------- Configuration ----------
DJANGO_DIR="/home/pajak/diamond-web"
VENV_DIR="$DJANGO_DIR/venv"
LOG_DIR="$DJANGO_DIR/backups/logs"
BACKUP_DIR="$DJANGO_DIR/backups"
ENV_FILE="$DJANGO_DIR/.env"
LOCK_FILE="/tmp/diamond_dbbackup.lock"

TIMESTAMP=$(date '+%Y%m%d-%H%M%S')
LOG_FILE="$LOG_DIR/db_backup_$TIMESTAMP.log"

# Retention: number of days to keep backups
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

# ---------- Ensure log and backup directories exist ----------
mkdir -p "$LOG_DIR" "$BACKUP_DIR"

# ---------- Prevent concurrent runs ----------
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$TIMESTAMP] ERROR: Backup already running (PID $LOCK_PID). Exiting." >> "$LOG_DIR/db_backup_error.log"
        exit 1
    else
        # Stale lock file
        rm -f "$LOCK_FILE"
    fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

# ---------- Environment setup ----------
export DJANGO_SETTINGS_MODULE=config.settings
export PYTHONPATH="${DJANGO_DIR}:${PYTHONPATH:-}"

# Source .env file (safely, ignoring comments and blank lines)
set -a
source "$ENV_FILE" 2>/dev/null || true
set +a

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# ---------- Helper functions ----------
log() {
    local level="$1"
    local msg="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $msg" | tee -a "$LOG_FILE"
}

log_step() {
    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "  $1" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
}

# ---------- Pre-flight checks ----------
log_step "PRE-FLIGHT CHECKS"

# Verify Django manage.py exists
if [ ! -f "$DJANGO_DIR/manage.py" ]; then
    log "ERROR" "manage.py not found at $DJANGO_DIR/manage.py"
    exit 1
fi

# Verify virtual environment exists
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    log "ERROR" "Virtual environment not found at $VENV_DIR"
    exit 1
fi

# Change to Django project directory
cd "$DJANGO_DIR"

log "INFO" "Backup directory : $BACKUP_DIR"
log "INFO" "Log file         : $LOG_FILE"
log "INFO" "Retention period : $RETENTION_DAYS days"

# ============================================================================
# STEP 1: Database Backup
# ============================================================================
log_step "STEP 1/2: Database Backup (dbbackup)"

DB_LOG="$LOG_DIR/dbbackup_$TIMESTAMP.log"
log "INFO" "Starting database backup (log: $DB_LOG)..."

if python manage.py dbbackup \
    --quiet \
    --compress \
    --database=default \
    >> "$DB_LOG" 2>&1; then
    log "OK" "Database backup BERHASIL."
    # Extract the backup filename from log
    tail -3 "$DB_LOG" | while IFS= read -r line; do
        log "INFO" "  $line"
    done
else
    DB_EXIT=$?
    log "ERROR" "Database backup GAGAL (exit code: $DB_EXIT)."
    log "ERROR" "Lihat detail: $DB_LOG"
    # Continue to media backup even if db fails
fi

# ============================================================================
# STEP 2: Media Backup (optional — uncomment if media files should be backed up)
# ============================================================================
log_step "STEP 2/2: Media Backup (mediabackup)"

MEDIA_LOG="$LOG_DIR/mediabackup_$TIMESTAMP.log"
log "INFO" "Starting media backup (log: $MEDIA_LOG)..."

if python manage.py mediabackup \
    --quiet \
    --compress \
    >> "$MEDIA_LOG" 2>&1; then
    log "OK" "Media backup BERHASIL."
    tail -3 "$MEDIA_LOG" | while IFS= read -r line; do
        log "INFO" "  $line"
    done
else
    MEDIA_EXIT=$?
    log "ERROR" "Media backup GAGAL (exit code: $MEDIA_EXIT)."
    log "ERROR" "Lihat detail: $MEDIA_LOG"
fi

# ============================================================================
# STEP 3: Cleanup old backups
# ============================================================================
log_step "STEP 3/3: Cleanup Old Backups (retention: $RETENTION_DAYS days)"

PURGED_COUNT=0
PURGED_SIZE=0

while IFS= read -r -d '' f; do
    if [ -f "$f" ]; then
        FILESIZE=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        rm -f "$f"
        PURGED_COUNT=$((PURGED_COUNT + 1))
        PURGED_SIZE=$((PURGED_SIZE + FILESIZE))
    fi
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.tar' -o -name '*.sqlite3' \) -mtime "+$RETENTION_DAYS" -print0 2>/dev/null || true)

if [ "$PURGED_COUNT" -gt 0 ]; then
    PURGED_SIZE_MB=$((PURGED_SIZE / 1048576))
    log "INFO" "Purged $PURGED_COUNT old backup file(s) (${PURGED_SIZE_MB}MB freed)."
else
    log "INFO" "No old backups to purge (retention: $RETENTION_DAYS days)."
fi

# ============================================================================
# Summary
# ============================================================================
log_step "SUMMARY"

BACKUP_COUNT=$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.dump' -o -name '*.tar' -o -name '*.sqlite3' \) -mtime "-1" 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1 || echo "unknown")

log "OK" "Daily database backup completed."
log "INFO" "Backup directory : $BACKUP_DIR"
log "INFO" "Total size       : $TOTAL_SIZE"
log "INFO" "Recent backups   : $BACKUP_COUNT in the last 24h"
log "INFO" "Master log       : $LOG_FILE"
log "INFO" "=== Daily Database Backup selesai ==="
