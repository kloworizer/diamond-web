"""Unit tests for notification views."""
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
