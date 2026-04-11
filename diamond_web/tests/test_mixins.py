"""Unit tests for view mixins and helper functions."""
import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.http import JsonResponse
from diamond_web.views.mixins import (
    AdminRequiredMixin, AdminAnyRequiredMixin, AdminP3DERequiredMixin,
    AdminPIDERequiredMixin, AdminPMDERequiredMixin, UserP3DERequiredMixin,
    UserPIDERequiredMixin, UserPMDERequiredMixin
)


@pytest.mark.django_db
class TestAdminRequiredMixin:
    """Tests for AdminRequiredMixin."""

    def test_admin_user_passes(self, admin_user):
        """Test admin user passes test_func."""
        mixin = AdminRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_non_admin_fails(self, authenticated_user):
        """Test non-admin user fails."""
        mixin = AdminRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = authenticated_user
        assert not mixin.test_func()


@pytest.mark.django_db
class TestAdminAnyRequiredMixin:
    """Tests for AdminAnyRequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = AdminAnyRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_p3de_passes(self, p3de_admin_user):
        """Test admin_p3de user passes."""
        mixin = AdminAnyRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = p3de_admin_user
        assert mixin.test_func()

    def test_admin_pide_passes(self, pide_admin_user):
        """Test admin_pide user passes."""
        mixin = AdminAnyRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pide_admin_user
        assert mixin.test_func()

    def test_admin_pmde_passes(self, pmde_admin_user):
        """Test admin_pmde user passes."""
        mixin = AdminAnyRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pmde_admin_user
        assert mixin.test_func()

    def test_non_admin_fails(self, authenticated_user):
        """Test non-admin fails."""
        mixin = AdminAnyRequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = authenticated_user
        assert not mixin.test_func()


@pytest.mark.django_db
class TestAdminP3DERequiredMixin:
    """Tests for AdminP3DERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = AdminP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_p3de_passes(self, p3de_admin_user):
        """Test admin_p3de user passes."""
        mixin = AdminP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = p3de_admin_user
        assert mixin.test_func()

    def test_other_admin_fails(self, pide_admin_user):
        """Test other admin type fails."""
        mixin = AdminP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pide_admin_user
        assert not mixin.test_func()


@pytest.mark.django_db
class TestAdminPIDERequiredMixin:
    """Tests for AdminPIDERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = AdminPIDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_pide_passes(self, pide_admin_user):
        """Test admin_pide user passes."""
        mixin = AdminPIDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pide_admin_user
        assert mixin.test_func()


@pytest.mark.django_db
class TestAdminPMDERequiredMixin:
    """Tests for AdminPMDERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = AdminPMDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_pmde_passes(self, pmde_admin_user):
        """Test admin_pmde user passes."""
        mixin = AdminPMDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pmde_admin_user
        assert mixin.test_func()


@pytest.mark.django_db
class TestUserP3DERequiredMixin:
    """Tests for UserP3DERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = UserP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_p3de_passes(self, p3de_admin_user):
        """Test admin_p3de user passes."""
        mixin = UserP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = p3de_admin_user
        assert mixin.test_func()

    def test_user_p3de_passes(self, authenticated_user):
        """Test user_p3de user passes."""
        mixin = UserP3DERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = authenticated_user
        assert mixin.test_func()

    def test_ajax_json_response_on_deny(self, pide_user):
        """Test AJAX request returns JSON on denial."""
        mixin = UserP3DERequiredMixin()
        factory = RequestFactory()
        request = factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = pide_user
        mixin.request = request
        
        response = mixin.handle_no_permission()
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403


@pytest.mark.django_db
class TestUserPIDERequiredMixin:
    """Tests for UserPIDERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = UserPIDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_pide_passes(self, pide_admin_user):
        """Test admin_pide user passes."""
        mixin = UserPIDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pide_admin_user
        assert mixin.test_func()

    def test_user_pide_passes(self, pide_user):
        """Test user_pide user passes."""
        mixin = UserPIDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pide_user
        assert mixin.test_func()

    def test_ajax_json_response_on_deny(self, authenticated_user):
        """Test AJAX request returns JSON on denial."""
        mixin = UserPIDERequiredMixin()
        factory = RequestFactory()
        request = factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = authenticated_user
        mixin.request = request
        
        response = mixin.handle_no_permission()
        assert isinstance(response, JsonResponse)
        assert response.status_code == 403


@pytest.mark.django_db
class TestUserPMDERequiredMixin:
    """Tests for UserPMDERequiredMixin."""

    def test_admin_passes(self, admin_user):
        """Test admin user passes."""
        mixin = UserPMDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = admin_user
        assert mixin.test_func()

    def test_admin_pmde_passes(self, pmde_admin_user):
        """Test admin_pmde user passes."""
        mixin = UserPMDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pmde_admin_user
        assert mixin.test_func()

    def test_user_pmde_passes(self, pmde_user):
        """Test user_pmde user passes."""
        mixin = UserPMDERequiredMixin()
        mixin.request = RequestFactory().get('/')
        mixin.request.user = pmde_user
        assert mixin.test_func()
