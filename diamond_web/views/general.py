from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth import logout

@login_required
@require_POST
def keep_alive(request):
    """Endpoint to extend the user's session. Call with POST (CSRF protected).
    Returns JSON with remaining session age in seconds.
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
    """Endpoint to handle session expiry. Logs out the user and returns confirmation.
    Call with POST (CSRF protected).
    """
    logout(request)
    return JsonResponse({"ok": True, "message": "Session expired. Logged out."})
