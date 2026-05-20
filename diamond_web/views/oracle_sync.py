from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

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
        # Prevent session from being deleted during long-running operation
        request.session.modified = False
        
        service = OracleDataSyncService()
        summary = service.check()
        
        # Refresh session to prevent timeout
        request.session.create()
        
        return JsonResponse({
            'success': True,
            'mode': 'check',
            'summary': summary.as_dict(),
        })
    except OracleSyncConfigError as exc:
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan check data. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)


@login_required
@user_passes_test(_is_admin_user)
@require_POST
@never_cache
def oracle_sync_run(request):
    try:
        # Prevent session from being deleted during long-running operation
        request.session.modified = False
        
        service = OracleDataSyncService()
        summary = service.sync()
        
        # Refresh session to prevent timeout
        request.session.create()
        
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
        error_msg = str(exc).strip()
        return JsonResponse({'success': False, 'message': error_msg}, status=400)
    except Exception as exc:
        error_msg = str(exc).strip()
        if not error_msg or '<' in error_msg:
            error_msg = 'Gagal melakukan sync data. Periksa koneksi Oracle.'
        return JsonResponse({'success': False, 'message': error_msg}, status=500)