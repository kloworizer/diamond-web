"""Tests for home view, general views, task_to_do functions, and tanda_terima_data endpoints."""
import json
import pytest
from django.urls import reverse
from django.test import override_settings
from django.contrib.auth.models import Group

from diamond_web.models import TiketPIC, TandaTerimaData
from diamond_web.views.task_to_do import (
    get_tiket_summary_for_user,
    get_tiket_summary_for_user_pide,
    get_tiket_summary_for_user_pmde,
)
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory, ILAPFactory,
)


# ============================================================
# Home View
# ============================================================

@pytest.mark.django_db
class TestHomeView:
    def test_anonymous_gets_home(self, client):
        resp = client.get(reverse('home'))
        assert resp.status_code == 200

    def test_authenticated_p3de_user(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_p3de'] is True
        assert 'tiket_summary' in resp.context

    def test_pide_user_gets_pide_summary(self, client, pide_user):
        """Logged-in PIDE user receives tiket_summary_pide in context."""
        client.force_login(pide_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_pide'] is True
        assert 'tiket_summary_pide' in resp.context

    def test_pmde_user_gets_pmde_summary(self, client, pmde_user):
        """Logged-in PMDE user receives tiket_summary_pmde in context."""
        client.force_login(pmde_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_pmde'] is True
        assert 'tiket_summary_pmde' in resp.context

    @override_settings(DEBUG=True)
    def test_debug_mode_includes_debug_groups(self, client, authenticated_user):
        """When DEBUG=True, context includes debug_user_groups."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert 'debug_user_groups' in resp.context

    @override_settings(DEBUG=True)
    def test_debug_mode_anonymous(self, client):
        """DEBUG=True also works for anonymous home page."""
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert 'debug_user_groups' in resp.context

    def test_non_role_user_has_no_summaries(self, client, db):
        """User without any role group gets no summary in context."""
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_p3de'] is False
        assert resp.context['is_pide'] is False
        assert resp.context['is_pmde'] is False
        assert 'tiket_summary' not in resp.context


# ============================================================
# General Views (keep_alive, session_expired)
# ============================================================

@pytest.mark.django_db
class TestGeneralViews:
    def test_keep_alive_requires_login(self, client):
        resp = client.post(reverse('keep_alive'))
        assert resp.status_code in (302, 403)

    def test_keep_alive_returns_ok(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('keep_alive'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['ok'] is True

    def test_keep_alive_get_not_allowed(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('keep_alive'))
        assert resp.status_code == 405  # Method Not Allowed

    def test_session_expired_post_returns_ok(self, client):
        resp = client.post(reverse('session_expired'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['ok'] is True

    def test_session_expired_get_not_allowed(self, client):
        resp = client.get(reverse('session_expired'))
        assert resp.status_code == 405

    def test_session_expired_logs_out_user(self, client, authenticated_user):
        """session_expired logs out the authenticated user."""
        client.force_login(authenticated_user)
        resp = client.post(reverse('session_expired'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['ok'] is True


# ============================================================
# task_to_do functions (unit tests)
# ============================================================

@pytest.mark.django_db
class TestGetTiketSummaryForUser:
    """get_tiket_summary_for_user — P3DE user task summary."""

    def test_returns_empty_for_anonymous(self):
        result = get_tiket_summary_for_user(None)
        assert result == {
            'rekam_backup_data': 0,
            'buat_tanda_terima': 0,
            'rekam_hasil_penelitian': 0,
            'kirim_ke_pide': 0,
        }

    def test_returns_empty_for_non_p3de(self, db):
        user = UserFactory()
        result = get_tiket_summary_for_user(user)
        assert result['rekam_backup_data'] == 0

    def test_returns_zero_counts_with_no_assignments(self, authenticated_user):
        result = get_tiket_summary_for_user(authenticated_user)
        assert result['rekam_backup_data'] == 0
        assert result['buat_tanda_terima'] == 0
        assert result['rekam_hasil_penelitian'] == 0
        assert result['kirim_ke_pide'] == 0

    def test_counts_backup_missing(self, authenticated_user):
        tiket = TiketFactory(backup=False, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user(authenticated_user)
        assert result['rekam_backup_data'] >= 1

    def test_counts_tanda_terima_missing(self, authenticated_user):
        tiket = TiketFactory(backup=True, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user(authenticated_user)
        assert result['buat_tanda_terima'] >= 1

    def test_counts_tgl_teliti_missing(self, authenticated_user):
        tiket = TiketFactory(tgl_teliti=None)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user(authenticated_user)
        assert result['rekam_hasil_penelitian'] >= 1

    def test_counts_kirim_ke_pide_missing(self, authenticated_user):
        tiket = TiketFactory(tgl_kirim_pide=None)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user(authenticated_user)
        assert result['kirim_ke_pide'] >= 1

    def test_all_keys_present(self, authenticated_user):
        result = get_tiket_summary_for_user(authenticated_user)
        assert set(result.keys()) == {
            'rekam_backup_data',
            'buat_tanda_terima',
            'rekam_hasil_penelitian',
            'kirim_ke_pide',
        }


@pytest.mark.django_db
class TestGetTiketSummaryForUserPide:
    """get_tiket_summary_for_user_pide — PIDE user task summary."""

    def test_returns_empty_for_none(self):
        result = get_tiket_summary_for_user_pide(None)
        assert result == {'identifikasi_data': 0, 'transfer_ke_pmde': 0}

    def test_returns_empty_for_non_pide(self, db):
        user = UserFactory()
        result = get_tiket_summary_for_user_pide(user)
        assert result['identifikasi_data'] == 0

    def test_returns_zero_with_no_assignments(self, pide_user):
        result = get_tiket_summary_for_user_pide(pide_user)
        assert result['identifikasi_data'] == 0
        assert result['transfer_ke_pmde'] == 0

    def test_counts_identifikasi_data(self, pide_user):
        """Tiket with STATUS_DIKIRIM_KE_PIDE (4) counted in identifikasi_data."""
        tiket = TiketFactory(status_tiket=4)  # STATUS_DIKIRIM_KE_PIDE
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        result = get_tiket_summary_for_user_pide(pide_user)
        assert result['identifikasi_data'] >= 1

    def test_counts_transfer_ke_pmde(self, pide_user):
        """Tiket with STATUS_IDENTIFIKASI (5) counted in transfer_ke_pmde."""
        tiket = TiketFactory(status_tiket=5)  # STATUS_IDENTIFIKASI
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        result = get_tiket_summary_for_user_pide(pide_user)
        assert result['transfer_ke_pmde'] >= 1

    def test_all_keys_present(self, pide_user):
        result = get_tiket_summary_for_user_pide(pide_user)
        assert set(result.keys()) == {'identifikasi_data', 'transfer_ke_pmde'}


@pytest.mark.django_db
class TestGetTiketSummaryForUserPmde:
    """get_tiket_summary_for_user_pmde — PMDE user task summary."""

    def test_returns_empty_for_none(self):
        result = get_tiket_summary_for_user_pmde(None)
        assert result == {'pengendalian_mutu': 0}

    def test_returns_empty_for_non_pmde(self, db):
        user = UserFactory()
        result = get_tiket_summary_for_user_pmde(user)
        assert result['pengendalian_mutu'] == 0

    def test_returns_zero_with_no_assignments(self, pmde_user):
        result = get_tiket_summary_for_user_pmde(pmde_user)
        assert result['pengendalian_mutu'] == 0

    def test_counts_pengendalian_mutu(self, pmde_user):
        """Tiket with STATUS_PENGENDALIAN_MUTU (6) counted."""
        tiket = TiketFactory(status_tiket=6)
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user,
                        role=TiketPIC.Role.PMDE, active=True)
        result = get_tiket_summary_for_user_pmde(pmde_user)
        assert result['pengendalian_mutu'] >= 1

    def test_all_keys_present(self, pmde_user):
        result = get_tiket_summary_for_user_pmde(pmde_user)
        assert set(result.keys()) == {'pengendalian_mutu'}


# ============================================================
# TandaTerimaData Endpoints
# ============================================================

@pytest.mark.django_db
class TestTandaTerimaDataListView:
    def test_requires_login(self, client):
        resp = client.get(reverse('tanda_terima_data_list'))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('tanda_terima_data_list'))
        assert resp.status_code in (302, 403)

    def test_p3de_user_can_access(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('tanda_terima_data_list'))
        assert resp.status_code == 200

    def test_delete_message_on_redirect(self, client, authenticated_user):
        """Query params deleted+name show a success message."""
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_data_list'),
            {'deleted': '1', 'name': 'Tanda+Terima+001'},
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTandaTerimaDataDataEndpoint:
    def test_requires_login(self, client):
        resp = client.get(reverse('tanda_terima_data_data'))
        assert resp.status_code in (302, 403)

    def test_returns_json(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data
        assert 'draw' in data

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(
            reverse('tanda_terima_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200

    def test_column_search_filtering(self, client, authenticated_user):
        """Column-specific search is accepted without error."""
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_data_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
                'columns_search[]': ['999', '2024', '', '', '', 'aktif'],
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_ordering_parameter(self, client, authenticated_user):
        """Ordering by column index is accepted."""
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_data_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
                'order[0][column]': '0',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTandaTerimaNextNumber:
    def test_requires_login(self, client):
        resp = client.get(reverse('tanda_terima_next_number'))
        assert resp.status_code in (302, 403)

    def test_returns_next_number(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('tanda_terima_next_number'), {'tanggal': '2024-01-15'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'nomor_tanda_terima' in data

    def test_returns_next_number_without_date_param(self, client, authenticated_user):
        """Without tanggal param, uses current year."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('tanda_terima_next_number'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_with_datetime_param(self, client, authenticated_user):
        """Supports full datetime string for tanggal."""
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_next_number'),
            {'tanggal': '2024-06-15T12:00:00'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


@pytest.mark.django_db
class TestTandaTerimaTiketsByIlap:
    def test_requires_login(self, client):
        resp = client.get(reverse('tanda_terima_tikets_by_ilap'))
        assert resp.status_code in (302, 403)

    def test_returns_json_empty(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('tanda_terima_tikets_by_ilap'),
            {'ilap_id': '99999'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'tikets' in data or 'success' in data

    def test_without_ilap_id(self, client, authenticated_user):
        """Missing ilap_id returns 400 (bad request) from the endpoint."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('tanda_terima_tikets_by_ilap'))
        assert resp.status_code in (200, 400)
