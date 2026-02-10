from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth import logout

@login_required
@require_POST
def keep_alive(request):
    """AJAX endpoint to extend the current user's session.

    Usage: called by client-side heartbeat (POST with CSRF) to mark the
    session as modified so the session backend will refresh expiry. Returns
    JSON: `{'ok': True, 'expiry': <seconds>}` where `expiry` is the
    remaining session age in seconds or `None` if not available.
    """
    # Mark session modified so SESSION_SAVE_EVERY_REQUEST (or session backend) will update expiry
    request.session.modified = True
    try:
        expiry = request.session.get_expiry_age()
    except Exception:
        expiry = None
    return JsonResponse({"ok": True, "expiry": expiry})


@require_POST
def session_expired(request):
    """AJAX endpoint to log the user out when the client detects session expiry.

    Side effects: calls `logout(request)` and returns a JSON confirmation.
    Intended to be invoked by client-side session-expiry handlers.
    """
    logout(request)
    return JsonResponse({"ok": True, "message": "Session expired. Logged out."})
