from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from datetime import datetime, timedelta
import uuid
import threading
import logging

from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError

logger = logging.getLogger(__name__)


def _is_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def oracle_sync_page(request):
    return render(request, 'oracle_sync/referensi.html')


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def oracle_sync_test_connection(request):
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
def oracle_sync_check(request):
    try:
        check_id = str(uuid.uuid4())

        bg_thread = threading.Thread(
            target=_check_referensi_data_background,
            args=(check_id,),
            daemon=True
        )
        bg_thread.start()

        cache.set(f'check_referensi_in_progress_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_started_at_{check_id}', datetime.now().isoformat(), timeout=3600)

        return JsonResponse({
            'success': True,
            'mode': 'check',
            'message': 'Check data dimulai di background.',
            'check_id': check_id,
        })
    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan check data. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


def _check_referensi_data_background(check_id):
    """Run check data in background thread to avoid reverse proxy timeout."""
    try:
        logger.info(f'[BG] Starting referensi check (check_id={check_id})...')
        service = OracleDataSyncService()
        summary = service.check()
        summary_dict = summary.as_dict() if hasattr(summary, 'as_dict') else {}

        cache.set(f'check_referensi_result_{check_id}', summary_dict, timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_in_progress_{check_id}', False, timeout=3600)
        logger.info(f'[BG] Referensi check completed (check_id={check_id})')
    except Exception as e:
        logger.error(f'[BG] Exception in background check: {str(e)}', exc_info=True)
        cache.set(f'check_referensi_error_{check_id}', str(e), timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_in_progress_{check_id}', False, timeout=3600)


def _sync_referensi_data_background(sync_id, request_user=None):
    """Run sync in background thread."""
    try:
        logger.info(f'[BG] Starting referensi sync (sync_id={sync_id})...')
        service = OracleDataSyncService()
        logger.info(f'[BG] OracleDataSyncService initialized')
        
        class FakeRequest:
            def __init__(self, user):
                self.user = user
        
        fake_request = FakeRequest(request_user) if request_user else None
        sync_summary = _sync_referensi_data(service, sync_id=sync_id, request=fake_request)
        logger.info(f'[BG] Referensi sync completed (sync_id={sync_id}): {sync_summary}')
        
        # Cache the final result
        cache.set(f'sync_referensi_result_{sync_id}', sync_summary, timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)
    except Exception as e:
        logger.error(f'[BG] Exception in background sync: {str(e)}', exc_info=True)
        cache.set(f'sync_referensi_error_{sync_id}', str(e), timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_run(request):
    try:
        sync_id = str(uuid.uuid4())
        
        # Start background thread
        bg_thread = threading.Thread(
            target=_sync_referensi_data_background,
            args=(sync_id, request.user),
            daemon=True
        )
        bg_thread.start()
        
        # Initialize cache values for progress tracking
        cache.set(f'sync_referensi_in_progress_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_started_at_{sync_id}', datetime.now().isoformat(), timeout=3600)
        
        return JsonResponse({
            'success': True,
            'message': 'Sync referensi dimulai di background.',
            'sync_id': sync_id,
        })
    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal memulai sync referensi. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@require_POST
@never_cache
def oracle_sync_stop(request):
    """Stop an in-progress sync operation (no auth check to avoid session locks)."""
    try:
        sync_id = request.POST.get('sync_id', '')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)
        
        # Set stop signal in cache
        cache.set(f'sync_referensi_stop_requested_{sync_id}', True, timeout=3600)
        
        return JsonResponse({
            'success': True,
            'message': 'Permintaan stop sync telah dikirim.',
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal menghentikan sync'}, status=500)


@require_GET
@never_cache
def oracle_sync_progress(request):
    """Get current progress of in-progress sync/check (no auth check to avoid session locks during long operations)."""
    try:
        mode = request.GET.get('mode', 'sync')

        if mode == 'check':
            check_id = request.GET.get('check_id', '')
            if not check_id:
                return JsonResponse({'success': False, 'message': 'check_id tidak ditemukan'}, status=400)

            is_done = cache.get(f'check_referensi_done_{check_id}', False)
            if is_done:
                result = cache.get(f'check_referensi_result_{check_id}')
                error = cache.get(f'check_referensi_error_{check_id}')

                if error:
                    return JsonResponse({
                        'success': False,
                        'done': True,
                        'mode': 'check',
                        'message': error,
                    })

                return JsonResponse({
                    'success': True,
                    'done': True,
                    'mode': 'check',
                    'result': result or {},
                })

            return JsonResponse({
                'success': True,
                'done': False,
                'mode': 'check',
                'message': 'Check data masih berjalan...',
            })

        sync_id = request.GET.get('sync_id', '')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)
        
        # Check if sync is done
        is_done = cache.get(f'sync_referensi_done_{sync_id}', False)
        
        if is_done:
            # Get final result or error
            result = cache.get(f'sync_referensi_result_{sync_id}')
            error = cache.get(f'sync_referensi_error_{sync_id}')
            
            if error:
                return JsonResponse({
                    'success': False,
                    'done': True,
                    'message': error,
                })
            
            return JsonResponse({
                'success': True,
                'done': True,
                'result': result or {},
            })
        
        # Still in progress
        return JsonResponse({
            'success': True,
            'done': False,
            'message': 'Sync masih berjalan...',
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal mendapatkan progress'}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_truncate(request):
    """Truncate all reference data tables that are synced and reset auto-increment."""
    try:
        from django.db import connection
        from django.apps import apps
        from ..utils.oracle_sync import HARD_CODED_SYNC_TABLES
        
        # Extract table names dynamically from HARD_CODED_SYNC_TABLES configurations
        tables_to_truncate = []
        for config in HARD_CODED_SYNC_TABLES:
            try:
                # Parse target_model_label (e.g., "diamond_web.KategoriILAP")
                app_label, model_name = config.target_model_label.split('.')
                model = apps.get_model(app_label, model_name)
                table_name = model._meta.db_table
                if table_name not in tables_to_truncate:
                    tables_to_truncate.append(table_name)
                logger.info(f"Identified table for truncate: {table_name} (from {config.name})")
            except Exception as e:
                logger.warning(f"Failed to identify table for {config.name}: {str(e)}")
        
        if not tables_to_truncate:
            return JsonResponse({
                'success': False,
                'message': 'No tables found to truncate from sync configurations.'
            }, status=400)
        
        truncated_count = 0
        db_vendor = connection.vendor  # 'sqlite', 'postgresql', 'mysql'
        
        with connection.cursor() as cursor:
            try:
                # Truncate tables (database-agnostic)
                for table_name in tables_to_truncate:
                    try:
                        if db_vendor == 'sqlite':
                            # SQLite uses DELETE instead of TRUNCATE
                            cursor.execute(f'DELETE FROM {table_name}')
                        elif db_vendor == 'postgresql':
                            # PostgreSQL uses TRUNCATE CASCADE to handle dependencies
                            cursor.execute(f'TRUNCATE TABLE {table_name} CASCADE')
                        elif db_vendor == 'mysql':
                            # MySQL uses TRUNCATE TABLE
                            cursor.execute(f'TRUNCATE TABLE {table_name}')
                        
                        truncated_count += 1
                        logger.info(f'Truncated table: {table_name}')
                    except Exception as e:
                        logger.debug(f'Failed to truncate {table_name}: {str(e)}')
                        # Continue with other tables
                
                # Reset auto-increment sequences (database-agnostic)
                for table_name in tables_to_truncate:
                    try:
                        if db_vendor == 'sqlite':
                            cursor.execute(f'DELETE FROM sqlite_sequence WHERE name="{table_name}"')
                        elif db_vendor == 'postgresql':
                            # PostgreSQL: reset sequence for each table
                            seq_name = f'{table_name}_id_seq'
                            cursor.execute(f"SELECT setval('{seq_name}', 1)")
                        elif db_vendor == 'mysql':
                            # MySQL: TRUNCATE already resets auto_increment
                            pass
                    except Exception as e:
                        logger.debug(f'Failed to reset sequence for {table_name}: {str(e)}')
            except Exception as e:
                # Log the error
                logger.error(f'Error during truncate: {str(e)}')
                raise e
        
        return JsonResponse({
            'success': True,
            'message': f'Tabel referensi berhasil dihapus ({truncated_count} tabel).',
            'truncated_tables': truncated_count,
            'tables': tables_to_truncate,
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg:
            error_msg = 'Gagal menghapus tabel referensi'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


def _sync_referensi_data(service, sync_id=None, request=None):
    """Sync reference data from Oracle to Django models.
    
    Args:
    - service: OracleDataSyncService instance
    - sync_id: Unique identifier for this sync run (for progress tracking)
    - request: Django request object (for logging current user)
    """
    try:
        summary = service.sync()
        return summary.as_dict() if hasattr(summary, 'as_dict') else {'message': 'Sync completed'}
    except Exception as e:
        logger.error(f'Error in referensi sync: {str(e)}', exc_info=True)
        raise
