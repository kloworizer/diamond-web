from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from django.utils import timezone
from django.urls import reverse
from datetime import datetime, timedelta
import uuid
import json
import logging
import os
import csv

from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ..tasks import check_referensi_data_task, sync_referensi_data_task

logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
SYNC_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'sync_logs')
os.makedirs(SYNC_LOGS_DIR, exist_ok=True)


@require_GET
@never_cache
def oracle_sync_download_errors(request, sync_id):
    """Download error log CSV file for a completed sync.

    Args:
        request: The HTTP request object.
        sync_id (str): The UUID string identifying the sync run.

    Returns:
        FileResponse: CSV file download if error log exists.
        JsonResponse: JSON error response with appropriate status code
            if the file is not found or the sync_id is invalid.

    Side Effects:
        Opens and streams a CSV file from the filesystem to the client.
    """
    try:
        # Validate sync_id format (UUID)
        try:
            uuid.UUID(sync_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Invalid sync_id format'}, status=400)
        
        error_log_path = os.path.join(SYNC_LOGS_DIR, f'sync_referensi_failed_rows_{sync_id}.csv')
        
        # Check if file exists
        if not os.path.exists(error_log_path):
            return JsonResponse({'success': False, 'message': 'Error log file not found'}, status=404)
        
        # Return file as download
        response = FileResponse(open(error_log_path, 'rb'), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sync_referensi_errors_{sync_id}.csv"'
        return response
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Error downloading sync log: {error_msg}', exc_info=True)
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal download error log'}, status=500)


def _log_failed_row(sync_id, row_identifier, category, error_msg, row_number=None):
    """Log a failed row to CSV file for review and debugging.

    Args:
        sync_id (str): The UUID string identifying the sync run.
        row_identifier (str): Identifier for the failed row (e.g., a key or 'table:key').
        category (str): Category of the failure (e.g., 'Sync Error', 'Skipped Row').
        error_msg (str): Description of the error that occurred.
        row_number (int, optional): The row number in the data source. Defaults to None.

    Returns:
        None

    Side Effects:
        Appends a row to a CSV log file on the filesystem under SYNC_LOGS_DIR.
    """
    try:
        # Create CSV log file for this sync run
        log_filename = os.path.join(SYNC_LOGS_DIR, f'sync_referensi_failed_rows_{sync_id}.csv')
        
        # Write header if file doesn't exist
        file_exists = os.path.exists(log_filename)
        
        with open(log_filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header on first row
            if not file_exists:
                writer.writerow([
                    'Timestamp',
                    'Row Number',
                    'Identifier',
                    'Category',
                    'Error Reason'
                ])
            
            # Write failed row data
            writer.writerow([
                timezone.now().isoformat(),
                row_number or '-',
                row_identifier or '-',
                category or '-',
                error_msg or 'Unknown error'
            ])
        
        logger.debug(f"Failed row logged to {log_filename}")
    except Exception as e:
        logger.error(f"Failed to log error row: {str(e)}")


def _is_admin_user(user):
    """Check if a user is an admin (superuser or belongs to the 'admin' group).

    Args:
        user: The Django user object to check.

    Returns:
        bool: True if the user is a superuser or belongs to the 'admin' group,
            False otherwise.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def oracle_sync_page(request):
    """Render the Oracle sync reference data page.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: The rendered 'oracle_sync/referensi.html' template.
    """
    return render(request, 'oracle_sync/referensi.html')


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def oracle_sync_test_connection(request):
    """Test the connection to Oracle primary (and secondary, if configured) databases.

    Args:
        request: The HTTP POST request object.

    Returns:
        JsonResponse: A JSON response with 'success', 'message', and 'connections'
            keys indicating the status of each database connection.

    Side Effects:
        Establishes and tears down Oracle database connections.
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
def oracle_sync_check(request):
    """Start a background check of reference data integrity against Oracle.

    Args:
        request: The HTTP POST request object.

    Returns:
        JsonResponse: A JSON response containing 'success', 'mode', 'message',
            and 'check_id' if the check was started successfully.

    Side Effects:
        Dispatches a Celery task (check_referensi_data_task) for background
        execution and sets several cache keys for progress tracking.
    """
    try:
        check_id = str(uuid.uuid4())

        cache.set(f'check_referensi_in_progress_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_started_at_{check_id}', datetime.now().isoformat(), timeout=3600)

        task_result = check_referensi_data_task.delay(check_id)
        cache.set(f'check_referensi_celery_task_id_{check_id}', task_result.id, timeout=3600)
        # Fixed key so the page can recover the check_id after navigation
        cache.set('check_referensi_active_check_id', check_id, timeout=3600)

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
    """Deprecated: kept as a thin shim; use check_referensi_data_task instead.

    Args:
        check_id (str): The UUID string identifying the check run.

    Returns:
        None

    Side Effects:
        Dispatches a Celery task to check reference data in the background.
    """
    check_referensi_data_task.delay(check_id)


def _sync_referensi_data_background(sync_id, request_user=None):
    """Deprecated: kept as a thin shim; use sync_referensi_data_task instead.

    Args:
        sync_id (str): The UUID string identifying the sync run.
        request_user (User, optional): The Django user who initiated the sync.
            Defaults to None.

    Returns:
        None

    Side Effects:
        Dispatches a Celery task to sync reference data in the background.
    """
    user_id = getattr(request_user, 'pk', None)
    sync_referensi_data_task.delay(sync_id, user_id)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_run(request):
    """Start a background sync of reference data from Oracle to Django models.

    Args:
        request: The HTTP POST request object.

    Returns:
        JsonResponse: A JSON response containing 'success', 'message', and 'sync_id'
            if the sync was started successfully.

    Side Effects:
        Dispatches a Celery task (sync_referensi_data_task) for background
        execution and sets several cache keys for progress tracking.
    """
    try:
        sync_id = str(uuid.uuid4())

        # Initialize cache values for progress tracking BEFORE dispatching
        cache.set(f'sync_referensi_in_progress_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', False, timeout=3600)
        cache.set(f'sync_referensi_started_at_{sync_id}', datetime.now().isoformat(), timeout=3600)

        task_result = sync_referensi_data_task.delay(sync_id, request.user.pk)
        cache.set(f'sync_referensi_celery_task_id_{sync_id}', task_result.id, timeout=3600)
        # Fixed key so the page can recover the sync_id after navigation
        cache.set('sync_referensi_active_sync_id', sync_id, timeout=3600)

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
    """Stop an in-progress sync operation (no auth check to avoid session locks).

    Args:
        request: The HTTP POST request object containing 'sync_id' in the body.

    Returns:
        JsonResponse: A JSON response confirming the stop request was received.

    Side Effects:
        Revokes the associated Celery task and updates cache keys to mark the
        sync as stopped with an error message.
    """
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        sync_id = data.get('sync_id', '')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)

        # Revoke and terminate the Celery task if we have its task ID
        celery_task_id = cache.get(f'sync_referensi_celery_task_id_{sync_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for sync {sync_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')

        cache.set(f'sync_referensi_stop_requested_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_error_{sync_id}', 'Sync dihentikan oleh pengguna', timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)

        return JsonResponse({
            'success': True,
            'message': 'Permintaan stop sync telah dikirim.',
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal menghentikan sync'}, status=500)


@require_POST
@never_cache
def oracle_sync_stop_check(request):
    """Stop an in-progress check operation.

    Args:
        request: The HTTP POST request object containing 'check_id' in the body.

    Returns:
        JsonResponse: A JSON response confirming the stop request was received.

    Side Effects:
        Revokes the associated Celery task and updates cache keys to mark the
        check as stopped with an error message.
    """
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        check_id = data.get('check_id', '')
        if not check_id:
            return JsonResponse({'success': False, 'message': 'check_id tidak ditemukan'}, status=400)
        
        # Revoke and terminate the Celery task if we have its task ID
        celery_task_id = cache.get(f'check_referensi_celery_task_id_{check_id}')
        if celery_task_id:
            try:
                from celery import current_app
                current_app.control.revoke(celery_task_id, terminate=True, signal='SIGTERM')
                logger.info(f'Revoked Celery task {celery_task_id} for check {check_id}')
            except Exception as revoke_err:
                logger.warning(f'Failed to revoke Celery task {celery_task_id}: {revoke_err}')
        
        cache.set(f'check_referensi_stop_requested_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_error_{check_id}', 'Cek Data dihentikan oleh pengguna', timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        
        return JsonResponse({
            'success': True,
            'message': 'Permintaan stop cek data telah dikirim.',
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal menghentikan cek data'}, status=500)


@require_POST
@never_cache
def oracle_sync_clear_session(request):
    """Clear a sync session by deleting all related cache keys.

    Args:
        request: The HTTP POST request object containing 'sync_id' in the body.

    Returns:
        JsonResponse: A JSON response indicating whether the session was cleared.

    Side Effects:
        Deletes all cache keys associated with the given sync_id from the cache.
    """
    try:
        sync_id = request.POST.get('sync_id', '')
        if not sync_id:
            return JsonResponse({'success': False, 'message': 'sync_id tidak ditemukan'}, status=400)
        
        # Delete all cache keys related to this sync
        cache_keys = [
            f'sync_referensi_in_progress_{sync_id}',
            f'sync_referensi_done_{sync_id}',
            f'sync_referensi_started_at_{sync_id}',
            f'sync_referensi_result_{sync_id}',
            f'sync_referensi_error_{sync_id}',
            f'sync_referensi_stop_requested_{sync_id}',
            f'sync_referensi_celery_task_id_{sync_id}',
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        # Also clear the fixed active-ID key if it still points to this sync
        if cache.get('sync_referensi_active_sync_id') == sync_id:
            cache.delete('sync_referensi_active_sync_id')
        
        return JsonResponse({
            'success': True,
            'message': f'Session {sync_id} cleared.',
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal clear session'}, status=500)


@require_GET
@never_cache
def oracle_sync_progress(request):
    """Get current progress of an in-progress sync or check operation.

    No auth check to avoid session locks during long operations.

    Args:
        request: The HTTP GET request object with query parameters:
            - mode (str): Either 'sync', 'check', or 'active'.
            - sync_id (str, optional): Required when mode is 'sync'.
            - check_id (str, optional): Required when mode is 'check'.

    Returns:
        JsonResponse: A JSON response with the current progress, result,
            or error status depending on the state of the operation.

    Side Effects:
        Reads cache keys for progress tracking (no write operations).
    """
    try:
        mode = request.GET.get('mode', 'sync')

        # Probe: return active sync_id or check_id from the fixed cache key
        if mode == 'active':
            active_sync_id = cache.get('sync_referensi_active_sync_id')
            if active_sync_id and not cache.get(f'sync_referensi_done_{active_sync_id}', False):
                return JsonResponse({'success': True, 'active': True, 'type': 'sync', 'sync_id': active_sync_id})
            active_check_id = cache.get('check_referensi_active_check_id')
            if active_check_id and not cache.get(f'check_referensi_done_{active_check_id}', False):
                return JsonResponse({'success': True, 'active': True, 'type': 'check', 'check_id': active_check_id})
            return JsonResponse({'success': True, 'active': False})

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

            progress = cache.get(f'check_referensi_progress_{check_id}')
            return JsonResponse({
                'success': True,
                'done': False,
                'mode': 'check',
                'message': 'Check data masih berjalan...',
                'progress': progress,
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
            
            # Build response with download link if error log exists
            response_data = {
                'success': True,
                'done': True,
                'result': result or {},
            }
            
            # Add error log download URL if errors were logged
            error_log_path = os.path.join(SYNC_LOGS_DIR, f'sync_referensi_failed_rows_{sync_id}.csv')
            if os.path.exists(error_log_path):
                response_data['error_log_url'] = reverse('oracle_sync_download_errors', kwargs={'sync_id': sync_id})
            
            return JsonResponse(response_data)
        
        # Still in progress
        progress = cache.get(f'sync_referensi_progress_{sync_id}')
        return JsonResponse({
            'success': True,
            'done': False,
            'message': 'Sync masih berjalan...',
            'progress': progress,
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg or 'Gagal mendapatkan progress'}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_truncate(request):
    """Truncate all reference data tables that are synced and reset auto-increment.

    Args:
        request: The HTTP POST request object.

    Returns:
        JsonResponse: A JSON response with details of which tables were truncated,
            how many succeeded, and any errors encountered.

    Side Effects:
        Deletes all rows from reference data tables, resets auto-increment
        sequences, and temporarily disables/re-enables foreign key constraints
        and triggers depending on the database vendor.
    """
    try:
        from django.conf import settings
        if settings.ENVIRONMENT == 'production':
            return JsonResponse({
                'success': False,
                'message': 'Truncate tidak diizinkan di lingkungan production.'
            }, status=403)

        from django.db import connection
        from django.apps import apps
        from ..utils.oracle_sync import HARD_CODED_SYNC_TABLES
        
        # Extract table names dynamically from HARD_CODED_SYNC_TABLES configurations
        tables_to_truncate = []
        failed_configs = []
        
        for config in HARD_CODED_SYNC_TABLES:
            try:
                # Check if config has target_model_label
                if not hasattr(config, 'target_model_label') or not config.target_model_label:
                    logger.warning(f"Config {config.name} has no target_model_label, skipping")
                    failed_configs.append((config.name, "No target_model_label"))
                    continue
                
                # Parse target_model_label (e.g., "diamond_web.KategoriILAP")
                parts = config.target_model_label.split('.')
                if len(parts) != 2:
                    logger.warning(f"Invalid target_model_label format for {config.name}: {config.target_model_label}")
                    failed_configs.append((config.name, f"Invalid label format: {config.target_model_label}"))
                    continue
                
                app_label, model_name = parts
                model = apps.get_model(app_label, model_name)
                table_name = model._meta.db_table
                if table_name not in tables_to_truncate:
                    tables_to_truncate.append(table_name)
                    logger.info(f"Identified table for truncate: {table_name} (from {config.name})")
                else:
                    logger.info(f"Table {table_name} already in truncate list (from {config.name})")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to identify table for {config.name}: {error_msg}")
                failed_configs.append((config.name, error_msg))
        
        if not tables_to_truncate:
            error_detail = "; ".join([f"{name}: {err}" for name, err in failed_configs]) if failed_configs else "Unknown error"
            return JsonResponse({
                'success': False,
                'message': f'No tables found to truncate. Details: {error_detail}'
            }, status=400)
        
        truncated_count = 0
        truncate_errors = []
        db_vendor = connection.vendor  # 'sqlite', 'postgresql', 'mysql'
        
        logger.info(f'Starting truncate for {len(tables_to_truncate)} tables: {tables_to_truncate}')
        
        # Store constraint definitions for PostgreSQL
        constraint_definitions = []
        
        with connection.cursor() as cursor:
            try:
                # Disable foreign key checks before truncating to handle dependencies
                if db_vendor == 'sqlite':
                    logger.info('Disabling foreign key checks for SQLite')
                    cursor.execute('PRAGMA foreign_keys = OFF')
                elif db_vendor == 'mysql':
                    logger.info('Disabling foreign key checks for MySQL')
                    cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
                elif db_vendor == 'postgresql':
                    # PostgreSQL: Save and disable all constraints temporarily
                    logger.info('Saving and disabling constraints for PostgreSQL')
                    for table_name in tables_to_truncate:
                        try:
                            # Disable all triggers on the table
                            cursor.execute(f'ALTER TABLE {table_name} DISABLE TRIGGER ALL')
                            logger.info(f'Disabled triggers for {table_name}')
                        except Exception as e:
                            logger.warning(f'Could not disable triggers for {table_name}: {str(e)}')
                    
                    # Get all foreign key constraints for later recreation
                    try:
                        cursor.execute("""
                            SELECT tc.constraint_name, tc.table_name, tc.table_schema,
                                   kcu.column_name, ccu.table_name AS foreign_table_name,
                                   ccu.column_name AS foreign_column_name,
                                   rc.update_rule, rc.delete_rule
                            FROM information_schema.table_constraints AS tc
                            JOIN information_schema.key_column_usage AS kcu
                              ON tc.constraint_name = kcu.constraint_name
                              AND tc.table_schema = kcu.table_schema
                            JOIN information_schema.constraint_column_usage AS ccu
                              ON ccu.constraint_name = tc.constraint_name
                              AND ccu.table_schema = tc.table_schema
                            JOIN information_schema.referential_constraints AS rc
                              ON rc.constraint_name = tc.constraint_name
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                        """)
                        constraints = cursor.fetchall()
                        constraint_definitions = constraints
                        
                        # Drop all foreign key constraints
                        for constraint_name, table_name, table_schema, *rest in constraints:
                            try:
                                cursor.execute(f'ALTER TABLE "{table_schema}"."{table_name}" DROP CONSTRAINT "{constraint_name}"')
                                logger.info(f'Dropped constraint {constraint_name} on {table_name}')
                            except Exception as e:
                                logger.warning(f'Could not drop constraint {constraint_name}: {str(e)}')
                    except Exception as e:
                        logger.warning(f'Error managing constraints: {str(e)}')
                
                # Delete/Truncate tables
                for table_name in tables_to_truncate:
                    try:
                        if db_vendor == 'sqlite':
                            # SQLite uses DELETE instead of TRUNCATE
                            cursor.execute(f'DELETE FROM {table_name}')
                            logger.info(f'Cleared table (DELETE): {table_name}')
                        elif db_vendor == 'postgresql':
                            # PostgreSQL uses DELETE (all constraints are already dropped)
                            cursor.execute(f'DELETE FROM {table_name}')
                            logger.info(f'Cleared table (DELETE): {table_name}')
                        elif db_vendor == 'mysql':
                            # MySQL uses TRUNCATE TABLE
                            cursor.execute(f'TRUNCATE TABLE {table_name}')
                            logger.info(f'Truncated table: {table_name}')
                        
                        truncated_count += 1
                    except Exception as e:
                        error_detail = str(e)
                        logger.error(f'Failed to clear {table_name}: {error_detail}')
                        truncate_errors.append(f"{table_name}: {error_detail}")
                
                # Reset auto-increment sequences (database-agnostic)
                for table_name in tables_to_truncate:
                    try:
                        if db_vendor == 'sqlite':
                            cursor.execute(f'DELETE FROM sqlite_sequence WHERE name="{table_name}"')
                        elif db_vendor == 'postgresql':
                            # PostgreSQL: reset sequence for each table
                            seq_name = f'{table_name}_id_seq'
                            try:
                                cursor.execute(f"SELECT setval('{seq_name}', 1)")
                                logger.info(f'Reset sequence: {seq_name}')
                            except Exception:
                                # Sequence might not exist, skip silently
                                pass
                        elif db_vendor == 'mysql':
                            # MySQL: TRUNCATE already resets auto_increment
                            # For DELETE, we need to reset it manually
                            cursor.execute(f'ALTER TABLE {table_name} AUTO_INCREMENT = 1')
                    except Exception as e:
                        error_detail = str(e)
                        logger.error(f'Failed to reset sequence for {table_name}: {error_detail}')
                        # Don't add to errors list since truncate itself succeeded
                
                # Re-enable foreign key checks and constraints
                if db_vendor == 'sqlite':
                    logger.info('Re-enabling foreign key checks for SQLite')
                    cursor.execute('PRAGMA foreign_keys = ON')
                elif db_vendor == 'mysql':
                    logger.info('Re-enabling foreign key checks for MySQL')
                    cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
                elif db_vendor == 'postgresql':
                    # Recreate foreign key constraints
                    logger.info('Recreating foreign key constraints for PostgreSQL')
                    if constraint_definitions:
                        for constraint_name, table_name, table_schema, column_name, foreign_table_name, foreign_column_name, update_rule, delete_rule in constraint_definitions:
                            try:
                                # Build the foreign key constraint
                                fk_sql = f'ALTER TABLE "{table_schema}"."{table_name}" ADD CONSTRAINT "{constraint_name}" FOREIGN KEY ("{column_name}") REFERENCES "{foreign_table_name}"("{foreign_column_name}")'
                                
                                # Add update and delete rules if specified
                                if update_rule and update_rule != 'RESTRICT':
                                    fk_sql += f' ON UPDATE {update_rule}'
                                if delete_rule and delete_rule != 'RESTRICT':
                                    fk_sql += f' ON DELETE {delete_rule}'
                                
                                cursor.execute(fk_sql)
                                logger.info(f'Recreated constraint {constraint_name}')
                            except Exception as e:
                                logger.warning(f'Could not recreate constraint {constraint_name}: {str(e)}')
                    
                    # Re-enable triggers
                    logger.info('Re-enabling triggers for PostgreSQL')
                    for table_name in tables_to_truncate:
                        try:
                            cursor.execute(f'ALTER TABLE {table_name} ENABLE TRIGGER ALL')
                            logger.info(f'Enabled triggers for {table_name}')
                        except Exception as e:
                            logger.warning(f'Could not enable triggers for {table_name}: {str(e)}')
                    
            except Exception as e:
                # Log the error
                logger.error(f'Error during truncate: {str(e)}')
                raise e
        
        message = f'Tabel referensi berhasil dihapus ({truncated_count} dari {len(tables_to_truncate)} tabel).'
        if truncate_errors:
            message += f' Errors: {"; ".join(truncate_errors)}'
        
        return JsonResponse({
            'success': truncated_count == len(tables_to_truncate),
            'message': message,
            'truncated_tables': truncated_count,
            'total_tables': len(tables_to_truncate),
            'tables': tables_to_truncate,
            'errors': truncate_errors,
        })
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg:
            error_msg = 'Gagal menghapus tabel referensi'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


def _sync_referensi_data(service, sync_id=None, request=None, progress_callback=None):
    """Sync reference data from Oracle to Django models.

    Args:
        service (OracleDataSyncService): The Oracle data sync service instance.
        sync_id (str, optional): Unique identifier for this sync run for
            progress tracking. Defaults to None.
        request: Django request object (for logging current user). Defaults to None.
        progress_callback (callable, optional): Callable for per-table progress
            updates. Defaults to None.

    Returns:
        dict: A summary dictionary of the sync results.

    Raises:
        Exception: If an error occurs during the sync process; the exception
            is logged before being re-raised.
    """
    try:
        summary = service.sync(progress_callback=progress_callback)
        summary_dict = summary.as_dict() if hasattr(summary, 'as_dict') else {'message': 'Sync completed'}
        
        # Log any errors to CSV file
        has_data_to_log = False
        
        if sync_id and hasattr(summary, 'errors') and summary.errors:
            has_data_to_log = True
            for idx, error_msg in enumerate(summary.errors, 1):
                _log_failed_row(
                    sync_id,
                    row_identifier=f"Error {idx}",
                    category="Sync Error",
                    error_msg=error_msg,
                    row_number=idx
                )
        
        # Log skipped rows from table summaries (per-row detail)
        if sync_id and hasattr(summary, 'table_summaries') and summary.table_summaries:
            for table_summary in summary.table_summaries:
                skipped_detail = getattr(table_summary, 'skipped_rows_detail', [])
                if skipped_detail:
                    has_data_to_log = True
                    table_name = getattr(table_summary, 'table_name', 'unknown')
                    for detail in skipped_detail:
                        _log_failed_row(
                            sync_id,
                            row_identifier=f"{table_name}:{detail.get('key', '-')}",
                            category="Skipped Row (FK missing)",
                            error_msg=detail.get('reason', 'Unknown'),
                            row_number=detail.get('row_number')
                        )
        
        # Store flag indicating if error log exists
        if sync_id and has_data_to_log:
            summary_dict['has_error_log'] = True
        
        return summary_dict
    except Exception as e:
        logger.error(f'Error in referensi sync: {str(e)}', exc_info=True)
        raise
