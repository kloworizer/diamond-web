from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import Notification

@login_required
def mark_notification_read(request, pk):
    """Mark a single `Notification` as read and redirect back.

    Permissions: the `recipient` of the `Notification` must match
    `request.user` (enforced via `get_object_or_404`).

    Side effects:
    - Sets `notification.is_read = True` and saves the instance.

    Redirects to the HTTP referer when available, otherwise to the
    named URL `home`.

    Parameters:
    - `pk` (int): primary key of the `Notification` to mark as read.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))