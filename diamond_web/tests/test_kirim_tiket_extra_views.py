"""Tests for the KirimPideTemp workflow views in kirim_tiket.py that had
zero coverage: DownloadNDPengantarView, KirimPideTempUpdateView,
KirimPideTempDeleteView, KirimKePIDEView, plus the remaining branches of
KirimTiketView.form_valid (select_all_pages, already_generated, exception
paths).
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import TiketPIC
from diamond_web.models.kirim_pide_temp import KirimPideTemp
from diamond_web.models.notification import Notification
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory


def _p3de_user():
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    return user


def _eligible_tiket(p3de_user):
    """A tiket that qualifies for kirim-ke-PIDE generation."""
    tiket = TiketFactory(status_tiket=2, backup=True, tanda_terima=True)
    TiketPICFactory(id_tiket=tiket, id_user=p3de_user,
                     role=TiketPIC.Role.P3DE, active=True)
    return tiket


# ============================================================
# KirimTiketView.form_valid - remaining branches
# ============================================================

@pytest.mark.django_db
class TestKirimTiketFormValidBranches:
    def test_select_all_pages_mode(self, client):
        """select_all_pages='true' generates temps for every eligible tiket."""
        user = _p3de_user()
        tiket1 = _eligible_tiket(user)
        tiket2 = _eligible_tiket(user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket'),
            # clean_tiket_ids() requires a non-empty, existing id regardless of
            # select_all_pages; form_valid() re-queries and ignores it once the
            # flag is set, so any valid id satisfies form validation here.
            {'tiket_ids': str(tiket1.pk), 'select_all_pages': 'true'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert KirimPideTemp.objects.filter(id_tiket=tiket1).exists()
        assert KirimPideTemp.objects.filter(id_tiket=tiket2).exists()

    def test_select_all_pages_with_ilap_filter(self, client):
        """select_all_pages honours the posted ilap_id filter."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        ilap_id = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap_id
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket'),
            {'tiket_ids': str(tiket.pk), 'select_all_pages': 'true', 'ilap_id': str(ilap_id)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert KirimPideTemp.objects.filter(id_tiket=tiket).exists()

    def test_already_generated_tiket_rejected(self, client):
        """A tiket already in a KirimPideTemp batch is reported as already generated."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket'),
            {'tiket_ids': str(tiket.pk)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False
        assert 'sudah pernah digenerate' in data['message']

    def test_already_generated_non_ajax(self, client):
        """Non-AJAX path for the already-generated branch renders form_invalid."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket'),
            {'tiket_ids': str(tiket.pk)},
        )
        assert resp.status_code == 200
        assert 'text/html' in resp.get('Content-Type', '')

    def test_invalid_ids_non_ajax_shows_form_invalid(self, client):
        """Non-AJAX path for ineligible tiket_ids renders form_invalid (not JSON)."""
        user = _p3de_user()
        # status_tiket=1 (Direkam) never qualifies.
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket'),
            {'tiket_ids': str(tiket.pk)},
        )
        assert resp.status_code == 200
        assert 'text/html' in resp.get('Content-Type', '')

    def test_form_valid_exception_ajax(self, client):
        """An unexpected exception in form_valid returns a JSON error for AJAX."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        client.force_login(user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket.KirimPideTemp.objects.create',
            side_effect=Exception('boom'),
        ):
            resp = client.post(
                reverse('kirim_tiket'),
                {'tiket_ids': str(tiket.pk)},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False
        assert 'Gagal generate template' in data['errors']['__all__'][0]

    def test_form_valid_exception_non_ajax(self, client):
        """An unexpected exception in form_valid falls back to form_invalid for non-AJAX."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        client.force_login(user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket.KirimPideTemp.objects.create',
            side_effect=Exception('boom'),
        ):
            resp = client.post(
                reverse('kirim_tiket'),
                {'tiket_ids': str(tiket.pk)},
            )
        assert resp.status_code == 200
        assert 'text/html' in resp.get('Content-Type', '')

    def test_non_ajax_docx_generation_fallback(self, client):
        """When doc generation returns falsy, non-AJAX falls back to messages.success."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        client.force_login(user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket._generate_docx_for_tickets',
            return_value=None,
        ):
            resp = client.post(
                reverse('kirim_tiket'),
                {'tiket_ids': str(tiket.pk)},
            )
        assert resp.status_code in (200, 302)
        assert KirimPideTemp.objects.filter(id_tiket=tiket, id_user=user).exists()

    def test_single_tiket_mode_admin_sees_all_ilap(self, client):
        """Single-tiket GET context: admin/superuser sees every ILAP option."""
        user = _p3de_user()
        user.is_superuser = True
        user.save()
        tiket = _eligible_tiket(user)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_tiket_from_tiket', kwargs={'tiket_pk': tiket.pk})
        )
        assert resp.status_code == 200

    def test_batch_mode_ilap_filter_applied(self, client):
        """GET with ?ilap_id= filters the batch tiket list."""
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        ilap_id = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap_id
        client.force_login(user)

        resp = client.get(reverse('kirim_tiket'), {'ilap_id': str(ilap_id)})
        assert resp.status_code == 200
        assert resp.context['selected_ilap_id'] == str(ilap_id)


# ============================================================
# DownloadNDPengantarView
# ============================================================

@pytest.mark.django_db
class TestDownloadNDPengantarView:
    def test_get_success_returns_docx(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_tiket_download', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 200
        assert 'openxmlformats' in resp.get('Content-Type', '')

    def test_get_no_records_redirects(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.get(
            reverse('kirim_tiket_download', kwargs={'id_temp': 999999})
        )
        assert resp.status_code == 302

    def test_get_forbidden_for_non_owner(self, client):
        user = _p3de_user()
        other = _p3de_user()
        tiket = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_tiket_download', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 403

    def test_get_docx_generation_failure_redirects(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=3, id_tiket=tiket, id_user=user)
        client.force_login(user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket._generate_docx_for_tickets',
            return_value=None,
        ):
            resp = client.get(
                reverse('kirim_tiket_download', kwargs={'id_temp': temp.id_temp})
            )
        assert resp.status_code == 302


# ============================================================
# KirimPideTempUpdateView
# ============================================================

@pytest.mark.django_db
class TestKirimPideTempUpdateView:
    def test_get_success(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'html' in data

    def test_get_404_when_no_records(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.get(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': 999999})
        )
        assert resp.status_code == 404

    def test_get_403_for_non_owner(self, client):
        user = _p3de_user()
        other = _p3de_user()
        tiket = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 403

    def test_post_add_and_remove(self, client):
        """POST adds newly checked tikets and removes unchecked ones."""
        user = _p3de_user()
        tiket_in = _eligible_tiket(user)
        tiket_new = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket_in, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp}),
            {'tiket_ids': [str(tiket_new.pk)]},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert not KirimPideTemp.objects.filter(id_temp=1, id_tiket=tiket_in).exists()
        assert KirimPideTemp.objects.filter(id_temp=1, id_tiket=tiket_new).exists()

    def test_post_empty_checked_ids(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp}),
            {},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_404_when_no_records(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.post(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': 999999}),
            {'tiket_ids': ['1']},
        )
        assert resp.status_code == 404

    def test_post_403_for_non_owner(self, client):
        user = _p3de_user()
        other = _p3de_user()
        tiket = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp}),
            {'tiket_ids': [str(tiket.pk)]},
        )
        assert resp.status_code == 403

    def test_post_ignores_ineligible_tiket_id(self, client):
        """A checked id that is not eligible (not this user's active PIC) is skipped."""
        user = _p3de_user()
        other = _p3de_user()
        tiket_in = _eligible_tiket(user)
        ineligible = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket_in, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_update', kwargs={'id_temp': temp.id_temp}),
            {'tiket_ids': [str(tiket_in.pk), str(ineligible.pk)]},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert not KirimPideTemp.objects.filter(id_temp=1, id_tiket=ineligible).exists()


# ============================================================
# KirimPideTempDeleteView
# ============================================================

@pytest.mark.django_db
class TestKirimPideTempDeleteView:
    def test_post_success(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_delete', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert not KirimPideTemp.objects.filter(id_temp=1).exists()

    def test_post_404_when_no_records(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.post(
            reverse('kirim_tiket_temp_delete', kwargs={'id_temp': 999999})
        )
        assert resp.status_code == 404

    def test_post_403_for_non_owner(self, client):
        user = _p3de_user()
        other = _p3de_user()
        tiket = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_tiket_temp_delete', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 403


# ============================================================
# KirimKePIDEView
# ============================================================

@pytest.mark.django_db
class TestKirimKePIDEViewGet:
    def test_get_success(self, client):
        user = _p3de_user()
        tiket = _eligible_tiket(user)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.get(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp})
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'html' in data

    def test_get_404_when_no_records(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.get(reverse('kirim_ke_pide', kwargs={'id_temp': 999999}))
        assert resp.status_code == 404

    def test_get_403_for_non_owner(self, client):
        user = _p3de_user()
        other = _p3de_user()
        tiket = _eligible_tiket(other)
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.get(reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestKirimKePIDEViewPost:
    def _setup_ready_tiket(self):
        """Tiket ready for kirim-ke-pide: Diteliti, backup, tanda_terima, tgl_teliti set."""
        from datetime import datetime

        user = _p3de_user()
        tiket = TiketFactory(status_tiket=2, backup=True, tanda_terima=True)
        tiket.tgl_teliti = datetime(2018, 1, 1)
        tiket.save(update_fields=['tgl_teliti'])
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
        pide_user = _p3de_user()
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)
        return user, tiket, pide_user

    def test_post_success_transitions_status_and_notifies(self, client):
        user, tiket, pide_user = self._setup_ready_tiket()
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
            {
                'tgl_nadine': '2020-01-01',
                'nomor_nd_nadine': 'ND-100/2020',
                'tgl_kirim_pide': '2020-01-01',
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

        tiket.refresh_from_db()
        assert tiket.status_tiket == 4  # STATUS_DIKIRIM_KE_PIDE
        assert tiket.nomor_nd_nadine == 'ND-100/2020'
        assert TiketAction.objects.filter(id_tiket=tiket, action=4).exists()
        assert Notification.objects.filter(recipient=pide_user).exists()
        assert not KirimPideTemp.objects.filter(id_temp=temp.id_temp).exists()

    def test_post_404_when_no_records(self, client):
        user = _p3de_user()
        client.force_login(user)
        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': 999999}),
            {'tgl_nadine': '2020-01-01', 'nomor_nd_nadine': 'X', 'tgl_kirim_pide': '2020-01-01'},
        )
        assert resp.status_code == 404

    def test_post_403_for_non_owner(self, client):
        user = _p3de_user()
        other, tiket, _ = self._setup_ready_tiket()
        temp = KirimPideTemp.objects.create(id_temp=2, id_tiket=tiket, id_user=other)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
            {'tgl_nadine': '2020-01-01', 'nomor_nd_nadine': 'X', 'tgl_kirim_pide': '2020-01-01'},
        )
        assert resp.status_code == 403

    def test_post_preflight_rejects_not_ready_tiket(self, client):
        """Preflight guard rejects tikets missing backup/tanda_terima/tgl_teliti."""
        user = _p3de_user()
        tiket = TiketFactory(status_tiket=2, backup=False, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
            {'tgl_nadine': '2020-01-01', 'nomor_nd_nadine': 'X', 'tgl_kirim_pide': '2020-01-01'},
        )
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data['success'] is False
        assert 'belum backup' in data['message']

    def test_post_form_invalid_returns_400(self, client):
        user, tiket, _ = self._setup_ready_tiket()
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
            {'tgl_nadine': '', 'nomor_nd_nadine': '', 'tgl_kirim_pide': ''},
        )
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data['success'] is False
        assert 'errors' in data

    def test_post_form_invalid_kirim_before_nadine(self, client):
        """KirimKePideForm.clean rejects tgl_kirim_pide before tgl_nadine."""
        user, tiket, _ = self._setup_ready_tiket()
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        resp = client.post(
            reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
            {
                'tgl_nadine': '2020-01-10',
                'nomor_nd_nadine': 'ND-1',
                'tgl_kirim_pide': '2020-01-01',
            },
        )
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_exception_returns_500(self, client):
        user, tiket, _ = self._setup_ready_tiket()
        temp = KirimPideTemp.objects.create(id_temp=1, id_tiket=tiket, id_user=user)
        client.force_login(user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket.TiketAction.objects.create',
            side_effect=Exception('boom'),
        ):
            resp = client.post(
                reverse('kirim_ke_pide', kwargs={'id_temp': temp.id_temp}),
                {
                    'tgl_nadine': '2020-01-01',
                    'nomor_nd_nadine': 'ND-1',
                    'tgl_kirim_pide': '2020-01-01',
                },
            )
        assert resp.status_code == 500
        data = json.loads(resp.content)
        assert data['success'] is False
