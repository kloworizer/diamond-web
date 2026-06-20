from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import Notification


@login_required
def notification_list(request):
    """Display all notifications for the current user with pagination.

    Shows a paginated list of notifications (read and unread) for the
    authenticated user, ordered by most recent first.

    Args:
        request (HttpRequest): The HTTP request object from authenticated user.

    Returns:
        HttpResponse: Rendered notification list page.
    """
    all_notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')

    paginator = Paginator(all_notifications, 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'is_paginated': paginator.num_pages > 1,
    }
    return render(request, 'notification/list.html', context)


@login_required
def mark_notification_read(request, pk):
    """Mark a single Notification as read and redirect back.

    Retrieves a notification record by primary key and ensures the current
    user is the recipient. Updates the notification's `is_read` status to True.

    Permissions:
    - The `recipient` field of the Notification must match `request.user`
      (enforced via `get_object_or_404`).

    Side effects:
    - Sets `notification.is_read = True` and saves the instance.

    Args:
        request (HttpRequest): The HTTP request object from authenticated user.
        pk (int): Primary key of the Notification to mark as read.

    Returns:
        HttpResponseRedirect: Redirects to the HTTP referer when available,
                             otherwise to the named URL 'home'.
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    return redirect(request.META.get('HTTP_REFERER', 'home'))


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all unread notifications as read for the current user.

    Side effects:
    - Updates all notifications where `is_read=False` for the current user
      to `is_read=True` in bulk.

    Args:
        request (HttpRequest): The HTTP request object from authenticated user.

    Returns:
        JsonResponse: JSON indicating success with the count of marked notifications.
    """
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True)
    return JsonResponse({'success': True, 'count': count})