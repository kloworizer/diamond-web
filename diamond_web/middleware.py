"""Custom middleware for diamond_web."""

import time

from django.conf import settings


class SlidingSessionMiddleware:
    """Refresh the session expiry of users who are actively browsing.

    ``SESSION_SAVE_EVERY_REQUEST`` is deliberately off (it rewrites the session
    row on every single request, which is a lock-contention problem on SQLite).
    The side effect is that ordinary navigation never refreshes the expiry:
    Django only rewrites ``expire_date`` when something marks the session as
    modified. A user clicking through the app was therefore logged out exactly
    ``SESSION_COOKIE_AGE`` after signing in — mid-work, with no warning, and
    only visible once the next full page load bounced them to the login page.
    The client-side keep-alive did not cover it either: it first fires ten
    minutes after a page loads, so anyone navigating more often than that never
    triggered a single one.

    This restores the sliding window without the per-request write. The last
    slide is recorded in the session itself, and the session is only touched
    again once ``REFRESH_RATIO`` of its lifetime has passed, so an active user
    costs at most one session write per refresh window. Writing the key marks
    the session modified, which makes ``SessionMiddleware`` save it on the way
    out, and saving recomputes ``expire_date`` as now + ``SESSION_COOKIE_AGE``.

    An idle user is still logged out on schedule — that is what the expiry is
    for. This only stops the clock running out underneath someone who is
    demonstrably still using the app.

    Must be listed after ``AuthenticationMiddleware`` (it reads ``request.user``)
    and inside ``SessionMiddleware`` (which performs the actual save).
    """

    #: Session key holding the epoch seconds of the last expiry refresh.
    SESSION_KEY = '_last_session_slide'

    #: Refresh once this fraction of ``SESSION_COOKIE_AGE`` has elapsed.
    REFRESH_RATIO = 0.5

    def __init__(self, get_response):
        self.get_response = get_response
        self.refresh_after = settings.SESSION_COOKIE_AGE * self.REFRESH_RATIO

    def __call__(self, request):
        self._maybe_slide(request)
        return self.get_response(request)

    def _maybe_slide(self, request):
        session = getattr(request, 'session', None)
        user = getattr(request, 'user', None)

        if session is None or not session.session_key:
            return
        if user is None or not user.is_authenticated:
            return
        # A non-default expiry (e.g. a "remember me" login) is somebody else's
        # decision; leave it alone.
        if session.get('_session_expiry'):
            return

        now = time.time()
        last_slide = session.get(self.SESSION_KEY)

        if last_slide is None or (now - last_slide) >= self.refresh_after:
            session[self.SESSION_KEY] = now
