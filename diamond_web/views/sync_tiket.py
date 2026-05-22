from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import uuid
import json
import logging
import signal
import threading
import time
import re
from functools import wraps
import os
import csv

from ..models import Tiket, BentukData, CaraPenyampaian, PeriodeJenisData, JenisPrioritasData, StatusPenelitian, PIC, TiketPIC, TiketAction
from ..constants.tiket_action_types import PICActionType
from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
SYNC_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync_logs')
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)


def retry_on_db_lock(max_retries=5, initial_delay=0.1, backoff_factor=2.0):
    """Decorator to retry database operations on lock with exponential backoff."""
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
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


class SyncTimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise SyncTimeoutError('Sinkronisasi timeout (> 5 menit)')


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def sync_tiket_page(request):
    return render(request, 'oracle_sync/tiket.html')


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def sync_tiket_test_connection(request):
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
    try:
        logger.info('Starting tiket check...')
        service = OracleDataSyncService()
        logger.info('OracleDataSyncService initialized')
        
        tiket_summary = _check_tiket_data(service)
        logger.info(f'Tiket check completed: {tiket_summary}')
        
        return JsonResponse({
            'success': True,
            'mode': 'check',
            'summary': tiket_summary,
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
    """Run sync in background thread."""
    try:
        logger.info(f'[BG] Starting tiket sync (sync_id={sync_id})...')
        service = OracleDataSyncService()
        logger.info(f'[BG] OracleDataSyncService initialized')
        
        class FakeRequest:
            def __init__(self, user):
                self.user = user
        
        fake_request = FakeRequest(request_user) if request_user else None
        tiket_summary = _sync_tiket_data(service, sync_id=sync_id, request=fake_request)
        logger.info(f'[BG] Tiket sync completed (sync_id={sync_id}): {tiket_summary}')
        
        # Cache the final result
        cache.set(f'sync_tiket_result_{sync_id}', tiket_summary, timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', True, timeout=3600)
    except Exception as e:
        logger.error(f'[BG] Exception in background sync: {str(e)}', exc_info=True)
        cache.set(f'sync_tiket_error_{sync_id}', str(e), timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', True, timeout=3600)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def sync_tiket_run(request):
    try:
        # Generate unique sync ID for tracking progress and stop signals
        sync_id = str(uuid.uuid4())
        cache.set(f'sync_tiket_stop_{sync_id}', False, timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', False, timeout=3600)
        
        logger.info(f'Starting tiket sync (sync_id={sync_id})...')
        
        # Start sync in background thread - don't block the response
        thread = threading.Thread(
            target=_sync_tiket_data_background,
            args=(sync_id, request.user),
            daemon=True
        )
        thread.start()
        
        logger.info(f'Background sync thread started (sync_id={sync_id})')
        
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
    """Stop an in-progress sync operation (no auth check to avoid session locks)."""
    try:
        data = json.loads(request.body)
        sync_id = data.get('sync_id')
        if sync_id:
            # Validate sync_id format (UUID)
            try:
                uuid.UUID(sync_id)
                cache.set(f'sync_tiket_stop_{sync_id}', True, timeout=3600)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)
        
        # Mark session as not modified to prevent session DB access
        request.session.modified = False
        
        return JsonResponse({'success': True, 'message': 'Sync dihentikan.'})
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_GET
@never_cache
def sync_tiket_progress(request):
    """Get current progress of in-progress sync (no auth check to avoid session locks during sync)."""
    try:
        sync_id = request.GET.get('sync_id')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id required'}, status=400)
        
        # Validate sync_id format (UUID)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'invalid sync_id'}, status=400)
        
        # Mark session as not modified to prevent session DB access
        request.session.modified = False
        
        # Check if sync is done
        is_done = cache.get(f'sync_tiket_done_{sync_id}', False)
        
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
                return JsonResponse({
                    'success': True,
                    'done': True,
                    'progress': progress_data,
                    'summary': result,
                    'message': f"Sync selesai: {result.get('inserts', 0)} insert, {result.get('updates', 0)} update, {len(result.get('errors', []))} error",
                })
        
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
    try:
        from django.db import connection
        
        # Delete dependent records first (TiketPIC and TiketAction) due to PROTECT constraint
        from ..models import TiketPIC, TiketAction
        TiketPIC.objects.all().delete()
        TiketAction.objects.all().delete()
        
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
    """Log a failed row to CSV file for review and debugging."""
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


def _make_aware_datetime(dt):
    """Convert naive datetime to timezone-aware. Return None if dt is None."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt
    return dt


def _assign_tiket_pics_sync(tiket, periode_jenis_data, today, base_time, request):
    """Assign all active P3DE, PIDE, PMDE PICs to a synced tiket from the PIC table only.
    
    Only adds PICs that are already configured in the PIC table for this sub_jenis_data_ilap.
    Does NOT automatically add the current user.
    """
    try:
        if not periode_jenis_data:
            return
        
        from django.contrib.auth.models import User
        admin_user = User.objects.get(username='admin')
        
        # Add all active P3DE, PIDE, PMDE PICs from PIC table
        active_filter = Q(start_date__lte=today) & Q(end_date__isnull=True)
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
            for idx, pic in enumerate(pic_qs.filter(active_filter), start=1):
                TiketPIC.objects.create(
                    id_tiket=tiket,
                    id_user=pic.id_user,
                    timestamp=timezone.now(),
                    role=role_value,
                    active=True,
                )
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=admin_user,  # Always log as admin (system action)
                    timestamp=base_time + timedelta(microseconds=1 + idx),
                    action=PICActionType.DITAMBAHKAN,
                    catatan=f'{tipe_label} {pic.id_user.username} ditambahkan'
                )
    except Exception:
        # Silently skip PIC assignment if it fails (don't block sync)
        pass


def _safe_int(value, default=None):
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


def _map_periode_data(periode_str, jenis_prioritas_obj=None, tahun_value=None):
    """
    Map Oracle periode_data values to PeriodeJenisData.
    Oracle values: 'tahun', 'april', 'triwulan I', 'semester I', etc.
    
    Strategy:
    1. Validate periode value (e.g., triwulan must be I/II/III/IV, not V or invalid)
    2. Map to periode_penyampaian category ('Bulanan', 'Triwulanan', etc.)
    3. Find PeriodePengiriman matching that category
    4. If jenis_prioritas_obj provided, use it to find the correct id_sub_jenis_data_ilap
    5. Find active PeriodeJenisData for that combination
    
    Returns: tuple(PeriodeJenisData object or None, periode_value int)
    """
    if not periode_str:
        return None, 1
    
    periode_str = periode_str.strip()
    periode_lower = periode_str.lower()
    
    # Validate specific periode values
    # Triwulan must be I, II, III, or IV (not V or higher)
    if 'triwulan' in periode_lower:
        valid_triwulan = ['i', 'ii', 'iii', 'iv']
        if not any(f'triwulan {tw}' in periode_lower for tw in valid_triwulan):
            # Invalid triwulan (e.g., 'triwulan v', 'triwulan 5')
            logger.warning(f"Invalid triwulan value: '{periode_str}', skipping")
            return None, 1
    
    # Semester must be I or II
    if 'semester' in periode_lower:
        if not any(f'semester {s}' in periode_lower for s in ['i', 'ii']):
            logger.warning(f"Invalid semester value: '{periode_str}', skipping")
            return None, 1
    
    # Month names that map to 'Bulanan' (Monthly)
    month_names = {
        'januari', 'february', 'februari', 'maret', 'april', 'mei', 'juni',
        'juli', 'agustus', 'september', 'oktober', 'november', 'desember'
    }
    
    # Determine the periode_penyampaian category
    django_period = None
    
    if periode_lower in month_names:
        django_period = 'Bulanan'
    elif 'triwulan' in periode_lower:
        django_period = 'Triwulanan'
    elif 'semester' in periode_lower:
        django_period = 'Semesteran'
    elif periode_lower == 'tahun' or periode_lower == 'tahunan':
        django_period = 'Tahunan'
    elif '2' in periode_str and 'minggu' in periode_lower:
        django_period = '2 Mingguan'
    elif 'minggu' in periode_lower:
        django_period = 'Mingguan'
    elif 'hari' in periode_lower or 'harian' in periode_lower:
        django_period = 'Harian'
    
    if not django_period:
        logger.warning(f"Unknown periode value: '{periode_str}', unable to map")
        return None, 1

    # Derive numeric periode value from Oracle source string (not from master table ID)
    month_numbers = {
        'januari': 1, 'februari': 2, 'february': 2, 'maret': 3, 'april': 4,
        'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8, 'september': 9,
        'oktober': 10, 'november': 11, 'desember': 12,
    }
    periode_value = 1

    if django_period == 'Bulanan':
        periode_value = month_numbers.get(periode_lower, 1)
    elif django_period == 'Triwulanan':
        triwulan_map = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, '1': 1, '2': 2, '3': 3, '4': 4}
        m = re.search(r'triwulan\s+([ivx]+|\d+)', periode_lower)
        periode_value = triwulan_map.get(m.group(1), 1) if m else 1
    elif django_period == 'Semesteran':
        semester_map = {'i': 1, 'ii': 2, '1': 1, '2': 2}
        m = re.search(r'semester\s+([ivx]+|\d+)', periode_lower)
        periode_value = semester_map.get(m.group(1), 1) if m else 1
    elif django_period in ('Mingguan', '2 Mingguan', 'Harian'):
        m = re.search(r'(\d+)', periode_lower)
        periode_value = int(m.group(1)) if m else 1
    
    # Find PeriodePengiriman matching the category
    from ..models.periode_pengiriman import PeriodePengiriman
    periode_pengiriman = PeriodePengiriman.objects.filter(
        periode_penyampaian__exact=django_period
    ).first()
    
    if not periode_pengiriman:
        logger.warning(f"No PeriodePengiriman found for category: '{django_period}'")
        return None, periode_value
    
    # If we have jenis_prioritas_obj, use its id_sub_jenis_data_ilap to find the correct PeriodeJenisData
    if jenis_prioritas_obj and hasattr(jenis_prioritas_obj, 'id_sub_jenis_data_ilap'):
        from django.utils import timezone as tz
        today = tz.now().date()
        
        # Find active PeriodeJenisData for this specific sub_jenis_data_ilap + periode
        periode_jenis_data = PeriodeJenisData.objects.filter(
            id_sub_jenis_data_ilap=jenis_prioritas_obj.id_sub_jenis_data_ilap,
            id_periode_pengiriman=periode_pengiriman,
            start_date__lte=today
        ).exclude(
            end_date__lt=today
        ).first()
        
        if periode_jenis_data:
            return periode_jenis_data, periode_value
    
    # Fallback: find any active PeriodeJenisData with this periode_pengiriman
    from django.utils import timezone as tz
    today = tz.now().date()
    
    periode_jenis_data = PeriodeJenisData.objects.filter(
        id_periode_pengiriman=periode_pengiriman,
        start_date__lte=today
    ).exclude(
        end_date__lt=today
    ).first()
    
    # If no active one found, just get any PeriodeJenisData with this periode
    if not periode_jenis_data:
        periode_jenis_data = PeriodeJenisData.objects.filter(
            id_periode_pengiriman=periode_pengiriman
        ).first()
    
    return periode_jenis_data, periode_value


def _check_tiket_data(service):
    """Check tiket data from Oracle without inserting."""
    try:
        sql_query = """
            SELECT DISTINCT 
                id_tiket,
                1 old_db,
                CASE 
                    WHEN status_tiket IN ('[SELESAI]-Sudah QC', '[SELESAI]-Tidak di QC', '[SELESAI]-Tiket 0 Row') THEN 8
                    WHEN status_tiket IN ('[P3DE]-Close Tiket','[PIDE]-Close Tiket') THEN 7
                    WHEN status_tiket IN ('[PMDE]-Proses QC') THEN 6
                    WHEN status_tiket IN ('[PIDE]-Proses Identifikasi') THEN 5
                    WHEN status_tiket IN ('[P3DE]-Proses Nadine') THEN 2
                    WHEN status_tiket IN ('[P3DE]-Proses Penelitian') THEN 1
                    ELSE 1
                END status_tiket,
                PERIODE_PENGIRIMAN periode_penerimaan,
                substr(id_tiket,1,9) || '_20' || substr(id_tiket,10,2) jenis_prioritas_data,
                COALESCE(periode_data, 'tahun') periode_data,
                COALESCE(tahun_data, EXTRACT(YEAR FROM SYSDATE)) tahun_data,
                1 penyampaian,
                '-' nomor_surat_pengantar,
                COALESCE(TGL_TERIMA, SYSDATE) tanggal_surat_pengantar,
                '-' nama_pengirim,
                'Softcopy' bentuk_data,
                'Online' cara_penyampaian,
                CASE WHEN status_tiket IN ('[SELESAI]-Tiket 0 Row') THEN 0 ELSE 1 END status_ketersediaan_data,
                NULL alasan_ketidaktersediaan,
                COALESCE(JML_ROW_P3DE, 0) baris_diterima,
                1 satuan_data,
                NULL tgl_terima_vertikal,
                COALESCE(TGL_TERIMA, SYSDATE) tgl_terima_dip,
                0 backup,
                0 tanda_terima,
                CASE WHEN COALESCE(JML_ROW_P3DE, 0)-COALESCE(JML_DATA_TELITI, 0)=0 THEN 'Lengkap' ELSE 'Tidak Lengkap' END status_penelitian,
                TGL_TELITI,
                COALESCE(JML_DATA_TELITI, 0) baris_lengkap,
                COALESCE(JML_ROW_P3DE, 0)-COALESCE(JML_DATA_TELITI, 0) baris_tidak_lengkap,
                TGL_NADINE,
                NO_NADINE,
                TGL_NADINE tgl_kirim_pide,
                NULL tgl_rekam_pide,
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
                COALESCE(b.QC_D, 0) QC_D
            FROM
                PVPTD.ZA_DDE_TABEL_FACT a
            LEFT JOIN PVPTD.ZA_REKAP_TARIKAN b ON a.ID_TIKET = b.NO_TIKET
        """
        
        with service._connect_oracle("primary") as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]
        
        # Get column names from cursor
        inserts = 0
        updates = 0
        errors = []
        inserted_keys = []
        updated_keys = []
        
        for row in rows:
            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('id_tiket')  # Oracle column name is id_tiket, but Django field is nomor_tiket
                
                if not nomor_tiket:
                    continue
                
                # Check if exists
                exists = Tiket.objects.filter(nomor_tiket=nomor_tiket).exists()
                if exists:
                    updates += 1
                    if len(updated_keys) < 5:
                        updated_keys.append(nomor_tiket)
                else:
                    inserts += 1
                    if len(inserted_keys) < 5:
                        inserted_keys.append(nomor_tiket)
            except Exception as e:
                errors.append(f"Row error: {str(e)[:100]}")
        
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
        return {
            'source_rows': 0,
            'inserts': 0,
            'updates': 0,
            'unchanged': 0,
            'errors': [str(e)],
            'inserted_keys': [],
            'updated_keys': [],
        }


def _sync_tiket_data(service, sync_id=None, request=None):
    """Sync tiket data from Oracle to Django model.
    
    Args:
    - service: OracleDataSyncService instance
    - sync_id: Unique identifier for this sync run (for progress tracking)
    - request: Django request object (for assigning current user to TiketPICs)
    """
    try:
        sql_query = """
            SELECT
                id_tiket,
                1 old_db,
                CASE 
                    WHEN status_tiket IN ('[SELESAI]-Sudah QC', '[SELESAI]-Tidak di QC', '[SELESAI]-Tiket 0 Row') THEN 8
                    WHEN status_tiket IN ('[P3DE]-Close Tiket','[PIDE]-Close Tiket') THEN 7
                    WHEN status_tiket IN ('[PMDE]-Proses QC') THEN 6
                    WHEN status_tiket IN ('[PIDE]-Proses Identifikasi') THEN 5
                    WHEN status_tiket IN ('[P3DE]-Proses Nadine') THEN 2
                    WHEN status_tiket IN ('[P3DE]-Proses Penelitian') THEN 1
                    ELSE 1
                END status_tiket,
                PERIODE_PENGIRIMAN periode_penerimaan,
                substr(id_tiket,1,9) || '_20' || substr(id_tiket,10,2) jenis_prioritas_data,
                COALESCE(periode_data, 'tahun') periode_data,
                COALESCE(tahun_data, EXTRACT(YEAR FROM SYSDATE)) tahun_data,
                1 penyampaian,
                '-' nomor_surat_pengantar,
                COALESCE(TGL_TERIMA, SYSDATE) tanggal_surat_pengantar,
                '-' nama_pengirim,
                'Softcopy' bentuk_data,
                'Online' cara_penyampaian,
                CASE WHEN status_tiket IN ('[SELESAI]-Tiket 0 Row') THEN 0 ELSE 1 END status_ketersediaan_data,
                NULL alasan_ketidaktersediaan,
                COALESCE(JML_ROW_P3DE, 0) baris_diterima,
                1 satuan_data,
                NULL tgl_terima_vertikal,
                COALESCE(TGL_TERIMA, SYSDATE) tgl_terima_dip,
                0 backup,
                0 tanda_terima,
                CASE WHEN COALESCE(JML_ROW_P3DE, 0)-COALESCE(JML_DATA_TELITI, 0)=0 THEN 'Lengkap' ELSE 'Tidak Lengkap' END status_penelitian,
                TGL_TELITI,
                COALESCE(JML_DATA_TELITI, 0) baris_lengkap,
                COALESCE(JML_ROW_P3DE, 0)-COALESCE(JML_DATA_TELITI, 0) baris_tidak_lengkap,
                TGL_NADINE,
                NO_NADINE,
                TGL_NADINE tgl_kirim_pide,
                NULL tgl_rekam_pide,
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
                COALESCE(b.QC_D, 0) QC_D
            FROM
                PVPTD.ZA_DDE_TABEL_FACT a
            LEFT JOIN PVPTD.ZA_REKAP_TARIKAN b ON a.ID_TIKET = b.NO_TIKET
        """
        
        logger.info('Connecting to Oracle...')
        with service._connect_oracle("primary") as conn:
            logger.info('Oracle connected, executing query...')
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                rows = cursor.fetchall()
                column_names = [desc[0].lower() for desc in cursor.description]
        logger.info(f'Oracle query completed, fetched {len(rows)} rows')
        
        inserts = 0
        updates = 0
        errors = []
        inserted_keys = []
        updated_keys = []
        
        logger.info('Setting up default lookups...')
        # Default lookups - try to find by deskripsi field, fallback to first record
        default_bentuk_data = None
        try:
            default_bentuk_data = BentukData.objects.filter(deskripsi='Softcopy').first()
        except:
            default_bentuk_data = BentukData.objects.first()
        
        default_cara_penyampaian = None
        try:
            default_cara_penyampaian = CaraPenyampaian.objects.filter(deskripsi='Online').first()
        except:
            default_cara_penyampaian = CaraPenyampaian.objects.first()
        
        logger.info(f'Starting sync loop with {len(rows)} rows...')
        for idx, row in enumerate(rows):
            # Check if sync was stopped
            if sync_id and cache.get(f'sync_tiket_stop_{sync_id}'):
                errors.append('Sync dihentikan oleh pengguna')
                logger.info('Sync stopped by user')
                break
            
            # Update progress in cache every 20 rows (less frequent to reduce lock contention)
            if idx % 20 == 0:
                progress_pct = int((idx / len(rows) * 100)) if rows else 0
                cache.set(f'sync_tiket_progress_{sync_id}', {
                    'current': idx,
                    'total': len(rows),
                    'percentage': progress_pct,
                    'inserts': inserts,
                    'updates': updates,
                    'errors': len(errors),
                }, timeout=3600)
                logger.debug(f'Progress: {progress_pct}% ({idx}/{len(rows)})')
            
            try:
                row_dict = dict(zip(column_names, row))
                nomor_tiket = row_dict.get('id_tiket')  # Oracle column name
                
                if not nomor_tiket:
                    continue
                
                # Parse tahun from Oracle first; this is authoritative for Tiket.tahun.
                oracle_tahun = _safe_int(row_dict.get('tahun_data'))

                # Parse jenis_prioritas_data to get JenisPrioritasData and fallback year from key
                jenis_prioritas_str = row_dict.get('jenis_prioritas_data')
                jenis_prioritas_obj, tahun_from_key = _parse_jenis_prioritas_data(
                    jenis_prioritas_str,
                    tahun_override=oracle_tahun,
                )

                # Final year for tiket mapping: Oracle tahun_data > key year > current year
                tahun_data = oracle_tahun if oracle_tahun is not None else (tahun_from_key if tahun_from_key is not None else timezone.now().year)
                
                # Parse periode_data to get PeriodeJenisData (REQUIRED field)
                # Pass jenis_prioritas_obj so it can find the correct PeriodeJenisData for that sub_jenis_data_ilap
                periode_str = row_dict.get('periode_data')
                periode_jenis_data_obj, periode_value = _map_periode_data(
                    periode_str,
                    jenis_prioritas_obj=jenis_prioritas_obj,
                    tahun_value=tahun_data,
                )
                
                # Skip rows without valid periode_jenis_data (required field)
                if not periode_jenis_data_obj:
                    error_msg = f"Periode '{periode_str}' not found in database"
                    errors.append(f"Tiket {nomor_tiket}: {error_msg}")
                    _log_failed_row(sync_id, nomor_tiket, periode_str, jenis_prioritas_str, tahun_data, error_msg, row_number=idx+1)
                    continue
                
                # Use periode value parsed from Oracle source (e.g., Triwulan I => 1)
                
                # Get status penelitian based on Oracle status_penelitian field
                status_penelitian_obj = None
                status_penelitian_str = row_dict.get('status_penelitian', '').strip().lower()
                if status_penelitian_str:
                    status_penelitian_obj = StatusPenelitian.objects.filter(
                        deskripsi__icontains=status_penelitian_str
                    ).first()
                
                # Make all datetime fields timezone-aware to fix RuntimeWarning
                today = timezone.now().date()
                base_time = timezone.now()
                
                # Prepare tiket data using correct Django field names
                tiket_data = {
                    'nomor_tiket': nomor_tiket,
                    'old_db': row_dict.get('old_db', 1),
                    'status_tiket': row_dict.get('status_tiket') if row_dict.get('status_tiket') is not None else 1,
                    'id_periode_data': periode_jenis_data_obj,  # ForeignKey to PeriodeJenisData (REQUIRED)
                    'id_jenis_prioritas_data': jenis_prioritas_obj,  # ForeignKey to JenisPrioritasData (nullable)
                    'periode': periode_value,
                    'tahun': tahun_data,
                    'penyampaian': row_dict.get('penyampaian', 1),
                    'nomor_surat_pengantar': row_dict.get('nomor_surat_pengantar', '-'),
                    'tanggal_surat_pengantar': _make_aware_datetime(row_dict.get('tanggal_surat_pengantar')),
                    'nama_pengirim': row_dict.get('nama_pengirim', '-'),
                    'id_bentuk_data': default_bentuk_data,
                    'id_cara_penyampaian': default_cara_penyampaian,
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
                
                # Prepare defaults for update_or_create (exclude nomor_tiket and old_db to prevent updates)
                defaults_data = {k: v for k, v in tiket_data.items() if k not in ('nomor_tiket', 'old_db')}
                
                # Create or update tiket with retry logic for database locks
                def db_upsert():
                    return Tiket.objects.update_or_create(
                        nomor_tiket=nomor_tiket,
                        defaults=defaults_data
                    )
                
                # Apply retry decorator logic manually for this operation
                tiket = None
                created = False
                retry_delay = 0.05  # Start with 50ms delay
                max_db_retries = 8
                
                for db_attempt in range(max_db_retries):
                    try:
                        tiket, created = db_upsert()
                        break  # Success, exit retry loop
                    except Exception as db_e:
                        db_error = str(db_e).lower()
                        if 'locked' in db_error and db_attempt < max_db_retries - 1:
                            logger.debug(f"DB lock on upsert {nomor_tiket} (attempt {db_attempt + 1}/{max_db_retries}), retrying in {retry_delay:.3f}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # Exponential backoff
                        else:
                            raise  # Give up or non-lock error
                
                if tiket is None:
                    continue  # Skip if upsert failed
                
                # Assign TiketPICs for new tikets only (to avoid redundant work for updates)
                if created and periode_jenis_data_obj:
                    try:
                        _assign_tiket_pics_sync(tiket, periode_jenis_data_obj, today, base_time, request)
                    except Exception as pic_error:
                        logger.warning(f"Failed to assign PICs for tiket {nomor_tiket}: {str(pic_error)}")
                        # Don't fail the sync if PIC assignment fails
                
                if created:
                    inserts += 1
                    if len(inserted_keys) < 5:
                        inserted_keys.append(nomor_tiket)
                else:
                    updates += 1
                    if len(updated_keys) < 5:
                        updated_keys.append(nomor_tiket)
                
                # Add small delay every 5 rows to reduce database lock contention
                if (idx + 1) % 5 == 0:
                    time.sleep(0.01)  # 10ms delay every 5 rows
                        
            except Exception as e:
                error_msg = str(e)
                # Log database lock errors separately for monitoring
                if 'locked' in error_msg.lower():
                    logger.warning(f"Tiket {row_dict.get('id_tiket', '?')}: database is locked after retries")
                    err_msg = "Database is locked after retries"
                    errors.append(f"Tiket {row_dict.get('id_tiket', '?')}: {err_msg}")
                    _log_failed_row(sync_id, row_dict.get('id_tiket'), row_dict.get('periode_data'), 
                                  row_dict.get('jenis_prioritas_data'), row_dict.get('tahun_data'), 
                                  err_msg, row_number=idx+1)
                else:
                    err_msg = error_msg[:150]
                    errors.append(f"Tiket {row_dict.get('id_tiket', '?')}: {err_msg}")
                    _log_failed_row(sync_id, row_dict.get('id_tiket'), row_dict.get('periode_data'), 
                                  row_dict.get('jenis_prioritas_data'), row_dict.get('tahun_data'), 
                                  err_msg, row_number=idx+1)
        
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
        return {
            'source_rows': 0,
            'inserts': 0,
            'updates': 0,
            'unchanged': 0,
            'errors': [str(e)],
            'inserted_keys': [],
            'updated_keys': [],
        }
