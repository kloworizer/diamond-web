"""Tests for the kasi (supervisor) roles on the home page and tiket list.

A kasi sees the same view as the corresponding user role of their unit, but is
not limited to the tikets where they are the active PIC.
"""
import json
import pytest
from django.urls import reverse

from diamond_web.constants.tiket_status import (
    STATUS_DIREKAM,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_PENGENDALIAN_MUTU,
)
from diamond_web.models import TiketPIC
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory
from diamond_web.views.task_to_do import (
    get_tiket_summary_for_user_p3de,
    get_tiket_summary_for_user_pide,
    get_tiket_summary_for_user_pmde,
)


# ============================================================
# Home page
# ============================================================

@pytest.mark.django_db
class TestHomeKasiRoles:
    """Home page role flags and category counts for kasi users."""

    def test_kasi_p3de_gets_p3de_home(self, client, kasi_p3de_user):
        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_p3de'] is True
        assert resp.context['is_kasi_p3de'] is True

    def test_kasi_pide_gets_pide_home(self, client, kasi_pide_user):
        client.force_login(kasi_pide_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_pide'] is True
        assert resp.context['is_kasi_pide'] is True

    def test_kasi_pmde_gets_pmde_home(self, client, kasi_pmde_user):
        client.force_login(kasi_pmde_user)
        resp = client.get(reverse('home'))
        assert resp.status_code == 200
        assert resp.context['is_pmde'] is True
        assert resp.context['is_kasi_pmde'] is True

    def test_kasi_p3de_counts_include_other_pic_tikets(self, client, kasi_p3de_user):
        """Kasi P3DE counts cover tikets owned by other PICs."""
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_DIREKAM, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home'))
        assert resp.context['p3de_category_counts']['belum_rekam_backup_data'] >= 1

    def test_p3de_user_counts_exclude_other_pic_tikets(self, client, authenticated_user):
        """A regular user_p3de still only sees their own tikets."""
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_DIREKAM, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        client.force_login(authenticated_user)
        resp = client.get(reverse('home'))
        assert resp.context['p3de_category_counts']['belum_rekam_backup_data'] == 0

    def test_kasi_p3de_is_not_admin(self, client, kasi_p3de_user):
        """Kasi is a supervisor, not an admin — admin-only panels stay hidden."""
        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home'))
        assert resp.context['is_admin_p3de'] is False
        assert 'p3de_jenis_data_tanpa_pic_count' not in resp.context


@pytest.mark.django_db
class TestHomeDataKasi:
    """The home_data DataTables endpoint for kasi users."""

    def test_kasi_p3de_sees_other_pic_tiket(self, client, kasi_p3de_user):
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_DIREKAM, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home_data'), {'category': 'belum_rekam_backup_data'})
        payload = json.loads(resp.content)
        assert any(row['nomor_tiket'] == tiket.nomor_tiket for row in payload['data'])

    def test_kasi_pide_sees_other_pic_tiket(self, client, kasi_pide_user):
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_DIKIRIM_KE_PIDE)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.PIDE, active=True)

        client.force_login(kasi_pide_user)
        resp = client.get(reverse('home_data'),
                          {'category': 'belum_mulai_proses_identifikasi'})
        payload = json.loads(resp.content)
        assert any(row['nomor_tiket'] == tiket.nomor_tiket for row in payload['data'])

    def test_kasi_pmde_sees_other_pic_tiket(self, client, kasi_pmde_user):
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_PENGENDALIAN_MUTU)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.PMDE, active=True)

        client.force_login(kasi_pmde_user)
        resp = client.get(reverse('home_data'),
                          {'category': 'dalam_proses_pengendalian_mutu'})
        payload = json.loads(resp.content)
        assert any(row['nomor_tiket'] == tiket.nomor_tiket for row in payload['data'])

    def test_kasi_p3de_denied_admin_category(self, client, kasi_p3de_user):
        """Admin-only categories remain closed to kasi."""
        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('home_data'), {'category': 'jenis_data_tanpa_pic_p3de'})
        assert resp.status_code == 403


# ============================================================
# Task summaries
# ============================================================

@pytest.mark.django_db
class TestTaskSummaryKasi:
    """Task-to-do summaries cover the whole unit for kasi users."""

    def test_p3de_summary_covers_all_tikets(self, kasi_p3de_user):
        other = UserFactory()
        tiket = TiketFactory(backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        assert get_tiket_summary_for_user_p3de(kasi_p3de_user)['rekam_backup_data'] >= 1

    def test_pide_summary_covers_all_tikets(self, kasi_pide_user):
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_DIKIRIM_KE_PIDE)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.PIDE, active=True)

        assert get_tiket_summary_for_user_pide(kasi_pide_user)['identifikasi_data'] >= 1

    def test_pmde_summary_covers_all_tikets(self, kasi_pmde_user):
        other = UserFactory()
        tiket = TiketFactory(status_tiket=STATUS_PENGENDALIAN_MUTU)
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.PMDE, active=True)

        assert get_tiket_summary_for_user_pmde(kasi_pmde_user)['pengendalian_mutu'] >= 1

    def test_summary_empty_for_unrelated_kasi(self, kasi_pide_user):
        """kasi_pide has no P3DE summary."""
        TiketFactory(backup=False)
        assert get_tiket_summary_for_user_p3de(kasi_pide_user)['rekam_backup_data'] == 0


# ============================================================
# Daftar Tiket
# ============================================================

@pytest.mark.django_db
class TestTiketListKasi:
    """Kasi users see every tiket in the daftar tiket page."""

    @pytest.mark.parametrize('fixture_name', ['kasi_p3de_user', 'kasi_pide_user', 'kasi_pmde_user'])
    def test_kasi_can_open_list(self, client, request, fixture_name):
        client.force_login(request.getfixturevalue(fixture_name))
        assert client.get(reverse('tiket_list')).status_code == 200

    def test_kasi_sees_tiket_without_pic_assignment(self, client, kasi_p3de_user):
        other = UserFactory()
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('tiket_data'), {'draw': 1, 'start': 0, 'length': 10000})
        payload = json.loads(resp.content)
        assert any(row['nomor_tiket'] == tiket.nomor_tiket for row in payload['data'])

    def test_non_kasi_user_does_not_see_other_tiket(self, client, authenticated_user):
        other = UserFactory()
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=other,
                        role=TiketPIC.Role.P3DE, active=True)

        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_data'), {'draw': 1, 'start': 0, 'length': 10})
        payload = json.loads(resp.content)
        assert payload['data'] == []

    def test_kasi_can_open_tiket_detail(self, client, kasi_p3de_user):
        """The list's view button must work, read-only, for a kasi."""
        tiket = TiketFactory()
        client.force_login(kasi_p3de_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert resp.context['user_is_active_pic'] is False
