from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
from django.urls import reverse
from datetime import datetime, timedelta
import uuid
import json
import logging
import signal
import time
import re
from functools import wraps
import os
import csv

from ..models import Tiket, BentukData, CaraPenyampaian, PeriodeJenisData, JenisPrioritasData, StatusPenelitian, PIC, TiketPIC, TiketAction
from ..constants.tiket_action_types import PICActionType
from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ..tasks import sync_tiket_data_task, check_tiket_data_task

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
SYNC_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync_logs')
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)

# Single shared Oracle query used by both _check_tiket_data and _sync_tiket_data.
_TIKET_ORACLE_SQL = """
    SELECT
    DISTINCT
    CASE 
        WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E' THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
        ELSE id_tiket 
    END id_tiket,
    1 old_db,
    CASE
        -- 1. Check if the ticket is already 'Selesai' (Status 8)
        WHEN status_tiket IN ('[SELESAI]-Sudah QC', '[SELESAI]-Tidak di QC', '[SELESAI]-Tiket 0 Row') THEN 8
        -- 2. Override to 7 ONLY if it falls into the 'Tidak Lengkap' criteria
        WHEN NOT (COALESCE(JML_ROW_P3DE, 0) = COALESCE(JML_DATA_TELITI, 0) AND COALESCE(JML_DATA_TELITI, 0) <> 0) -- Not Lengkap
         AND NOT (COALESCE(JML_ROW_P3DE, 0) > COALESCE(JML_DATA_TELITI, 0) AND COALESCE(JML_DATA_TELITI, 0) <> 0) -- Not Lengkap Sebagian
         AND JML_DATA_TELITI IS NOT NULL
        THEN 7
        -- 3. Otherwise, fall back to standard status mappings (Lengkap & Lengkap Sebagian end up here)
        WHEN status_tiket IN ('[P3DE]-Close Tiket', '[PIDE]-Close Tiket') THEN 7
        WHEN status_tiket IN ('[PMDE]-Proses QC') THEN 6
        WHEN status_tiket IN ('[PIDE]-Proses Identifikasi') AND c.tgl_tiket IS NOT NULL THEN 5
        WHEN status_tiket IN ('[PIDE]-Proses Identifikasi') AND c.tgl_tiket IS NULL THEN 4
        WHEN status_tiket IN ('[P3DE]-Proses Nadine') THEN 2
        WHEN status_tiket IN ('[P3DE]-Proses Penelitian') THEN 1
        ELSE 1
    END status_tiket,
    CASE 
        WHEN PERIODE_PENGIRIMAN IS NULL AND periode_data LIKE '%ahun' THEN 'Tahunan' 
        WHEN PERIODE_PENGIRIMAN IS NULL AND periode_data NOT LIKE '%ahun' THEN 'Bulanan'
        ELSE PERIODE_PENGIRIMAN
    END periode_penerimaan,
    SUBSTR(id_tiket, 1, 9) || '_20' || SUBSTR(id_tiket, 10, 2) jenis_prioritas_data,
    COALESCE(periode_data, 'Tahun') periode_data,
    COALESCE(tahun_data, 2099) tahun_data,
    ROW_NUMBER() OVER (
        PARTITION BY
            CASE
                WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E' THEN SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2)
                ELSE id_tiket
            END,
            COALESCE(periode_data, 'Tahun'),
            COALESCE(tahun_data, 2099)
        ORDER BY TGL_TERIMA ASC
    ) penyampaian,
    COALESCE(NO_SURATPENGANTAR, '-') nomor_surat_pengantar,
    COALESCE(
        TGL_SURATPENGANTAR,
        TGL_TERIMA,
        CASE
            WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E'
             AND SUBSTR(id_tiket, 12, 2) BETWEEN '01' AND '12'
             AND SUBSTR(id_tiket, 14, 2) BETWEEN '01' AND '31'
            THEN TO_DATE(SUBSTR(SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2), 11, 6), 'YYMMDD')
            WHEN SUBSTR(id_tiket, 12, 2) BETWEEN '01' AND '12'
             AND SUBSTR(id_tiket, 14, 2) BETWEEN '01' AND '31'
            THEN TO_DATE(SUBSTR(id_tiket, 10, 6), 'YYMMDD')
        END
    ) tanggal_surat_pengantar,
    COALESCE(nama_pengirim, '-') nama_pengirim,
    BENTUK_DATA,
    CARA_PENYAMPAIAN,
    CASE
        WHEN status_tiket IN ('[SELESAI]-Tiket 0 Row') THEN 0
        ELSE 1
    END status_ketersediaan_data,
    NULL alasan_ketidaktersediaan,
    COALESCE(JML_ROW_P3DE, 0) baris_diterima,
    1 satuan_data,
    NULL tgl_terima_vertikal,
    COALESCE(
        TGL_TERIMA,
        CASE
            WHEN LENGTH(id_tiket) = 16 AND SUBSTR(id_tiket,1,1) = 'E'
             AND SUBSTR(id_tiket, 12, 2) BETWEEN '01' AND '12'
             AND SUBSTR(id_tiket, 14, 2) BETWEEN '01' AND '31'
            THEN TO_DATE(SUBSTR(SUBSTR(id_tiket, 1, 1) || 'I' || SUBSTR(id_tiket, 2), 11, 6), 'YYMMDD')
            WHEN SUBSTR(id_tiket, 12, 2) BETWEEN '01' AND '12'
             AND SUBSTR(id_tiket, 14, 2) BETWEEN '01' AND '31'
            THEN TO_DATE(SUBSTR(id_tiket, 10, 6), 'YYMMDD')
        END
    ) tgl_terima_dip,
    0 backup,
    0 tanda_terima,
    CASE
        WHEN COALESCE(JML_ROW_P3DE, 0) = COALESCE(JML_DATA_TELITI, 0) AND COALESCE(JML_DATA_TELITI, 0) <> 0 THEN 'Lengkap'
        WHEN COALESCE(JML_ROW_P3DE, 0) > COALESCE(JML_DATA_TELITI, 0) AND COALESCE(JML_DATA_TELITI, 0) <> 0 THEN 'Lengkap Sebagian'
        ELSE 'Tidak Lengkap'
    END status_penelitian,
    TGL_TELITI,
    COALESCE(JML_DATA_TELITI, 0) baris_lengkap,
    COALESCE(JML_ROW_P3DE, 0) - COALESCE(JML_DATA_TELITI, 0) baris_tidak_lengkap,
    TGL_NADINE,
    NO_NADINE,
    TGL_NADINE tgl_kirim_pide,
    c.tgl_tiket tgl_rekam_pide,
    NULL id_durasi_jatuh_tempo_pide,
    COALESCE(b.JML_LOG, 0) baris_i,
    COALESCE(b.JML_LOG_U, 0) baris_u,
    COALESCE(b.JML_RES, 0) baris_res,
    COALESCE(b.JML_CDE, 0) baris_cde,
    b.tgl_transfer,
    b.TGL_REMATCH tgl_rematch,
    NULL id_durasi_jatuh_tempo_pmde,
    COALESCE(b.SUDAH_QC, 0) SUDAH_QC,
    COALESCE(b.belum_qc, 0) belum_qc,
    COALESCE(b.lolos_qc, 0) lolos_qc,
    COALESCE(b.TIDAK_LOLOS_QC, 0) tidak_lolos_qc,
    COALESCE(b.QC_P, 0) QC_P,
    COALESCE(b.QC_X, 0) QC_X,
    COALESCE(b.QC_W, 0) QC_W,
    COALESCE(b.QC_F, 0) QC_F,
    COALESCE(b.QC_A, 0) QC_A,
    COALESCE(b.QC_C, 0) QC_C,
    COALESCE(b.QC_N, 0) QC_N,
    COALESCE(b.QC_Y, 0) QC_Y,
    COALESCE(b.QC_Z, 0) QC_Z,
    COALESCE(b.QC_U, 0) QC_U,
    COALESCE(b.QC_E, 0) QC_E,
    COALESCE(b.QC_V, 0) QC_V,
    COALESCE(b.QC_R, 0) QC_R,
    COALESCE(b.QC_D, 0) QC_D,
    c.tgl_tiket
    FROM
        PVPTD.ZA_DDE_TABEL_FACT a
    LEFT JOIN (
        SELECT
            no_tiket,
            MIN(tgl_transfer) tgl_transfer,
            MAX(tgl_rematch) tgl_rematch,
            SUM(JML_LOG) JML_LOG,
            SUM(JML_LOG_U) JML_LOG_U,
            SUM(JML_RES) JML_RES,
            SUM(JML_CDE) JML_CDE,
            SUM(SUDAH_QC) SUDAH_QC,
            SUM(belum_qc) belum_qc,
            SUM(lolos_qc) lolos_qc,
            SUM(TIDAK_LOLOS_QC) TIDAK_LOLOS_QC,
            SUM(QC_P) QC_P,
            SUM(QC_X) QC_X,
            SUM(QC_W) QC_W,
            SUM(QC_F) QC_F,
            SUM(QC_A) QC_A,
            SUM(QC_C) QC_C,
            SUM(QC_N) QC_N,
            SUM(QC_Y) QC_Y,
            SUM(QC_Z) QC_Z,
            SUM(QC_U) QC_U,
            SUM(QC_E) QC_E,
            SUM(QC_V) QC_V,
            SUM(QC_R) QC_R,
            SUM(QC_D) QC_D
        FROM
            PVPTD.ZA_REKAP_TARIKAN
        GROUP BY
            no_tiket
    ) b ON a.ID_TIKET = b.NO_TIKET
    LEFT JOIN 
    (select no_tiket, tgl_tiket from pvptd.za_rekap_tiket) c ON a.ID_TIKET = c.NO_TIKET
    LEFT JOIN 
    (SELECT ID_TIKET ID_TIKET_D, NO_SURATPENGANTAR, TGL_SURATPENGANTAR, NAMA_PENGIRIM, BENTUK_DATA, CARA_PENYAMPAIAN FROM PROD.APP_PENERIMAANBACKUP) d
    ON a.ID_TIKET = d.ID_TIKET_D
"""


def retry_on_db_lock(max_retries=5, initial_delay=0.1, backoff_factor=2.0):
    """Decorator to retry database operations on lock with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts before giving up.
            Defaults to 5.
        initial_delay: Initial delay in seconds before the first retry.
            Defaults to 0.1.
        backoff_factor: Multiplier applied to the delay after each retry.
            Defaults to 2.0.

    Returns:
        A decorator that wraps the target function with retry logic.

    Side Effects:
        Logs debug messages on each retry attempt and a warning when
        all retries are exhausted.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check for database lock errors
                    if 'database is locked' in error_msg or 'locked' in error_msg:
                        last_exception = e
                        if attempt < max_retries - 1:
                            logger.debug(f"DB lock on {func.__name__} (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s...")
                            time.sleep(delay)
                            delay *= backoff_factor
                        else:
                            logger.warning(f"DB lock on {func.__name__} after {max_retries} attempts")
                    else:
                        # Non-lock error, raise immediately
                        raise
            
            # If we exhausted retries due to lock, raise the last exception
            if last_exception:
                raise last_exception
            return None
        return wrapper
    return decorator


logger = logging.getLogger(__name__)


def _is_admin_user(user):
    """Check if the given user is an admin user.

    Args:
        user: The Django User instance to check.

    Returns:
        True if the user is authenticated and is either a superuser
        or belongs to the 'admin' group. False otherwise.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


class SyncTimeoutError(Exception):
    """Custom exception raised when a sync operation exceeds the timeout limit."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for sync timeout.

    Args:
        signum: The signal number received.
        frame: The current stack frame at the time of the signal.

    Raises:
        SyncTimeoutError: Always raised to indicate the sync has timed out
            (more than 5 minutes).
    """
    raise SyncTimeoutError('Sinkronisasi timeout (> 5 menit)')


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def sync_tiket_page(request):
    """Render the Oracle tiket sync page.

    Args:
        request: The incoming HTTP request.

    Returns:
        HttpResponse with the rendered 'oracle_sync/tiket.html' template.
    """
    return render(request, 'oracle_sync/tiket.html')


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def sync_tiket_test_connection(request):
    """Test Oracle database connections (primary and optional secondary).

    Args:
        request: The incoming HTTP request (must be POST).

    Returns:
        JsonResponse with success status and connection status messages
        for both primary and secondary Oracle connections.

    Raises:
        400: If Oracle configuration is invalid (OracleSyncConfigError).
        500: If connection to Oracle server fails unexpectedly.
    """
    try:
        service = OracleDataSyncService()
        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")

        secondary = service.oracle_connections.get("secondary")
        secondary_configured = bool(
            secondary
            and secondary.user
            and secondary.password
            and secondary.host
            and (secondary.service_name or secondary.sid)
        )

        secondary_message = "Secondary tidak dikonfigurasi."
        if secondary_configured:
            with service._connect_oracle("secondary") as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
            secondary_message = "Koneksi secondary berhasil."

        return JsonResponse({
            'success': True,
            'message': 'Koneksi Oracle berhasil.',
            'connections': {
                'primary': 'Koneksi primary berhasil.',
                'secondary': secondary_message,
            }
        })
    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal koneksi ke Oracle server. Periksa konfigurasi dan konektivitas network.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_check(request):
    """Start a tiket data check operation (dry-run comparing Oracle vs local DB).

    Dispatches a Celery task to compare Oracle tiket data with the local
    database without making any changes. Progress can be polled via
    sync_tiket_progress with mode='check'.

    Args:
        request: The incoming HTTP request (must be POST).

    Returns:
        JsonResponse with a unique check_id for progress tracking and
        a message indicating the check has started.

    Raises:
        400: If Oracle configuration is invalid.
        500: If an unexpected error occurs during dispatch.
    """
    try:
        check_id = str(uuid.uuid4())
        cache.set(f'check_tiket_done_{check_id}', False, timeout=3600)
        cache.set(f'check_tiket_in_progress_{check_id}', True, timeout=3600)

        logger.info(f'Dispatching tiket check task (check_id={check_id})...')
        task_result = check_tiket_data_task.delay(check_id)
        cache.set(f'check_tiket_celery_task_id_{check_id}', task_result.id, timeout=3600)

        return JsonResponse({
            'success': True,
            'mode': 'check',
            'check_id': check_id,
            'message': 'Check dimulai. Silakan tunggu...',
        })
    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        logger.error(f'OracleSyncConfigError in check: {error_msg}')
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in check: {error_msg}', exc_info=True)
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan check data tiket. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


def _sync_tiket_data_background(sync_id, request_user=None):
    """Deprecated: kept as a thin shim; use sync_tiket_data_task instead."""
    user_id = getattr(request_user, 'pk', None)
    sync_tiket_data_task.delay(sync_id, user_id)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_run(request):
    """Start a full tiket sync operation from Oracle to local database.

    Dispatches a Celery task to synchronise all tiket data from Oracle
    into the local database, performing inserts for new records and
    updates for existing ones. Progress can be polled via
    sync_tiket_progress with mode='sync'.

    Args:
        request: The incoming HTTP request (must be POST).

    Returns:
        JsonResponse with a unique sync_id for progress tracking and
        a message indicating the sync has started.

    Raises:
        400: If Oracle configuration is invalid.
        500: If an unexpected error occurs during dispatch.
    """
    try:
        # Generate unique sync ID for tracking progress and stop signals
        sync_id = str(uuid.uuid4())
        cache.set(f'sync_tiket_stop_{sync_id}', False, timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', False, timeout=3600)
        cache.set(f'sync_tiket_in_progress_{sync_id}', True, timeout=3600)

        logger.info(f'Starting tiket sync (sync_id={sync_id})...')

        task_result = sync_tiket_data_task.delay(sync_id, request.user.pk)
        cache.set(f'sync_tiket_celery_task_id_{sync_id}', task_result.id, timeout=3600)

        logger.info(f'Celery sync task dispatched (sync_id={sync_id})')

        # Return immediately with sync_id so client can start polling
        return JsonResponse({
            'success': True,
            'mode': 'sync',
            'sync_id': sync_id,
            'message': 'Sync dimulai. Silakan tunggu...',
        })

    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        logger.error(f'OracleSyncConfigError in sync: {error_msg}')
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in sync: {error_msg}', exc_info=True)
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan sync tiket. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_POST
@never_cache
def sync_tiket_stop(request):
    """Stop an in-progress sync operation (no auth check to avoid session locks).

    Revokes the associated Celery task and sets cache flags to signal
    the sync runner to stop. No authentication check is performed to
    avoid session lock contention.

    Args:
        request: The incoming HTTP request with JSON body containing
            'sync_id'.

    Returns:
        JsonResponse indicating success or failure of the stop request.

    Side Effects:
        Revokes the Celery task (SIGTERM) and sets cache stop signals.
    """
    try:
        data = json.loads(request.body)
        sync_id = data.get('sync_id')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)

        # Revoke and terminate the Celery task if we have its task ID
        celery_task_id = cache.get(f'sync_tiket_celery_task_id_{sync_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for sync {sync_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')

        cache.set(f'sync_tiket_stop_{sync_id}', True, timeout=3600)
        cache.set(f'sync_tiket_error_{sync_id}', 'Sync dihentikan oleh pengguna', timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', True, timeout=3600)

        request.session.modified = False
        return JsonResponse({'success': True, 'message': 'Sync dihentikan.'})
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_GET
@never_cache
def sync_tiket_progress(request):
    """Get current progress of an in-progress check or sync operation.

    No authentication check is performed to avoid session lock contention.
    Supports two modes: 'check' (dry-run comparison) and 'sync' (data sync).
    Returns progress data including current/total rows, percentage, inserts,
    updates, and errors.

    Args:
        request: The incoming HTTP request. Expects 'mode' (default 'sync')
            and either 'check_id' or 'sync_id' query parameters.

    Returns:
        JsonResponse with success status, done flag, progress data,
        and optionally a summary result when the operation is complete.
        Includes an error_log_url if a CSV error log file exists.

    Side Effects:
        Sets request.session.modified = False to avoid unnecessary
        session saves during polling.
    """
    try:
        mode = request.GET.get('mode', 'sync')
        request.session.modified = False

        if mode == 'check':
            check_id = request.GET.get('check_id')
            if not check_id:
                return JsonResponse({'success': False, 'message': 'check_id required'}, status=400)
            try:
                uuid.UUID(check_id)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'invalid check_id'}, status=400)

            is_done = cache.get(f'check_tiket_done_{check_id}')   # None = key absent
            is_in_progress = cache.get(f'check_tiket_in_progress_{check_id}')  # None = key absent
            progress_data = cache.get(f'check_tiket_progress_{check_id}') or {
                'current': 0, 'total': 0, 'percentage': 0,
                'inserts': 0, 'updates': 0, 'errors': 0,
            }

            # Both keys absent → session expired or never started → tell browser to clear up
            if is_done is None and is_in_progress is None:
                return JsonResponse({'success': False, 'done': True, 'progress': progress_data,
                                     'message': 'Session check kadaluarsa atau tidak ditemukan.'})

            if is_done:
                result = cache.get(f'check_tiket_result_{check_id}')
                error = cache.get(f'check_tiket_error_{check_id}')
                if error:
                    return JsonResponse({'success': False, 'done': True, 'progress': progress_data, 'message': error})
                if result:
                    return JsonResponse({
                        'success': True, 'done': True,
                        'progress': progress_data, 'summary': result,
                        'message': f"Check selesai: {result.get('inserts', 0)} akan insert, {result.get('updates', 0)} akan update",
                    })
                # Done but no result yet (race), treat as still running
                return JsonResponse({'success': True, 'done': False, 'progress': progress_data})

            return JsonResponse({'success': True, 'done': False, 'progress': progress_data})

        # Default: mode=sync
        sync_id = request.GET.get('sync_id')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id required'}, status=400)
        
        # Validate sync_id format (UUID)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)
        
        # Check if sync is done
        is_done = cache.get(f'sync_tiket_done_{sync_id}')          # None = key absent
        is_in_progress = cache.get(f'sync_tiket_in_progress_{sync_id}')  # None = key absent

        # Both keys absent → session expired → tell browser to clean up
        if is_done is None and is_in_progress is None:
            return JsonResponse({'success': False, 'done': True,
                                 'progress': {'current': 0, 'total': 0, 'percentage': 0,
                                              'inserts': 0, 'updates': 0, 'errors': 0},
                                 'message': 'Session sync kadaluarsa atau tidak ditemukan.'})

        # Get progress data
        progress_data = cache.get(f'sync_tiket_progress_{sync_id}')
        if progress_data is None:
            progress_data = {
                'current': 0,
                'total': 0,
                'percentage': 0,
                'inserts': 0,
                'updates': 0,
                'errors': 0,
            }
        
        # If done, check for result or error
        if is_done:
            result = cache.get(f'sync_tiket_result_{sync_id}')
            error = cache.get(f'sync_tiket_error_{sync_id}')
            
            if error:
                return JsonResponse({
                    'success': False,
                    'done': True,
                    'progress': progress_data,
                    'message': error,
                })
            
            if result:
                response_data = {
                    'success': True,
                    'done': True,
                    'progress': progress_data,
                    'summary': result,
                    'message': f"Sync selesai: {result.get('inserts', 0)} insert, {result.get('updates', 0)} update, {len(result.get('errors', []))} error",
                }
                # Add error log download URL if CSV exists
                error_log_path = os.path.join(SYNC_LOGS_DIR, f'sync_failed_rows_{sync_id}.csv')
                if os.path.exists(error_log_path):
                    response_data['error_log_url'] = reverse('sync_tiket_download_errors', kwargs={'sync_id': sync_id})
                return JsonResponse(response_data)
        
        return JsonResponse({
            'success': True,
            'done': False,
            'progress': progress_data,
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Exception in progress endpoint: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg}, status=500)



@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_truncate(request):
    """Delete all tiket records and reset the primary key sequence.

    Removes all dependent records (DetilTandaTerima, BackupData,
    TiketAction, TiketPIC) before deleting all Tiket rows. Resets
    the auto-increment sequence in a database-agnostic way.

    Args:
        request: The incoming HTTP request (must be POST).

    Returns:
        JsonResponse with the number of deleted rows and a success
        message, or an error message on failure.

    Side Effects:
        Deletes all rows from DetilTandaTerima, BackupData, TiketAction,
        TiketPIC, and Tiket tables. Resets the primary key sequence.
    """
    try:
        from django.db import connection
        
        # Delete all dependent records in correct order before Tiket (all have PROTECT FK)
        from ..models import TiketPIC, TiketAction
        from ..models.backup_data import BackupData
        from ..models.detil_tanda_terima import DetilTandaTerima
        DetilTandaTerima.objects.all().delete()
        BackupData.objects.all().delete()
        TiketAction.objects.all().delete()
        TiketPIC.objects.all().delete()
        
        count = Tiket.objects.all().count()
        Tiket.objects.all().delete()
        
        # Reset auto-increment (database-agnostic)
        db_vendor = connection.vendor  # 'sqlite', 'postgresql', 'mysql'
        with connection.cursor() as cursor:
            if db_vendor == 'sqlite':
                cursor.execute('DELETE FROM sqlite_sequence WHERE name="tiket"')
            elif db_vendor == 'postgresql':
                # PostgreSQL uses sequences
                cursor.execute("SELECT setval('tiket_id_seq', 1)")
            elif db_vendor == 'mysql':
                # MySQL auto-increment is reset by TRUNCATE, already done by delete
                pass
        
        return JsonResponse({
            'success': True,
            'message': f'Tabel tiket berhasil dihapus ({count} baris) dan primary key direset.',
            'deleted_count': count,
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg:
            error_msg = 'Gagal menghapus tabel tiket'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


def _log_failed_row(sync_id, nomor_tiket, periode_str, jenis_prioritas_str, tahun_data, error_msg, row_number=None):
    """Log a failed row to a CSV file for review and debugging.

    Creates or appends to a CSV file named 'sync_failed_rows_{sync_id}.csv'
    in the sync_logs directory. Each row contains timestamp, row number,
    ticket identifier, metadata, and the error reason.

    Args:
        sync_id: Unique identifier for the sync run.
        nomor_tiket: The ticket number that failed.
        periode_str: The period string from Oracle data.
        jenis_prioritas_str: The jenis prioritas string from Oracle data.
        tahun_data: The year data from Oracle.
        error_msg: Description of the error that occurred.
        row_number: Optional 1-based row number in the source data.

    Side Effects:
        Writes a row to a CSV log file on disk.
    """
    try:
        # Create CSV log file for this sync run
        log_filename = os.path.join(SYNC_LOGS_DIR, f'sync_failed_rows_{sync_id}.csv')
        
        # Write header if file doesn't exist
        file_exists = os.path.exists(log_filename)
        
        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header on first row
            if not file_exists:
                writer.writerow([
                    'Timestamp',
                    'Row Number',
                    'Nomor Tiket',
                    'Jenis Prioritas',
                    'Tahun',
                    'Periode',
                    'Error Reason'
                ])
            
            # Write failed row data
            writer.writerow([
                timezone.now().isoformat(),
                row_number or '-',
                nomor_tiket or '-',
                jenis_prioritas_str or '-',
                tahun_data or '-',
                periode_str or '-',
                error_msg or 'Unknown error'
            ])
        
        logger.debug(f"Failed row logged to {log_filename}")
    except Exception as e:
        logger.error(f"Failed to log error row: {str(e)}")


@require_GET
@never_cache
def sync_tiket_download_errors(request, sync_id):
    """Download the error log CSV file for a completed tiket sync.

    Args:
        request: The incoming HTTP request.
        sync_id: The UUID of the sync run to download errors for.

    Returns:
        FileResponse with the CSV file content, or JsonResponse with
        404 if the file does not exist, or 400 if sync_id is invalid.
    """
    try:
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid sync_id format'}, status=400)
        
        error_log_path = os.path.join(SYNC_LOGS_DIR, f'sync_failed_rows_{sync_id}.csv')
        
        if not os.path.exists(error_log_path):
            return JsonResponse({'success': False, 'message': 'Error log file not found'}, status=404)
        
        response = FileResponse(open(error_log_path, 'rb'), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sync_tiket_errors_{sync_id}.csv"'
        return response
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Error downloading tiket sync log: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal download error log'}, status=500)


@require_POST
@never_cache
def sync_tiket_stop_check(request):
    """Stop an in-progress tiket check (dry-run) operation.

    Revokes the associated Celery task and sets cache flags to signal
    the check runner to stop. No authentication check is performed to
    avoid session lock contention.

    Args:
        request: The incoming HTTP request with JSON body containing
            'check_id'.

    Returns:
        JsonResponse indicating success or failure of the stop request.

    Side Effects:
        Revokes the Celery task (SIGTERM) and sets cache stop signals.
    """
    try:
        data = json.loads(request.body)
        check_id = data.get('check_id', '')
        if not check_id:
            return JsonResponse({'success': False, 'message': 'check_id tidak ditemukan'}, status=400)
        try:
            uuid.UUID(check_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid check_id'}, status=400)
        
        # Revoke and terminate the Celery task if we have its task ID
        celery_task_id = cache.get(f'check_tiket_celery_task_id_{check_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for check {check_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')
        
        cache.set(f'check_tiket_stop_requested_{check_id}', True, timeout=3600)
        cache.set(f'check_tiket_error_{check_id}', 'Cek Data dihentikan oleh pengguna', timeout=3600)
        cache.set(f'check_tiket_done_{check_id}', True, timeout=3600)
        
        request.session.modified = False
        return JsonResponse({'success': True, 'message': 'Permintaan stop cek data telah dikirim.'})
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal menghentikan cek data'}, status=500)


def _make_aware_datetime(dt):
    """Return a datetime safe for DB storage respecting USE_TZ setting.
    
    When USE_TZ=True: make naive datetimes timezone-aware.
    When USE_TZ=False: ensure datetimes are naive (strip tz if present).
    Returns None if dt is None.
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        from django.conf import settings
        if settings.USE_TZ:
            if timezone.is_naive(dt):
                return timezone.make_aware(dt)
            return dt
        else:
            # USE_TZ=False: must be naive for SQLite compatibility
            if timezone.is_aware(dt):
                return dt.replace(tzinfo=None)
            return dt
    return dt


def _ensure_naive_datetimes(data: dict) -> dict:
    """Return a copy of *data* with all datetime values coerced to timezone-naive.
    
    Safe no-op when USE_TZ=True or when no datetime values are aware.
    Use as a last line of defence before model construction / DB writes.
    """
    from django.conf import settings
    if settings.USE_TZ:
        return data
    out = dict(data)
    for k, v in out.items():
        if isinstance(v, datetime) and timezone.is_aware(v):
            out[k] = v.replace(tzinfo=None)
    return out


def _assign_tiket_pics_sync(tiket, periode_jenis_data, today, base_time, request, batch_size=100):
    """Assign all active P3DE, PIDE, PMDE PICs to a synced tiket from the PIC table only.
    
    Only adds PICs that are already configured in the PIC table for this sub_jenis_data_ilap.
    Does NOT automatically add the current user.
    Uses bulk_create for efficiency.
    """
    try:
        if not periode_jenis_data:
            return
        
        from django.contrib.auth.models import User
        admin_user = User.objects.get(username='admin')
        
        # Collect PICs and actions to bulk create
        tiket_pics_to_create = []
        tiket_actions_to_create = []
        
        # Add all active P3DE, PIDE, PMDE PICs from PIC table
        active_filter = Q(start_date__lte=today) & Q(end_date__isnull=True)
        action_idx = 1
        for role_value, tipe in (
            (TiketPIC.Role.P3DE, PIC.TipePIC.P3DE),
            (TiketPIC.Role.PIDE, PIC.TipePIC.PIDE),
            (TiketPIC.Role.PMDE, PIC.TipePIC.PMDE),
        ):
            pic_qs = PIC.objects.filter(
                tipe=tipe,
                id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap
            )
            tipe_label = dict(PIC.TipePIC.choices).get(tipe, tipe)
            for pic in pic_qs.filter(active_filter):
                tiket_pics_to_create.append(
                    TiketPIC(
                        id_tiket=tiket,
                        id_user=pic.id_user,
                        timestamp=timezone.now(),
                        role=role_value,
                        active=True,
                    )
                )
                tiket_actions_to_create.append(
                    TiketAction(
                        id_tiket=tiket,
                        id_user=admin_user,
                        timestamp=base_time + timedelta(microseconds=1 + action_idx),
                        action=PICActionType.DITAMBAHKAN,
                        catatan=f'{tipe_label} {pic.id_user.username} ditambahkan'
                    )
                )
                action_idx += 1
        
        # Bulk create all PICs and actions
        if tiket_pics_to_create:
            TiketPIC.objects.bulk_create(tiket_pics_to_create, batch_size=batch_size, ignore_conflicts=False)
        if tiket_actions_to_create:
            TiketAction.objects.bulk_create(tiket_actions_to_create, batch_size=batch_size, ignore_conflicts=False)
    except Exception:
        # Silently skip PIC assignment if it fails (don't block sync)
        pass


def _safe_int(value, default=None):
    """Safely convert a value to int, returning a default on failure.

    Args:
        value: The value to convert (can be None, string, or numeric).
        default: Value to return if conversion fails. Defaults to None.

    Returns:
        The integer value if conversion succeeds, otherwise the default.
    """
    try:
        if value is None or value == '':
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_jenis_prioritas_data(jenis_prioritas_str, tahun_override=None):
    """
    Parse jenis_prioritas_data from Oracle format: 'PD2717901_2026'
    Extract id_sub_jenis_data and tahun, then lookup in JenisPrioritasData.
    Returns (JenisPrioritasData object or None, tahun_value)
    """
    if not jenis_prioritas_str:
        return None, None
    
    try:
        parts = jenis_prioritas_str.split('_')
        if len(parts) != 2:
            return None, None
        
        id_sub_jenis = parts[0]  # e.g., 'PD2717901'
        tahun_from_key = parts[1]  # e.g., '2026'
        lookup_tahun = str(tahun_override) if tahun_override is not None else tahun_from_key
        
        jenis_prioritas = JenisPrioritasData.objects.filter(
            id_sub_jenis_data_ilap__id_sub_jenis_data=id_sub_jenis,
            tahun=lookup_tahun
        ).first()

        # Fallback to key-derived year when override year has no master mapping.
        if not jenis_prioritas and lookup_tahun != tahun_from_key:
            jenis_prioritas = JenisPrioritasData.objects.filter(
                id_sub_jenis_data_ilap__id_sub_jenis_data=id_sub_jenis,
                tahun=tahun_from_key
            ).first()
        
        return jenis_prioritas, _safe_int(tahun_from_key)
    except Exception:
        return None, None


def _build_periode_lookup_cache():
    """Build a lookup cache mapping id_sub_jenis_data to PeriodeJenisData.

    Iterates over all PeriodeJenisData rows ordered by id and keeps
    only the first row for each unique id_sub_jenis_data. This cache
    is used by _map_periode_data to avoid per-row database queries.

    Returns:
        dict[str, PeriodeJenisData]: A mapping from id_sub_jenis_data
        string to the first matching PeriodeJenisData instance.
    """
    cache_by_sub_jenis: dict[str, PeriodeJenisData] = {}

    for pjd in PeriodeJenisData.objects.select_related('id_sub_jenis_data_ilap').all().order_by('id'):
        sub_jenis = getattr(pjd.id_sub_jenis_data_ilap, 'id_sub_jenis_data', None)
        if sub_jenis and sub_jenis not in cache_by_sub_jenis:
            cache_by_sub_jenis[sub_jenis] = pjd

    return cache_by_sub_jenis


def _map_periode_data(
    periode_str,
    jenis_prioritas_obj=None,
    tahun_value=None,
    nomor_tiket=None,
    periode_lookup_cache=None,
):
    """
    Map Oracle periode_data values to (PeriodeJenisData, periode_value).

    The PeriodeJenisData (id_periode_data FK on Tiket) is resolved purely from
    the first 9 characters of nomor_tiket, which encode id_sub_jenis_data.
    The numeric periode_value is derived from the Oracle periode_str string and
    stored directly in tiket.periode; tahun comes from the Oracle tahun_data
    column and is stored directly in tiket.tahun.

        Lookup rule for PeriodeJenisData:
            - nomor_tiket[:9] must match `JenisDataILAP.id_sub_jenis_data`
            - use the first `PeriodeJenisData` for that `JenisDataILAP`
            - no fallback to other keys or period types

    Returns: tuple(PeriodeJenisData | None, periode_value int)
    """
    if not periode_str:
        return None, 1

    periode_str = periode_str.strip()
    periode_lower = periode_str.lower()

    # --- Validate triwulan / semester values ---
    if 'triwulan' in periode_lower:
        if not any(f'triwulan {tw}' in periode_lower for tw in ['i', 'ii', 'iii', 'iv']):
            logger.warning(f"Invalid triwulan value: '{periode_str}', skipping")
            return None, 1
    if 'semester' in periode_lower:
        if not any(f'semester {s}' in periode_lower for s in ['i', 'ii']):
            logger.warning(f"Invalid semester value: '{periode_str}', skipping")
            return None, 1

    # --- Derive numeric periode_value ---
    month_numbers = {
        'januari': 1, 'februari': 2, 'february': 2, 'maret': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8, 'september': 9,
        'oktober': 10, 'november': 11, 'desember': 12,
    }
    periode_value = 1

    if periode_lower in month_numbers:
        periode_value = month_numbers[periode_lower]
    elif 'triwulan' in periode_lower:
        triwulan_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}
        m = re.search(r'triwulan\s+([ivx]+|\d+)', periode_lower)
        if m:
            periode_value = triwulan_map.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else 1)
    elif 'semester' in periode_lower:
        m = re.search(r'semester\s+([ivx]+|\d+)', periode_lower)
        if m:
            periode_value = {'i': 1, 'ii': 2}.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else 1)
    elif periode_lower in ('tahun', 'tahunan'):
        periode_value = 1
    elif 'minggu' in periode_lower or 'hari' in periode_lower or 'harian' in periode_lower:
        m = re.search(r'(\d+)', periode_lower)
        periode_value = int(m.group(1)) if m else 1

    # --- Resolve PeriodeJenisData strictly by sub_jenis_data from nomor_tiket prefix ---
    if not nomor_tiket or len(nomor_tiket) < 9:
        logger.warning(
            f"_map_periode_data: invalid nomor_tiket '{nomor_tiket}' (must be >= 9 chars)"
        )
        return None, periode_value

    sub_jenis_data_id = nomor_tiket[:9]
    pjd = None
    if periode_lookup_cache is not None:
        pjd = periode_lookup_cache.get(sub_jenis_data_id)
    else:
        from ..models.jenis_data_ilap import JenisDataILAP
        jenis_data_obj = JenisDataILAP.objects.filter(
            id_sub_jenis_data=sub_jenis_data_id
        ).first()
        if jenis_data_obj:
            pjd = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap=jenis_data_obj
            ).first()

    if not pjd:
        logger.warning(
            f"_map_periode_data: no PeriodeJenisData/JenisDataILAP for sub_jenis_data '{sub_jenis_data_id}' "
            f"(nomor_tiket='{nomor_tiket}')"
        )
        return None, periode_value

    return pjd, periode_value


def _build_bentuk_data_lookup_cache():
    """Build a lookup cache mapping deskripsi to BentukData instances.

    Returns:
        dict[str, BentukData]: A mapping from deskripsi string to the
        corresponding BentukData instance.
    """
    return {bd.deskripsi: bd for bd in BentukData.objects.all()}


def _build_cara_penyampaian_lookup_cache():
    """Build a lookup cache mapping deskripsi to CaraPenyampaian instances.

    Returns:
        dict[str, CaraPenyampaian]: A mapping from deskripsi string to the
        corresponding CaraPenyampaian instance.
    """
    return {cp.deskripsi: cp for cp in CaraPenyampaian.objects.all()}


def _check_tiket_data(service, check_id=None, stop_checker=None):
    """Check tiket data from Oracle without inserting.
    
    Uses a single bulk DB query for exists-check instead of per-row .exists().
    Writes progress to cache every 1000 rows when check_id is provided.
    
    Args:
        service: OracleDataSyncService instance
        check_id: optional UUID for tracking check progress
        stop_checker: optional callable() that returns True if check should stop
    """
    try:
        sql_query = _TIKET_ORACLE_SQL

        if check_id:
            cache.set(f'check_tiket_progress_{check_id}', {
                'current': 0, 'total': 0, 'percentage': 0,
                'inserts': 0, 'updates': 0, 'errors': 0,
                'table_name': 'Menghubungkan ke Oracle...',
            }, timeout=3600)

        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]
        
        total = len(rows)
        inserts = 0
        updates = 0
        errors = []
        inserted_keys = []
        updated_keys = []

        # Validate against the same prerequisite used by sync:
        # nomor_tiket[:9] must resolve to PeriodeJenisData.
        periode_lookup_cache = _build_periode_lookup_cache()
        valid_sub_jenis_ids = set(periode_lookup_cache.keys())
        logger.info(
            f'Periode lookup cache loaded: {len(valid_sub_jenis_ids)} sub_jenis_data with PeriodeJenisData'
        )

        if check_id:
            cache.set(f'check_tiket_progress_{check_id}', {
                'current': 0, 'total': total, 'percentage': 0,
                'inserts': 0, 'updates': 0, 'errors': 0,
                'table_name': f'Memeriksa {total:,} baris...',
            }, timeout=3600)

        # --- Bulk exists check: chunked to avoid SQLite variable limit ---
        all_nomor_tikets = []
        for row in rows:
            row_dict = dict(zip(column_names, row))
            nt = row_dict.get('id_tiket')
            if nt:
                all_nomor_tikets.append(nt)
        all_nomor_tikets = list(dict.fromkeys(all_nomor_tikets))  # deduplicate preserving order

        CHUNK = 500
        existing_set: set[str] = set()
        for i in range(0, len(all_nomor_tikets), CHUNK):
            existing_set.update(
                Tiket.objects.filter(nomor_tiket__in=all_nomor_tikets[i:i+CHUNK])
                .values_list('nomor_tiket', flat=True)
            )
        logger.info(f'Bulk exists check: {len(existing_set)} existing / {len(all_nomor_tikets)} unique oracle rows')

        # --- Classify rows using the pre-fetched set ---
        for idx, row in enumerate(rows):
            # Check stop signal during row iteration
            if stop_checker and stop_checker():
                logger.warning(f'Stop signal received during check after {idx} rows')
                break
                
            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('id_tiket')

                if not nomor_tiket:
                    continue

                if len(nomor_tiket) < 9:
                    errors.append(f"Tiket {nomor_tiket}: nomor_tiket invalid (<9 chars)")
                    continue

                sub_jenis_data_id = nomor_tiket[:9]
                if sub_jenis_data_id not in valid_sub_jenis_ids:
                    errors.append(
                        f"Tiket {nomor_tiket}: PeriodeJenisData/JenisDataILAP not found for sub_jenis_data '{sub_jenis_data_id}'"
                    )
                    continue

                if nomor_tiket in existing_set:
                    updates += 1
                    if len(updated_keys) < 5:
                        updated_keys.append(nomor_tiket)
                else:
                    inserts += 1
                    if len(inserted_keys) < 5:
                        inserted_keys.append(nomor_tiket)
            except Exception as e:
                errors.append(f"Row error: {str(e)[:100]}")

            # Write progress every 1000 rows
            if check_id and (idx % 1000 == 0 or idx == total - 1):
                pct = int((idx + 1) / total * 100) if total else 100
                cache.set(f'check_tiket_progress_{check_id}', {
                    'current': idx + 1, 'total': total, 'percentage': pct,
                    'inserts': inserts, 'updates': updates, 'errors': len(errors),
                    'table_name': 'Memeriksa baris...',
                }, timeout=3600)
        
        return {
            'source_rows': total,
            'inserts': inserts,
            'updates': updates,
            'unchanged': total - inserts - updates,
            'errors': errors,
            'inserted_keys': inserted_keys,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        return {
            'source_rows': 0,
            'inserts': 0,
            'updates': 0,
            'unchanged': 0,
            'errors': [str(e)],
            'inserted_keys': [],
            'updated_keys': [],
        }


def _sync_tiket_data(service, sync_id=None, request=None, stop_checker=None):
    """Fast bulk sync using CSV intermediate storage.
    
    Process:
    1. Query all tiket data from Oracle into memory
    2. Parse and validate all rows
    3. Batch insert new records using bulk_create
    4. Batch update existing records
    5. Assign PICs and audit trails
    
    Args:
        service: OracleDataSyncService instance
        sync_id: optional UUID for tracking sync progress
        request: optional Django request for user info
        stop_checker: optional callable() that returns True if sync should stop
    """
    try:
        # Detect database and set appropriate batch sizes
        from django.db import connection
        db_vendor = connection.vendor  # 'sqlite', 'postgresql', 'mysql'
        if db_vendor == 'sqlite':
            BATCH_SIZE = 50  # SQLite has ~999-2000 variable limit
            LOOKUP_BATCH_SIZE = 50
        elif db_vendor == 'postgresql':
            BATCH_SIZE = 500  # PostgreSQL can handle ~34,000 variables
            LOOKUP_BATCH_SIZE = 500
        else:  # mysql
            BATCH_SIZE = 250  # MySQL ~16,000 variables
            LOOKUP_BATCH_SIZE = 250
        logger.info(f'Using batch sizes for {db_vendor}: BATCH_SIZE={BATCH_SIZE}, LOOKUP_BATCH_SIZE={LOOKUP_BATCH_SIZE}')
        
        sql_query = _TIKET_ORACLE_SQL

        logger.info('Connecting to Oracle...')
        with service._connect_oracle("primary") as conn:
            logger.info('Oracle connected, executing bulk query...')
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]
        logger.info(f'Oracle query completed, fetched {len(rows)} rows for bulk processing')

        # Build lookup once to avoid per-row DB query in _map_periode_data.
        periode_lookup_cache = _build_periode_lookup_cache()
        logger.info(
            f'Periode lookup cache loaded: {len(periode_lookup_cache)} sub_jenis_data with PeriodeJenisData'
        )

        # Build BentukData and CaraPenyampaian caches for Oracle value lookups
        bentuk_data_cache = _build_bentuk_data_lookup_cache()
        cara_penyampaian_cache = _build_cara_penyampaian_lookup_cache()
        logger.info(
            f'BentukData cache: {len(bentuk_data_cache)} entries, '
            f'CaraPenyampaian cache: {len(cara_penyampaian_cache)} entries'
        )

        # --- Bulk exists pre-fetch (same pattern as _check_tiket_data) ---
        all_nomor_tikets = list(dict.fromkeys(
            dict(zip(column_names, r)).get('id_tiket')
            for r in rows
            if dict(zip(column_names, r)).get('id_tiket')
        ))
        CHUNK = 500
        existing_set: set = set()
        for i in range(0, len(all_nomor_tikets), CHUNK):
            existing_set.update(
                Tiket.objects.filter(nomor_tiket__in=all_nomor_tikets[i:i + CHUNK])
                .values_list('nomor_tiket', flat=True)
            )
        logger.info(f'Bulk exists pre-fetch: {len(existing_set)} existing / {len(all_nomor_tikets)} unique oracle rows')

        inserts = 0
        updates = 0
        errors = []
        inserted_keys = []
        updated_keys = []
        
        logger.info('Setting up default lookups...')
        default_bentuk_data = bentuk_data_cache.get('Softcopy') or BentukData.objects.first()
        default_cara_penyampaian = cara_penyampaian_cache.get('Online') or CaraPenyampaian.objects.first()
        
        logger.info(f'Parsing {len(rows)} rows for bulk insert/update...')
        today = timezone.now().date()
        base_time = timezone.now()
        
        # Separate rows into two groups: new inserts and updates
        to_create = []
        to_update = []  # (nomor_tiket, tiket_obj, update_dict)
        
        # First pass: validate and parse all rows
        for idx, row in enumerate(rows):
            # Check if sync was stopped
            if sync_id and cache.get(f'sync_tiket_stop_{sync_id}'):
                errors.append('Sync dihentikan oleh pengguna')
                logger.info('Sync stopped by user')
                break
            
            # Check stop_checker callable (from tasks/tests)
            if stop_checker and stop_checker():
                logger.warning(f'Stop signal received during sync after {idx} rows')
                break
            
            # Update progress every 50 rows
            if idx % 50 == 0 and sync_id:
                progress_pct = int((idx / len(rows) * 100)) if rows else 0
                cache.set(f'sync_tiket_progress_{sync_id}', {
                    'current': idx,
                    'total': len(rows),
                    'percentage': progress_pct,
                    'inserts': inserts,
                    'updates': updates,
                    'errors': len(errors),
                }, timeout=3600)
            
            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('id_tiket')
                
                if not nomor_tiket:
                    continue
                
                # Parse and validate tiket data
                oracle_tahun = _safe_int(row_dict.get('tahun_data'))
                jenis_prioritas_str = row_dict.get('jenis_prioritas_data')
                jenis_prioritas_obj, _ = _parse_jenis_prioritas_data(jenis_prioritas_str, tahun_override=oracle_tahun)
                tahun_data = oracle_tahun

                if tahun_data is None:
                    error_msg = "Tahun data kosong/tidak valid"
                    errors.append(f"Tiket {nomor_tiket}: {error_msg}")
                    _log_failed_row(sync_id, nomor_tiket, row_dict.get('periode_data'), jenis_prioritas_str, row_dict.get('tahun_data'), error_msg, row_number=idx+1)
                    continue
                
                periode_str = row_dict.get('periode_data')
                periode_jenis_data_obj, periode_value = _map_periode_data(
                    periode_str,
                    jenis_prioritas_obj=jenis_prioritas_obj,
                    tahun_value=tahun_data,
                    nomor_tiket=nomor_tiket,
                    periode_lookup_cache=periode_lookup_cache,
                )
                
                if not periode_jenis_data_obj:
                    error_msg = f"Periode '{periode_str}' not found in database"
                    errors.append(f"Tiket {nomor_tiket}: {error_msg}")
                    _log_failed_row(sync_id, nomor_tiket, periode_str, jenis_prioritas_str, tahun_data, error_msg, row_number=idx+1)
                    continue
                
                status_penelitian_obj = None
                status_penelitian_str = row_dict.get('status_penelitian', '').strip().lower()
                if status_penelitian_str:
                    status_penelitian_obj = StatusPenelitian.objects.filter(deskripsi__icontains=status_penelitian_str).first()
                
                # Look up BentukData and CaraPenyampaian from Oracle row values
                bentuk_data_str = row_dict.get('bentuk_data')
                if bentuk_data_str and bentuk_data_str in bentuk_data_cache:
                    bentuk_data_obj = bentuk_data_cache[bentuk_data_str]
                else:
                    bentuk_data_obj = default_bentuk_data

                cara_penyampaian_str = row_dict.get('cara_penyampaian')
                if cara_penyampaian_str and cara_penyampaian_str in cara_penyampaian_cache:
                    cara_penyampaian_obj = cara_penyampaian_cache[cara_penyampaian_str]
                else:
                    cara_penyampaian_obj = default_cara_penyampaian

                # Prepare tiket data dict
                tiket_data = {
                    'nomor_tiket': nomor_tiket,
                    'old_db': _safe_int(row_dict.get('old_db'), 1),
                    'status_tiket': row_dict.get('status_tiket') if row_dict.get('status_tiket') is not None else 1,
                    'id_periode_data': periode_jenis_data_obj,
                    'id_jenis_prioritas_data': jenis_prioritas_obj,
                    'periode': periode_value,
                    'tahun': tahun_data,
                    'penyampaian': row_dict.get('penyampaian', 1),
                    'nomor_surat_pengantar': row_dict.get('nomor_surat_pengantar') or '-',
                    'tanggal_surat_pengantar': _make_aware_datetime(row_dict.get('tanggal_surat_pengantar')) or timezone.now(),
                    'nama_pengirim': row_dict.get('nama_pengirim', '-'),
                    'id_bentuk_data': bentuk_data_obj,
                    'id_cara_penyampaian': cara_penyampaian_obj,
                    'status_ketersediaan_data': bool(row_dict.get('status_ketersediaan_data', 1)),
                    'alasan_ketidaktersediaan': row_dict.get('alasan_ketidaktersediaan'),
                    'baris_diterima': row_dict.get('baris_diterima') if row_dict.get('baris_diterima') is not None else 0,
                    'satuan_data': row_dict.get('satuan_data', 1),
                    'tgl_terima_vertikal': _make_aware_datetime(row_dict.get('tgl_terima_vertikal')),
                    'tgl_terima_dip': _make_aware_datetime(row_dict.get('tgl_terima_dip')) or timezone.now(),
                    'backup': bool(row_dict.get('backup', 0)),
                    'tanda_terima': bool(row_dict.get('tanda_terima', 0)),
                    'id_status_penelitian': status_penelitian_obj,
                    'tgl_teliti': _make_aware_datetime(row_dict.get('tgl_teliti')),
                    'baris_lengkap': row_dict.get('baris_lengkap'),
                    'baris_tidak_lengkap': row_dict.get('baris_tidak_lengkap'),
                    'tgl_nadine': _make_aware_datetime(row_dict.get('tgl_nadine')),
                    'nomor_nd_nadine': row_dict.get('no_nadine'),
                    'tgl_kirim_pide': _make_aware_datetime(row_dict.get('tgl_kirim_pide')),
                    'tgl_rekam_pide': _make_aware_datetime(row_dict.get('tgl_rekam_pide')),
                    'baris_i': row_dict.get('baris_i'),
                    'baris_u': row_dict.get('baris_u'),
                    'baris_res': row_dict.get('baris_res'),
                    'baris_cde': row_dict.get('baris_cde'),
                    'tgl_transfer': _make_aware_datetime(row_dict.get('tgl_transfer')),
                    'tgl_rematch': _make_aware_datetime(row_dict.get('tgl_rematch')),
                    'sudah_qc': row_dict.get('sudah_qc'),
                    'belum_qc': row_dict.get('belum_qc'),
                    'lolos_qc': row_dict.get('lolos_qc'),
                    'tidak_lolos_qc': row_dict.get('tidak_lolos_qc'),
                    'qc_p': row_dict.get('qc_p'),
                    'qc_x': row_dict.get('qc_x'),
                    'qc_w': row_dict.get('qc_w'),
                    'qc_f': row_dict.get('qc_f'),
                    'qc_a': row_dict.get('qc_a'),
                    'qc_c': row_dict.get('qc_c'),
                    'qc_n': row_dict.get('qc_n'),
                    'qc_y': row_dict.get('qc_y'),
                    'qc_z': row_dict.get('qc_z'),
                    'qc_u': row_dict.get('qc_u'),
                    'qc_e': row_dict.get('qc_e'),
                    'qc_v': row_dict.get('qc_v'),
                    'qc_r': row_dict.get('qc_r'),
                    'qc_d': row_dict.get('qc_d'),
                }
                
                # Check if exists (using pre-fetched set — no per-row DB query)
                if nomor_tiket in existing_set:
                    update_dict = {k: v for k, v in tiket_data.items() if k not in ('nomor_tiket', 'old_db')}
                    to_update.append((nomor_tiket, tiket_data, update_dict, periode_jenis_data_obj))
                else:
                    to_create.append(Tiket(**_ensure_naive_datetimes(tiket_data)))
            
            except Exception as e:
                error_msg = str(e)[:200]
                # Safely get row context - row_dict may not be defined if error occurred early
                try:
                    row_id = row_dict.get('id_tiket', f'row_{idx+1}')
                    row_periode = row_dict.get('periode_data', '')
                    row_jenis = row_dict.get('jenis_prioritas_data', '')
                    row_tahun = row_dict.get('tahun_data', '')
                except (NameError, AttributeError):
                    row_id = f'row_{idx+1}'
                    row_periode = ''
                    row_jenis = ''
                    row_tahun = ''
                errors.append(f"Tiket {row_id}: {error_msg}")
                _log_failed_row(sync_id, row_id, row_periode, row_jenis, row_tahun, 
                              error_msg, row_number=idx+1)
        
        # Bulk insert new records
        logger.info(f'Bulk creating {len(to_create)} new tiket records...')
        if to_create:
            for i in range(0, len(to_create), BATCH_SIZE):
                batch = to_create[i:i+BATCH_SIZE]
                try:
                    created_objs = Tiket.objects.bulk_create(batch, batch_size=BATCH_SIZE, ignore_conflicts=False)
                    inserts += len(created_objs)
                    if len(inserted_keys) < 5:
                        inserted_keys.extend([t.nomor_tiket for t in created_objs[:5-len(inserted_keys)]])

                    for tiket in created_objs:
                        try:
                            periode_jenis_data_obj = tiket.id_periode_data
                            _assign_tiket_pics_sync(tiket, periode_jenis_data_obj, today, base_time, request, BATCH_SIZE)
                        except Exception as pic_error:
                            logger.warning(f"Failed to assign PICs for tiket {tiket.nomor_tiket}: {str(pic_error)}")
                except Exception as bulk_error:
                    bulk_error_msg = str(bulk_error)
                    logger.warning(f"Bulk insert failed: {bulk_error_msg}, trying one-by-one...")
                    # Log the bulk error so it shows in progress summary
                    errors.append(f"Bulk insert batch error: {bulk_error_msg[:200]}")
                    for tiket_obj in batch:
                        try:
                            safe_data = {k: v for k, v in tiket_obj.__dict__.items() if not k.startswith('_')}
                            created = Tiket.objects.create(**_ensure_naive_datetimes(safe_data))
                            inserts += 1
                            if len(inserted_keys) < 5:
                                inserted_keys.append(created.nomor_tiket)
                            
                            try:
                                periode_jenis_data_obj = created.id_periode_data
                                _assign_tiket_pics_sync(created, periode_jenis_data_obj, today, base_time, request, BATCH_SIZE)
                            except Exception as pic_error:
                                logger.warning(f"Failed to assign PICs for tiket {created.nomor_tiket}: {str(pic_error)}")
                        except Exception as single_error:
                            error_msg = str(single_error)[:200]
                            errors.append(f"Tiket {tiket_obj.nomor_tiket}: {error_msg}")
                            logger.error(f"Failed to insert tiket {tiket_obj.nomor_tiket}: {error_msg}")
                            _log_failed_row(
                                sync_id, tiket_obj.nomor_tiket,
                                str(getattr(tiket_obj, 'periode', '?')),
                                str(getattr(tiket_obj, 'id_jenis_prioritas_data', '') 
                                    if getattr(tiket_obj, 'id_jenis_prioritas_data', None) else ''),
                                str(getattr(tiket_obj, 'tahun', '')),
                                error_msg
                            )
        
        # Bulk update existing records
        logger.info(f'Bulk updating {len(to_update)} existing tiket records...')
        if to_update:
            nomor_tikets_to_update = [t[0] for t in to_update]
            existing_tikets = {}
            for i in range(0, len(nomor_tikets_to_update), LOOKUP_BATCH_SIZE):
                batch = nomor_tikets_to_update[i:i+LOOKUP_BATCH_SIZE]
                for tiket in Tiket.objects.filter(nomor_tiket__in=batch):
                    existing_tikets[tiket.nomor_tiket] = tiket

            tikets_to_save = []
            for nomor_tiket, tiket_data, update_dict, periode_jenis_data_obj in to_update:
                if nomor_tiket in existing_tikets:
                    tiket = existing_tikets[nomor_tiket]
                    # Update fields except old_db — ensure datetimes are naive
                    safe_updates = _ensure_naive_datetimes(update_dict)
                    for key, val in safe_updates.items():
                        setattr(tiket, key, val)
                    tikets_to_save.append((nomor_tiket, tiket, safe_updates))
            
            if tikets_to_save:
                for i in range(0, len(tikets_to_save), BATCH_SIZE):
                    batch = tikets_to_save[i:i+BATCH_SIZE]
                    batch_objs = [t[1] for t in batch]
                    batch_updates = batch[0][2] if batch else {}
                    
                    try:
                        Tiket.objects.bulk_update(batch_objs, batch_size=BATCH_SIZE, fields=list(batch_updates.keys()))
                        updates += len(batch)
                        if len(updated_keys) < 5:
                            updated_keys.extend([t[0] for t in batch[:5-len(updated_keys)]])
                    except Exception as bulk_error:
                        bulk_error_msg = str(bulk_error)
                        logger.warning(f"Bulk update failed: {bulk_error_msg}, trying one-by-one...")
                        # Log the bulk error so it shows in progress summary
                        errors.append(f"Bulk update batch error: {bulk_error_msg[:200]}")
                        for nomor_tiket, tiket_obj, upd_dict in batch:
                            try:
                                safe_updates = _ensure_naive_datetimes(upd_dict)
                                for key, val in safe_updates.items():
                                    setattr(tiket_obj, key, val)
                                tiket_obj.save()
                                updates += 1
                                if len(updated_keys) < 5:
                                    updated_keys.append(nomor_tiket)
                            except Exception as single_error:
                                error_msg = str(single_error)[:200]
                                errors.append(f"Tiket {nomor_tiket}: {error_msg}")
                                logger.error(f"Failed to update tiket {nomor_tiket}: {error_msg}")
                                _log_failed_row(
                                    sync_id, nomor_tiket,
                                    str(getattr(tiket_obj, 'periode', '?')),
                                    str(getattr(tiket_obj, 'id_jenis_prioritas_data', '') 
                                        if getattr(tiket_obj, 'id_jenis_prioritas_data', None) else ''),
                                    str(getattr(tiket_obj, 'tahun', '')),
                                    error_msg
                                )

        # --- Auto-settle qualifying tickets to Selesai after sync ---
        # Find PeriodeJenisData records linked to "Tidak Diidentifikasi" JenisTabel,
        # then update all matching Tiket records.
        from ..constants.tiket_status import STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI
        try:
            from datetime import datetime
            from django.conf import settings as django_settings
            cutoff_date = datetime(2024, 5, 1)
            if django_settings.USE_TZ:
                cutoff_date = timezone.make_aware(cutoff_date)
            
            # Resolve PeriodeJenisData IDs whose JenisDataILAP has JenisTabel = 'Tidak Diidentifikasi'
            auto_settle_periode_ids = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi='Tidak Diidentifikasi',
            ).values_list('pk', flat=True)
            
            auto_settled = Tiket.objects.filter(
                status_tiket=STATUS_PENGENDALIAN_MUTU,
                tgl_transfer__lt=cutoff_date,
                id_periode_data__in=auto_settle_periode_ids,
            ).update(status_tiket=STATUS_SELESAI)
            
            if auto_settled:
                logger.info(f'Auto-settled {auto_settled} tickets to Selesai (status 8)')
        except Exception as settle_err:
            logger.warning(f'Auto-settlement failed (non-blocking): {settle_err}')
        
        return {
            'source_rows': len(rows),
            'inserts': inserts,
            'updates': updates,
            'unchanged': len(rows) - inserts - updates,
            'errors': errors,
            'inserted_keys': inserted_keys,
            'updated_keys': updated_keys,
        }
    except Exception as e:
        logger.error(f'Bulk sync failed: {str(e)}', exc_info=True)
        return {
            'source_rows': 0,
            'inserts': 0,
            'updates': 0,
            'unchanged': 0,
            'errors': [str(e)],
            'inserted_keys': [],
            'updated_keys': [],
        }
