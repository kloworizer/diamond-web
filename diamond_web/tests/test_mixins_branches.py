"""Tests for mixins.py uncovered branches.

Covers missing lines per coverage report:
- Line 110: UserP3DERequiredMixin.handle_no_permission AJAX path → JSON 403
- Lines 124-133: ActiveTiketPICRequiredMixin.test_func get_object() fallback
- Lines 152-181: ActiveTiketPICRequiredForEditMixin.test_func all branches
- Lines 184-191: ActiveTiketPICRequiredForEditMixin.handle_no_permission AJAX 403
- Lines 201-234: ActiveTiketP3DERequiredForEditMixin.test_func all branches
- Line 239: ActiveTiketP3DERequiredForEditMixin.handle_no_permission AJAX 403
- Lines 311-316: ActiveTiketPICListRequiredMixin.test_func
- Lines 384-385: AjaxFormMixin.form_valid get_success_url exception fallback
- Line 406: AjaxFormMixin.get_success_message (no success_message)
- Lines 409-410: AjaxFormMixin.get_success_message format exception
- Lines 438-466: SafeDeleteMixin.delete ProtectedError path
- Lines 475-479: SafeDeleteMixin.get_protected_error_message without related_models
- Line 483: SafeDeleteMixin.get_general_error_message
- context_processors.py: git helper branches
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser, Group
from django.http import HttpResponse
from django.urls import reverse

from diamond_web.views.mixins import (
    UserP3DERequiredMixin,
    ActiveTiketPICRequiredMixin,
    ActiveTiketPICRequiredForEditMixin,
    ActiveTiketP3DERequiredForEditMixin,
    ActiveTiketPICListRequiredMixin,
    AjaxFormMixin,
    SafeDeleteMixin,
)
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import (
    UserFactory, TiketFactory, TiketPICFactory,
)


# ============================================================
# UserP3DERequiredMixin.handle_no_permission — AJAX → JSON 403
# ============================================================

@pytest.mark.django_db
class TestUserP3DEHandleNoPermissionAjax:
    """UserP3DERequiredMixin returns JSON 403 for unauthorized AJAX requests."""

    def test_ajax_forbidden_returns_json_403(self, client, pide_user):
        """A pide_user (not in user_p3de) hitting a P3DE view via AJAX gets JSON 403."""
        # Use backup_data_create which uses UserP3DERequiredMixin
        # pide_user is in user_pide group, not user_p3de
        client.force_login(pide_user)
        resp = client.get(
            reverse('backup_data_create'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert data['success'] is False
        assert 'Forbidden' in data['message']

    def test_non_ajax_forbidden_returns_403(self, client, pide_user):
        """A pide_user hitting a P3DE view without AJAX gets a 403 (PermissionDenied)."""
        client.force_login(pide_user)
        resp = client.get(reverse('backup_data_create'))
        assert resp.status_code == 403


# ============================================================
# ActiveTiketPICRequiredMixin — test_func get_object() fallback
# ============================================================

@pytest.mark.django_db
class TestActiveTiketPICRequiredMixinGetObject:
    """ActiveTiketPICRequiredMixin test_func can use get_object() when self.object is None."""

    def _make_mixin_instance(self, user, tiket=None, get_object_raises=False):
        """Build a mock view instance using ActiveTiketPICRequiredMixin."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = user

        mixin = ActiveTiketPICRequiredMixin()
        mixin.request = request
        mixin.kwargs = {}
        # object not pre-set (None) to trigger the get_object() fallback
        if tiket is not None:
            if get_object_raises:
                mixin.get_object = MagicMock(side_effect=Exception("not found"))
            else:
                mixin.get_object = MagicMock(return_value=tiket)
        else:
            mixin.get_object = MagicMock(side_effect=Exception("not found"))
        return mixin

    def test_get_object_fallback_with_valid_pic(self, authenticated_user):
        """When self.object is None, get_object() is called and PIC check runs."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mixin = self._make_mixin_instance(authenticated_user, tiket=tiket)
        assert mixin.test_func() is True

    def test_get_object_raises_returns_false(self, authenticated_user):
        """When get_object() raises, test_func returns False."""
        mixin = self._make_mixin_instance(authenticated_user, get_object_raises=True)
        assert mixin.test_func() is False

    def test_admin_user_always_allowed(self, admin_user):
        """Superuser/admin always passes test_func without checking TiketPIC."""
        mixin = self._make_mixin_instance(admin_user)
        assert mixin.test_func() is True

    def test_no_pic_returns_false(self, authenticated_user):
        """User without TiketPIC returns False via get_object() fallback."""
        tiket = TiketFactory()
        mixin = self._make_mixin_instance(authenticated_user, tiket=tiket)
        # No TiketPIC created → should return False
        assert mixin.test_func() is False


# ============================================================
# ActiveTiketPICRequiredForEditMixin — test_func all branches
# ============================================================

@pytest.mark.django_db
class TestActiveTiketPICRequiredForEditMixinBranches:
    """Test all branches in ActiveTiketPICRequiredForEditMixin.test_func."""

    def _make_mixin_instance(self, user, tiket_pk=None, obj=None, get_object_raises=False):
        """Create a mock view instance for testing."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = user

        mixin = ActiveTiketPICRequiredForEditMixin()
        mixin.request = request
        mixin.kwargs = {}
        if tiket_pk is not None:
            mixin.kwargs['tiket_pk'] = tiket_pk
        if obj is not None:
            mixin.get_object = MagicMock(return_value=obj)
        elif get_object_raises:
            mixin.get_object = MagicMock(side_effect=Exception("not found"))
        else:
            mixin.get_object = MagicMock(side_effect=Exception("no object"))
        return mixin

    def test_admin_always_allowed(self, admin_user):
        """Superuser passes immediately."""
        mixin = self._make_mixin_instance(admin_user)
        assert mixin.test_func() is True

    def test_tiket_pk_in_kwargs(self, authenticated_user):
        """tiket_pk in kwargs: finds tiket and checks active TiketPIC."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=tiket.pk)
        assert mixin.test_func() is True

    def test_tiket_pk_in_kwargs_no_pic(self, authenticated_user):
        """tiket_pk in kwargs: no TiketPIC → False."""
        tiket = TiketFactory()
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=tiket.pk)
        assert mixin.test_func() is False

    def test_tiket_pk_nonexistent_returns_false(self, authenticated_user):
        """tiket_pk that doesn't exist → Tiket.DoesNotExist → False."""
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=999999)
        assert mixin.test_func() is False

    def test_get_object_with_id_tiket_attr(self, authenticated_user):
        """Object has id_tiket attribute → use it as tiket."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        # Simulate an object that has id_tiket FK
        mock_obj = MagicMock()
        mock_obj.id_tiket = tiket
        del mock_obj.id_tiket_id  # ensure id_tiket path is taken
        mock_obj.id_tiket.pk = tiket.pk
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is True

    def test_get_object_with_id_tiket_id_attr(self, authenticated_user):
        """Object has id_tiket_id attribute → use it as tiket_pk."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mock_obj = MagicMock(spec=['id_tiket_id'])
        mock_obj.id_tiket_id = tiket.pk
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is True

    def test_get_object_raises_returns_false(self, authenticated_user):
        """get_object() raises → test_func returns False."""
        mixin = self._make_mixin_instance(authenticated_user, get_object_raises=True)
        assert mixin.test_func() is False

    def test_no_tiket_pk_returns_false(self, authenticated_user):
        """get_object() succeeds but no tiket_pk found → False."""
        mock_obj = MagicMock(spec=[])  # no id_tiket, id_tiket_id attrs
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is False

    def test_handle_no_permission_ajax_returns_json_403(self, authenticated_user):
        """handle_no_permission for AJAX returns JSON 403."""
        factory = RequestFactory()
        request = factory.get('/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.headers = {'X-Requested-With': 'XMLHttpRequest'}
        request.user = authenticated_user
        mixin = ActiveTiketPICRequiredForEditMixin()
        mixin.request = request
        response = mixin.handle_no_permission()
        assert response.status_code == 403
        data = json.loads(response.content)
        assert data['success'] is False

    def test_handle_no_permission_non_ajax_returns_403_page(self, authenticated_user):
        """handle_no_permission for non-AJAX returns HttpResponseForbidden."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = authenticated_user
        mixin = ActiveTiketPICRequiredForEditMixin()
        mixin.request = request
        response = mixin.handle_no_permission()
        assert response.status_code == 403


# ============================================================
# ActiveTiketP3DERequiredForEditMixin — test_func all branches
# ============================================================

@pytest.mark.django_db
class TestActiveTiketP3DERequiredForEditMixinBranches:
    """Test all branches in ActiveTiketP3DERequiredForEditMixin.test_func."""

    def _make_mixin_instance(self, user, tiket_pk=None, obj=None, get_object_raises=False):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = user
        mixin = ActiveTiketP3DERequiredForEditMixin()
        mixin.request = request
        mixin.kwargs = {}
        if tiket_pk is not None:
            mixin.kwargs['tiket_pk'] = tiket_pk
        if obj is not None:
            mixin.get_object = MagicMock(return_value=obj)
        elif get_object_raises:
            mixin.get_object = MagicMock(side_effect=Exception("not found"))
        else:
            mixin.get_object = MagicMock(side_effect=Exception("no object"))
        return mixin

    def test_admin_always_allowed(self, admin_user):
        mixin = self._make_mixin_instance(admin_user)
        assert mixin.test_func() is True

    def test_tiket_pk_in_kwargs_with_p3de_pic(self, authenticated_user):
        """tiket_pk in kwargs with active P3DE TiketPIC → True."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=tiket.pk)
        assert mixin.test_func() is True

    def test_tiket_pk_in_kwargs_no_p3de_pic(self, authenticated_user):
        """tiket_pk in kwargs with no P3DE TiketPIC → False."""
        tiket = TiketFactory()
        # PIDE PIC, not P3DE
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.PIDE, active=True)
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=tiket.pk)
        assert mixin.test_func() is False

    def test_tiket_pk_nonexistent(self, authenticated_user):
        """Nonexistent tiket_pk → DoesNotExist → False."""
        mixin = self._make_mixin_instance(authenticated_user, tiket_pk=999999)
        assert mixin.test_func() is False

    def test_get_object_with_id_tiket_attr(self, authenticated_user):
        """Object has id_tiket FK → use tiket.pk."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mock_obj = MagicMock()
        mock_obj.id_tiket.pk = tiket.pk
        del mock_obj.id_tiket_id
        del mock_obj.pk
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is True

    def test_get_object_with_id_tiket_id_attr(self, authenticated_user):
        """Object has id_tiket_id → use as tiket_pk."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mock_obj = MagicMock(spec=['id_tiket_id'])
        mock_obj.id_tiket_id = tiket.pk
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is True

    def test_get_object_with_pk_attr(self, authenticated_user):
        """Object has .pk (is a tiket itself) → use obj.pk as tiket_pk."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mock_obj = MagicMock(spec=['pk'])
        mock_obj.pk = tiket.pk
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is True

    def test_get_object_raises_returns_false(self, authenticated_user):
        """get_object() raises → False."""
        mixin = self._make_mixin_instance(authenticated_user, get_object_raises=True)
        assert mixin.test_func() is False

    def test_no_tiket_pk_resolves_to_none(self, authenticated_user):
        """Object with no tiket-related attrs → tiket_pk None → False."""
        mock_obj = MagicMock(spec=[])
        mixin = self._make_mixin_instance(authenticated_user, obj=mock_obj)
        assert mixin.test_func() is False

    def test_handle_no_permission_ajax_returns_json_403(self, authenticated_user):
        """AJAX handle_no_permission returns JSON 403."""
        factory = RequestFactory()
        request = factory.get('/')
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        request.user = authenticated_user
        # Patch headers since RequestFactory doesn't set them as dict
        mixin = ActiveTiketP3DERequiredForEditMixin()
        mixin.request = request
        # Override headers to simulate AJAX
        with patch.object(type(request), 'headers', new_callable=lambda: property(
            lambda self: {'X-Requested-With': 'XMLHttpRequest'}
        )):
            response = mixin.handle_no_permission()
        assert response.status_code == 403
        data = json.loads(response.content)
        assert data['success'] is False

    def test_handle_no_permission_non_ajax_returns_403(self, authenticated_user):
        """Non-AJAX handle_no_permission returns HttpResponseForbidden."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = authenticated_user
        mixin = ActiveTiketP3DERequiredForEditMixin()
        mixin.request = request
        response = mixin.handle_no_permission()
        assert response.status_code == 403


# ============================================================
# ActiveTiketP3DERequiredForEditMixin via HTTP (through backup_data views)
# ============================================================

@pytest.mark.django_db
class TestActiveTiketP3DEViaBackupDataView:
    """Test ActiveTiketP3DERequiredForEditMixin via BackupData views."""

    def test_non_p3de_user_gets_json_403_ajax(self, client, pide_user):
        """PIDE user trying to access backup_data create gets JSON 403."""
        tiket = TiketFactory()
        client.force_login(pide_user)
        resp = client.get(
            reverse('backup_data_create'),
            {'tiket_pk': tiket.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        # pide_user fails UserP3DERequiredMixin test_func → AJAX → JSON 403
        assert resp.status_code == 403
        data = json.loads(resp.content)
        assert data['success'] is False


# ============================================================
# ActiveTiketPICListRequiredMixin — test_func branches
# ============================================================

@pytest.mark.django_db
class TestActiveTiketPICListRequiredMixin:
    """Test ActiveTiketPICListRequiredMixin.test_func branches."""

    def _make_mixin(self, user):
        factory = RequestFactory()
        request = factory.get('/')
        request.user = user
        mixin = ActiveTiketPICListRequiredMixin()
        mixin.request = request
        return mixin

    def test_unauthenticated_returns_false(self):
        """Unauthenticated user returns False."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = AnonymousUser()
        mixin = ActiveTiketPICListRequiredMixin()
        mixin.request = request
        assert mixin.test_func() is False

    def test_admin_returns_true(self, admin_user):
        """Admin user returns True."""
        mixin = self._make_mixin(admin_user)
        assert mixin.test_func() is True

    def test_user_with_active_tiket_pic_returns_true(self, authenticated_user):
        """User with active TiketPIC returns True."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        mixin = self._make_mixin(authenticated_user)
        assert mixin.test_func() is True

    def test_user_without_tiket_pic_returns_false(self, db):
        """User with no TiketPIC returns False."""
        user = UserFactory()
        # Don't add to any group, no TiketPIC
        for group_name in ['admin', 'admin_p3de', 'user_p3de']:
            user.groups.remove(Group.objects.filter(name=group_name).first() or Group())
        mixin = self._make_mixin(user)
        # Clean user with no active TiketPIC
        assert mixin.test_func() is False


# ============================================================
# AjaxFormMixin — form_valid exception path (get_success_url raises)
# ============================================================

@pytest.mark.django_db
class TestAjaxFormMixinExceptionPaths:
    """Test AjaxFormMixin.form_valid when get_success_url raises, and get_success_message."""

    def test_form_valid_get_success_url_exception_fallback(self, client, admin_user):
        """When get_success_url() raises, fallback to success_url attr."""
        # Use kategori_ilap_create which uses AjaxFormMixin
        # We need to make get_success_url raise; mock it on the view class
        import uuid
        client.force_login(admin_user)
        with patch('diamond_web.views.kategori_ilap.KategoriILAPCreateView.get_success_url',
                   side_effect=Exception("no url")):
            uid = uuid.uuid4().hex[:4]
            resp = client.post(
                reverse('kategori_ilap_create'),
                {'id_kategori': uid[:2], 'nama_kategori': f'TestKategori_{uid}'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        # Should still succeed but without redirect key (or with success_url fallback)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_get_success_message_empty(self):
        """get_success_message returns empty string when success_message is ''."""
        mixin = AjaxFormMixin()
        mixin.success_message = ""
        mixin.object = MagicMock()
        result = mixin.get_success_message(MagicMock())
        assert result == ""

    def test_get_success_message_format_exception(self):
        """get_success_message catches format exception and returns raw message."""
        mixin = AjaxFormMixin()
        mixin.success_message = "Saved {object.broken_attribute}"
        mock_obj = MagicMock()
        # Make format raise by using a real object that doesn't have broken_attribute
        class FakeObj:
            pass
        mixin.object = FakeObj()
        result = mixin.get_success_message(MagicMock())
        # Should return raw message (not raise)
        assert result == "Saved {object.broken_attribute}"


# ============================================================
# SafeDeleteMixin — ProtectedError, general error, helper messages
# ============================================================

@pytest.mark.django_db
class TestSafeDeleteMixinProtectedError:
    """Test SafeDeleteMixin.delete() ProtectedError and general Exception paths."""

    def _make_delete_view(self, user, obj, model_class):
        """Build a minimal view instance mixing SafeDeleteMixin."""
        factory = RequestFactory()
        request = factory.post('/',
                               HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        request.user = user

        class MockView(SafeDeleteMixin):
            model = model_class
            success_url = '/success/'

            def get_object(self):
                return obj

            def get_success_url(self):
                return self.success_url

        view = MockView()
        view.request = request
        view.kwargs = {}
        view.args = []
        return view, request

    def test_protected_error_with_related_models_ajax(self, admin_user):
        """ProtectedError with related objects → JSON 400 with model names."""
        from django.db.models.deletion import ProtectedError
        from diamond_web.models.kanwil import Kanwil

        mock_obj = MagicMock()
        mock_obj.__str__ = MagicMock(return_value="Test Object")

        # Create a protected object mock
        protected_obj = MagicMock()
        protected_obj._meta.verbose_name_plural = "kantor wilayah"

        view, request = self._make_delete_view(admin_user, mock_obj, Kanwil)

        with patch.object(mock_obj, 'delete',
                          side_effect=ProtectedError("protected", {protected_obj})):
            response = view.delete(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False
        assert 'kantor wilayah' in data['message']

    def test_protected_error_without_related_models_ajax(self, admin_user):
        """ProtectedError with empty protected_objects → generic message."""
        from django.db.models.deletion import ProtectedError
        from diamond_web.models.kanwil import Kanwil

        mock_obj = MagicMock()
        mock_obj.__str__ = MagicMock(return_value="Test Object")

        view, request = self._make_delete_view(admin_user, mock_obj, Kanwil)

        with patch.object(mock_obj, 'delete',
                          side_effect=ProtectedError("protected", set())):
            response = view.delete(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False
        # no related_models → generic message
        assert 'masih digunakan' in data['message']

    def test_general_exception_ajax(self, admin_user):
        """General Exception in delete() → JSON 400 with generic message."""
        from diamond_web.models.kanwil import Kanwil

        mock_obj = MagicMock()
        mock_obj.__str__ = MagicMock(return_value="Test Object")

        view, request = self._make_delete_view(admin_user, mock_obj, Kanwil)

        with patch.object(mock_obj, 'delete',
                          side_effect=Exception("unexpected error")):
            response = view.delete(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False

    def test_protected_error_non_ajax(self, admin_user):
        """ProtectedError on non-AJAX request → JSON 400 (SafeDeleteMixin always returns JSON)."""
        from django.db.models.deletion import ProtectedError
        from diamond_web.models.kanwil import Kanwil

        factory = RequestFactory()
        request = factory.post('/')  # non-AJAX
        request.user = admin_user

        mock_obj = MagicMock()
        mock_obj.__str__ = MagicMock(return_value="Test Object")

        class MockView(SafeDeleteMixin):
            model = Kanwil
            success_url = '/success/'

            def get_object(self):
                return mock_obj

            def get_success_url(self):
                return self.success_url

        view = MockView()
        view.request = request

        protected_obj = MagicMock()
        protected_obj._meta.verbose_name_plural = "kpp"

        with patch.object(mock_obj, 'delete',
                          side_effect=ProtectedError("protected", {protected_obj})):
            # Need messages middleware for messages.error
            from django.contrib.messages.storage.fallback import FallbackStorage
            setattr(request, 'session', {})
            setattr(request, '_messages', FallbackStorage(request))
            response = view.delete(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False

    def test_general_exception_non_ajax(self, admin_user):
        """General Exception on non-AJAX → JSON 400."""
        from diamond_web.models.kanwil import Kanwil

        factory = RequestFactory()
        request = factory.post('/')
        request.user = admin_user

        mock_obj = MagicMock()
        mock_obj.__str__ = MagicMock(return_value="Test Object")

        class MockView(SafeDeleteMixin):
            model = Kanwil
            success_url = '/success/'

            def get_object(self):
                return mock_obj

            def get_success_url(self):
                return self.success_url

        view = MockView()
        view.request = request

        with patch.object(mock_obj, 'delete',
                          side_effect=Exception("db error")):
            from django.contrib.messages.storage.fallback import FallbackStorage
            setattr(request, 'session', {})
            setattr(request, '_messages', FallbackStorage(request))
            response = view.delete(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['success'] is False

    def test_get_protected_error_message_with_related(self, admin_user):
        """get_protected_error_message with related_models includes their names."""
        from diamond_web.models.kanwil import Kanwil

        class MockView(SafeDeleteMixin):
            model = Kanwil

        view = MockView()
        msg = view.get_protected_error_message("ObjName", ["kpp"])
        assert "kpp" in msg
        assert "ObjName" in msg

    def test_get_protected_error_message_without_related(self, admin_user):
        """get_protected_error_message without related_models uses generic message."""
        from diamond_web.models.kanwil import Kanwil

        class MockView(SafeDeleteMixin):
            model = Kanwil

        view = MockView()
        msg = view.get_protected_error_message("ObjName", [])
        assert "ObjName" in msg
        assert "masih digunakan" in msg

    def test_get_general_error_message(self):
        """get_general_error_message returns a non-empty string."""
        from diamond_web.models.kanwil import Kanwil

        class MockView(SafeDeleteMixin):
            model = Kanwil

        view = MockView()
        msg = view.get_general_error_message("some error")
        assert isinstance(msg, str)
        assert len(msg) > 0


# ============================================================
# context_processors.py — git helper branches
# ============================================================

class TestContextProcessorsGitHelpers:
    """Test context_processors git helper branches."""

    def test_get_git_commit_from_env_var(self):
        """Returns GIT_COMMIT_SHORT when set in environment."""
        import os
        from diamond_web import context_processors as cp
        with patch.dict(os.environ, {'GIT_COMMIT_SHORT': 'abc1234'}):
            result = cp._get_git_commit()
        assert result == 'abc1234'

    def test_get_git_commit_from_git_command(self):
        """Returns git output when subprocess.run succeeds."""
        from diamond_web import context_processors as cp
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'deadbeef\n'
        with patch('diamond_web.context_processors.subprocess.run',
                   return_value=mock_result):
            with patch.dict('os.environ', {}, clear=False):
                import os
                os.environ.pop('GIT_COMMIT_SHORT', None)
                os.environ.pop('GIT_COMMIT', None)
                result = cp._get_git_commit()
        assert result == 'deadbeef'

    def test_get_git_commit_subprocess_exception(self):
        """Falls through to GIT_COMMIT file when subprocess raises."""
        import os
        from diamond_web import context_processors as cp
        with patch('diamond_web.context_processors.subprocess.run',
                   side_effect=Exception("git not found")):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('GIT_COMMIT_SHORT', None)
                os.environ.pop('GIT_COMMIT', None)
                result = cp._get_git_commit()
        # Falls to file check or empty string
        assert isinstance(result, str)

    def test_get_git_long_and_date_success(self):
        """_get_git_long_and_date returns sha and date from git output."""
        from diamond_web import context_processors as cp
        from pathlib import Path
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'abc123def456;2024-01-15T10:00:00+07:00\n'
        with patch('diamond_web.context_processors.subprocess.run',
                   return_value=mock_result):
            long_sha, date_str = cp._get_git_long_and_date(Path('.'))
        assert long_sha == 'abc123def456'
        assert '2024-01-15' in date_str

    def test_get_git_long_and_date_exception(self):
        """_get_git_long_and_date returns env vars on exception."""
        import os
        from diamond_web import context_processors as cp
        from pathlib import Path
        with patch('diamond_web.context_processors.subprocess.run',
                   side_effect=Exception("no git")):
            with patch.dict(os.environ, {
                'GIT_COMMIT_LONG': 'longsha',
                'GIT_COMMIT_DATE': '2024-01-01',
            }):
                long_sha, date_str = cp._get_git_long_and_date(Path('.'))
        assert long_sha == 'longsha'
        assert date_str == '2024-01-01'

    def test_get_git_branch_success(self):
        """_get_git_branch returns branch name from git output."""
        from diamond_web import context_processors as cp
        from pathlib import Path
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'main\n'
        with patch('diamond_web.context_processors.subprocess.run',
                   return_value=mock_result):
            branch = cp._get_git_branch(Path('.'))
        assert branch == 'main'

    def test_get_git_branch_exception(self):
        """_get_git_branch returns env var on exception."""
        import os
        from diamond_web import context_processors as cp
        from pathlib import Path
        with patch('diamond_web.context_processors.subprocess.run',
                   side_effect=Exception("no git")):
            with patch.dict(os.environ, {'GIT_BRANCH': 'develop'}):
                branch = cp._get_git_branch(Path('.'))
        assert branch == 'develop'

    def test_git_commit_context_processor_date_parse(self, rf):
        """git_commit context processor handles ISO date with 'Z' suffix."""
        from diamond_web.context_processors import git_commit
        request = rf.get('/')
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'abc123def456;2024-01-15T03:00:00Z\n'
        with patch('diamond_web.context_processors.subprocess.run',
                   return_value=mock_result):
            context = git_commit(request)
        assert 'git_commit' in context
        assert 'git_commit_info' in context
        # The date should have been parsed
        assert '2024-01-15' in context['git_commit_info']['date']

    def test_git_commit_context_processor_invalid_date(self, rf):
        """git_commit context processor handles unparseable date string."""
        from diamond_web.context_processors import git_commit
        request = rf.get('/')
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'abc123;not-a-date\n'
        with patch('diamond_web.context_processors.subprocess.run',
                   return_value=mock_result):
            context = git_commit(request)
        assert 'git_commit' in context
        # Invalid date → commit_date_display = date_str (raw)
        assert context['git_commit_info']['date'] == 'not-a-date'
