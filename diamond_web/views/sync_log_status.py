import os
import re
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

logger = __import__('logging').getLogger(__name__)

# Path to sync_logs directory (same as in sync_tiket.py and sync_data_referensi.py)
SYNC_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'sync_logs'
)

# Regex to parse log filenames: <type>_YYYY-MM-DD_HH-MM-SS.log
LOG_FILENAME_PATTERN = re.compile(
    r'^(.+)_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})\.log$'
)

# Regex for error log files without timestamp: <type>_error.log
ERROR_LOG_PATTERN = re.compile(
    r'^(.+)_error\.log$'
)

# Regex for failed rows CSV: sync_failed_rows_<uuid>.csv
FAILED_ROWS_CSV_PATTERN = re.compile(
    r'^sync_failed_rows_([a-f0-9\-]+)\.csv$'
)

# Regex for referensi failed rows CSV: sync_referensi_failed_rows_<uuid>.csv
REFERENSI_FAILED_ROWS_CSV_PATTERN = re.compile(
    r'^sync_referensi_failed_rows_([a-f0-9\-]+)\.csv$'
)


def _is_admin_user(user):
    """Check if the given user is an admin user."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name='admin').exists()


def _get_file_timestamp(filepath):
    """Get the modification timestamp of a file.

    Args:
        filepath (str): Full path to the file.

    Returns:
        datetime or None: The file's modification time, or None on error.
    """
    try:
        mod_time = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mod_time)
    except OSError:
        return None


def _get_sync_logs():
    """Scan the sync_logs directory and return parsed log entries.

    Returns:
        list of dict: Each entry contains:
            - sync_type (str): The type of sync (e.g., 'daily_sync', 'tiket_sync')
            - sync_type_display (str): Human-readable sync type name
            - timestamp (datetime or None): The parsed timestamp
            - filename (str): The actual filename
            - filepath (str): Full path to the file
            - file_size (int): File size in bytes
    """
    log_entries = []

    if not os.path.isdir(SYNC_LOGS_DIR):
        return log_entries

    try:
        for filename in os.listdir(SYNC_LOGS_DIR):
            filepath = os.path.join(SYNC_LOGS_DIR, filename)

            if not os.path.isfile(filepath):
                continue

            # --- 1. Try matching standard .log files: <type>_YYYY-MM-DD_HH-MM-SS.log ---
            match = LOG_FILENAME_PATTERN.match(filename)
            if match:
                sync_type = match.group(1)
                date_str = match.group(2)
                time_str = match.group(3).replace('-', ':')
                try:
                    timestamp = datetime.strptime(
                        f'{date_str} {time_str}',
                        '%Y-%m-%d %H:%M:%S'
                    )
                except ValueError:
                    timestamp = _get_file_timestamp(filepath)

                log_entries.append({
                    'sync_type': sync_type,
                    'sync_type_display': _get_type_display_name(sync_type),
                    'timestamp': timestamp,
                    'filename': filename,
                    'filepath': filepath,
                    'file_size': os.path.getsize(filepath),
                })
                continue

            # --- 2. Try error log pattern (no timestamp in name): <type>_error.log ---
            err_match = ERROR_LOG_PATTERN.match(filename)
            if err_match:
                sync_type = err_match.group(1)
                log_entries.append({
                    'sync_type': sync_type,
                    'sync_type_display': _get_type_display_name(sync_type),
                    'timestamp': _get_file_timestamp(filepath),
                    'filename': filename,
                    'filepath': filepath,
                    'file_size': os.path.getsize(filepath),
                })
                continue

            # --- 3. Try failed rows CSV: sync_failed_rows_<uuid>.csv ---
            csv_match = FAILED_ROWS_CSV_PATTERN.match(filename)
            if csv_match:
                log_entries.append({
                    'sync_type': 'sync_failed_rows',
                    'sync_type_display': 'Tiket Sync (Failed Rows)',
                    'timestamp': _get_file_timestamp(filepath),
                    'filename': filename,
                    'filepath': filepath,
                    'file_size': os.path.getsize(filepath),
                })
                continue

            # --- 4. Try referensi failed rows CSV: sync_referensi_failed_rows_<uuid>.csv ---
            ref_csv_match = REFERENSI_FAILED_ROWS_CSV_PATTERN.match(filename)
            if ref_csv_match:
                log_entries.append({
                    'sync_type': 'sync_referensi_failed_rows',
                    'sync_type_display': 'Referensi Sync (Failed Rows)',
                    'timestamp': _get_file_timestamp(filepath),
                    'filename': filename,
                    'filepath': filepath,
                    'file_size': os.path.getsize(filepath),
                })
                continue

    except OSError as exc:
        logger.error(f'Error reading sync_logs directory: {exc}')

    return log_entries


def _get_type_display_name(sync_type):
    """Convert a sync type slug to a human-readable display name.

    Args:
        sync_type (str): The raw sync type (e.g., 'daily_sync', 'cleanup_dryrun')

    Returns:
        str: Human-readable name (e.g., 'Daily Sync', 'Cleanup Dry Run')
    """
    # Map known sync types to display names
    display_map = {
        'daily_sync': 'Daily Sync',
        'referensi_sync': 'Sinkronisasi Data Referensi',
        'tiket_sync': 'Sinkronisasi Data Tiket',
        'cleanup_dryrun': 'Cleanup (Dry Run)',
        'cleanup_exec': 'Cleanup (Execute)',
        'cleanup_pre_production': 'Cleanup Pre Production',
        'cleanup_verify': 'Cleanup Verify',
        'cleanup_pre_production_error': 'Cleanup Pre Production (Error)',
        'sync_failed_rows': 'Tiket Sync (Failed Rows)',
        'sync_referensi_failed_rows': 'Referensi Sync (Failed Rows)',
    }
    # For unknown types, convert underscores to spaces and title-case
    if sync_type in display_map:
        return display_map[sync_type]
    return sync_type.replace('_', ' ').title()


def _get_latest_per_type(log_entries):
    """Group log entries by sync type and return only the latest for each type.

    Args:
        log_entries (list): List of log entry dicts from _get_sync_logs()

    Returns:
        list of dict: One entry per sync type, sorted by type name,
            containing the latest log file info.
    """
    latest = {}
    for entry in log_entries:
        sync_type = entry['sync_type']
        if sync_type not in latest:
            latest[sync_type] = entry
        else:
            existing = latest[sync_type]
            # Keep the one with the later timestamp
            if existing['timestamp'] and entry['timestamp']:
                if entry['timestamp'] > existing['timestamp']:
                    latest[sync_type] = entry
            elif entry['timestamp'] and not existing['timestamp']:
                latest[sync_type] = entry

    # Sort by display name
    result = sorted(latest.values(), key=lambda x: x['sync_type_display'].lower())
    return result


@login_required
@user_passes_test(_is_admin_user)
@require_GET
@never_cache
def sync_log_status(request):
    """Render the sync log status page showing the latest run of each sync type.

    Args:
        request: The incoming HTTP request.

    Returns:
        HttpResponse with the rendered sync_log_status.html template.
    """
    log_entries = _get_sync_logs()
    latest_logs = _get_latest_per_type(log_entries)

    context = {
        'latest_logs': latest_logs,
    }
    return render(request, 'oracle_sync/sync_log_status.html', context)


@login_required
@user_passes_test(_is_admin_user)
@require_GET
def sync_log_download(request, filename):
    """Download a log file from the sync_logs directory.

    Args:
        request: The incoming HTTP request.
        filename (str): The log filename to download.

    Returns:
        FileResponse with the log file content, or 404 if not found.
    """
    # Security: prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return JsonResponse(
            {'success': False, 'message': 'Invalid filename'},
            status=400
        )

    filepath = os.path.join(SYNC_LOGS_DIR, filename)

    # Ensure the resolved path is within SYNC_LOGS_DIR
    try:
        resolved = os.path.realpath(filepath)
        sync_logs_real = os.path.realpath(SYNC_LOGS_DIR)
        if not resolved.startswith(sync_logs_real):
            return JsonResponse(
                {'success': False, 'message': 'Access denied'},
                status=403
            )
    except OSError:
        return JsonResponse(
            {'success': False, 'message': 'Invalid file path'},
            status=400
        )

    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return JsonResponse(
            {'success': False, 'message': 'File not found'},
            status=404
        )

    try:
        # Determine content type based on extension
        content_type = 'text/plain'
        if filename.endswith('.csv'):
            content_type = 'text/csv'
        elif filename.endswith('.log'):
            content_type = 'text/plain'

        response = FileResponse(
            open(filepath, 'rb'),
            content_type=content_type
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as exc:
        error_msg = str(exc).strip()
        logger.error(f'Error downloading sync log: {error_msg}', exc_info=True)
        return JsonResponse(
            {'success': False, 'message': error_msg or 'Gagal download log'},
            status=500
        )
