"""Tests for the tiket special_request field.

Covers: model default, TiketForm handling, SpecialRequestView (modal action),
the tiket detail page rendering of the flag/button, and the daftar tiket
list filter.
"""
import json
from datetime import datetime

import pytest
from django.urls import reverse

from diamond_web.models import Tiket, TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.constants.tiket_action_types import SpecialRequestActionType
from diamond_web.forms.special_request import SpecialRequestForm
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, PICFactory, UserFactory,
    PeriodeJenisDataFactory,
)
from diamond_web.tests.test_rekam_tiket_gaps import (
    _build_tiket_post_data, _create_full_tiket_setup, _get_or_create_group,
)


# ============================================================
# Model
# ============================================================

@pytest.mark.django_db
class TestTiketSpecialRequestField:
    """Tiket.special_request – boolean, default False."""

    def test_defaults_to_false(self):
        tiket = TiketFactory()
        tiket.refresh_from_db()
        assert tiket.special_request is False

    def test_can_be_set_true(self):
        tiket = TiketFactory(special_request=True)
        tiket.refresh_from_db()
        assert tiket.special_request is True

    def test_field_is_boolean_with_default(self):
        field = Tiket._meta.get_field('special_request')
        assert field.get_internal_type() == 'BooleanField'
        assert field.default is False


@pytest.mark.django_db
class TestTiketTglSpecialRequestField:
    """Tiket.tgl_special_request – due date of the special request.

    Nullable at the database level (tikets without a special request have
    none); the forms require it whenever the flag is switched on.
    """

    def test_defaults_to_none(self):
        tiket = TiketFactory()
        tiket.refresh_from_db()
        assert tiket.tgl_special_request is None

    def test_can_be_set(self):
        due = datetime(2026, 8, 20, 23, 59, 59)
        tiket = TiketFactory(special_request=True, tgl_special_request=due)
        tiket.refresh_from_db()
        assert tiket.tgl_special_request == due

    def test_field_is_optional_datetime(self):
        field = Tiket._meta.get_field('tgl_special_request')
        assert field.get_internal_type() == 'DateTimeField'
        assert field.null is True
        assert field.blank is True


# ============================================================
# SpecialRequestForm
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestForm:
    """Unchecked checkbox must stay a valid submission (required=False)."""

    def test_valid_when_unchecked(self):
        tiket = TiketFactory(special_request=True)
        form = SpecialRequestForm(data={}, instance=tiket)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['special_request'] is False

    def test_valid_when_checked(self):
        tiket = TiketFactory()
        form = SpecialRequestForm(
            data={'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            instance=tiket,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data['special_request'] is True

    def test_initial_reflects_instance(self):
        tiket = TiketFactory(special_request=True)
        form = SpecialRequestForm(instance=tiket)
        assert form.initial['special_request'] is True

    def test_due_date_required_when_checked(self):
        tiket = TiketFactory()
        form = SpecialRequestForm(data={'special_request': 'on'}, instance=tiket)
        assert not form.is_valid()
        assert 'tgl_special_request' in form.errors

    def test_due_date_not_required_when_unchecked(self):
        tiket = TiketFactory()
        form = SpecialRequestForm(data={}, instance=tiket)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['tgl_special_request'] is None

    def test_due_date_stored_at_end_of_day(self):
        tiket = TiketFactory()
        form = SpecialRequestForm(
            data={'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            instance=tiket,
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data['tgl_special_request'] == datetime(2026, 8, 20, 23, 59, 59)

    def test_due_date_cleared_when_unchecked(self):
        tiket = TiketFactory(special_request=True,
                             tgl_special_request=datetime(2026, 8, 20, 23, 59, 59))
        form = SpecialRequestForm(data={'tgl_special_request': '2026-08-20'}, instance=tiket)
        assert form.is_valid(), form.errors
        assert form.cleaned_data['special_request'] is False
        assert form.cleaned_data['tgl_special_request'] is None


# ============================================================
# Rekam Tiket (create)
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestOnRekamTiket:
    """TiketRekamCreateView persists the special_request checkbox."""

    def _admin(self):
        admin = UserFactory(is_staff=True, is_superuser=True)
        admin.groups.add(_get_or_create_group('admin'))
        return admin

    def test_checked_creates_tiket_with_special_request(self, client):
        admin = self._admin()
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'
        post_data['special_request'] = 'on'
        post_data['tgl_special_request'] = '2026-08-20'

        client.force_login(admin)
        resp = client.post(reverse('tiket_rekam_create'), post_data, follow=True)
        assert resp.status_code == 200

        created = Tiket.objects.filter(id_periode_data=pd).first()
        assert created is not None
        assert created.special_request is True

    def test_checked_without_due_date_is_accepted(self, client):
        """The due date is optional for a special request tiket.

        It was mandatory until the switch was made truly optional; the tiket
        must now save with the switch on and no ``tgl_special_request``.
        """
        admin = self._admin()
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'
        post_data['special_request'] = 'on'

        client.force_login(admin)
        resp = client.post(reverse('tiket_rekam_create'), post_data, follow=True)
        assert resp.status_code == 200

        created = Tiket.objects.filter(id_periode_data=pd).first()
        assert created is not None
        assert created.special_request is True
        assert created.tgl_special_request is None

    def test_checked_persists_due_date(self, client):
        admin = self._admin()
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'
        post_data['special_request'] = 'on'
        post_data['tgl_special_request'] = '2026-08-20'

        client.force_login(admin)
        resp = client.post(reverse('tiket_rekam_create'), post_data, follow=True)
        assert resp.status_code == 200

        created = Tiket.objects.filter(id_periode_data=pd).first()
        assert created is not None
        assert created.tgl_special_request == datetime(2026, 8, 20, 23, 59, 59)

    def test_due_date_ignored_when_not_special_request(self, client):
        admin = self._admin()
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'
        post_data['tgl_special_request'] = '2026-08-20'

        client.force_login(admin)
        resp = client.post(reverse('tiket_rekam_create'), post_data, follow=True)
        assert resp.status_code == 200

        created = Tiket.objects.filter(id_periode_data=pd).first()
        assert created is not None
        assert created.special_request is False
        assert created.tgl_special_request is None

    def test_unchecked_creates_tiket_without_special_request(self, client):
        admin = self._admin()
        _, pd = _create_full_tiket_setup()
        post_data = _build_tiket_post_data(pd)
        post_data['status_ketersediaan_data'] = '1'

        client.force_login(admin)
        resp = client.post(reverse('tiket_rekam_create'), post_data, follow=True)
        assert resp.status_code == 200

        created = Tiket.objects.filter(id_periode_data=pd).first()
        assert created is not None
        assert created.special_request is False


# ============================================================
# SpecialRequestView
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestView:
    """SpecialRequestView – the active PIC owning the tiket (by status) toggles the flag.

    status 1-3 -> P3DE, status 4-5 -> PIDE, status 6 -> PMDE, status 7-8 -> nobody.
    """

    def _setup_p3de(self, user, status=1, **tiket_kwargs):
        tiket = TiketFactory(status_tiket=status, **tiket_kwargs)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def _setup_pide(self, user, status=4, **tiket_kwargs):
        tiket = TiketFactory(status_tiket=status, **tiket_kwargs)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.PIDE, active=True)
        return tiket

    def _setup_pmde(self, user, status=6, **tiket_kwargs):
        tiket = TiketFactory(status_tiket=status, **tiket_kwargs)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.PMDE, active=True)
        return tiket

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, authenticated_user, tiket):
        client.force_login(authenticated_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_for_inactive_pic(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=False)
        client.force_login(authenticated_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_pmde_allowed_at_pengendalian_mutu(self, client, pmde_user):
        """PMDE PIC may edit while the tiket is in Pengendalian Mutu (status 6)."""
        tiket = self._setup_pmde(pmde_user)
        client.force_login(pmde_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.special_request is True

    def test_p3de_denied_when_status_owned_by_pide(self, client, authenticated_user):
        """A P3DE PIC cannot edit once the tiket has moved to PIDE (status 4)."""
        tiket = self._setup_p3de(authenticated_user, status=4)
        client.force_login(authenticated_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_pide_denied_when_status_owned_by_p3de(self, client, pide_user):
        """A PIDE PIC cannot edit while the tiket is still with P3DE (status 1)."""
        tiket = self._setup_pide(pide_user, status=1)
        client.force_login(pide_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_pmde_denied_when_status_not_pengendalian_mutu(self, client, pmde_user):
        """A PMDE PIC cannot edit outside Pengendalian Mutu (e.g. status 1)."""
        tiket = self._setup_pmde(pmde_user, status=1)
        client.force_login(pmde_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_for_final_statuses(self, client, authenticated_user):
        """No PIC may edit once the tiket is Dibatalkan (7) or Selesai (8)."""
        for status in (7, 8):
            tiket = self._setup_p3de(authenticated_user, status=status)
            client.force_login(authenticated_user)
            resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
            assert resp.status_code in (302, 403)

    def test_ajax_denied_returns_json_403(self, client, authenticated_user, tiket):
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('special_request_tiket', args=[tiket.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 403
        assert resp.json()['success'] is False

    def test_get_modal_form_as_p3de(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code == 200
        assert b'special_request' in resp.content

    def test_get_modal_form_as_pide(self, client, pide_user):
        tiket = self._setup_pide(pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('special_request_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_p3de_enables_special_request(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20',
             'catatan': 'Permintaan mendesak'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.special_request is True

    def test_pide_enables_special_request(self, client, pide_user):
        tiket = self._setup_pide(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.special_request is True

    def test_unchecked_disables_special_request(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user, special_request=True)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'catatan': 'Tidak jadi'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.special_request is False

    def test_ajax_post_returns_json(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['success'] is True
        assert payload['special_request'] is True
        tiket.refresh_from_db()
        assert tiket.special_request is True

    def test_records_action_when_enabled(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20',
             'catatan': 'Permintaan Direktur'},
        )
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=SpecialRequestActionType.DIAKTIFKAN
        ).first()
        assert action is not None
        assert action.catatan == 'Permintaan Direktur'
        assert action.id_user == authenticated_user

    def test_records_action_when_disabled(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user, special_request=True)
        client.force_login(authenticated_user)
        client.post(reverse('special_request_tiket', args=[tiket.pk]), {})
        assert TiketAction.objects.filter(
            id_tiket=tiket, action=SpecialRequestActionType.DINONAKTIFKAN
        ).exists()

    def test_no_action_when_value_unchanged(self, client, authenticated_user):
        tiket = self._setup_p3de(
            authenticated_user, special_request=True,
            tgl_special_request=datetime(2026, 8, 20, 23, 59, 59),
        )
        client.force_login(authenticated_user)
        client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
        )
        tiket.refresh_from_db()
        assert tiket.special_request is True
        assert not TiketAction.objects.filter(
            id_tiket=tiket,
            action__in=[SpecialRequestActionType.DIAKTIFKAN,
                        SpecialRequestActionType.DINONAKTIFKAN],
        ).exists()

    def test_does_not_change_other_fields(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        original_status = tiket.status_tiket
        original_baris = tiket.baris_diterima
        client.force_login(authenticated_user)
        client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20',
             'status_tiket': 7, 'baris_diterima': 999999},
        )
        tiket.refresh_from_db()
        assert tiket.special_request is True
        assert tiket.status_tiket == original_status
        assert tiket.baris_diterima == original_baris

    def test_enabling_persists_due_date(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.special_request is True
        assert tiket.tgl_special_request == datetime(2026, 8, 20, 23, 59, 59)

    def test_enabling_without_due_date_is_rejected(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload['success'] is False
        assert 'tgl_special_request' in payload['errors']
        tiket.refresh_from_db()
        assert tiket.special_request is False
        assert tiket.tgl_special_request is None

    def test_disabling_clears_due_date(self, client, authenticated_user):
        tiket = self._setup_p3de(
            authenticated_user, special_request=True,
            tgl_special_request=datetime(2026, 8, 20, 23, 59, 59),
        )
        client.force_login(authenticated_user)
        client.post(reverse('special_request_tiket', args=[tiket.pk]), {})
        tiket.refresh_from_db()
        assert tiket.special_request is False
        assert tiket.tgl_special_request is None

    def test_changing_only_due_date_records_action(self, client, authenticated_user):
        tiket = self._setup_p3de(
            authenticated_user, special_request=True,
            tgl_special_request=datetime(2026, 8, 20, 23, 59, 59),
        )
        client.force_login(authenticated_user)
        client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-09-30'},
        )
        tiket.refresh_from_db()
        assert tiket.tgl_special_request == datetime(2026, 9, 30, 23, 59, 59)
        action = TiketAction.objects.filter(
            id_tiket=tiket, action=SpecialRequestActionType.DIAKTIFKAN
        ).first()
        assert action is not None
        assert '30-09-2026' in action.catatan

    def test_no_action_when_flag_and_due_date_unchanged(self, client, authenticated_user):
        tiket = self._setup_p3de(
            authenticated_user, special_request=True,
            tgl_special_request=datetime(2026, 8, 20, 23, 59, 59),
        )
        client.force_login(authenticated_user)
        client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
        )
        assert not TiketAction.objects.filter(
            id_tiket=tiket,
            action__in=[SpecialRequestActionType.DIAKTIFKAN,
                        SpecialRequestActionType.DINONAKTIFKAN],
        ).exists()

    def test_ajax_post_returns_due_date(self, client, authenticated_user):
        tiket = self._setup_p3de(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on', 'tgl_special_request': '2026-08-20'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        assert resp.json()['tgl_special_request'] == '20-08-2026'

    def test_other_user_cannot_toggle(self, client, authenticated_user):
        """A P3DE PIC of another tiket cannot toggle this one."""
        tiket = self._setup_p3de(authenticated_user)
        other = UserFactory()
        client.force_login(other)
        resp = client.post(
            reverse('special_request_tiket', args=[tiket.pk]),
            {'special_request': 'on'},
        )
        assert resp.status_code in (302, 403)
        tiket.refresh_from_db()
        assert tiket.special_request is False


# ============================================================
# Detail page integration
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestOnDetailPage:
    """Detail page shows the flag and offers the modal button to active PICs."""

    def _active_pic_tiket(self, user, tipe, role, status):
        tiket = TiketFactory(status_tiket=status)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=role, active=True)
        # Active PIC record (no end_date) is required for user_is_active_pic_*
        PICFactory(
            tipe=tipe,
            id_sub_jenis_data_ilap=tiket.id_periode_data.id_sub_jenis_data_ilap,
            id_user=user,
            end_date=None,
        )
        return tiket

    def _active_p3de_tiket(self, user, status=1):
        return self._active_pic_tiket(user, 'P3DE', TiketPIC.Role.P3DE, status)

    def test_detail_shows_special_request_value(self, client, authenticated_user):
        tiket = self._active_p3de_tiket(authenticated_user)
        tiket.special_request = True
        tiket.save(update_fields=['special_request'])
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert resp.context['tiket_details']['special_request'] == 'Ya'
        assert b'Permintaan Khusus' in resp.content

    def test_detail_shows_due_date(self, client, authenticated_user):
        tiket = self._active_p3de_tiket(authenticated_user)
        tiket.special_request = True
        tiket.tgl_special_request = datetime(2026, 8, 20, 23, 59, 59)
        tiket.save(update_fields=['special_request', 'tgl_special_request'])
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert resp.context['tiket_details']['tgl_special_request'] == tiket.tgl_special_request
        assert b'Jatuh Tempo Permintaan Khusus' in resp.content

    def test_detail_hides_due_date_when_not_special_request(self, client, authenticated_user):
        tiket = self._active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert b'Jatuh Tempo Permintaan Khusus' not in resp.content

    def test_button_visible_for_active_p3de(self, client, authenticated_user):
        tiket = self._active_p3de_tiket(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_special_request'] is True
        assert b'specialRequestModal' in resp.content

    def test_button_hidden_for_non_pic(self, client, admin_user):
        tiket = TiketFactory(status_tiket=1)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert resp.context['user_can_edit_special_request'] is False
        assert b'Ubah Permintaan Khusus' not in resp.content

    def test_button_visible_for_active_pide_at_pide_status(self, client, pide_user):
        tiket = self._active_pic_tiket(pide_user, 'PIDE', TiketPIC.Role.PIDE, status=4)
        client.force_login(pide_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_special_request'] is True
        assert b'specialRequestModal' in resp.content

    def test_button_visible_for_active_pmde_at_pengendalian_mutu(self, client, pmde_user):
        tiket = self._active_pic_tiket(pmde_user, 'PMDE', TiketPIC.Role.PMDE, status=6)
        client.force_login(pmde_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_special_request'] is True

    def test_button_hidden_for_p3de_when_status_owned_by_pide(self, client, authenticated_user):
        # P3DE PIC, but tiket already moved to PIDE (status 4)
        tiket = self._active_p3de_tiket(authenticated_user, status=4)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_special_request'] is False
        assert b'Ubah Permintaan Khusus' not in resp.content

    def test_button_hidden_for_final_status(self, client, authenticated_user):
        # Active P3DE PIC but tiket is Selesai (status 8) -> no one may edit
        tiket = self._active_p3de_tiket(authenticated_user, status=8)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.context['user_can_edit_special_request'] is False
        assert b'Ubah Permintaan Khusus' not in resp.content


# ============================================================
# Daftar Tiket list filter
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestListFilter:
    """The tiket_data endpoint filters and exposes options for special_request."""

    def test_filter_options_includes_special_request(self, client, admin_user, tiket):
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {'get_filter_options': '1'})
        assert resp.status_code == 200
        opts = json.loads(resp.content)['filter_options']
        assert 'special_request' in opts

    def test_filter_options_reflects_present_values(self, client, admin_user):
        TiketFactory(special_request=True)
        TiketFactory(special_request=False)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {'get_filter_options': '1'})
        opts = json.loads(resp.content)['filter_options']['special_request']
        ids = {o['id'] for o in opts}
        assert ids == {'1', '0'}

    def test_filter_yes_returns_only_special_request_tikets(self, client, admin_user):
        special = TiketFactory(special_request=True)
        TiketFactory(special_request=False)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '100',
            'special_request': '1',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        ids = {row['id'] for row in data['data']}
        assert special.id in ids
        assert all(row['special_request'] == 'Ya' for row in data['data'])

    def test_filter_no_returns_only_non_special_request_tikets(self, client, admin_user):
        TiketFactory(special_request=True)
        normal = TiketFactory(special_request=False)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '100',
            'special_request': '0',
        })
        data = json.loads(resp.content)
        ids = {row['id'] for row in data['data']}
        assert normal.id in ids
        assert all(row['special_request'] == 'Tidak' for row in data['data'])

    def test_row_data_includes_special_request(self, client, admin_user, tiket):
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        data = json.loads(resp.content)
        assert data['data']
        assert 'special_request' in data['data'][0]


# ============================================================
# Permintaan Khusus on the Tugas Saya home page
# ============================================================

@pytest.mark.django_db
class TestSpecialRequestHomeTask:
    """Home page (Tugas Saya) exposes the Permintaan Khusus category."""

    def test_menu_shown_for_user_role(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert b'data-filter="special_request"' in resp.content
        assert b'Permintaan Khusus' in resp.content

    def test_menu_shown_for_kasi_role(self, client, kasi_pide_user):
        client.force_login(kasi_pide_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert b'data-filter="special_request"' in resp.content

    def test_count_reflects_pic_special_request_tikets(self, client, authenticated_user):
        pjd = PeriodeJenisDataFactory()
        # A special-request tiket the user is an active PIC for
        special = TiketFactory(special_request=True, id_periode_data=pjd)
        TiketPICFactory(id_tiket=special, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        # A special-request tiket the user is NOT a PIC for (excluded)
        TiketFactory(special_request=True, id_periode_data=pjd)
        # A normal tiket the user is a PIC for (excluded)
        normal = TiketFactory(special_request=False, id_periode_data=pjd)
        TiketPICFactory(id_tiket=normal, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.context['special_request_count'] == 1

    def test_kasi_count_includes_all_special_request_tikets(self, client, kasi_p3de_user):
        pjd = PeriodeJenisDataFactory()
        TiketFactory(special_request=True, id_periode_data=pjd)
        TiketFactory(special_request=True, id_periode_data=pjd)
        TiketFactory(special_request=False, id_periode_data=pjd)
        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home'))
        assert resp.context['special_request_count'] == 2

    def test_data_endpoint_returns_only_pic_special_request(self, client, authenticated_user):
        pjd = PeriodeJenisDataFactory()
        special = TiketFactory(special_request=True, id_periode_data=pjd)
        TiketPICFactory(id_tiket=special, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        other = TiketFactory(special_request=True, id_periode_data=pjd)  # not a PIC → excluded
        normal = TiketFactory(special_request=False, id_periode_data=pjd)
        TiketPICFactory(id_tiket=normal, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), {
            'draw': '1', 'start': '0', 'length': '100',
            'category': 'special_request',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        nomors = {row['nomor_tiket'] for row in data['data']}
        assert special.nomor_tiket in nomors
        assert other.nomor_tiket not in nomors
        assert normal.nomor_tiket not in nomors

    def test_data_row_has_requested_columns(self, client, authenticated_user):
        special = TiketFactory(special_request=True)
        TiketPICFactory(id_tiket=special, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'category': 'special_request',
        })
        data = json.loads(resp.content)
        assert data['data']
        row = data['data'][0]
        for key in ('nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'status_tiket',
                    'tgl_special_request', 'actions'):
            assert key in row

    def test_data_row_formats_due_date(self, client, authenticated_user):
        special = TiketFactory(special_request=True,
                               tgl_special_request=datetime(2026, 8, 20, 23, 59, 59))
        TiketPICFactory(id_tiket=special, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'category': 'special_request',
        })
        row = json.loads(resp.content)['data'][0]
        assert row['tgl_special_request'] == '20-08-2026'
        assert row['tgl_special_request_order'] == '2026-08-20'

    def test_data_can_be_ordered_by_due_date(self, client, authenticated_user):
        pjd = PeriodeJenisDataFactory()
        later = TiketFactory(special_request=True, id_periode_data=pjd,
                             tgl_special_request=datetime(2026, 9, 30, 23, 59, 59))
        earlier = TiketFactory(special_request=True, id_periode_data=pjd,
                               tgl_special_request=datetime(2026, 8, 20, 23, 59, 59))
        for t in (later, earlier):
            TiketPICFactory(id_tiket=t, id_user=authenticated_user,
                            role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'category': 'special_request',
            'order[0][column]': '4', 'order[0][dir]': 'asc',
        })
        rows = json.loads(resp.content)['data']
        assert [r['nomor_tiket'] for r in rows] == [earlier.nomor_tiket, later.nomor_tiket]
