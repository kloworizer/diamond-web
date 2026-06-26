#!/bin/bash
# =============================================================================
# Pre-Production Cleanup Script
# Membersihkan semua data testing sebelum go-live produksi:
#   1. Truncate semua BackupData, TandaTerimaData, DetilTandaTerima
#   2. Hapus TiketAction kecuali action=301 (PIC Ditambahkan)
#   3. Hapus semua tiket dengan old_db=False beserta relasinya
#
# Tujuan:
#   Menghapus seluruh data entry testing user, hanya menyisakan tiket
#   yang sudah disinkron/dimigrasi dari DB lama (old_db=True).
#
# Schedule: satu kali pada 1 Juli 2026 pukul 00:00 WIB (GMT+7)
#   via crontab: 0 0 1 7 * /home/pajak/diamond-web/scripts/cleanup_pre_production.sh
#
# Logs: /home/pajak/diamond-web/sync_logs/
# =============================================================================
set -euo pipefail

# ---------- Configuration ----------
DJANGO_DIR="/home/pajak/diamond-web"
VENV_DIR="$DJANGO_DIR/venv"
LOG_DIR="$DJANGO_DIR/sync_logs"
ENV_FILE="$DJANGO_DIR/.env"
LOCK_FILE="/tmp/diamond_cleanup_pre_production.lock"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="$LOG_DIR/cleanup_pre_production_$TIMESTAMP.log"

# ---------- Prevent concurrent runs ----------
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$TIMESTAMP] ERROR: Cleanup already running (PID $LOCK_PID). Exiting." >> "$LOG_DIR/cleanup_pre_production_error.log"
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

# ---------- Safety check: hanya jalan di tanggal yang benar ----------
# Mode dry-run (--dry-run) boleh jalan kapan saja untuk testing / simulasi
# Tanpa --dry-run, script hanya akan jalan pada TARGET_DATE untuk eksekusi nyata
DRY_RUN_MODE=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN_MODE=true
fi

TARGET_DATE="2026-07-01"
CURRENT_DATE=$(date '+%Y-%m-%d')

if [ "$CURRENT_DATE" != "$TARGET_DATE" ] && [ "$DRY_RUN_MODE" = false ]; then
    echo "[$TIMESTAMP] WARN: Script hanya boleh dijalankan pada $TARGET_DATE (saat ini: $CURRENT_DATE)." >> "$LOG_DIR/cleanup_pre_production_error.log"
    exit 0
fi

DRY_RUN_FLAG=""
if [ "$DRY_RUN_MODE" = true ]; then
    DRY_RUN_FLAG="--dry-run"
    log "INFO" "DRY-RUN MODE: tidak ada data yang benar-benar dihapus."
fi

# ---------- Start ----------
mkdir -p "$LOG_DIR"
cd "$DJANGO_DIR"

log "INFO" "=== Pre-Production Cleanup dimulai ==="
log "INFO" "Log file: $LOG_FILE"
log "INFO" "Target : bersihkan data testing (BackupData, TandaTerimaData, DetilTandaTerima, TiketAction) + hapus tiket old_db=False"

# ===== STEP 1: Dry-run untuk lihat estimasi =====
log_step "STEP 1/3: Dry-Run (estimasi data yang akan dihapus)"

DRYRUN_LOG="$LOG_DIR/cleanup_dryrun_$TIMESTAMP.log"
log "INFO" "Menjalankan dry-run..."

if python manage.py cleanup_pre_production --dry-run >> "$DRYRUN_LOG" 2>&1; then
    log "OK" "Dry-run selesai. Detail:"
    while IFS= read -r line; do
        log "INFO" "  $line"
    done < <(tail -20 "$DRYRUN_LOG")
else
    EXIT_CODE=$?
    log "ERROR" "Dry-run gagal (exit code: $EXIT_CODE)."
    log "ERROR" "Lihat detail: $DRYRUN_LOG"
    exit "$EXIT_CODE"
fi

# ===== STEP 2: Eksekusi penghapusan =====
log_step "STEP 2/3: Eksekusi Penghapusan"

CLEANUP_LOG="$LOG_DIR/cleanup_exec_$TIMESTAMP.log"
log "INFO" "Menjalankan penghapusan (log: $CLEANUP_LOG)..."

MANAGE_CMD="python manage.py cleanup_pre_production $DRY_RUN_FLAG"
if $MANAGE_CMD >> "$CLEANUP_LOG" 2>&1; then
    log "OK" "Penghapusan BERHASIL."
    while IFS= read -r line; do
        log "INFO" "  $line"
    done < <(tail -10 "$CLEANUP_LOG")
else
    EXIT_CODE=$?
    log "ERROR" "Penghapusan GAGAL (exit code: $EXIT_CODE)."
    log "ERROR" "Lihat detail: $CLEANUP_LOG"
    exit "$EXIT_CODE"
fi

# ===== STEP 3: Verifikasi =====
log_step "STEP 3/3: Verifikasi"

VERIF_LOG="$LOG_DIR/cleanup_verify_$TIMESTAMP.log"
log "INFO" "Memverifikasi tidak ada lagi tiket dengan old_db=False..."

if python manage.py cleanup_pre_production --dry-run >> "$VERIF_LOG" 2>&1; then
    VERIF_LINES=$(wc -l < "$VERIF_LOG")
    if grep -q "tidak ada tiket" "$VERIF_LOG"; then
        log "OK" "Verifikasi: TIDAK ada tiket dengan old_db=False — bersih."
    else
        log "WARN" "Verifikasi: Masih ada tiket dengan old_db=False. Cek log: $VERIF_LOG"
    fi
fi

# ===== Summary =====
log_step "SUMMARY"

MODE_MSG=""
if [ "$DRY_RUN_MODE" = true ]; then
    MODE_MSG=" (DRY-RUN — tidak ada data yang dihapus)"
fi

log "OK" "Pre-production cleanup SELESAI$MODE_MSG."
log "INFO" "Dry-run log    : $DRYRUN_LOG"
log "INFO" "Execute log    : $CLEANUP_LOG"
log "INFO" "Verify log     : $VERIF_LOG"
log "INFO" "Master log     : $LOG_FILE"
log "INFO" "=== Pre-Production Cleanup selesai$MODE_MSG ==="

exit 0
