#!/bin/bash
# =============================================================================
# Tiket Update Cron Script
# Updates QC/transfer columns from Oracle and applies status transitions.
# Designed to run AFTER the main tiket sync (sync_tiket_data).
# Schedule: every day at 09:30 WIB (GMT+7) — 30 min after main sync
# Logs: /home/pajak/diamond-web/sync_logs/
# =============================================================================
set -euo pipefail

# ---------- Configuration ----------
DJANGO_DIR="/home/pajak/diamond-web"
VENV_DIR="$DJANGO_DIR/venv"
LOG_DIR="$DJANGO_DIR/sync_logs"
ENV_FILE="$DJANGO_DIR/.env"
LOCK_FILE="/tmp/diamond_tiket_update.lock"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/tiket_update_cron_$TIMESTAMP.log"

# ---------- Prevent concurrent runs ----------
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$TIMESTAMP] ERROR: Tiket update already running (PID $LOCK_PID). Exiting." >> "$LOG_DIR/tiket_update_error.log"
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

# ---------- Start ----------
log "INFO" "=== Tiket Update Sync dimulai ==="
log "INFO" "Log file: $LOG_FILE"

mkdir -p "$LOG_DIR"
cd "$DJANGO_DIR"

# ===== Tiket Update Sync =====
log_step "Oracle Tiket Update (QC & Status Transitions)"

log "INFO" "Memulai tiket update..."

if python manage.py sync_tiket_update >> "$LOG_FILE" 2>&1; then
    log "OK" "Tiket update BERHASIL."
    # Extract summary from log
    tail -5 "$LOG_FILE" | while IFS= read -r line; do
        log "INFO" "  $line"
    done
else
    EXIT_CODE=$?
    log "ERROR" "Tiket update GAGAL (exit code: $EXIT_CODE)."
    log "ERROR" "Lihat detail: $LOG_FILE"
    exit "$EXIT_CODE"
fi

# ===== Summary =====
log_step "SUMMARY"

log "OK" "Tiket update sync SELESAI."
log "INFO" "Log file: $LOG_FILE"
log "INFO" "=== Tiket Update Sync selesai ==="
