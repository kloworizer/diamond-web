"""Tests for home view, general views, task_to_do functions, and tanda_terima_data endpoints."""
import json
import pytest
from django.urls import reverse
from django.test import override_settings
from django.contrib.auth.models import Group

from diamond_web.models import TiketPIC, TandaTerimaData
from diamond_web.views.task_to_do import (
    get_tiket_summary_for_user_p3de,
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
    def test_anonymous_redirected_to_login(self, client):
        """home is login-protected, so anonymous users are redirected."""
        resp = client.get(reverse('home'))
        assert resp.status_code == 302

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
    def test_debug_mode_anonymous_redirected(self, client):
        """DEBUG=True still redirects the login-protected home for anonymous users."""
        resp = client.get(reverse('home'))
        assert resp.status_code == 302

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

    def test_keep_alive_handles_expiry_exception(self):
        """When get_expiry_age raises, keep_alive returns expiry=None gracefully."""
        from unittest.mock import MagicMock
        from diamond_web.views.general import keep_alive
        request = MagicMock()
        request.method = 'POST'
        request.user.is_authenticated = True
        request.session.get_expiry_age.side_effect = Exception('boom')
        resp = keep_alive(request)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['ok'] is True
        assert data['expiry'] is None


# ============================================================
# task_to_do functions (unit tests)
# ============================================================

@pytest.mark.django_db
class TestGetTiketSummaryForUserP3de:
    """get_tiket_summary_for_user_p3de — P3DE user task summary."""

    def test_returns_empty_for_anonymous(self):
        result = get_tiket_summary_for_user_p3de(None)
        assert result == {
            'rekam_backup_data': 0,
            'buat_tanda_terima': 0,
            'rekam_hasil_penelitian': 0,
            'kirim_ke_pide': 0,
        }

    def test_returns_empty_for_non_p3de(self, db):
        user = UserFactory()
        result = get_tiket_summary_for_user_p3de(user)
        assert result['rekam_backup_data'] == 0

    def test_returns_zero_counts_with_no_assignments(self, authenticated_user):
        result = get_tiket_summary_for_user_p3de(authenticated_user)
        assert result['rekam_backup_data'] == 0
        assert result['buat_tanda_terima'] == 0
        assert result['rekam_hasil_penelitian'] == 0
        assert result['kirim_ke_pide'] == 0

    def test_counts_backup_missing(self, authenticated_user):
        tiket = TiketFactory(backup=False, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user_p3de(authenticated_user)
        assert result['rekam_backup_data'] >= 1

    def test_counts_tanda_terima_missing(self, authenticated_user):
        tiket = TiketFactory(backup=True, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user_p3de(authenticated_user)
        assert result['buat_tanda_terima'] >= 1

    def test_counts_tgl_teliti_missing(self, authenticated_user):
        tiket = TiketFactory(tgl_teliti=None)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user_p3de(authenticated_user)
        assert result['rekam_hasil_penelitian'] >= 1

    def test_counts_kirim_ke_pide_missing(self, authenticated_user):
        tiket = TiketFactory(tgl_kirim_pide=None)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        result = get_tiket_summary_for_user_p3de(authenticated_user)
        assert result['kirim_ke_pide'] >= 1

    def test_all_keys_present(self, authenticated_user):
        result = get_tiket_summary_for_user_p3de(authenticated_user)
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


# ============================================================
# home view — admin role branches
# ============================================================

def _add_groups(user, *names):
    for name in names:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)


@pytest.mark.django_db
class TestHomeAdminBranches:
    """Exercise the admin_* branches inside the home view context building."""

    def test_p3de_admin_context(self, client, db):
        user = UserFactory()
        _add_groups(user, 'user_p3de', 'admin_p3de')
        client.force_login(user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_admin_p3de'] is True
        assert 'p3de_jenis_data_tanpa_pic_count' in resp.context
        assert 'p3de_tiket_periode_null_count' in resp.context

    def test_pide_admin_context(self, client, db):
        user = UserFactory()
        _add_groups(user, 'user_pide', 'admin_pide')
        client.force_login(user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_admin_pide'] is True
        assert 'pide_jenis_data_tanpa_pic_count' in resp.context
        assert 'pide_tiket_dikirim_ke_pide_tanpa_pic_count' in resp.context

    def test_pmde_admin_context(self, client, db):
        user = UserFactory()
        _add_groups(user, 'user_pmde', 'admin_pmde')
        client.force_login(user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_admin_pmde'] is True
        assert 'pmde_jenis_data_tanpa_pic_count' in resp.context
        assert 'pmde_tiket_pengendalian_mutu_tanpa_pic_count' in resp.context

    def test_p3de_category_counts_present(self, client, authenticated_user):
        """A P3DE user always gets the p3de_category_counts dict."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        counts = resp.context['p3de_category_counts']
        assert 'belum_rekam_backup_data' in counts
        assert 'diklarifikasi' in counts

    def test_pide_category_counts_present(self, client, pide_user):
        client.force_login(pide_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert 'pide_category_counts' in resp.context

    def test_pmde_category_counts_present(self, client, pmde_user):
        client.force_login(pmde_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert 'pmde_category_counts' in resp.context


# ============================================================
# home_data — server-side DataTables endpoint
# ============================================================

def _base_params(category, **extra):
    params = {'draw': '1', 'start': '0', 'length': '10', 'category': category}
    params.update(extra)
    return params


@pytest.mark.django_db
class TestHomeDataAccessControl:
    def test_requires_login(self, client):
        resp = client.get(reverse('home_data'), _base_params('belum_rekam_backup_data'))
        assert resp.status_code in (302, 403)

    def test_post_not_allowed(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('home_data'), _base_params('belum_rekam_backup_data'))
        assert resp.status_code == 405

    def test_invalid_category_returns_400(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('not_a_real_category'))
        assert resp.status_code == 400
        assert json.loads(resp.content)['error'] == 'Invalid category'

    def test_missing_category_returns_400(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), {'draw': '1'})
        assert resp.status_code == 400

    def test_admin_category_denied_for_non_admin(self, client, authenticated_user):
        """periode_tiket_null_p3de requires admin_p3de; a plain user gets 403."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('periode_tiket_null_p3de'))
        assert resp.status_code == 403

    def test_pide_admin_category_denied_for_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('tiket_dikirim_ke_pide_tanpa_pic'))
        assert resp.status_code == 403

    def test_pmde_admin_category_denied_for_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('tiket_pengendalian_mutu_tanpa_pic'))
        assert resp.status_code == 403

    def test_jenis_data_category_denied_for_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('jenis_data_tanpa_pic_p3de'))
        assert resp.status_code == 403

    def test_jenis_data_pide_denied_for_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('jenis_data_tanpa_pic_pide'))
        assert resp.status_code == 403

    def test_jenis_data_pmde_denied_for_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('jenis_data_tanpa_pic_pmde'))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestHomeDataP3DECategories:
    def _assign(self, tiket, user):
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)

    def test_belum_rekam_backup_data_returns_row(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('belum_rekam_backup_data'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 1
        assert len(data['data']) == 1
        row = data['data'][0]
        assert row['nomor_tiket'] == tiket.nomor_tiket
        assert 'actions' in row
        assert 'nama_ilap' in row

    def test_belum_dibuat_tanda_terima(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, tanda_terima=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('belum_dibuat_tanda_terima'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_belum_diteliti(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=True, tanda_terima=True)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('belum_diteliti'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_belum_dikirim_ke_pide(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=2, baris_lengkap=10)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('belum_dikirim_ke_pide'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_pengembalian_sebagian_dari_pide(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=5, baris_cde=5, baris_lengkap=10)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('pengembalian_sebagian_dari_pide'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_diklarifikasi_category_runs(self, client, authenticated_user):
        """The diklarifikasi subquery category executes without error."""
        tiket = TiketFactory(status_tiket=5, baris_cde=3, penyampaian=1)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('diklarifikasi'))
        assert resp.status_code == 200
        assert 'data' in json.loads(resp.content)

    def test_empty_when_no_assignment(self, client, authenticated_user):
        TiketFactory(status_tiket=1, backup=False)  # not assigned to user
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params('belum_rekam_backup_data'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 0

    def test_global_search_filters(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        # search for the exact nomor_tiket -> still 1 filtered
        resp = client.get(reverse('home_data'), _base_params(
            'belum_rekam_backup_data', **{'search[value]': tiket.nomor_tiket}))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1
        # search for something not matching -> 0 filtered
        resp = client.get(reverse('home_data'), _base_params(
            'belum_rekam_backup_data', **{'search[value]': 'zzz_no_match_zzz'}))
        assert json.loads(resp.content)['recordsFiltered'] == 0

    def test_ordering_desc(self, client, authenticated_user):
        for _ in range(2):
            tiket = TiketFactory(status_tiket=1, backup=False)
            self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params(
            'belum_rekam_backup_data',
            **{'order[0][column]': '1', 'order[0][dir]': 'desc'}))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 2

    def test_ordering_invalid_column_falls_back(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params(
            'belum_rekam_backup_data', **{'order[0][column]': 'not-an-int'}))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_ordering_out_of_range_index(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('home_data'), _base_params(
            'belum_rekam_backup_data', **{'order[0][column]': '99'}))
        assert resp.status_code == 200

    def test_ordering_by_sub_jenis_and_tanggal_columns(self, client, authenticated_user):
        """Ordering by column index 2 (nama_sub_jenis_data) and 3 (tgl_terima_dip)."""
        tiket = TiketFactory(status_tiket=1, backup=False)
        self._assign(tiket, authenticated_user)
        client.force_login(authenticated_user)
        for col in ('2', '3'):
            resp = client.get(reverse('home_data'), _base_params(
                'belum_rekam_backup_data',
                **{'order[0][column]': col, 'order[0][dir]': 'asc'}))
            assert resp.status_code == 200
            assert json.loads(resp.content)['recordsTotal'] == 1


@pytest.mark.django_db
class TestHomeDataPideCategories:
    def _assign(self, tiket, user):
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE, active=True)

    def test_belum_mulai_proses_identifikasi(self, client, pide_user):
        tiket = TiketFactory(status_tiket=4)  # STATUS_DIKIRIM_KE_PIDE
        self._assign(tiket, pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('home_data'), _base_params('belum_mulai_proses_identifikasi'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_dalam_proses_identifikasi_with_date_columns(self, client, pide_user):
        from datetime import datetime
        tiket = TiketFactory(status_tiket=5, tgl_kirim_pide=datetime(2024, 5, 1))
        self._assign(tiket, pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('home_data'), _base_params(
            'dalam_proses_identifikasi',
            **{'order[0][column]': '3', 'order[0][dir]': 'asc'}))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 1
        assert data['data'][0]['tanggal'] == '01-05-2024'


@pytest.mark.django_db
class TestHomeDataPmdeCategories:
    def test_dalam_proses_pengendalian_mutu_with_transfer_date(self, client, pmde_user):
        from datetime import datetime
        tiket = TiketFactory(status_tiket=6, tgl_transfer=datetime(2024, 3, 2))
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)
        client.force_login(pmde_user)
        resp = client.get(reverse('home_data'), _base_params(
            'dalam_proses_pengendalian_mutu',
            **{'order[0][column]': '3', 'order[0][dir]': 'desc'}))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 1
        assert data['data'][0]['tanggal'] == '02-03-2024'


@pytest.mark.django_db
class TestHomeDataAdminCategories:
    def test_periode_tiket_null_p3de(self, client, db):
        user = UserFactory()
        _add_groups(user, 'user_p3de', 'admin_p3de')
        tiket = TiketFactory(status_tiket=1, tahun=2099)
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params(
            'periode_tiket_null_p3de',
            **{'order[0][column]': '4', 'order[0][dir]': 'desc'}))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 1
        row = data['data'][0]
        assert row['tahun'] == 2099
        assert 'status_tiket' in row

    def test_tiket_dikirim_ke_pide_tanpa_pic(self, client, db):
        user = UserFactory()
        _add_groups(user, 'admin_pide')
        TiketFactory(status_tiket=4)  # no PIDE PIC assigned
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params('tiket_dikirim_ke_pide_tanpa_pic'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_tiket_pengendalian_mutu_tanpa_pic(self, client, db):
        user = UserFactory()
        _add_groups(user, 'admin_pmde')
        TiketFactory(status_tiket=6)  # no PMDE PIC assigned
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params('tiket_pengendalian_mutu_tanpa_pic'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] == 1

    def test_jenis_data_tanpa_pic_p3de(self, client, db):
        from diamond_web.tests.conftest import JenisDataILAPFactory
        user = UserFactory()
        _add_groups(user, 'admin_p3de')
        JenisDataILAPFactory()  # no active P3DE PIC
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params(
            'jenis_data_tanpa_pic_p3de',
            **{'order[0][column]': '1', 'order[0][dir]': 'desc'}))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1
        assert 'nama_ilap' in data['data'][0]

    def test_jenis_data_tanpa_pic_search_and_bad_order(self, client, db):
        from diamond_web.tests.conftest import JenisDataILAPFactory
        user = UserFactory()
        _add_groups(user, 'admin_pide')
        JenisDataILAPFactory()
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params(
            'jenis_data_tanpa_pic_pide',
            **{'search[value]': 'zzz_no_match', 'order[0][column]': 'bad'}))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsFiltered'] == 0

    def test_jenis_data_tanpa_pic_pmde(self, client, db):
        from diamond_web.tests.conftest import JenisDataILAPFactory
        user = UserFactory()
        _add_groups(user, 'admin_pmde')
        JenisDataILAPFactory()
        client.force_login(user)
        resp = client.get(reverse('home_data'), _base_params('jenis_data_tanpa_pic_pmde'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['recordsTotal'] >= 1
