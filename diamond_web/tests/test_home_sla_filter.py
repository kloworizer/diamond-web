"""
Tests for SLA-based age_group filtering in Tugas Saya (home_data endpoint).

Verifies that:
  - belum_mulai_proses_identifikasi: 30 working days (42 cal) from tgl_kirim_pide
  - dalam_proses_identifikasi: 30 working days (42 cal) from tgl_rekam_pide (fallback tgl_kirim_pide)
  - dalam_proses_pengendalian_mutu: 85 working days (119 cal) from tgl_transfer

Each category is tested:
  - age_group=new    → only tickets WITHIN the SLA window appear
  - age_group=critical → only tickets PAST the SLA window appear
  - age_group=all    → all tickets appear regardless of date
  - summary keys (critical_count, new_count) match correctly
"""
import json
import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.urls import reverse

from diamond_web.models import TiketPIC
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory


def _params(category, **extra):
    params = {'draw': '1', 'start': '0', 'length': '50', 'category': category}
    params.update(extra)
    return params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_dt():
    return timezone.now()


# PIDE SLA threshold = 42 calendar days
PIDE_SLA_DAYS = 42
# PMDE SLA threshold = 119 calendar days
PMDE_SLA_DAYS = 119


# ---------------------------------------------------------------------------
# PIDE — Belum Mulai Proses Identifikasi
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBelumMulaiSLAFilter:
    """Tests SLA filtering on belum_mulai_proses_identifikasi (30 hari kerja = 42 cal days from tgl_kirim_pide)."""

    def _assign_pide(self, tiket, user):
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE, active=True)

    def _make_fresh_tiket(self):
        """Ticket with tgl_kirim_pide = today (well within 42 days)."""
        return TiketFactory(status_tiket=4, tgl_kirim_pide=_now_dt())

    def _make_overdue_tiket(self):
        """Ticket with tgl_kirim_pide = 50 days ago (past 42-day SLA)."""
        return TiketFactory(status_tiket=4, tgl_kirim_pide=_now_dt() - timedelta(days=50))

    def test_age_group_new_shows_only_fresh_tickets(self, client, pide_user):
        fresh = self._make_fresh_tiket()
        overdue = self._make_overdue_tiket()
        self._assign_pide(fresh, pide_user)
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi', age_group='new'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        ticket_ids = {row['nomor_tiket'] for row in data['data']}
        assert fresh.nomor_tiket in ticket_ids
        assert overdue.nomor_tiket not in ticket_ids

    def test_age_group_critical_shows_only_overdue_tickets(self, client, pide_user):
        fresh = self._make_fresh_tiket()
        overdue = self._make_overdue_tiket()
        self._assign_pide(fresh, pide_user)
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi', age_group='critical'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        ticket_ids = {row['nomor_tiket'] for row in data['data']}
        assert overdue.nomor_tiket in ticket_ids
        assert fresh.nomor_tiket not in ticket_ids

    def test_age_group_all_shows_all_tickets(self, client, pide_user):
        fresh = self._make_fresh_tiket()
        overdue = self._make_overdue_tiket()
        self._assign_pide(fresh, pide_user)
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 2

    def test_summary_critical_count_and_new_count_correct(self, client, pide_user):
        fresh = self._make_fresh_tiket()
        overdue = self._make_overdue_tiket()
        self._assign_pide(fresh, pide_user)
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi'))
        data = json.loads(resp.content)
        summary = data.get('summary', {})
        assert summary.get('critical_count') == 1  # 1 overdue
        assert summary.get('new_count') == 1        # 1 fresh

    def test_ticket_on_boundary_day_counts_as_new(self, client, pide_user):
        """Ticket at exactly 41 days ago is still within SLA (new)."""
        boundary = TiketFactory(status_tiket=4, tgl_kirim_pide=_now_dt() - timedelta(days=41))
        self._assign_pide(boundary, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi', age_group='new'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1

    def test_ticket_past_boundary_counts_as_critical(self, client, pide_user):
        """Ticket at exactly 43 days ago is past SLA (critical)."""
        overdue = TiketFactory(status_tiket=4, tgl_kirim_pide=_now_dt() - timedelta(days=43))
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('belum_mulai_proses_identifikasi', age_group='critical'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1


# ---------------------------------------------------------------------------
# PIDE — Dalam Proses Identifikasi
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDalamProsesIdentifikasiSLAFilter:
    """Tests SLA filtering on dalam_proses_identifikasi (30 hari kerja = 42 cal days from tgl_rekam_pide, fallback tgl_kirim_pide)."""

    def _assign_pide(self, tiket, user):
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE, active=True)

    def test_uses_tgl_rekam_pide_when_available(self, client, pide_user):
        """When tgl_rekam_pide is set, SLA is counted from tgl_rekam_pide, not tgl_kirim_pide."""
        # tgl_kirim_pide is old (60 days) but tgl_rekam_pide is recent (today)
        # → ticket should be classified as NEW (within SLA from rekam_pide)
        tiket = TiketFactory(
            status_tiket=5,
            tgl_kirim_pide=_now_dt() - timedelta(days=60),  # would be critical if using kirim date
            tgl_rekam_pide=_now_dt(),                        # but rekam is today → new
        )
        self._assign_pide(tiket, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi', age_group='new'))
        data = json.loads(resp.content)
        ticket_ids = {row['nomor_tiket'] for row in data['data']}
        assert tiket.nomor_tiket in ticket_ids, "Ticket should be NEW since tgl_rekam_pide is today"

    def test_fallback_to_tgl_kirim_pide_when_rekam_pide_null(self, client, pide_user):
        """When tgl_rekam_pide is NULL, fallback to tgl_kirim_pide for SLA check."""
        # No tgl_rekam_pide, tgl_kirim_pide is fresh → new
        tiket = TiketFactory(
            status_tiket=5,
            tgl_kirim_pide=_now_dt(),
            tgl_rekam_pide=None,
        )
        self._assign_pide(tiket, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi', age_group='new'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1

    def test_fallback_overdue_when_rekam_pide_null_and_kirim_old(self, client, pide_user):
        """When tgl_rekam_pide is NULL and tgl_kirim_pide is old → critical."""
        tiket = TiketFactory(
            status_tiket=5,
            tgl_kirim_pide=_now_dt() - timedelta(days=50),
            tgl_rekam_pide=None,
        )
        self._assign_pide(tiket, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi', age_group='critical'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1

    def test_age_group_all_shows_all_tickets(self, client, pide_user):
        t1 = TiketFactory(status_tiket=5, tgl_kirim_pide=_now_dt(), tgl_rekam_pide=_now_dt())
        t2 = TiketFactory(status_tiket=5, tgl_kirim_pide=_now_dt() - timedelta(days=50), tgl_rekam_pide=None)
        self._assign_pide(t1, pide_user)
        self._assign_pide(t2, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi'))
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 2

    def test_summary_counts_correct(self, client, pide_user):
        fresh = TiketFactory(status_tiket=5, tgl_kirim_pide=_now_dt(), tgl_rekam_pide=_now_dt())
        overdue = TiketFactory(status_tiket=5, tgl_kirim_pide=_now_dt() - timedelta(days=50), tgl_rekam_pide=None)
        self._assign_pide(fresh, pide_user)
        self._assign_pide(overdue, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi'))
        data = json.loads(resp.content)
        summary = data.get('summary', {})
        assert summary.get('critical_count') == 1
        assert summary.get('new_count') == 1

    def test_tanggal_column_shows_tgl_rekam_pide_when_set(self, client, pide_user):
        """Tanggal column in datatable rows should show tgl_rekam_pide when present."""
        rekam_date = datetime(2024, 6, 15)
        kirim_date = datetime(2024, 1, 1)
        tiket = TiketFactory(
            status_tiket=5,
            tgl_kirim_pide=kirim_date,
            tgl_rekam_pide=rekam_date,
        )
        self._assign_pide(tiket, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi'))
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 1
        row = data['data'][0]
        # Should show tgl_rekam_pide (15-06-2024), not tgl_kirim_pide (01-01-2024)
        assert row['tanggal'] == '15-06-2024'

    def test_tanggal_column_falls_back_to_tgl_kirim_pide(self, client, pide_user):
        """When tgl_rekam_pide is None, tanggal column falls back to tgl_kirim_pide."""
        kirim_date = datetime(2024, 5, 1)
        tiket = TiketFactory(status_tiket=5, tgl_kirim_pide=kirim_date, tgl_rekam_pide=None)
        self._assign_pide(tiket, pide_user)
        client.force_login(pide_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_identifikasi'))
        data = json.loads(resp.content)
        assert data['data'][0]['tanggal'] == '01-05-2024'


# ---------------------------------------------------------------------------
# PMDE — Dalam Proses Pengendalian Mutu
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDalamProsesPengendalianMutuSLAFilter:
    """Tests SLA filtering on dalam_proses_pengendalian_mutu (85 hari kerja = 119 cal days from tgl_transfer)."""

    def _assign_pmde(self, tiket, user):
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)

    def _fresh_tiket(self):
        """tgl_transfer = today → well within 119 days."""
        return TiketFactory(status_tiket=6, tgl_transfer=_now_dt())

    def _overdue_tiket(self):
        """tgl_transfer = 130 days ago → past 119-day SLA."""
        return TiketFactory(status_tiket=6, tgl_transfer=_now_dt() - timedelta(days=130))

    def test_age_group_new_shows_only_fresh_tickets(self, client, pmde_user):
        fresh = self._fresh_tiket()
        overdue = self._overdue_tiket()
        self._assign_pmde(fresh, pmde_user)
        self._assign_pmde(overdue, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu', age_group='new'))
        data = json.loads(resp.content)
        ticket_ids = {row['nomor_tiket'] for row in data['data']}
        assert fresh.nomor_tiket in ticket_ids
        assert overdue.nomor_tiket not in ticket_ids

    def test_age_group_critical_shows_only_overdue_tickets(self, client, pmde_user):
        fresh = self._fresh_tiket()
        overdue = self._overdue_tiket()
        self._assign_pmde(fresh, pmde_user)
        self._assign_pmde(overdue, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu', age_group='critical'))
        data = json.loads(resp.content)
        ticket_ids = {row['nomor_tiket'] for row in data['data']}
        assert overdue.nomor_tiket in ticket_ids
        assert fresh.nomor_tiket not in ticket_ids

    def test_age_group_all_shows_all_tickets(self, client, pmde_user):
        fresh = self._fresh_tiket()
        overdue = self._overdue_tiket()
        self._assign_pmde(fresh, pmde_user)
        self._assign_pmde(overdue, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu'))
        data = json.loads(resp.content)
        assert data['recordsTotal'] == 2

    def test_summary_critical_and_new_count_correct(self, client, pmde_user):
        fresh = self._fresh_tiket()
        overdue = self._overdue_tiket()
        self._assign_pmde(fresh, pmde_user)
        self._assign_pmde(overdue, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu'))
        data = json.loads(resp.content)
        summary = data.get('summary', {})
        assert summary.get('critical_count') == 1
        assert summary.get('new_count') == 1

    def test_ticket_at_118_days_is_new(self, client, pmde_user):
        """Ticket 118 days old is still within 119-day SLA → new."""
        t = TiketFactory(status_tiket=6, tgl_transfer=_now_dt() - timedelta(days=118))
        self._assign_pmde(t, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu', age_group='new'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1

    def test_ticket_at_120_days_is_critical(self, client, pmde_user):
        """Ticket 120 days old is past 119-day SLA → critical."""
        t = TiketFactory(status_tiket=6, tgl_transfer=_now_dt() - timedelta(days=120))
        self._assign_pmde(t, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu', age_group='critical'))
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 1

    def test_tanggal_column_shows_tgl_transfer(self, client, pmde_user):
        transfer_date = datetime(2024, 3, 2)
        tiket = TiketFactory(status_tiket=6, tgl_transfer=transfer_date)
        self._assign_pmde(tiket, pmde_user)
        client.force_login(pmde_user)

        resp = client.get(reverse('home_data'), _params('dalam_proses_pengendalian_mutu'))
        data = json.loads(resp.content)
        assert data['data'][0]['tanggal'] == '02-03-2024'
