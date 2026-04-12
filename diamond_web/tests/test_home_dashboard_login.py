"""Unit tests for home, dashboard, and login views."""
import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse
from unittest.mock import patch, MagicMock

from diamond_web.views.home import home
from diamond_web.views.dashboard import index
from diamond_web.views.new_login import new_login


@pytest.mark.django_db
class TestHomeView:
    """Tests for the home view."""

    def test_home_view_unauthenticated(self, client):
        """Test home view returns correct template for unauthenticated user."""
        response = client.get(reverse('home'))
        assert response.status_code == 200
        assert 'is_p3de' in response.context
        assert 'is_pide' in response.context
        assert 'is_pmde' in response.context
        assert response.context['is_p3de'] is False
        assert response.context['is_pide'] is False
        assert response.context['is_pmde'] is False

    def test_home_view_p3de_user(self, client, authenticated_user):
        """Test home view identifies P3DE user and computes tiket summary."""
        client.force_login(authenticated_user)
        with patch('diamond_web.views.home.get_tiket_summary_for_user') as mock_summary:
            mock_summary.return_value = {'test': 'data'}
            response = client.get(reverse('home'))
            assert response.status_code == 200
            assert response.context['is_p3de'] is True
            assert response.context['tiket_summary'] == {'test': 'data'}
            mock_summary.assert_called_once_with(authenticated_user)

    def test_home_view_pide_user(self, client, pide_user):
        """Test home view identifies PIDE user."""
        client.force_login(pide_user)
        with patch('diamond_web.views.home.get_tiket_summary_for_user_pide') as mock_summary:
            mock_summary.return_value = {'pide': 'data'}
            response = client.get(reverse('home'))
            assert response.status_code == 200
            assert response.context['is_pide'] is True
            assert response.context['tiket_summary_pide'] == {'pide': 'data'}

    def test_home_view_pmde_user(self, client, pmde_user):
        """Test home view identifies PMDE user."""
        client.force_login(pmde_user)
        with patch('diamond_web.views.home.get_tiket_summary_for_user_pmde') as mock_summary:
            mock_summary.return_value = {'pmde': 'data'}
            response = client.get(reverse('home'))
            assert response.status_code == 200
            assert response.context['is_pmde'] is True
            assert response.context['tiket_summary_pmde'] == {'pmde': 'data'}

    def test_home_view_all_user_types(self, client, db):
        """Test home view with user in all three groups."""
        from diamond_web.tests.conftest import UserFactory
        user = UserFactory()
        for group_name in ['user_p3de', 'user_pide', 'user_pmde']:
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
        
        client.force_login(user)
        with patch('diamond_web.views.home.get_tiket_summary_for_user') as mock_p3de, \
             patch('diamond_web.views.home.get_tiket_summary_for_user_pide') as mock_pide, \
             patch('diamond_web.views.home.get_tiket_summary_for_user_pmde') as mock_pmde:
            mock_p3de.return_value = {'p3de': 'data'}
            mock_pide.return_value = {'pide': 'data'}
            mock_pmde.return_value = {'pmde': 'data'}
            response = client.get(reverse('home'))
            assert response.status_code == 200
            assert response.context['is_p3de'] is True
            assert response.context['is_pide'] is True
            assert response.context['is_pmde'] is True

    def test_home_view_debug_groups(self, client, admin_user, settings):
        """Test home view works with admin user."""
        client.force_login(admin_user)
        
        # Create test groups
        for group_name in ['user_p3de', 'user_pide', 'user_pmde']:
            Group.objects.get_or_create(name=group_name)
        
        response = client.get(reverse('home'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestDashboardView:
    """Tests for the dashboard view."""

    def test_dashboard_unauthenticated(self, client):
        """Test dashboard redirects unauthenticated user."""
        response = client.get(reverse('dashboard_index'), follow=False)
        # Should redirect to login
        assert response.status_code in [302, 403]

    def test_dashboard_authenticated(self, client, authenticated_user):
        """Test dashboard renders for authenticated user."""
        client.force_login(authenticated_user)
        response = client.get(reverse('dashboard_index'))
        assert response.status_code == 200

    def test_dashboard_returns_correct_template(self, client, authenticated_user):
        """Test dashboard uses correct template."""
        client.force_login(authenticated_user)
        response = client.get(reverse('dashboard_index'))
        assert 'dashboard/index.html' in [t.name for t in response.templates]


@pytest.mark.django_db
class TestNewLoginView:
    """Tests for the new login view."""

    def test_new_login_view(self, client):
        """Test login view renders correctly."""
        response = client.get(reverse('new_login'))
        assert response.status_code == 200
        assert 'login/auth-login-creative.html' in [t.name for t in response.templates]

    def test_new_login_unauthenticated(self, client):
        """Test login view accessible to unauthenticated user."""
        response = client.get(reverse('new_login'))
        assert response.status_code == 200

    def test_new_login_authenticated(self, client, authenticated_user):
        """Test authenticated user can still view login page."""
        client.force_login(authenticated_user)
        response = client.get(reverse('new_login'))
        assert response.status_code == 200
