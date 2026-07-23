"""Unit tests for notification views."""
import json
import pytest
from django.urls import reverse
from django.test import Client
from diamond_web.models import Notification


@pytest.mark.django_db
class TestNotificationViews:
    """Tests for notification-related views."""

    def test_mark_notification_read_unauthenticated(self, client, notification):
        """Test mark_notification_read redirects unauthenticated user."""
        response = client.get(
            reverse('mark_notification_read', args=[notification.pk]),
            follow=False
        )
        assert response.status_code in [302, 403]

    def test_mark_notification_read_authenticated(self, client, authenticated_user, notification):
        """Test marking notification as read."""
        notification.recipient = authenticated_user
        notification.is_read = False
        notification.save()
        
        client.force_login(authenticated_user)
        response = client.get(
            reverse('mark_notification_read', args=[notification.pk]),
            follow=False
        )
        
        # Should redirect
        assert response.status_code == 302
        
        # Notification should be marked as read
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_notification_read_wrong_user(self, client, authenticated_user, db):
        """Test user cannot mark another user's notification as read."""
        from diamond_web.tests.conftest import UserFactory, NotificationFactory
        other_user = UserFactory()
        notification = NotificationFactory(recipient=other_user)
        
        client.force_login(authenticated_user)
        response = client.get(
            reverse('mark_notification_read', args=[notification.pk]),
            follow=False
        )
        
        # Should 404 - user doesn't have permission
        assert response.status_code == 404

    def test_mark_notification_read_nonexistent(self, client, authenticated_user):
        """Test marking non-existent notification returns 404."""
        client.force_login(authenticated_user)
        response = client.get(
            reverse('mark_notification_read', args=[99999]),
            follow=False
        )
        assert response.status_code == 404

    def test_mark_notification_read_redirect_referer(self, client, authenticated_user, notification):
        """Test notification view redirects to referer."""
        notification.recipient = authenticated_user
        notification.save()
        
        client.force_login(authenticated_user)
        referer_url = reverse('home')
        response = client.get(
            reverse('mark_notification_read', args=[notification.pk]),
            HTTP_REFERER=referer_url,
            follow=False
        )
        
        assert response.status_code == 302
        assert response.url == referer_url

    def test_mark_notification_read_no_referer(self, client, authenticated_user, notification):
        """Test notification view redirects to home when no referer."""
        notification.recipient = authenticated_user
        notification.save()
        
        client.force_login(authenticated_user)
        response = client.get(
            reverse('mark_notification_read', args=[notification.pk]),
            follow=False
        )
        
        assert response.status_code == 302
        # Should redirect to home view
        assert 'home' in response.url or response.url == '/'

    def test_mark_notification_read_toggle_multiple_times(self, client, authenticated_user, notification):
        """Test marking notification read twice."""
        notification.recipient = authenticated_user
        notification.is_read = False
        notification.save()
        
        client.force_login(authenticated_user)
        
        # First mark as read
        client.get(reverse('mark_notification_read', args=[notification.pk]))
        notification.refresh_from_db()
        assert notification.is_read is True
        
        # Mark again (simulate reading again)
        notification.is_read = False
        notification.save()

        client.get(reverse('mark_notification_read', args=[notification.pk]))
        notification.refresh_from_db()
        assert notification.is_read is True


@pytest.mark.django_db
class TestNotificationListView:
    """Tests for the notification_list view."""

    def test_requires_login(self, client):
        resp = client.get(reverse('notification_list'))
        assert resp.status_code in (302, 403)

    def test_lists_notifications_for_user(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory
        NotificationFactory.create_batch(3, recipient=authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('notification_list'))
        assert resp.status_code == 200
        assert 'notification/list.html' in [t.name for t in resp.templates]
        assert 'page_obj' in resp.context
        assert resp.context['is_paginated'] is False

    def test_pagination_when_over_15(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory
        NotificationFactory.create_batch(16, recipient=authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('notification_list'))
        assert resp.status_code == 200
        assert resp.context['is_paginated'] is True
        # First page shows the paginator page size (15)
        assert len(resp.context['page_obj'].object_list) == 15

    def test_page_param(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory
        NotificationFactory.create_batch(16, recipient=authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('notification_list'), {'page': '2'})
        assert resp.status_code == 200
        assert len(resp.context['page_obj'].object_list) == 1

    def test_only_own_notifications_shown(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory, UserFactory
        NotificationFactory.create_batch(2, recipient=authenticated_user)
        NotificationFactory.create_batch(3, recipient=UserFactory())
        client.force_login(authenticated_user)
        resp = client.get(reverse('notification_list'))
        assert resp.context['page_obj'].paginator.count == 2


@pytest.mark.django_db
class TestMarkAllNotificationsRead:
    """Tests for the mark_all_notifications_read view."""

    def test_requires_login(self, client):
        resp = client.post(reverse('mark_all_notifications_read'))
        assert resp.status_code in (302, 403)

    def test_get_not_allowed(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('mark_all_notifications_read'))
        assert resp.status_code == 405

    def test_marks_all_unread(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory
        NotificationFactory.create_batch(4, recipient=authenticated_user, is_read=False)
        client.force_login(authenticated_user)
        resp = client.post(reverse('mark_all_notifications_read'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['count'] == 4
        assert Notification.objects.filter(
            recipient=authenticated_user, is_read=False).count() == 0

    def test_does_not_touch_other_users(self, client, authenticated_user):
        from diamond_web.tests.conftest import NotificationFactory, UserFactory
        other = UserFactory()
        NotificationFactory.create_batch(2, recipient=other, is_read=False)
        NotificationFactory.create_batch(1, recipient=authenticated_user, is_read=False)
        client.force_login(authenticated_user)
        resp = client.post(reverse('mark_all_notifications_read'))
        data = json.loads(resp.content)
        assert data['count'] == 1
        assert Notification.objects.filter(recipient=other, is_read=False).count() == 2
