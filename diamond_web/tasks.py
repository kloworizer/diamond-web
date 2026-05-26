"""Celery tasks for background Oracle sync operations."""
import logging
from django.core.cache import cache

from celery import shared_task

logger = logging.getLogger(__name__)


def _get_user(user_id):
    """Return a User instance for user_id, or None."""
    if user_id is None:
        return None
    try:
        from django.contrib.auth.models import User
        return User.objects.get(pk=user_id)
    except Exception:
        return None


@shared_task(bind=True, name='diamond_web.tasks.check_referensi_data_task')
def check_referensi_data_task(self, check_id):
    """Run Oracle referensi check in a Celery worker."""
    try:
        logger.info(f'[TASK] Starting referensi check (check_id={check_id})...')
        from .utils.oracle_sync import OracleDataSyncService
        service = OracleDataSyncService()

        def _on_progress(current, total, table_name, inserts, updates, errors):
            # Check stop signal - if set, raise to halt service
            if cache.get(f'check_referensi_stop_requested_{check_id}'):
                logger.info(f'[TASK] Stop requested for check {check_id}, raising interrupt')
                raise InterruptedError('Cek Data dihentikan oleh pengguna')
            pct = int(current / total * 100) if total else 0
            cache.set(f'check_referensi_progress_{check_id}', {
                'current': current, 'total': total, 'percentage': pct,
                'table_name': table_name, 'inserts': inserts,
                'updates': updates, 'errors': errors,
            }, timeout=3600)
        
        def _stop_checker():
            """Check if stop was requested; called frequently during row iteration."""
            return bool(cache.get(f'check_referensi_stop_requested_{check_id}'))

        summary = service.check(progress_callback=_on_progress, stop_checker=_stop_checker)
        summary_dict = summary.as_dict() if hasattr(summary, 'as_dict') else {}

        cache.set(f'check_referensi_result_{check_id}', summary_dict, timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_in_progress_{check_id}', False, timeout=3600)
        cache.delete('check_referensi_active_check_id')
        logger.info(f'[TASK] Referensi check completed (check_id={check_id})')
    except InterruptedError as e:
        logger.info(f'[TASK] Referensi check interrupted: {str(e)}')
        cache.set(f'check_referensi_error_{check_id}', str(e), timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_in_progress_{check_id}', False, timeout=3600)
        cache.delete('check_referensi_active_check_id')
    except Exception as e:
        logger.error(f'[TASK] Exception in referensi check: {str(e)}', exc_info=True)
        cache.set(f'check_referensi_error_{check_id}', str(e), timeout=3600)
        cache.set(f'check_referensi_done_{check_id}', True, timeout=3600)
        cache.set(f'check_referensi_in_progress_{check_id}', False, timeout=3600)
        cache.delete('check_referensi_active_check_id')


@shared_task(bind=True, name='diamond_web.tasks.sync_referensi_data_task')
def sync_referensi_data_task(self, sync_id, user_id=None):
    """Run Oracle referensi sync in a Celery worker."""
    try:
        logger.info(f'[TASK] Starting referensi sync (sync_id={sync_id})...')
        from .utils.oracle_sync import OracleDataSyncService
        from .views.sync_data_referensi import _sync_referensi_data

        service = OracleDataSyncService()
        logger.info(f'[TASK] OracleDataSyncService initialized')

        def _on_progress(current, total, table_name, inserts, updates, errors):
            # Check stop signal — raise to halt the sync
            if cache.get(f'sync_referensi_stop_requested_{sync_id}'):
                logger.info(f'[TASK] Stop requested for referensi sync {sync_id}, raising interrupt')
                raise InterruptedError('Sync dihentikan oleh pengguna')
            pct = int(current / total * 100) if total else 0
            cache.set(f'sync_referensi_progress_{sync_id}', {
                'current': current, 'total': total, 'percentage': pct,
                'table_name': table_name, 'inserts': inserts,
                'updates': updates, 'errors': errors,
            }, timeout=3600)

        user = _get_user(user_id)

        class FakeRequest:
            def __init__(self, u):
                self.user = u

        fake_request = FakeRequest(user) if user is not None else None
        sync_summary = _sync_referensi_data(service, sync_id=sync_id, request=fake_request, progress_callback=_on_progress)
        logger.info(f'[TASK] Referensi sync completed (sync_id={sync_id}): {sync_summary}')

        cache.set(f'sync_referensi_result_{sync_id}', sync_summary, timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_in_progress_{sync_id}', False, timeout=3600)
        cache.delete('sync_referensi_active_sync_id')
    except InterruptedError as e:
        logger.info(f'[TASK] Referensi sync interrupted: {str(e)}')
        cache.set(f'sync_referensi_error_{sync_id}', str(e), timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_in_progress_{sync_id}', False, timeout=3600)
        cache.delete('sync_referensi_active_sync_id')
    except Exception as e:
        logger.error(f'[TASK] Exception in referensi sync: {str(e)}', exc_info=True)
        cache.set(f'sync_referensi_error_{sync_id}', str(e), timeout=3600)
        cache.set(f'sync_referensi_done_{sync_id}', True, timeout=3600)
        cache.set(f'sync_referensi_in_progress_{sync_id}', False, timeout=3600)
        cache.delete('sync_referensi_active_sync_id')


@shared_task(bind=True, name='diamond_web.tasks.check_tiket_data_task')
def check_tiket_data_task(self, check_id):
    """Run Oracle tiket check in a Celery worker."""
    try:
        logger.info(f'[TASK] Starting tiket check (check_id={check_id})...')
        from .utils.oracle_sync import OracleDataSyncService
        from .views.sync_tiket import _check_tiket_data

        # Check if stop was requested before task even starts
        if cache.get(f'check_tiket_stop_requested_{check_id}'):
            logger.info(f'[TASK] Tiket check stop requested before start (check_id={check_id})')
            cache.set(f'check_tiket_error_{check_id}', 'Cek Data dihentikan oleh pengguna', timeout=3600)
            cache.set(f'check_tiket_done_{check_id}', True, timeout=3600)
            cache.set(f'check_tiket_in_progress_{check_id}', False, timeout=3600)
            return

        service = OracleDataSyncService(connection_only=True)
        
        def _stop_checker():
            """Check if stop was requested; called frequently during row iteration."""
            return bool(cache.get(f'check_tiket_stop_requested_{check_id}'))
        
        # Wrap the check operation to handle stop requests
        try:
            summary = _check_tiket_data(service, check_id=check_id, stop_checker=_stop_checker)
        except InterruptedError as e:
            logger.info(f'[TASK] Tiket check interrupted: {str(e)}')
            cache.set(f'check_tiket_error_{check_id}', str(e), timeout=3600)
            cache.set(f'check_tiket_done_{check_id}', True, timeout=3600)
            cache.set(f'check_tiket_in_progress_{check_id}', False, timeout=3600)
            return
            
        cache.set(f'check_tiket_result_{check_id}', summary, timeout=3600)
        cache.set(f'check_tiket_done_{check_id}', True, timeout=3600)
        cache.set(f'check_tiket_in_progress_{check_id}', False, timeout=3600)
        logger.info(f'[TASK] Tiket check completed (check_id={check_id})')
    except Exception as e:
        logger.error(f'[TASK] Exception in tiket check: {str(e)}', exc_info=True)
        cache.set(f'check_tiket_error_{check_id}', str(e), timeout=3600)
        cache.set(f'check_tiket_done_{check_id}', True, timeout=3600)
        cache.set(f'check_tiket_in_progress_{check_id}', False, timeout=3600)


@shared_task(bind=True, name='diamond_web.tasks.sync_tiket_data_task')
def sync_tiket_data_task(self, sync_id, user_id=None):
    """Run Oracle tiket sync in a Celery worker."""
    try:
        logger.info(f'[TASK] Starting tiket sync (sync_id={sync_id})...')
        from .utils.oracle_sync import OracleDataSyncService
        from .views.sync_tiket import _sync_tiket_data

        service = OracleDataSyncService(connection_only=True)
        logger.info(f'[TASK] OracleDataSyncService initialized')

        user = _get_user(user_id)

        class FakeRequest:
            def __init__(self, u):
                self.user = u

        fake_request = FakeRequest(user) if user is not None else None
        tiket_summary = _sync_tiket_data(service, sync_id=sync_id, request=fake_request)
        logger.info(f'[TASK] Tiket sync completed (sync_id={sync_id}): {tiket_summary}')

        cache.set(f'sync_tiket_result_{sync_id}', tiket_summary, timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', True, timeout=3600)
        cache.set(f'sync_tiket_in_progress_{sync_id}', False, timeout=3600)
    except Exception as e:
        logger.error(f'[TASK] Exception in tiket sync: {str(e)}', exc_info=True)
        cache.set(f'sync_tiket_error_{sync_id}', str(e), timeout=3600)
        cache.set(f'sync_tiket_done_{sync_id}', True, timeout=3600)
        cache.set(f'sync_tiket_in_progress_{sync_id}', False, timeout=3600)
