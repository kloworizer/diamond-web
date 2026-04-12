"""Tests for tiket/list.py – covering the 32 remaining uncovered lines.

Uses RequestFactory to bypass the Django Debug Toolbar middleware issue that
causes all tests in test_tiket_list_view.py to fail.

Uncovered lines: 127-128, 139, 147, 150, 221-227, 255-256, 282-283,
                 328-329, 344-345, 389-390, 498, 501, 504, 507, 510,
                 537-538, 540, 570-571
"""
import json
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.test import RequestFactory
from django.contrib.auth.models import Group
from django.db import connection
from django.utils import timezone

from diamond_web.views.tiket.list import tiket_data
from diamond_web.models import TiketPIC, PIC, Tiket
from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory, PICFactory,
    ILAPFactory, KategoriILAPFactory, KategoriWilayahFactory,
    JenisDataILAPFactory, PeriodeJenisDataFactory,
    DurasiJatuhTempoFactory, KanwilFactory, KPPFactory,
    BentukDataFactory, CaraPenyampaianFactory,
    KlasifikasiJenisDataFactory, PeriodePengirimanFactory,
    DasarHukumFactory, JenisTabelFactory,
)


rf = RequestFactory()


def _call_tiket_data(user, params):
    """Helper: call tiket_data view directly via RequestFactory."""
    request = rf.get('/tiket/data/', params)
    request.user = user
    response = tiket_data(request)
    return response


@pytest.fixture
def admin_user(db):
    user = UserFactory(is_staff=True, is_superuser=True)
    group, _ = Group.objects.get_or_create(name='admin')
    user.groups.add(group)
    return user


# ===========================================================================
# Lines 127-128: except ValueError: pass in tahun filter for get_filter_options
# Lines 282-283: same pattern for jenis filter section
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsTahunInvalid:
    """Lines 127-128 and 282-283: ValueError handlers for tahun param."""

    def test_invalid_tahun_triggers_except_lines_127_128_282_283(self, admin_user, db):
        """Pass non-integer tahun to get_filter_options; both ValueError handlers fire."""
        # Need at least one tiket so queryset is not empty
        TiketFactory()

        resp = _call_tiket_data(admin_user, {
            'get_filter_options': '1',
            'tahun': 'notanumber',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data
        # The tahun exception is swallowed, filter_options still returns


# ===========================================================================
# Line 139: continue when nomor_tiket is None or duplicate
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsNomorTiket:
    """Line 139: continue for null/duplicate nomor_tiket."""

    def test_duplicate_nomor_tiket_triggers_continue_line_139(self, admin_user, db):
        """Two tikets with same nomor_tiket; second iteration triggers `n in nomor_seen: continue`."""
        nomor = 'DUP-001-2025-0001'
        TiketFactory(nomor_tiket=nomor)
        TiketFactory(nomor_tiket=nomor)  # duplicate

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        opts = data['filter_options']['nomor_tiket']
        # Despite two tikets with same nomor, only one option is returned
        assert sum(1 for o in opts if o['id'] == nomor) == 1


# ===========================================================================
# Line 147: continue when tahun is None
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsTahunNull:
    """Lines 147 and 150: continue for null tahun and duplicate tahun string."""

    def test_null_and_duplicate_tahun_covers_lines_147_150(self, admin_user, db):
        """Mock tahun values_list to return [None, 2025, 2025] so:
        - y=None  → line 147 (if y is None: continue)
        - y=2025 (first)  → normal processing, added to tahun_seen
        - y=2025 (second) → line 150 (if y_str in tahun_seen: continue)
        """
        TiketFactory(tahun=2025)

        from django.db.models.query import QuerySet
        original_vl = QuerySet.values_list

        def mock_vl(self_qs, *args, flat=False, **kwargs):
            # Only intercept the flat tahun values_list to inject None + duplicate
            if flat and len(args) == 1 and args[0] == 'tahun':
                class WithNullAndDuplicate:
                    def distinct(self):
                        return self

                    def order_by(self, *a):
                        # Return [None, 2025, 2025] to trigger both line 147 and 150
                        return iter([None, 2025, 2025])

                return WithNullAndDuplicate()
            return original_vl(self_qs, *args, flat=flat, **kwargs)

        with patch.object(QuerySet, 'values_list', mock_vl):
            resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})

        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data
        # Only one tahun=2025 in options (null and duplicate were skipped)
        tahun_opts = data['filter_options']['tahun']
        assert sum(1 for o in tahun_opts if o['id'] == '2025') == 1



# ===========================================================================
# Lines 221-227: _pic_options_filtered for loop body
# Line 223: continue for duplicate user
# Line 226: full_name
# Line 227: else user.username (no full_name)
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsPICOptionsLoop:
    """Lines 221-227: the for loop body in _pic_options_filtered."""

    def _setup_pic_with_tiket(self, user, tipe='P3DE', role=None):
        """Create a PIC with end_date=None and a TiketPIC linking user to a tiket."""
        if role is None:
            role = TiketPIC.Role.P3DE
        jenis_data = JenisDataILAPFactory()
        pic = PICFactory(
            tipe=tipe,
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
        tiket = TiketFactory(id_periode_data=pd)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=role, active=True)
        return tiket, pic, jenis_data

    def test_pic_user_with_fullname_covers_lines_221_226_loop_body(self, admin_user, db):
        """User has full name: loop body executes at lines 221-226, label includes name."""
        user = UserFactory(first_name='John', last_name='Doe')
        self._setup_pic_with_tiket(user)

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        pic_p3de_opts = data['filter_options']['pic_p3de']
        # user appears in options with "username - John Doe" label format
        assert any(str(user.id) == opt['id'] for opt in pic_p3de_opts)

    def test_pic_user_no_fullname_covers_line_227_else(self, admin_user, db):
        """User has empty first/last name: label = username only (else branch at line 227)."""
        user = UserFactory(first_name='', last_name='')
        self._setup_pic_with_tiket(user)

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        pic_p3de_opts = data['filter_options']['pic_p3de']
        # user appears with username-only label
        matching = [o for o in pic_p3de_opts if o['id'] == str(user.id)]
        assert len(matching) == 1
        assert matching[0]['name'] == user.username

    def test_duplicate_pic_user_triggers_continue_line_223(self, admin_user, db):
        """Same user in vals twice (two PIC records) → second triggers continue at line 223."""
        user = UserFactory(first_name='Jane', last_name='Smith')
        jenis_data1 = JenisDataILAPFactory()
        jenis_data2 = JenisDataILAPFactory()
        # Two PIC records for same user (different sub_jenis), both with end_date=None
        PICFactory(
            tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jenis_data1,
            id_user=user, start_date=date.today() - timedelta(days=30), end_date=None
        )
        PICFactory(
            tipe=PIC.TipePIC.P3DE, id_sub_jenis_data_ilap=jenis_data2,
            id_user=user, start_date=date.today() - timedelta(days=30), end_date=None
        )
        # Create two tikets linking user via TiketPIC
        for jd in [jenis_data1, jenis_data2]:
            pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jd)
            t = TiketFactory(id_periode_data=pd)
            TiketPICFactory(id_tiket=t, id_user=user, role=TiketPIC.Role.P3DE, active=True)

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        pic_opts = data['filter_options']['pic_p3de']
        # Despite two PIC records for the same user, only one option should appear
        matching = [o for o in pic_opts if o['id'] == str(user.id)]
        assert len(matching) == 1


# ===========================================================================
# Lines 255-256: ilap_filter_qs with kategori_ilap param
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsKategoriIlap:
    """Lines 255-256: ilap_filter_qs filtered by kategori_ilap."""

    def test_kategori_ilap_param_covers_ilap_filter_qs_lines_255_256(self, admin_user, db):
        """Pass valid kategori_ilap param so lines 255-256 execute."""
        tiket = TiketFactory()
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        kategori_id = ilap.id_kategori.id

        resp = _call_tiket_data(admin_user, {
            'get_filter_options': '1',
            'kategori_ilap': str(kategori_id),
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data
        # ILAP options should include the tiket's ILAP
        ilap_opts = data['filter_options']['ilap']
        assert any(str(ilap.id) == o['id'] for o in ilap_opts)


# ===========================================================================
# Lines 328-329: kanwil options (ILAP with KPP → Kanwil)
# Lines 344-345: kpp options
# Lines 389-390: dasar_hukum options (KlasifikasiJenisData)
# ===========================================================================

@pytest.mark.django_db
class TestGetFilterOptionsKanwilKppDasarHukum:
    """Lines 328-329, 344-345, 389-390: kanwil, kpp, dasar_hukum options."""

    def _setup_tiket_with_kpp_kanwil(self):
        """Create a tiket whose ILAP has id_kpp set (enabling kanwil/kpp options)."""
        kanwil = KanwilFactory()
        kpp = KPPFactory(id_kanwil=kanwil)
        kategori = KategoriILAPFactory()
        kategori_wilayah = KategoriWilayahFactory()
        ilap = ILAPFactory(
            id_kategori=kategori,
            id_kategori_wilayah=kategori_wilayah,
            id_kpp=kpp,
        )
        jenis_data = JenisDataILAPFactory(id_ilap=ilap)
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
        tiket = TiketFactory(id_periode_data=pd)
        return tiket, kanwil, kpp, jenis_data

    def test_kanwil_options_covers_lines_328_329(self, admin_user, db):
        """ILAP with KPP → Kanwil chain → kanwil options populated → lines 328-329."""
        tiket, kanwil, kpp, _ = self._setup_tiket_with_kpp_kanwil()

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        kanwil_opts = data['filter_options']['kanwil']
        assert any(str(kanwil.id) == o['id'] for o in kanwil_opts)

    def test_kpp_options_covers_lines_344_345(self, admin_user, db):
        """ILAP with KPP → kpp options populated → lines 344-345."""
        tiket, _, kpp, _ = self._setup_tiket_with_kpp_kanwil()

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        kpp_opts = data['filter_options']['kpp']
        assert any(str(kpp.id) == o['id'] for o in kpp_opts)

    def test_dasar_hukum_options_covers_lines_389_390(self, admin_user, db):
        """KlasifikasiJenisData linked to sub_jenis → dasar_hukum options populated → lines 389-390."""
        _, _, _, jenis_data = self._setup_tiket_with_kpp_kanwil()
        dasar_hukum = DasarHukumFactory()
        KlasifikasiJenisDataFactory(
            id_jenis_data_ilap=jenis_data,
            id_klasifikasi_tabel=dasar_hukum,
        )

        resp = _call_tiket_data(admin_user, {'get_filter_options': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        dh_opts = data['filter_options']['dasar_hukum']
        assert any(str(dasar_hukum.id) == o['id'] for o in dh_opts)


# ===========================================================================
# Lines 498, 501, 504, 507, 510: DataTables filter params
# (kanwil, kpp, kategori_wilayah, jenis_tabel, dasar_hukum)
# ===========================================================================

@pytest.mark.django_db
class TestTiketDataFilterParams:
    """Lines 498-510: kanwil, kpp, kategori_wilayah, jenis_tabel, dasar_hukum filters."""

    def _base_dt_params(self):
        return {'draw': '1', 'start': '0', 'length': '10'}

    def test_filter_kanwil_line_498(self, admin_user, db):
        """Pass kanwil filter param to tiket_data → line 498 executed."""
        kanwil = KanwilFactory()
        resp = _call_tiket_data(admin_user, {
            **self._base_dt_params(),
            'kanwil': str(kanwil.id),
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_filter_kpp_line_501(self, admin_user, db):
        """Pass kpp filter param → line 501 executed."""
        kpp = KPPFactory()
        resp = _call_tiket_data(admin_user, {
            **self._base_dt_params(),
            'kpp': str(kpp.id),
        })
        assert resp.status_code == 200

    def test_filter_kategori_wilayah_line_504(self, admin_user, db):
        """Pass kategori_wilayah filter param → line 504 executed."""
        kw = KategoriWilayahFactory()
        resp = _call_tiket_data(admin_user, {
            **self._base_dt_params(),
            'kategori_wilayah': str(kw.id),
        })
        assert resp.status_code == 200

    def test_filter_jenis_tabel_line_507(self, admin_user, db):
        """Pass jenis_tabel filter param → line 507 executed."""
        jt = JenisTabelFactory()
        resp = _call_tiket_data(admin_user, {
            **self._base_dt_params(),
            'jenis_tabel': str(jt.id),
        })
        assert resp.status_code == 200

    def test_filter_dasar_hukum_line_510(self, admin_user, db):
        """Pass dasar_hukum filter param → line 510 executed."""
        dh = DasarHukumFactory()
        resp = _call_tiket_data(admin_user, {
            **self._base_dt_params(),
            'dasar_hukum': str(dh.id),
        })
        assert resp.status_code == 200


# ===========================================================================
# Lines 537-538: deadline computed when obj has tgl_terima_dip + durasi
# Line 540: late_ids.append when is_late = True
# ===========================================================================

@pytest.mark.django_db
class TestTiketDataTerlambatWithDurasi:
    """Lines 537-538, 540: terlambat logic when tiket has id_durasi_jatuh_tempo_pide."""

    def _setup_late_tiket(self):
        """Create a tiket whose deadline is in the past (late)."""
        pide_group, _ = Group.objects.get_or_create(name='user_pide')
        jenis_data = JenisDataILAPFactory()
        durasi = DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis_data,
            seksi=pide_group,
            durasi=1,           # 1-day deadline
            start_date=date.today() - timedelta(days=60),
            end_date=None,
        )
        # tgl_terima_dip = 30 days ago, durasi = 1 day → deadline = 29 days ago (past)
        import datetime
        tgl_terima = timezone.now() - timedelta(days=30)
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
        tiket = TiketFactory(
            id_periode_data=pd,
            id_durasi_jatuh_tempo_pide=durasi,
            tgl_terima_dip=tgl_terima,
        )
        return tiket

    def test_terlambat_ya_with_past_deadline_covers_537_538_540(self, admin_user, db):
        """Tiket with past deadline + terlambat=Ya → lines 537-538 execute (deadline computed),
        line 540 executes (late_ids.append)."""
        tiket = self._setup_late_tiket()

        resp = _call_tiket_data(admin_user, {
            'draw': '1', 'start': '0', 'length': '10',
            'terlambat': 'Ya',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        # The tiket is late, so it should appear when filtering for terlambat=Ya
        tiket_ids = [r['id'] for r in data['data']]
        assert tiket.id in tiket_ids

    def test_terlambat_tidak_with_past_deadline_covers_537_538(self, admin_user, db):
        """Same setup but terlambat=Tidak → lines 537-538 execute, tiket excluded."""
        tiket = self._setup_late_tiket()

        resp = _call_tiket_data(admin_user, {
            'draw': '1', 'start': '0', 'length': '10',
            'terlambat': 'Tidak',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        # The tiket is late, so it should NOT appear when filtering for terlambat=Tidak
        tiket_ids = [r['id'] for r in data['data']]
        assert tiket.id not in tiket_ids


# ===========================================================================
# Lines 570-571: sort exception fallback (non-integer column index)
# ===========================================================================

@pytest.mark.django_db
class TestTiketDataSortException:
    """Lines 570-571: except Exception: qs = qs.order_by('id')."""

    def test_invalid_order_column_triggers_except_lines_570_571(self, admin_user, db):
        """Pass non-integer order column index → int('xyz') raises → except fires."""
        TiketFactory()

        resp = _call_tiket_data(admin_user, {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'xyz',  # non-integer triggers ValueError → except
            'order[0][dir]': 'asc',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        # Falls back to default ordering by id, still returns data
        assert 'data' in data
