#!/bin/bash
# =============================================================================
# Daily Oracle Sync Cron Script
# Runs: referensi sync → tiket sync (sequential)
# Schedule: every day at 09:00 WIB (GMT+7)
# Logs: /home/pajak/diamond-web/sync_logs/
# =============================================================================
set -euo pipefail

# ---------- Configuration ----------
DJANGO_DIR="/home/pajak/diamond-web"
VENV_DIR="$DJANGO_DIR/venv"
LOG_DIR="$DJANGO_DIR/sync_logs"
ENV_FILE="$DJANGO_DIR/.env"
LOCK_FILE="/tmp/diamond_oracle_sync.lock"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/daily_sync_$TIMESTAMP.log"

# ---------- Prevent concurrent runs ----------
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$TIMESTAMP] ERROR: Sync already running (PID $LOCK_PID). Exiting." >> "$LOG_DIR/daily_sync_error.log"
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
log "INFO" "=== Daily Oracle sync dimulai ==="
log "INFO" "Log file: $LOG_FILE"

mkdir -p "$LOG_DIR"
cd "$DJANGO_DIR"

TOTAL_EXIT_CODE=0

# ===== STEP 1: Referensi Sync =====
log_step "STEP 1/2: Oracle Referensi Sync"

REFERENSI_LOG="$LOG_DIR/referensi_sync_$TIMESTAMP.log"
log "INFO" "Memulai referensi sync (log: $REFERENSI_LOG)..."

if python manage.py sync_oracle_data >> "$REFERENSI_LOG" 2>&1; then
    log "OK" "Referensi sync BERHASIL."
    # Extract summary from log
    tail -5 "$REFERENSI_LOG" | while IFS= read -r line; do
        log "INFO" "  $line"
    done
else
    REF_EXIT=$?
    log "ERROR" "Referensi sync GAGAL (exit code: $REF_EXIT)."
    log "ERROR" "Lihat detail: $REFERENSI_LOG"
    TOTAL_EXIT_CODE=$REF_EXIT
    # Don't exit — continue to tiket sync anyway
fi

# ===== STEP 2: Tiket Sync =====
log_step "STEP 2/2: Oracle Tiket Sync"

TIKET_LOG="$LOG_DIR/tiket_sync_$TIMESTAMP.log"
log "INFO" "Memulai tiket sync (log: $TIKET_LOG)..."

if python manage.py sync_tiket_data >> "$TIKET_LOG" 2>&1; then
    log "OK" "Tiket sync BERHASIL."
    tail -5 "$TIKET_LOG" | while IFS= read -r line; do
        log "INFO" "  $line"
    done
else
    TIK_EXIT=$?
    log "ERROR" "Tiket sync GAGAL (exit code: $TIK_EXIT)."
    log "ERROR" "Lihat detail: $TIKET_LOG"
    TOTAL_EXIT_CODE=$TIK_EXIT
fi

# ===== Summary =====
log_step "SUMMARY"

if [ "$TOTAL_EXIT_CODE" -eq 0 ]; then
    log "OK" "Daily Oracle sync SELESAI (all success)."
else
    log "WARN" "Daily Oracle sync SELESAI dengan error (exit code: $TOTAL_EXIT_CODE)."
fi

log "INFO" "Referensi log : $REFERENSI_LOG"
log "INFO" "Tiket log     : $TIKET_LOG"
log "INFO" "Master log    : $LOG_FILE"
log "INFO" "=== Daily Oracle sync selesai ==="

exit "$TOTAL_EXIT_CODE"
