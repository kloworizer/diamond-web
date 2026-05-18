from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from ..utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError


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
    return render(request, 'oracle_sync/page.html')


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def oracle_sync_check(request):
    try:
        service = OracleDataSyncService()
        summary = service.check()
        return JsonResponse({
            'success': True,
            'mode': 'check',
            'summary': summary.as_dict(),
        })
    except OracleSyncConfigError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'Gagal cek data: {exc}'}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
def oracle_sync_run(request):
    try:
        service = OracleDataSyncService()
        summary = service.sync()
        if summary.errors:
            return JsonResponse({
                'success': False,
                'message': 'Sync dihentikan karena ada error data.',
                'summary': summary.as_dict(),
            }, status=400)

        return JsonResponse({
            'success': True,
            'mode': 'sync',
            'summary': summary.as_dict(),
            'message': 'Sync Oracle selesai.',
        })
    except OracleSyncConfigError as exc:
        return JsonResponse({'success': False, 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'success': False, 'message': f'Gagal sync data: {exc}'}, status=500)