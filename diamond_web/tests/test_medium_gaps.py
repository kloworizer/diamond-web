"""Tests to cover medium-sized gaps in various view files.

Covers:
- durasi_jatuh_tempo.py: PIDE/PMDE list exceptions, delete AJAX paths, datatables desc/column search
- jenis_data_ilap.py: list exception, delete non-AJAX GET, column search, desc ordering, next-ID endpoints
- jenis_prioritas_data.py: list exception, delete non-AJAX GET
- periode_jenis_data.py: list exception, delete non-AJAX GET
- kategori_ilap.py: column search, ordering variants
- pic.py: list exception, datatables column search
- various 1-line gaps in bentuk_data, cara_penyampaian, etc.
"""
import json
import pytest
import datetime
from unittest.mock import patch
from django.urls import reverse
from django.contrib.auth.models import Group

from .conftest import (
    UserFactory,
    KategoriILAPFactory,
    JenisDataILAPFactory,
    ILAPFactory,
    DurasiJatuhTempoFactory,
    JenisPrioritasDataFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    PICFactory,
    KanwilFactory,
    KPPFactory,
    BentukDataFactory,
    CaraPenyampaianFactory,
    MediaBackupFactory,
    StatusDataFactory,
    KlasifikasiJenisDataFactory,
    KategoriWilayahFactory,
    JenisTabelFactory,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def p3de_admin(db):
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_p3de')
    user.groups.add(grp)
    return user


@pytest.fixture
def pide_admin(db):
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_pide')
    user.groups.add(grp)
    return user


@pytest.fixture
def pide_group(db):
    grp, _ = Group.objects.get_or_create(name='user_pide')
    return grp


@pytest.fixture
def pmde_admin(db):
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_pmde')
    user.groups.add(grp)
    return user


@pytest.fixture
def pmde_group(db):
    grp, _ = Group.objects.get_or_create(name='user_pmde')
    return grp


# ─── DurasiJatuhTempo PIDE gaps ───────────────────────────────────────────────

@pytest.mark.django_db
class TestDurasiJatuhTempoPIDEGaps:
    """Cover remaining PIDE gaps: list exception, delete AJAX, datatables."""

    def test_pide_list_exception(self, client, pide_admin):
        """Lines 39-40: except Exception: pass in PIDE list view."""
        client.force_login(pide_admin)
        with patch('diamond_web.views.durasi_jatuh_tempo.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('durasi_jatuh_tempo_pide_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_pide_delete_ajax_post(self, client, pide_admin, pide_group):
        """Lines 173-174: AJAX POST delete for PIDE DurasiJatuhTempo."""
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        jdi = JenisDataILAPFactory()
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi,
            seksi=pide_group,
            durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_pide_datatables_column0_search(self, client, pide_admin, pide_group):
        """Line 213: PIDE datatables column 0 search (sub_jenis_data)."""
        jdi = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(id_sub_jenis_data=jdi, seksi=pide_group,
                                start_date=datetime.date(2024, 1, 1))
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [jdi.nama_sub_jenis_data, '', '', ''],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pide_datatables_desc_ordering(self, client, pide_admin, pide_group):
        """Line 232: PIDE datatables desc ordering (col = '-' + col)."""
        jdi = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(id_sub_jenis_data=jdi, seksi=pide_group,
                                start_date=datetime.date(2024, 1, 1))
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',  # durasi column
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1


# ─── DurasiJatuhTempo PMDE gaps ───────────────────────────────────────────────

@pytest.mark.django_db
class TestDurasiJatuhTempoPMDEGaps:
    """Cover remaining PMDE gaps: list exception, delete AJAX, datatables."""

    def test_pmde_list_exception(self, client, pmde_admin):
        """Lines 278-279: except Exception: pass in PMDE list view."""
        client.force_login(pmde_admin)
        with patch('diamond_web.views.durasi_jatuh_tempo.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('durasi_jatuh_tempo_pmde_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_pmde_delete_ajax_post(self, client, pmde_admin, pmde_group):
        """Line 358: AJAX POST delete for PMDE DurasiJatuhTempo."""
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        jdi = JenisDataILAPFactory()
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi,
            seksi=pmde_group,
            durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_pmde_datatables_exception_ordering(self, client, pmde_admin):
        """Line 393: PMDE datatables exception in ordering (non-numeric column)."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': 'bad',
                'order[0][dir]': 'asc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pmde_datatables_column0_search(self, client, pmde_admin, pmde_group):
        """Line 442: PMDE datatables column 0 search (sub_jenis_data)."""
        jdi = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(id_sub_jenis_data=jdi, seksi=pmde_group,
                                start_date=datetime.date(2024, 1, 1))
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [jdi.nama_sub_jenis_data, '', '', ''],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pmde_datatables_column3_search(self, client, pmde_admin, pmde_group):
        """Line 448: PMDE datatables column 3 search (end_date)."""
        jdi = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(id_sub_jenis_data=jdi, seksi=pmde_group,
                                start_date=datetime.date(2024, 1, 1),
                                end_date=datetime.date(2024, 12, 31))
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '', '', '2024'],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pmde_datatables_desc_ordering(self, client, pmde_admin):
        """PMDE datatables desc ordering."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pmde_delete_non_ajax_get(self, client, pmde_admin, pmde_group):
        """Line 393: non-AJAX GET in DurasiJatuhTempoPMDEDeleteView.get() — render_to_response path."""
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        jdi = JenisDataILAPFactory()
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi,
            seksi=pmde_group,
            durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        # GET without 'ajax' param → hits line 393: return self.render_to_response(...)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk]))
        assert resp.status_code == 200


# ─── JenisDataILAP gaps ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestJenisDataILAPGaps:
    """Cover remaining jenis_data_ilap.py gaps."""

    def test_list_exception(self, client, p3de_admin):
        """Lines 38-39: except Exception: pass in JenisDataILAP list view."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.jenis_data_ilap.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('jenis_data_ilap_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_delete_non_ajax_get(self, client, p3de_admin, db):
        """Line 112: non-AJAX GET in JenisDataILAPDeleteView."""
        obj = JenisDataILAPFactory()
        client.force_login(p3de_admin)
        # GET without 'ajax' param → hits line 112
        resp = client.get(reverse('jenis_data_ilap_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_datatables_column2_search(self, client, p3de_admin, db):
        """Line 169: datatables column 2 search (kategori_ilap)."""
        obj = JenisDataILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '', obj.id_ilap.id_kategori.nama_kategori, '', '', '', ''],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_datatables_desc_ordering(self, client, p3de_admin, db):
        """Datatables desc ordering in jenis_data_ilap_data."""
        JenisDataILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '4',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_get_next_jenis_data_id_if_last_block(self, client, p3de_admin, db):
        """Lines 267-268: get_next_jenis_data_id except Exception branch when suffix is non-numeric."""
        from diamond_web.models import JenisDataILAP as JDIModel
        jt = JenisTabelFactory()
        sd = StatusDataFactory()
        ilap = ILAPFactory()
        # id_jenis_data 'TPMEDXX' has suffix 'XX' (non-numeric) → triggers except Exception: last_number = 0
        JDIModel.objects.create(
            id_ilap=ilap, id_jenis_data='TPMEDXX', id_sub_jenis_data='TPMEDXX01',
            nama_jenis_data='Test', nama_sub_jenis_data='Test Sub',
            nama_tabel_I='tbl', nama_tabel_U='tbl', id_jenis_tabel=jt, id_status_data=sd,
        )
        client.force_login(p3de_admin)
        # Pass non-numeric string → except branch → prefix='TPMED' → finds 'TPMEDXX' → suffix='XX' → lines 267-268
        resp = client.get(reverse('get_next_jenis_data_id'), {'ilap_id': 'TPMED'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'next_id' in data
        assert data['next_id'].startswith('TPMED')

    def test_get_existing_jenis_data_non_numeric(self, client, p3de_admin, db):
        """Lines 303-306: get_existing_jenis_data with non-numeric string triggers except branch."""
        from diamond_web.models import JenisDataILAP as JDIModel, JenisTabel, StatusData
        jt = JenisTabelFactory()
        sd = StatusDataFactory()
        ilap = ILAPFactory()
        JDIModel.objects.create(
            id_ilap=ilap, id_jenis_data='TPEX01', id_sub_jenis_data='TPEX0101',
            nama_jenis_data='Test', nama_sub_jenis_data='Test Sub',
            nama_tabel_I='tbl', nama_tabel_U='tbl', id_jenis_tabel=jt, id_status_data=sd,
        )
        client.force_login(p3de_admin)
        # Non-numeric string → int() raises → except block (lines 303-306)
        resp = client.get(reverse('get_existing_jenis_data'), {'ilap_id': 'TPEX'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'items' in data

    def test_get_next_sub_jenis_id_with_existing_data(self, client, p3de_admin, db):
        """Lines 365-366: get_next_sub_jenis_id except Exception branch when suffix is non-numeric."""
        from diamond_web.models import JenisDataILAP as JDIModel
        jt = JenisTabelFactory()
        sd = StatusDataFactory()
        ilap = ILAPFactory()
        # id_sub_jenis_data 'TPSUB01AB' has suffix 'AB' (non-numeric) → triggers except Exception: last_number = 0
        JDIModel.objects.create(
            id_ilap=ilap, id_jenis_data='TPSUB01', id_sub_jenis_data='TPSUB01AB',
            nama_jenis_data='Test', nama_sub_jenis_data='Test Sub',
            nama_tabel_I='tbl', nama_tabel_U='tbl', id_jenis_tabel=jt, id_status_data=sd,
        )
        client.force_login(p3de_admin)
        # Query with 'TPSUB01' → finds 'TPSUB01AB' → suffix='AB' → int('AB') raises → lines 365-366 covered
        resp = client.get(reverse('get_next_sub_jenis_id'), {'id_jenis_data': 'TPSUB01'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'next_id' in data
        assert data['next_id'].startswith('TPSUB01')

    def test_get_next_sub_jenis_id_missing_param(self, client, p3de_admin):
        """get_next_sub_jenis_id with missing id_jenis_data → 400."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('get_next_sub_jenis_id'))
        assert resp.status_code == 400


# ─── JenisPrioritasData gaps ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestJenisPrioritasDataGaps:
    """Cover remaining jenis_prioritas_data.py gaps."""

    def test_list_exception(self, client, p3de_admin):
        """Lines 36-37: except Exception: pass in JenisPrioritasData list view."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.jenis_prioritas_data.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('jenis_prioritas_data_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_delete_non_ajax_get(self, client, p3de_admin, db):
        """Line 141: non-AJAX GET in JenisPrioritasDataDeleteView."""
        jdi = JenisDataILAPFactory()
        obj = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jdi,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(p3de_admin)
        # GET without 'ajax' param → hits non-AJAX render path
        resp = client.get(reverse('jenis_prioritas_data_delete', args=[obj.pk]))
        assert resp.status_code == 200


# ─── PeriodeJenisData gaps ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPeriodeJenisDataGaps:
    """Cover remaining periode_jenis_data.py gaps."""

    def test_list_exception(self, client, p3de_admin):
        """Lines 37-38: except Exception: pass in PeriodeJenisData list view."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.periode_jenis_data.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('periode_jenis_data_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_delete_non_ajax_get(self, client, p3de_admin, db):
        """Line 147: non-AJAX GET in PeriodeJenisDataDeleteView."""
        jdi = JenisDataILAPFactory()
        periode = PeriodePengirimanFactory()
        obj = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(p3de_admin)
        # GET without 'ajax' param → hits non-AJAX render path
        resp = client.get(reverse('periode_jenis_data_delete', args=[obj.pk]))
        assert resp.status_code == 200


# ─── KategoriILAP datatables gaps ────────────────────────────────────────────

@pytest.mark.django_db
class TestKategoriILAPDataTablesGaps:
    """Cover remaining kategori_ilap.py datatables gaps."""

    def test_datatables_column0_search(self, client, p3de_admin, db):
        """Lines 218-219: column 0 search (id_kategori) in datatables."""
        obj = KategoriILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kategori_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [obj.id_kategori, ''],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_datatables_column1_search(self, client, p3de_admin, db):
        """Lines 220-221: column 1 search (nama_kategori) in datatables."""
        obj = KategoriILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kategori_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', obj.nama_kategori],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_datatables_asc_ordering(self, client, p3de_admin, db):
        """Lines 230-235: ordering section with asc direction."""
        KategoriILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kategori_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'asc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_datatables_desc_ordering(self, client, p3de_admin, db):
        """Line 234: desc ordering (col = '-' + col) in kategori_ilap datatables."""
        KategoriILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kategori_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '0',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_datatables_exception_ordering(self, client, p3de_admin):
        """Lines 236-237: exception ordering (non-numeric column) in kategori_ilap datatables."""
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kategori_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': 'bad',
                'order[0][dir]': 'asc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1


# ─── PIC list exception gap ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPICGaps:
    """Cover remaining pic.py gaps."""

    def test_pic_list_exception(self, client, p3de_admin):
        """Lines 62-63: except Exception: pass in PIC list view."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.pic.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(
                reverse('pic_p3de_list'),
                {'deleted': '1', 'name': 'Test'},
            )
        assert resp.status_code == 200

    def test_pic_datatables_column1_user_search(self, client, p3de_admin, db):
        """Lines 658-659: pic datatables column 1 search (user)."""
        pic_obj = PICFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('pic_p3de_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', pic_obj.id_user.username, '', ''],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_pic_datatables_column3_enddate_search(self, client, p3de_admin, db):
        """Line 665: pic datatables column 3 search (end_date)."""
        pic_obj = PICFactory()
        search_val = str(pic_obj.end_date) if pic_obj.end_date else '2025'
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('pic_p3de_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '', '', search_val],
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1


# ─── Small 1-2 line gaps in bentuk_data, cara_penyampaian, etc. ─────────────

@pytest.mark.django_db
class TestSmallGaps:
    """Cover 1-2 line gaps in various view files."""

    def test_bentuk_data_delete_non_ajax_get(self, client, p3de_admin, db):
        """bentuk_data.py line 90: non-AJAX GET in delete view."""
        obj = BentukDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('bentuk_data_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_cara_penyampaian_delete_non_ajax_get(self, client, p3de_admin, db):
        """cara_penyampaian.py line 90: non-AJAX GET in delete view."""
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('cara_penyampaian_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_media_backup_delete_non_ajax_get(self, client, p3de_admin, db):
        """media_backup.py line 90: non-AJAX GET in delete view."""
        obj = MediaBackupFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('media_backup_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_jenis_tabel_delete_non_ajax_get(self, client, p3de_admin, db):
        """jenis_tabel.py line 97: non-AJAX GET in delete view."""
        obj = JenisTabelFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('jenis_tabel_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_kanwil_delete_non_ajax_get(self, client, p3de_admin, db):
        """kanwil.py line 96: non-AJAX GET in delete view."""
        obj = KanwilFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('kanwil_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_kpp_delete_non_ajax_get(self, client, p3de_admin, db):
        """kpp.py line 96: non-AJAX GET in delete view."""
        obj = KPPFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('kpp_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_kategori_wilayah_delete_non_ajax_get(self, client, p3de_admin, db):
        """kategori_wilayah.py line 115: non-AJAX GET in delete view."""
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('kategori_wilayah_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_klasifikasi_jenis_data_delete_non_ajax_get(self, client, p3de_admin, db):
        """klasifikasi_jenis_data.py line 116: non-AJAX GET in delete view."""
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('klasifikasi_jenis_data_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_periode_pengiriman_delete_non_ajax_get(self, client, p3de_admin, db):
        """periode_pengiriman.py line 116: non-AJAX GET in delete view."""
        from diamond_web.models import PeriodePengiriman
        obj, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian='TestPeriodeMedGap1',
            defaults={'periode_penerimaan': 'TestRecv1'}
        )
        client.force_login(p3de_admin)
        resp = client.get(reverse('periode_pengiriman_delete', args=[obj.pk]))
        assert resp.status_code == 200

    def test_mixins_form_invalid_ajax(self, client, p3de_admin):
        """mixins.py line 110: AjaxFormMixin.form_invalid with AJAX request."""
        client.force_login(p3de_admin)
        resp = client.post(
            reverse('bentuk_data_create'),
            data={'deskripsi': ''},  # invalid (required field empty)
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data or 'error' in data or 'errors' in data


# ─── kanwil datatables exception gap ─────────────────────────────────────────

@pytest.mark.django_db
class TestKanwilKPPGaps:
    """Cover kanwil and kpp datatables gaps."""

    def test_kanwil_datatables_desc_ordering(self, client, p3de_admin, db):
        """kanwil.py: datatables desc ordering."""
        KanwilFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kanwil_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_kpp_datatables_desc_ordering(self, client, p3de_admin, db):
        """kpp.py: datatables desc ordering."""
        KPPFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('kpp_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_klasifikasi_jenis_data_desc_ordering(self, client, p3de_admin, db):
        """klasifikasi_jenis_data.py: datatables desc ordering."""
        KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('klasifikasi_jenis_data_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_periode_pengiriman_desc_ordering(self, client, p3de_admin, db):
        """periode_pengiriman.py: datatables desc ordering."""
        client.force_login(p3de_admin)
        resp = client.get(
            reverse('periode_pengiriman_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
            },
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1
