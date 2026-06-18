from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth import logout

@login_required
@require_POST
def keep_alive(request):
    """Extend the current user's session expiry via AJAX.

    Called by the client-side heartbeat (POST with CSRF token) to mark the
    session as modified so the session backend refreshes the expiry timeout.

    Returns:
        JsonResponse: A JSON object with:
            - ``ok`` (bool): Always ``True``.
            - ``expiry`` (int | None): Remaining session age in seconds, or
              ``None`` if the expiry age could not be determined.
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
    """Log the user out when the client detects session expiry.

    Intended to be invoked by client-side session-expiry handlers after the
    session has timed out.  Calls ``logout(request)`` and returns a JSON
    confirmation.

    Returns:
        JsonResponse: A JSON object with:
            - ``ok`` (bool): Always ``True``.
            - ``message`` (str): Confirmation text, e.g.
              ``"Session expired. Logged out."``.
    """
    logout(request)
    return JsonResponse({"ok": True, "message": "Session expired. Logged out."})
