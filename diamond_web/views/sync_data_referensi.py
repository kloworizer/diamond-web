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
    """Download error log CSV file for a completed sync."""
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
    """Log a failed row to CSV file for review and debugging."""
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

        cache.set(f'check_referensi_in_progress_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_started_at_{check_id}', datetime.now().isoformat(), timeout=3600)

        check_referensi_data_task.delay(check_id)

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
    """Deprecated: kept as a thin shim; use check_referensi_data_task instead."""
    check_referensi_data_task.delay(check_id)


def _sync_referensi_data_background(sync_id, request_user=None):
    """Deprecated: kept as a thin shim; use sync_referensi_data_task instead."""
    user_id = getattr(request_user, 'pk', None)
    sync_referensi_data_task.delay(sync_id, user_id)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_run(request):
    try:
        sync_id = str(uuid.uuid4())

        # Initialize cache values for progress tracking BEFORE dispatching
        cache.set(f'sync_referensi_in_progress_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', False, timeout=3600)
        cache.set(f'sync_referensi_started_at_{sync_id}', datetime.now().isoformat(), timeout=3600)

        sync_referensi_data_task.delay(sync_id, request.user.pk)

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


@require_POST
@never_cache
def oracle_sync_clear_session(request):
    """Clear a sync session by deleting all related cache keys."""
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
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
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
    """Truncate all reference data tables that are synced and reset auto-increment."""
    try:
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
    - service: OracleDataSyncService instance
    - sync_id: Unique identifier for this sync run (for progress tracking)
    - request: Django request object (for logging current user)
    - progress_callback: optional callable for per-table progress updates
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
        
        # Log skipped rows from table summaries
        if sync_id and hasattr(summary, 'table_summaries') and summary.table_summaries:
            row_idx = 1
            for table_summary in summary.table_summaries:
                # Calculate skipped rows: source_rows - (inserts + updates + unchanged)
                if hasattr(table_summary, 'source_rows'):
                    total_processed = (
                        getattr(table_summary, 'inserts', 0) + 
                        getattr(table_summary, 'updates', 0) + 
                        getattr(table_summary, 'unchanged', 0)
                    )
                    skipped = table_summary.source_rows - total_processed
                    
                    if skipped > 0:
                        has_data_to_log = True
                        table_name = getattr(table_summary, 'table_name', 'unknown')
                        _log_failed_row(
                            sync_id,
                            row_identifier=f"{table_name}",
                            category="Skipped Rows",
                            error_msg=f"{skipped} row(s) skipped due to foreign key constraint or validation errors",
                            row_number=row_idx
                        )
                        row_idx += 1
        
        # Store flag indicating if error log exists
        if sync_id and has_data_to_log:
            summary_dict['has_error_log'] = True
        
        return summary_dict
    except Exception as e:
        logger.error(f'Error in referensi sync: {str(e)}', exc_info=True)
        raise
