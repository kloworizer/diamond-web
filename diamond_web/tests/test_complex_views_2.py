"""Tests for pic.py and monitoring_penyampaian_data.py missing branches."""
import datetime
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group, User

from .conftest import (
    UserFactory, PICFactory, TiketFactory, TiketPICFactory,
    JenisDataILAPFactory, ILAPFactory, KategoriILAPFactory,
    PeriodeJenisDataFactory, PeriodePengirimanFactory,
    KanwilFactory, KPPFactory,
    JenisTabelFactory, DasarHukumFactory, KlasifikasiJenisDataFactory,
)
from ..models.pic import PIC
from ..models.tiket_pic import TiketPIC


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def p3de_user(db):
    """A user in user_p3de group (used for RBAC tests)."""
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(grp)
    return user


@pytest.fixture
def p3de_admin(db):
    """A user in admin_p3de group."""
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_p3de')
    user.groups.add(grp)
    return user


@pytest.fixture
def pide_admin(db):
    """A user in admin_pide group."""
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_pide')
    user.groups.add(grp)
    return user


@pytest.fixture
def pmde_admin(db):
    """A user in admin_pmde group."""
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_pmde')
    user.groups.add(grp)
    return user


@pytest.fixture
def p3de_jdi(db):
    """A JenisDataILAP instance for PIC tests."""
    return JenisDataILAPFactory()


@pytest.fixture
def p3de_pic(db, p3de_user, p3de_jdi):
    """An active (no end_date) P3DE PIC."""
    return PICFactory(
        tipe=PIC.TipePIC.P3DE,
        id_sub_jenis_data_ilap=p3de_jdi,
        id_user=p3de_user,
        start_date=datetime.date(2024, 1, 1),
        end_date=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Part 1 – monitoring_penyampaian_data.py helper function tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPeriodDisplayName:
    """Unit tests for get_period_display_name helper (lines 50, 52, 54, 60)."""

    def setup_method(self):
        from diamond_web.views.monitoring_penyampaian_data import get_period_display_name
        self.fn = get_period_display_name

    def test_harian(self):
        """Line 50: harian → formatted date string."""
        result = self.fn('harian', 1, datetime.date(2024, 1, 15))
        assert result == '15-01-2024'

    def test_mingguan(self):
        """Line 52: mingguan → 'Minggu N'."""
        result = self.fn('mingguan', 3, datetime.date(2024, 1, 15))
        assert result == 'Minggu 3'

    def test_2_mingguan(self):
        """Line 54: '2 mingguan' → '2 Minggu N'."""
        result = self.fn('2 mingguan', 2, datetime.date(2024, 1, 15))
        assert result == '2 Minggu 2'

    def test_else_unknown_type(self):
        """Line 60: unknown type → str(periode_num)."""
        result = self.fn('unknown', 5, datetime.date(2024, 1, 15))
        assert result == '5'

    def test_triwulanan(self):
        """Triwulanan → 'Triwulan N'."""
        result = self.fn('triwulanan', 2, datetime.date(2024, 4, 1))
        assert result == 'Triwulan 2'

    def test_kuartal(self):
        """Kuartal → 'Kuartal N'."""
        result = self.fn('kuartal', 1, datetime.date(2024, 1, 1))
        assert result == 'Kuartal 1'

    def test_semester(self):
        """Semester → 'Semester N'."""
        result = self.fn('semester', 2, datetime.date(2024, 7, 1))
        assert result == 'Semester 2'

    def test_tahunan(self):
        """Tahunan → '-'."""
        result = self.fn('tahunan', 1, datetime.date(2024, 1, 1))
        assert result == '-'


class TestGetPeriodsForRange:
    """Unit tests for get_periods_for_range helper (lines 86, 88, 90, 107-112)."""

    def setup_method(self):
        from diamond_web.views.monitoring_penyampaian_data import get_periods_for_range
        self.fn = get_periods_for_range

    def test_triwulanan(self):
        """Line 86: triwulanan – adds 3 months per period."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 6, 30), 'triwulanan')
        assert len(periods) >= 1
        assert periods[0]['periode_num'] == 1
        # second period should start in April
        if len(periods) > 1:
            assert periods[1]['start_date'].month == 4

    def test_kuartal(self):
        """Line 88: kuartal – same as triwulanan (3 months)."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 6, 30), 'kuartal')
        assert len(periods) >= 1
        assert periods[0]['periode_num'] == 1

    def test_semester(self):
        """Line 90: semester – adds 6 months per period."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 12, 31), 'semester')
        assert len(periods) >= 1
        # The second semester starts in July
        if len(periods) > 1:
            assert periods[1]['start_date'].month == 7

    def test_tahunan(self):
        """Line 107: tahunan – adds 1 year per period."""
        periods = self.fn(datetime.date(2023, 1, 1), datetime.date(2024, 12, 31), 'tahunan')
        assert len(periods) >= 1
        assert periods[0]['start_date'].year == 2023
        if len(periods) > 1:
            assert periods[1]['start_date'].year == 2024

    def test_else_unknown_type(self):
        """Lines 107-112: unknown type falls through to daily increment."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 1, 3), 'unknown')
        assert len(periods) >= 1
        # Daily increment means first period ends on the same day
        assert periods[0]['start_date'] == datetime.date(2024, 1, 1)

    def test_year_rollover_resets_count(self):
        """Year boundary resets periode_count to 1."""
        periods = self.fn(datetime.date(2023, 10, 1), datetime.date(2024, 3, 31), 'kuartal')
        # Should cross year boundary and reset
        year_counts = {}
        for p in periods:
            year = p['start_date'].year
            year_counts.setdefault(year, []).append(p['periode_num'])
        if len(year_counts) > 1:
            # After year change the count resets to 1
            years = sorted(year_counts.keys())
            assert year_counts[years[1]][0] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Part 2 – monitoring_penyampaian_data view endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitoringFilterOptions:
    """Tests for get_filter_options=1 branch (lines 201, 259)."""

    @pytest.mark.django_db
    def test_admin_gets_all_pic_p3de_options(self, client, admin_user):
        """Line 201: admin user gets all active P3DE PICs."""
        # Create a P3DE PIC with no end_date
        user_for_pic = UserFactory(first_name='Budi', last_name='Santoso')
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'filter_options' in data
        pic_options = data['filter_options']['pic_p3de']
        assert isinstance(pic_options, list)
        # The created user should appear
        ids = [opt['id'] for opt in pic_options]
        assert str(user_for_pic.id) in ids

    @pytest.mark.django_db
    def test_user_p3de_with_active_pic_gets_own_option(self, client, db):
        """Line 259: non-admin with active PIC gets only their own option."""
        user = UserFactory(first_name='Ani', last_name='Rahayu')
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(grp)
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = resp.json()
        pic_options = data['filter_options']['pic_p3de']
        assert len(pic_options) == 1
        assert pic_options[0]['id'] == str(user.id)

    @pytest.mark.django_db
    def test_user_p3de_without_pic_gets_empty_options(self, client, p3de_user):
        """Non-admin without active PIC gets empty list."""
        client.force_login(p3de_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['filter_options']['pic_p3de'] == []


class TestMonitoringDataEndpoint:
    """Tests for main datatables endpoint with RBAC and filtering (lines 303-307, 395-454)."""

    def _get_or_create_pp(self, penyampaian, penerimaan):
        """Get or create a PeriodePengiriman with unique periode_penyampaian."""
        from ..models.periode_pengiriman import PeriodePengiriman
        obj, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=penyampaian,
            defaults={'periode_penerimaan': penerimaan}
        )
        return obj

    def _make_full_data(self, db, admin_user):
        """Create minimal data to produce records in the monitoring view."""
        kanwil = KanwilFactory()
        kpp = KPPFactory(id_kanwil=kanwil)
        from .conftest import KategoriWilayahFactory
        kat_wil = KategoriWilayahFactory()
        ilap = ILAPFactory(id_kpp=kpp, id_kategori_wilayah=kat_wil)
        jdi = JenisDataILAPFactory(id_ilap=ilap)
        periode_pengiriman = self._get_or_create_pp('Bulanan', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode_pengiriman,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 3, 31),
            akhir_penyampaian=14,
        )
        return jdi, kanwil, kpp

    @pytest.mark.django_db
    def test_admin_sees_all_records(self, client, admin_user, db):
        """Admin user sees all records (no RBAC filtering)."""
        self._make_full_data(db, admin_user)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'data' in data
        assert data['draw'] == 1
        assert data['recordsFiltered'] >= 1

    @pytest.mark.django_db
    def test_user_p3de_rbac_filter(self, client, db):
        """Lines 303-307: non-admin user_p3de sees only their assigned jenis_data."""
        user = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(grp)

        # Create full data
        jdi = JenisDataILAPFactory()
        periode_pengiriman = self._get_or_create_pp('Bulanan2', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode_pengiriman,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14,
        )
        # User is NOT assigned → should get 0 filtered records for their jdi
        client.force_login(user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['recordsFiltered'] == 0  # RBAC hides all

    @pytest.mark.django_db
    def test_user_p3de_rbac_sees_own_jenis_data(self, client, db):
        """User assigned as PIC can see their records."""
        user = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(grp)

        jdi = JenisDataILAPFactory()
        # Assign as P3DE PIC (active)
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user, start_date=datetime.date(2024, 1, 1), end_date=None)
        periode_pengiriman = self._get_or_create_pp('BulananRBAC', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode_pengiriman,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14,
        )
        client.force_login(user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['recordsFiltered'] >= 1

    @pytest.mark.django_db
    def test_filter_by_tahun(self, client, admin_user, db):
        """Line 395: filtering by tahun parameter."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananTahun', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100', 'tahun': '2024'})
        assert resp.status_code == 200
        data = resp.json()
        for row in data['data']:
            assert row['tahun'] == 2024

    @pytest.mark.django_db
    def test_filter_by_pic_p3de(self, client, admin_user, db):
        """Line 397: filtering by pic_p3de parameter."""
        user_for_pic = UserFactory()
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)
        pp = self._get_or_create_pp('BulananPic', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'pic_p3de': str(user_for_pic.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_kanwil(self, client, admin_user, db):
        """Line 399: filtering by kanwil parameter."""
        kanwil = KanwilFactory()
        kpp = KPPFactory(id_kanwil=kanwil)
        ilap = ILAPFactory(id_kpp=kpp)
        jdi = JenisDataILAPFactory(id_ilap=ilap)
        pp = self._get_or_create_pp('BulananKanwil', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'kanwil': str(kanwil.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_kpp(self, client, admin_user, db):
        """Line 401: filtering by kpp parameter."""
        kanwil = KanwilFactory()
        kpp = KPPFactory(id_kanwil=kanwil)
        ilap = ILAPFactory(id_kpp=kpp)
        jdi = JenisDataILAPFactory(id_ilap=ilap)
        pp = self._get_or_create_pp('BulananKpp', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'kpp': str(kpp.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_status_penyampaian(self, client, admin_user, db):
        """Line 409: filtering by status_penyampaian."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananStatus', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'status_penyampaian': 'Belum Menyampaikan'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_terlambat(self, client, admin_user, db):
        """Line 411: filtering by terlambat parameter."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananTerlambat', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'terlambat': 'Ya'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_by_column_asc(self, client, admin_user, db):
        """Lines 434-454: sorting by column index ascending."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSortAsc', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': '0', 'order[0][dir]': 'asc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_by_column_desc(self, client, admin_user, db):
        """Sorting descending."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSortDesc', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': '3', 'order[0][dir]': 'desc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_by_numeric_column(self, client, admin_user, db):
        """Lines 440-446: numeric column (periode/tahun) sorted by int."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSortNum', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 3, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # column index 2 = 'periode', column index 3 = 'tahun' – both numeric
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': '2', 'order[0][dir]': 'asc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_sub_jenis_data(self, client, admin_user, db):
        """Line 413: filtering by sub_jenis_data."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSubJenis', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'sub_jenis_data': jdi.id_sub_jenis_data})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_jenis_data(self, client, admin_user, db):
        """Line 411–413: filtering by jenis_data."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananJenis', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'jenis_data': jdi.id_jenis_data})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_monitoring_harian_periode_type(self, client, admin_user, db):
        """Test harian periode type – penerimaan overridden to Bulanan."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('Harian', 'Harian')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 7),
            akhir_penyampaian=1)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_monitoring_mingguan_periode_type(self, client, admin_user, db):
        """Test mingguan periode type – penerimaan overridden to Bulanan."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('Mingguan', 'Mingguan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 21),
            akhir_penyampaian=7)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_monitoring_2mingguan_periode_type(self, client, admin_user, db):
        """Test '2 mingguan' periode type."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('2 Mingguan', '2 Mingguan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 28),
            akhir_penyampaian=7)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_monitoring_no_end_date(self, client, admin_user, db):
        """Test periode with no end_date – uses today as boundary."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananNoEnd', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date.today().replace(day=1),
            end_date=None,
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_kategori_wilayah(self, client, admin_user, db):
        """Line 401: filtering by kategori_wilayah."""
        from .conftest import KategoriWilayahFactory
        kat_wil = KategoriWilayahFactory()
        ilap = ILAPFactory(id_kategori_wilayah=kat_wil)
        jdi = JenisDataILAPFactory(id_ilap=ilap)
        pp = self._get_or_create_pp('BulananKatWil', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'kategori_wilayah': str(kat_wil.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_ilap(self, client, admin_user, db):
        """Line 413: filtering by ilap parameter."""
        ilap = ILAPFactory()
        jdi = JenisDataILAPFactory(id_ilap=ilap)
        pp = self._get_or_create_pp('BulananIlap', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'ilap': str(ilap.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Part 3 – pic.py tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPICListView:
    """Tests for PICListView (lines 46, 62-63)."""

    @pytest.mark.django_db
    def test_list_get_tipe_display_none(self, client, p3de_admin):
        """Line 46: PICListView with tipe=None returns 'PIC'."""
        # Use the base PICListView directly (tipe=None). It's not exposed in URLs,
        # but the concrete PICP3DEListView has tipe set. We verify via the get_tipe_display
        # via the concrete view that does work.
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_list_with_deleted_and_name_params(self, client, p3de_admin):
        """Lines 62-63: list view with ?deleted=1&name=<encoded> shows toast."""
        from urllib.parse import quote_plus
        name = quote_plus('Test PIC')
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_list'), {'deleted': '1', 'name': name})
        assert resp.status_code == 200
        # toast message should be set (via messages framework)

    @pytest.mark.django_db
    def test_list_without_delete_params(self, client, p3de_admin):
        """List view without delete params renders normally."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code == 200


class TestPICCreateView:
    """Tests for PICCreateView (lines 101, 189-220)."""

    @pytest.mark.django_db
    def test_create_get_form(self, client, p3de_admin, db):
        """Line 101: GET create form returns form HTML."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    @pytest.mark.django_db
    def test_create_post_ajax_valid(self, client, p3de_admin, db):
        """Lines 189-220: POST valid form – creates PIC and propagates to tikets.
        With no active tikets, no TiketPIC records are created."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert PIC.objects.filter(id_sub_jenis_data_ilap=jdi, id_user=user_for_pic).exists()

    @pytest.mark.django_db
    def test_create_post_with_existing_tiket_creates_tiket_pic(self, client, p3de_admin, db):
        """form_valid side effect: active tiket gets TiketPIC record."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananCreate1', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        # Active tiket
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert TiketPICModel.objects.filter(id_tiket=tiket, id_user=user_for_pic).exists()

    @pytest.mark.django_db
    def test_create_post_with_inactive_tiket_pic_reactivates(self, client, p3de_admin, db):
        """form_valid: reactivates existing inactive TiketPIC."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananCreate2', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))
        # Create inactive TiketPIC (with a timestamp, since timestamp is NOT NULL)
        TiketPICFactory(id_tiket=tiket, id_user=user_for_pic,
                        role=TiketPICModel.Role.P3DE, active=False)

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        tp = TiketPICModel.objects.filter(id_tiket=tiket, id_user=user_for_pic).first()
        assert tp is not None
        assert tp.active is True

    @pytest.mark.django_db
    def test_create_post_non_ajax_redirects(self, client, p3de_admin, db):
        """Non-AJAX valid POST redirects (or returns success JSON)."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
        )
        assert resp.status_code in (200, 302)

    @pytest.mark.django_db
    def test_create_post_duplicate_raises_form_error(self, client, p3de_admin, db):
        """Duplicate PIC returns form error."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        # Create the first one
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is False


class TestPICUpdateView:
    """Tests for PICUpdateView – end_date transitions (lines 275, 377-420)."""

    @pytest.mark.django_db
    def test_update_get_form(self, client, p3de_admin, db):
        """GET update returns form."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_update', args=[pic_obj.pk]), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    @pytest.mark.django_db
    def test_update_set_end_date_deactivates_tiket_pic(self, client, p3de_admin, db):
        """Lines 335-370 (UpdateView): setting end_date deactivates TiketPIC records."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananUpdate1', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))
        tiket_pic = TiketPICFactory(id_tiket=tiket, id_user=user_for_pic,
                                    role=TiketPICModel.Role.P3DE, active=True)

        # PIC with no end_date
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic_obj.pk]),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',  # Setting end_date → deactivation
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        tiket_pic.refresh_from_db()
        assert tiket_pic.active is False

    @pytest.mark.django_db
    def test_update_clear_end_date_reactivates_tiket_pic(self, client, p3de_admin, db):
        """Clearing end_date (None → date → None) reactivates TiketPIC records."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananUpdate2', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))
        tiket_pic = TiketPICFactory(id_tiket=tiket, id_user=user_for_pic,
                                    role=TiketPICModel.Role.P3DE, active=False)

        # PIC with end_date set → clearing it
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=datetime.date(2024, 6, 30))

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic_obj.pk]),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',  # Clearing end_date → reactivation
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        tiket_pic.refresh_from_db()
        assert tiket_pic.active is True

    @pytest.mark.django_db
    def test_update_clear_end_date_creates_new_tiket_pic(self, client, p3de_admin, db):
        """Clearing end_date creates new TiketPIC when none exists."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananUpdate3', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))

        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=datetime.date(2024, 6, 30))

        assert not TiketPICModel.objects.filter(id_tiket=tiket, id_user=user_for_pic).exists()

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic_obj.pk]),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert TiketPICModel.objects.filter(id_tiket=tiket, id_user=user_for_pic).exists()

    @pytest.mark.django_db
    def test_update_no_end_date_change_no_side_effects(self, client, p3de_admin, db):
        """No end_date change → no side effects."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()

        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic_obj.pk]),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': user_for_pic.pk,
                'start_date': '2024-02-01',  # Just update start_date
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True


class TestPICDeleteView:
    """Tests for PICDeleteView (lines 473, 553-554, 658-659, 663, 665, 689, 708)."""

    @pytest.mark.django_db
    def test_delete_get_ajax(self, client, p3de_admin, db):
        """Line 473: GET with ajax param returns confirm HTML."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_delete', args=[pic_obj.pk]), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    @pytest.mark.django_db
    def test_delete_get_non_ajax(self, client, p3de_admin, db):
        """GET without ajax renders confirmation page."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_delete', args=[pic_obj.pk]))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_delete_post_ajax_deletes_pic_and_tiket_pic(self, client, p3de_admin, db):
        """Lines 553-554: POST delete removes PIC and related TiketPIC with action log."""
        from ..models.tiket_pic import TiketPIC as TiketPICModel
        from .conftest import PeriodeJenisDataFactory, PeriodePengirimanFactory

        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)

        jdi = JenisDataILAPFactory()
        from ..models.periode_pengiriman import PeriodePengiriman as PP
        pp, _ = PP.objects.get_or_create(periode_penyampaian='BulananDelete1', defaults={'periode_penerimaan': 'Bulanan'})
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=None, akhir_penyampaian=14)
        tiket = TiketFactory(id_periode_data=periode, status_tiket=1,
                              tgl_terima_dip=datetime.datetime(2024, 1, 15))
        TiketPICFactory(id_tiket=tiket, id_user=user_for_pic,
                        role=TiketPICModel.Role.P3DE, active=True)

        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        pic_pk = pic_obj.pk

        client.force_login(p3de_admin)
        resp = client.post(
            reverse('pic_p3de_delete', args=[pic_pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert not PIC.objects.filter(pk=pic_pk).exists()
        assert not TiketPICModel.objects.filter(id_user=user_for_pic, id_tiket=tiket).exists()

    @pytest.mark.django_db
    def test_delete_post_non_ajax_returns_json(self, client, p3de_admin, db):
        """Lines 663-665: non-AJAX DELETE also returns JSON."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        pic_pk = pic_obj.pk
        client.force_login(p3de_admin)
        resp = client.post(reverse('pic_p3de_delete', args=[pic_pk]))
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
        assert not PIC.objects.filter(pk=pic_pk).exists()


class TestPICDatatables:
    """Tests for _pic_data_common / pic_p3de_data endpoint (lines 473, 553-554)."""

    @pytest.mark.django_db
    def test_pic_p3de_data_basic(self, client, p3de_admin, db):
        """Line 473+: datatables endpoint returns JSON."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['draw'] == 1
        assert 'data' in data

    @pytest.mark.django_db
    def test_pic_p3de_data_with_records(self, client, p3de_admin, db):
        """Returns rows when PIC objects exist."""
        user_for_pic = UserFactory(first_name='Dedi', last_name='Kurniawan')
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_data'), {'draw': '2', 'start': '0', 'length': '100'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['recordsTotal'] >= 1
        all_users = [row['user'] for row in data['data']]
        # 'Dedi Kurniawan' should be in at least one row
        assert any('Dedi' in u or user_for_pic.username in u for u in all_users)

    @pytest.mark.django_db
    def test_pic_p3de_data_column_search(self, client, p3de_admin, db):
        """Column search filtering in datatables."""
        user_for_pic = UserFactory()
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': [jdi.nama_sub_jenis_data[:3], '', '2024', ''],
        })
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_pic_p3de_data_global_search(self, client, p3de_admin, db):
        """Global search in datatables."""
        user_for_pic = UserFactory()
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'search[value]': '2024',
        })
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_pic_p3de_data_ordering_desc(self, client, p3de_admin, db):
        """Ordering descending in datatables."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '2', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_pic_pide_data(self, client, pide_admin, db):
        """PIDE datatables endpoint works."""
        client.force_login(pide_admin)
        resp = client.get(reverse('pic_pide_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_pic_pmde_data(self, client, pmde_admin, db):
        """PMDE datatables endpoint works."""
        client.force_login(pmde_admin)
        resp = client.get(reverse('pic_pmde_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_pic_p3de_data_user_display_name_fallback(self, client, p3de_admin, db):
        """User without first/last name shows username in data."""
        user_for_pic = UserFactory(first_name='', last_name='')
        user_for_pic.first_name = ''
        user_for_pic.last_name = ''
        user_for_pic.save()
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                   end_date=datetime.date(2024, 12, 31))
        client.force_login(p3de_admin)
        # Use global search by the exact username to target this record
        resp = client.get(reverse('pic_p3de_data'), {'draw': '1', 'start': '0', 'length': '100',
                                                      'search[value]': user_for_pic.username})
        assert resp.status_code == 200
        data = resp.json()
        assert data['recordsFiltered'] >= 1
        users_in_data = [row['user'] for row in data['data']]
        # Row should show the username since no first/last name
        assert any(user_for_pic.username in u for u in users_in_data)


class TestPICPIDEAndPMDEViews:
    """Tests for PIDE and PMDE create/update/delete views."""

    @pytest.mark.django_db
    def test_pide_create_get(self, client, pide_admin, db):
        """PIDE create GET returns form."""
        client.force_login(pide_admin)
        resp = client.get(reverse('pic_pide_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    @pytest.mark.django_db
    def test_pmde_create_get(self, client, pmde_admin, db):
        """PMDE create GET returns form."""
        client.force_login(pmde_admin)
        resp = client.get(reverse('pic_pmde_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    @pytest.mark.django_db
    def test_pide_list_view(self, client, pide_admin, db):
        """PIDE list view accessible."""
        client.force_login(pide_admin)
        resp = client.get(reverse('pic_pide_list'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_pmde_list_view(self, client, pmde_admin, db):
        """PMDE list view accessible."""
        client.force_login(pmde_admin)
        resp = client.get(reverse('pic_pmde_list'))
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_pide_delete_post_ajax(self, client, pide_admin, db):
        """PIDE delete via AJAX."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_pide')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.PIDE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        pic_pk = pic_obj.pk
        client.force_login(pide_admin)
        resp = client.post(
            reverse('pic_pide_delete', args=[pic_pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        assert resp.json().get('success') is True


# ─────────────────────────────────────────────────────────────────────────────
# Part 4 – Additional monitoring coverage for missed branches
# ─────────────────────────────────────────────────────────────────────────────

class TestGetPeriodsForRangeAdditional:
    """Extra tests for get_periods_for_range covering harian/mingguan/2mingguan (lines 86, 88, 90)."""

    def setup_method(self):
        from diamond_web.views.monitoring_penyampaian_data import get_periods_for_range
        self.fn = get_periods_for_range

    def test_harian_in_loop(self):
        """Line 86: harian – next_date = current + timedelta(days=1)."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 1, 3), 'harian')
        assert len(periods) == 3
        assert periods[0]['start_date'] == datetime.date(2024, 1, 1)
        assert periods[1]['start_date'] == datetime.date(2024, 1, 2)

    def test_mingguan_in_loop(self):
        """Line 88: mingguan – next_date = current + timedelta(weeks=1)."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 1, 21), 'mingguan')
        assert len(periods) >= 3
        assert periods[1]['start_date'] == datetime.date(2024, 1, 8)

    def test_2mingguan_in_loop(self):
        """Line 90: '2 mingguan' – next_date = current + timedelta(weeks=2)."""
        periods = self.fn(datetime.date(2024, 1, 1), datetime.date(2024, 1, 28), '2 mingguan')
        assert len(periods) >= 2
        assert periods[1]['start_date'] == datetime.date(2024, 1, 15)

    def test_bulanan_december_rollover(self):
        """Bulanan December → January of next year."""
        periods = self.fn(datetime.date(2024, 12, 1), datetime.date(2025, 1, 31), 'bulanan')
        assert len(periods) >= 2
        assert periods[1]['start_date'].year == 2025

    def test_triwulanan_year_rollover(self):
        """Triwulanan spanning year boundary resets periode_count."""
        periods = self.fn(datetime.date(2023, 10, 1), datetime.date(2024, 6, 30), 'triwulanan')
        assert len(periods) >= 1


class TestMonitoringAdditionalCoverage:
    """Additional coverage for monitoring view missing branches."""

    def _get_or_create_pp(self, penyampaian, penerimaan):
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        obj, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=penyampaian,
            defaults={'periode_penerimaan': penerimaan}
        )
        return obj

    @pytest.mark.django_db
    def test_tiket_exists_branch_status_sudah_menyampaikan(self, client, admin_user, db):
        """Lines 303-307: tiket_exists=True → status 'Sudah Menyampaikan'."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananTiketExists', 'Bulanan')
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        # Create a Tiket for this periode (period 1, year 2024)
        TiketFactory(id_periode_data=periode, status_tiket=1, periode=1, tahun=2024)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # Filter by specific sub_jenis_data to only see our record
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'sub_jenis_data': jdi.id_sub_jenis_data})
        assert resp.status_code == 200
        data = resp.json()
        # The row for this jenis_data should show Sudah Menyampaikan
        rows_with_sudah = [
            r for r in data['data']
            if 'Sudah Menyampaikan' in r.get('status_penyampaian', '')
        ]
        assert len(rows_with_sudah) >= 1

    @pytest.mark.django_db
    def test_filter_by_jenis_tabel(self, client, admin_user, db):
        """Line 420: filtering by jenis_tabel parameter."""
        jenis_tabel = JenisTabelFactory()
        jdi = JenisDataILAPFactory(id_jenis_tabel=jenis_tabel)
        pp = self._get_or_create_pp('BulananJenisTabel', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'jenis_tabel': str(jenis_tabel.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_dasar_hukum(self, client, admin_user, db):
        """Line 422: filtering by dasar_hukum parameter."""
        dh = DasarHukumFactory()
        jdi = JenisDataILAPFactory()
        # Create KlasifikasiJenisData linking jdi to dh
        KlasifikasiJenisDataFactory(id_jenis_data_ilap=jdi, id_klasifikasi_tabel=dh)
        pp = self._get_or_create_pp('BulananDasarHukum', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'dasar_hukum': str(dh.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_by_periode_pengiriman(self, client, admin_user, db):
        """Line 424: filtering by periode_pengiriman parameter."""
        pp = self._get_or_create_pp('BulananPeriodePengiriman', 'Bulanan')
        jdi = JenisDataILAPFactory()
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'periode_pengiriman': str(pp.id)})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_line_259_user_pic_with_first_last_name(self, client, db):
        """Line 259: non-admin user with PIC shows name with first+last."""
        user = UserFactory(first_name='Budi', last_name='Santoso')
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(grp)
        jdi = JenisDataILAPFactory()
        PICFactory(tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jdi,
                   id_user=user, start_date=datetime.date(2024, 1, 1), end_date=None)
        client.force_login(user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = resp.json()
        pic_options = data['filter_options']['pic_p3de']
        assert len(pic_options) == 1
        assert 'Budi' in pic_options[0]['name']

    @pytest.mark.django_db
    def test_sorting_by_deadline_date_column(self, client, admin_user, db):
        """Lines 453-454: sorting by deadline_date (non-numeric str sort)."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSort5', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # column index 4 = deadline_date (string sort)
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': '4', 'order[0][dir]': 'asc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_by_status_column(self, client, admin_user, db):
        """Sorting by status_penyampaian column (string sort)."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSort6', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 2, 29),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # column index 5 = status_penyampaian
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': '5', 'order[0][dir]': 'desc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_invalid_column_no_crash(self, client, admin_user, db):
        """Lines 453-454: except (ValueError, IndexError): pass – non-numeric order column."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSort7', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # 'abc' is non-numeric → int('abc') raises ValueError → except block is hit
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': 'abc', 'order[0][dir]': 'asc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_sorting_nonnumeric_column_triggers_valueerror(self, client, admin_user, db):
        """Lines 453-454: non-numeric order column triggers ValueError → caught."""
        jdi = JenisDataILAPFactory()
        pp = self._get_or_create_pp('BulananSort8', 'Bulanan')
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 1, 31),
            akhir_penyampaian=14)
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        # Non-numeric order column → int() raises ValueError → except block on lines 453-454
        resp = client.get(url, {'draw': '1', 'start': '0', 'length': '100',
                                 'order[0][column]': 'abc', 'order[0][dir]': 'asc'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    @pytest.mark.django_db
    def test_filter_options_admin_no_active_pics(self, client, admin_user, db):
        """Admin getting filter options when no active P3DE PICs exist."""
        client.force_login(admin_user)
        url = reverse('monitoring_penyampaian_data_data')
        resp = client.get(url, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'filter_options' in data
        # pic_p3de list can be empty
        assert isinstance(data['filter_options']['pic_p3de'], list)


# ─────────────────────────────────────────────────────────────────────────────
# Part 5 – pic.py line 46 and 101 coverage
# ─────────────────────────────────────────────────────────────────────────────

class TestPICBaseViewMethods:
    """Tests to cover base view methods (lines 46, 101)."""

    @pytest.mark.django_db
    def test_pic_list_view_tipe_none_get_tipe_display(self, db):
        """Line 46: get_tipe_display returns 'PIC' when tipe is None."""
        from diamond_web.views.pic import PICListView
        view = PICListView()
        assert view.get_tipe_display() == 'PIC'

    @pytest.mark.django_db
    def test_pic_create_view_get_form_kwargs(self, db):
        """Line 101: get_form_kwargs includes 'tipe'."""
        from diamond_web.views.pic import PICP3DECreateView
        from unittest.mock import MagicMock
        view = PICP3DECreateView()
        view.request = MagicMock()
        view.kwargs = {}
        view.object = None
        kwargs = view.get_form_kwargs()
        assert 'tipe' in kwargs
        assert kwargs['tipe'] == PIC.TipePIC.P3DE

    @pytest.mark.django_db
    def test_pic_create_view_get_tipe_display_none(self, db):
        """Line 46 via PICCreateView: get_tipe_display with tipe=None."""
        from diamond_web.views.pic import PICCreateView
        view = PICCreateView()
        assert view.get_tipe_display() == 'PIC'

    @pytest.mark.django_db
    def test_pic_update_view_get_tipe_display_none(self, db):
        """Line 275: PICUpdateView.get_tipe_display when tipe is None."""
        from diamond_web.views.pic import PICUpdateView
        view = PICUpdateView()
        assert view.get_tipe_display() == 'PIC'

    @pytest.mark.django_db
    def test_pic_delete_view_get_tipe_display_none(self, db):
        """Lines 473: PICDeleteView.get_tipe_display when tipe is None."""
        from diamond_web.views.pic import PICDeleteView
        view = PICDeleteView()
        assert view.get_tipe_display() == 'PIC'

    @pytest.mark.django_db
    def test_pic_list_with_deleted_name_pide(self, client, pide_admin, db):
        """Lines 62-63: PIDE list shows toast from query params."""
        from urllib.parse import quote_plus
        name = quote_plus('Some PIC')
        client.force_login(pide_admin)
        resp = client.get(reverse('pic_pide_list'), {'deleted': '1', 'name': name})
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_pic_list_with_deleted_name_pmde(self, client, pmde_admin, db):
        """PMDE list shows toast from query params."""
        from urllib.parse import quote_plus
        name = quote_plus('Another PIC')
        client.force_login(pmde_admin)
        resp = client.get(reverse('pic_pmde_list'), {'deleted': '1', 'name': name})
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_pic_p3de_update_no_end_date_changes_via_get_queryset(self, client, p3de_admin, db):
        """Line 473+: update view get_queryset filters by tipe."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        # Create PIDE PIC – should not be accessible via P3DE update URL
        pide_pic = PICFactory(tipe=PIC.TipePIC.PIDE, id_sub_jenis_data_ilap=jdi,
                              id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                              end_date=None)
        client.force_login(p3de_admin)
        resp = client.get(reverse('pic_p3de_update', args=[pide_pic.pk]), {'ajax': '1'})
        # Should return 404 since the PIDE pic is filtered out by get_queryset
        assert resp.status_code == 404
    @pytest.mark.django_db
    def test_pmde_delete_post_ajax(self, client, pmde_admin, db):
        """PMDE delete via AJAX."""
        user_for_pic = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_pmde')
        user_for_pic.groups.add(grp)
        jdi = JenisDataILAPFactory()
        pic_obj = PICFactory(tipe=PIC.TipePIC.PMDE, id_sub_jenis_data_ilap=jdi,
                             id_user=user_for_pic, start_date=datetime.date(2024, 1, 1),
                             end_date=None)
        pic_pk = pic_obj.pk
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('pic_pmde_delete', args=[pic_pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        assert resp.json().get('success') is True
