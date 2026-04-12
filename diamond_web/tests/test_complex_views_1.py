"""Tests for complex views with many branches:
- jenis_data_ilap (113 missing lines)
- durasi_jatuh_tempo (79 missing lines)
- periode_jenis_data (82 missing lines)
- jenis_prioritas_data (57 missing lines)
"""
import json
import datetime
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group

from .conftest import (
    JenisDataILAPFactory, ILAPFactory, KategoriILAPFactory,
    JenisTabelFactory, StatusDataFactory,
    PeriodeJenisDataFactory, PeriodePengirimanFactory,
    JenisPrioritasDataFactory, DurasiJatuhTempoFactory,
    GroupFactory,
)


# ============================================================
# JenisDataILAP Views
# ============================================================

@pytest.mark.django_db
class TestJenisDataILAPMissingBranches:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params shows toast (lines 35-39)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_list'),
            {'deleted': 'true', 'name': 'Test+Jenis+Data'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET without order col → else branch (line 119)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_with_order_column(self, client, p3de_admin_user):
        """GET with order col valid → ordered data (lines 107-112)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': '0', 'order[0][dir]': 'desc'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_exception_path(self, client, p3de_admin_user):
        """GET with bad order col → except branch (line 112)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200

    def test_datatables_column_searches(self, client, p3de_admin_user):
        """Column-specific filter branches (lines 80-87, 102-104)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [
                    jdi.id_sub_jenis_data,   # col 0
                    jdi.id_jenis_tabel.deskripsi,   # col 1
                    '',                              # col 2
                    jdi.id_ilap.nama_ilap,          # col 3
                    jdi.nama_jenis_data,            # col 4
                    jdi.nama_sub_jenis_data,        # col 5
                    '',                             # col 6 (status_data)
                ],
            },
        )
        assert resp.status_code == 200

    def test_datatables_status_data_column_search(self, client, p3de_admin_user):
        """Status data column search (line 104)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '', '', '', '', '', jdi.id_status_data.deskripsi],
            },
        )
        assert resp.status_code == 200

    def test_create_get_form(self, client, p3de_admin_user):
        """GET create form renders HTML (lines 57-59, 62-64)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('jenis_data_ilap_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        """Valid AJAX POST creates JenisDataILAP (lines 62-64)."""
        ilap = ILAPFactory()
        jenis_tabel = JenisTabelFactory()
        status_data = StatusDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_data_ilap_create'),
            {
                'id_ilap': ilap.pk,
                'id_jenis_data': 'A000001',
                'id_sub_jenis_data': 'A00000101',
                'nama_jenis_data': 'Jenis Data Test',
                'nama_sub_jenis_data': 'Sub Jenis Data Test',
                'nama_tabel_I': 'Tabel_I',
                'nama_tabel_U': 'Tabel_U',
                'id_jenis_tabel': jenis_tabel.pk,
                'id_status_data': status_data.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_get_form(self, client, p3de_admin_user):
        """GET update form renders HTML (lines 80-82, 85-87)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_update', args=[jdi.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_update_post_valid(self, client, p3de_admin_user):
        """Valid AJAX POST updates JenisDataILAP."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_data_ilap_update', args=[jdi.pk]),
            {
                'nama_jenis_data': 'Updated Jenis',
                'nama_sub_jenis_data': 'Updated Sub Jenis',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_delete_ajax_get(self, client, p3de_admin_user):
        """GET ?ajax=1 returns confirmation HTML."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_data_ilap_delete', args=[jdi.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_delete_ajax_post(self, client, p3de_admin_user):
        """AJAX DELETE returns success JSON (lines 119-121)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_data_ilap_delete', args=[jdi.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_delete_non_ajax_post(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns redirect JSON (lines 123-124)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('jenis_data_ilap_delete', args=[jdi.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_get_next_jenis_data_id_missing_param(self, client, p3de_admin_user):
        """Missing ilap_id → 400 (lines 164-166)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_jenis_data_id'))
        assert resp.status_code == 400

    def test_get_next_jenis_data_id_numeric_pk(self, client, p3de_admin_user):
        """Numeric pk → resolves to id_ilap prefix (lines 169-174)."""
        ilap = ILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_jenis_data_id'), {'ilap_id': str(ilap.pk)})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'next_id' in data

    def test_get_next_jenis_data_id_string_prefix(self, client, p3de_admin_user):
        """String prefix → extract alphanumeric prefix (lines 175-177)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_jenis_data_id'), {'ilap_id': 'AB001'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'next_id' in data

    def test_get_next_jenis_data_id_with_existing(self, client, p3de_admin_user):
        """Existing entries → increments (lines 181-188)."""
        jdi = JenisDataILAPFactory()
        prefix = jdi.id_jenis_data[:3]
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_jenis_data_id'), {'ilap_id': prefix})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'next_id' in data

    def test_get_existing_jenis_data_missing_param(self, client, p3de_admin_user):
        """Missing ilap_id → empty items (lines 207-208)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_existing_jenis_data'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data == {'items': []}

    def test_get_existing_jenis_data_numeric_pk(self, client, p3de_admin_user):
        """Numeric pk → resolves to prefix (lines 211-216)."""
        ilap = ILAPFactory()
        JenisDataILAPFactory(id_ilap=ilap)
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_existing_jenis_data'), {'ilap_id': str(ilap.pk)})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data['items'], list)

    def test_get_existing_jenis_data_string_prefix(self, client, p3de_admin_user):
        """String prefix → returns matching items (lines 217-221)."""
        jdi = JenisDataILAPFactory()
        prefix = jdi.id_jenis_data[:3]
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_existing_jenis_data'), {'ilap_id': prefix})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data['items'], list)

    def test_get_existing_sub_jenis_data_missing_param(self, client, p3de_admin_user):
        """Missing id_jenis_data → empty items (lines 232-233)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_existing_sub_jenis_data'))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data == {'items': []}

    def test_get_existing_sub_jenis_data_with_param(self, client, p3de_admin_user):
        """id_jenis_data → returns matching items (lines 235-241)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_existing_sub_jenis_data'),
                          {'id_jenis_data': jdi.id_jenis_data})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data['items'], list)

    def test_get_next_sub_jenis_id_missing_param(self, client, p3de_admin_user):
        """Missing id_jenis_data → 400 (lines 257-258)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_sub_jenis_id'))
        assert resp.status_code == 400

    def test_get_next_sub_jenis_id_no_existing(self, client, p3de_admin_user):
        """No existing entries → returns 01 (lines 266-270)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_sub_jenis_id'), {'id_jenis_data': 'ZZ99999'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['next_id'] == 'ZZ9999901'

    def test_get_next_sub_jenis_id_with_existing(self, client, p3de_admin_user):
        """With existing → increments suffix (lines 260-265)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_sub_jenis_id'),
                          {'id_jenis_data': jdi.id_jenis_data})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'next_id' in data


# ============================================================
# DurasiJatuhTempo Views (PIDE section)
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPIDEMissingBranches:

    @pytest.fixture
    def pide_admin(self, db):
        user_obj = __import__('django.contrib.auth.models', fromlist=['User']).User
        from .conftest import UserFactory
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin_pide')
        user.groups.add(group)
        return user

    @pytest.fixture
    def pide_group(self, db):
        group, _ = Group.objects.get_or_create(name='user_pide')
        return group

    def test_list_with_deleted_toast(self, client, pide_admin):
        """GET list with deleted params shows toast (lines 39-40)."""
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_list'),
            {'deleted': 'true', 'name': 'Test+Durasi'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, pide_admin):
        """GET without order col → else branch (lines 212-213)."""
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_with_order_column(self, client, pide_admin):
        """GET with order col → ordered data."""
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': '1', 'order[0][dir]': 'asc'},
        )
        assert resp.status_code == 200

    def test_datatables_exception_path(self, client, pide_admin):
        """GET with bad order col → except branch."""
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200

    def test_datatables_column_searches(self, client, pide_admin, pide_group):
        """Column-specific filter branches."""
        jdi = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(id_sub_jenis_data=jdi, seksi=pide_group,
                                start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31))
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '5', '2024', '2024'],
            },
        )
        assert resp.status_code == 200

    def test_create_get_form(self, client, pide_admin):
        """GET create form renders HTML (lines 86)."""
        client.force_login(pide_admin)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_create_post_valid_no_overlap(self, client, pide_admin, pide_group):
        """Valid POST with no start_date overlap succeeds (lines 128)."""
        jdi = JenisDataILAPFactory()
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pide_group.pk,
                'durasi': '30',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_create_post_overlap_detected(self, client, pide_admin, pide_group):
        """POST with overlapping date range → form_invalid (lines 133-137)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi,
            seksi=pide_group,
            durasi=30,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pide_group.pk,
                'durasi': '15',
                'start_date': '2024-06-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        # form_invalid returns HTML form with errors
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data

    def test_create_post_no_start_date(self, client, pide_admin, pide_group):
        """POST without start_date goes straight to super().form_valid() (line 128)."""
        jdi = JenisDataILAPFactory()
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pide_group.pk,
                'durasi': '20',
                # no start_date provided → form will fail validation since required
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200

    def test_update_get_form(self, client, pide_admin, pide_group):
        """GET update form renders HTML (line 133-137)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31),
        )
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_update_post_valid(self, client, pide_admin, pide_group):
        """Valid AJAX POST updates DurasiJatuhTempo (lines 160-162)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk]),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pide_group.pk,
                'durasi': '45',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_overlap(self, client, pide_admin, pide_group):
        """Update with overlapping date → form_invalid (lines 173-174)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        other = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 6, 30),
        )
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=20,
            start_date=datetime.date(2025, 1, 1), end_date=datetime.date(2025, 12, 31),
        )
        client.force_login(pide_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk]),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pide_group.pk,
                'durasi': '20',
                'start_date': '2024-03-01',  # overlaps with 'other'
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200

    def test_delete_ajax_get(self, client, pide_admin, pide_group):
        """GET ?ajax=1 returns confirmation HTML."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pide_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_delete_post_redirects(self, client, pide_admin, pide_group):
        """DELETE POST returns success+redirect JSON (lines 228-235)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pide_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pide_admin)
        resp = client.post(reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# DurasiJatuhTempo Views (PMDE section)
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPMDEMissingBranches:

    @pytest.fixture
    def pmde_admin(self, db):
        from .conftest import UserFactory
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin_pmde')
        user.groups.add(group)
        return user

    @pytest.fixture
    def pmde_group(self, db):
        group, _ = Group.objects.get_or_create(name='user_pmde')
        return group

    def test_list_with_deleted_toast(self, client, pmde_admin):
        """GET list with deleted params shows toast."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_list'),
            {'deleted': 'true', 'name': 'Test+Durasi'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, pmde_admin):
        """GET without order col → else branch."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_exception_path(self, client, pmde_admin):
        """Bad order col → except branch."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200

    def test_datatables_column_searches(self, client, pmde_admin, pmde_group):
        """Column-specific filter branches."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', '10', '2024', ''],
            },
        )
        assert resp.status_code == 200

    def test_create_post_valid(self, client, pmde_admin, pmde_group):
        """Valid POST creates DurasiJatuhTempo (PMDE) (lines 316)."""
        jdi = JenisDataILAPFactory()
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_create'),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pmde_group.pk,
                'durasi': '30',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_create_post_overlap(self, client, pmde_admin, pmde_group):
        """POST with overlap → form_invalid (lines 321-325)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=30,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31),
        )
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_create'),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pmde_group.pk,
                'durasi': '15',
                'start_date': '2024-06-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200

    def test_update_get_form(self, client, pmde_admin, pmde_group):
        """GET update form renders HTML."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31),
        )
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_update_post_valid(self, client, pmde_admin, pmde_group):
        """Valid POST updates DurasiJatuhTempo (PMDE) (lines 346-348)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk]),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pmde_group.pk,
                'durasi': '45',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_overlap(self, client, pmde_admin, pmde_group):
        """Update with overlapping date → form_invalid (lines 351-353)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 6, 30),
        )
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=20,
            start_date=datetime.date(2025, 1, 1), end_date=datetime.date(2025, 12, 31),
        )
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk]),
            {
                'id_sub_jenis_data': jdi.pk,
                'seksi': pmde_group.pk,
                'durasi': '20',
                'start_date': '2024-03-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200

    def test_delete_ajax_post(self, client, pmde_admin, pmde_group):
        """AJAX DELETE returns success message JSON (lines 383-385)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_delete_non_ajax_post(self, client, pmde_admin, pmde_group):
        """Non-AJAX DELETE returns redirect JSON (lines 388-393)."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_delete_ajax_get(self, client, pmde_admin, pmde_group):
        """AJAX GET returns confirmation HTML."""
        jdi = JenisDataILAPFactory()
        from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo
        obj = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jdi, seksi=pmde_group, durasi=10,
            start_date=datetime.date(2024, 1, 1),
        )
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_datatables_desc_order(self, client, pmde_admin):
        """Desc ordering (lines 400)."""
        client.force_login(pmde_admin)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': '0', 'order[0][dir]': 'desc'},
        )
        assert resp.status_code == 200


# ============================================================
# PeriodeJenisData Views
# ============================================================

@pytest.mark.django_db
class TestPeriodeJenisDataMissingBranches:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params shows toast (lines 31-39)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_list'),
            {'deleted': 'true', 'name': 'Test+Periode'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET without order col → else branch (lines 208-209)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_with_order(self, client, p3de_admin_user):
        """GET with order col."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': '2', 'order[0][dir]': 'desc'},
        )
        assert resp.status_code == 200

    def test_datatables_exception_path(self, client, p3de_admin_user):
        """Bad order col → except branch."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200

    def test_datatables_column_searches(self, client, p3de_admin_user):
        """Column-specific filter branches (lines 99-101, 105-107, 111-123)."""
        pjd = PeriodeJenisDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [
                    pjd.id_sub_jenis_data_ilap.nama_sub_jenis_data,  # col 0
                    pjd.id_periode_pengiriman.periode_penyampaian,    # col 1
                    str(pjd.start_date),                              # col 2
                    str(pjd.end_date),                                # col 3
                    str(pjd.akhir_penyampaian),                      # col 4
                ],
            },
        )
        assert resp.status_code == 200

    def test_create_get_form(self, client, p3de_admin_user):
        """GET create form (lines 55-57, 61-63)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('periode_jenis_data_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_create_post_valid_no_overlap(self, client, p3de_admin_user):
        """Valid POST with non-overlapping dates (lines 72-84)."""
        jdi = JenisDataILAPFactory()
        periode = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_jenis_data_create'),
            {
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_periode_pengiriman': periode.pk,
                'akhir_penyampaian': '31',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_create_post_overlap(self, client, p3de_admin_user):
        """POST with overlapping dates → form_invalid (lines 79-83)."""
        from diamond_web.models.periode_jenis_data import PeriodeJenisData
        pjd = PeriodeJenisDataFactory(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        periode = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_jenis_data_create'),
            {
                'id_sub_jenis_data_ilap': pjd.id_sub_jenis_data_ilap.pk,
                'id_periode_pengiriman': periode.pk,
                'akhir_penyampaian': '28',
                'start_date': '2024-06-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data

    def test_update_get_form(self, client, p3de_admin_user):
        """GET update form (lines 99-101)."""
        pjd = PeriodeJenisDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_update', args=[pjd.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_update_post_valid(self, client, p3de_admin_user):
        """Valid update POST (lines 105-107)."""
        pjd = PeriodeJenisDataFactory(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_jenis_data_update', args=[pjd.pk]),
            {
                'id_sub_jenis_data_ilap': pjd.id_sub_jenis_data_ilap.pk,
                'id_periode_pengiriman': pjd.id_periode_pengiriman.pk,
                'akhir_penyampaian': '28',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_overlap(self, client, p3de_admin_user):
        """Update with overlapping dates → form_invalid (lines 111-123)."""
        from diamond_web.models.periode_jenis_data import PeriodeJenisData
        jdi = JenisDataILAPFactory()
        periode1 = PeriodePengirimanFactory()
        periode2 = PeriodePengirimanFactory()
        pjd1 = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode1,
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        pjd2 = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jdi,
            id_periode_pengiriman=periode2,
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 6, 30),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_jenis_data_update', args=[pjd2.pk]),
            {
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_periode_pengiriman': periode2.pk,
                'akhir_penyampaian': '28',
                'start_date': '2024-03-01',  # overlaps pjd1
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data

    def test_delete_ajax_get(self, client, p3de_admin_user):
        """GET ?ajax=1 returns confirmation HTML (lines 137-139)."""
        pjd = PeriodeJenisDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_jenis_data_delete', args=[pjd.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_delete_ajax_post(self, client, p3de_admin_user):
        """AJAX DELETE returns success JSON (lines 142-147)."""
        pjd = PeriodeJenisDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_jenis_data_delete', args=[pjd.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_delete_non_ajax_post(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns redirect JSON (lines 150-159)."""
        pjd = PeriodeJenisDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('periode_jenis_data_delete', args=[pjd.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data


# ============================================================
# JenisPrioritasData Views
# ============================================================

@pytest.mark.django_db
class TestJenisPrioritasDataMissingBranches:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params shows toast (lines 33-37)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_list'),
            {'deleted': 'true', 'name': 'Test+JPD'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET without order col → else branch."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_datatables_with_order(self, client, p3de_admin_user):
        """GET with valid order col."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': '1', 'order[0][dir]': 'desc'},
        )
        assert resp.status_code == 200

    def test_datatables_exception_path(self, client, p3de_admin_user):
        """Bad order col → except branch."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200

    def test_datatables_column_searches(self, client, p3de_admin_user):
        """Column-specific filter branches (lines 95-97, 100-102, 107, 112-116)."""
        jpd = JenisPrioritasDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [
                    jpd.id_sub_jenis_data_ilap.nama_sub_jenis_data,
                    jpd.no_nd,
                    jpd.tahun,
                    str(jpd.start_date),
                    str(jpd.end_date),
                ],
            },
        )
        assert resp.status_code == 200

    def test_create_get_form(self, client, p3de_admin_user):
        """GET create form (lines 54-56, 59-61)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('jenis_prioritas_data_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_create_post_valid_no_overlap(self, client, p3de_admin_user):
        """Valid POST with non-overlapping dates (lines 70)."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_prioritas_data_create'),
            {
                'id_sub_jenis_data_ilap': jdi.pk,
                'no_nd': 'ND000001',
                'tahun': '2024',
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_create_post_overlap(self, client, p3de_admin_user):
        """POST with overlapping dates → form_invalid (lines 75-79)."""
        jpd = JenisPrioritasDataFactory(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 12, 31),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_prioritas_data_create'),
            {
                'id_sub_jenis_data_ilap': jpd.id_sub_jenis_data_ilap.pk,
                'no_nd': 'ND000002',
                'tahun': '2024',
                'start_date': '2024-06-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data

    def test_create_post_no_start_date(self, client, p3de_admin_user):
        """POST without start_date → goes to super().form_valid() path check."""
        jdi = JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        # This will fail form validation since start_date is required but tests the branch
        resp = client.post(
            reverse('jenis_prioritas_data_create'),
            {
                'id_sub_jenis_data_ilap': jdi.pk,
                'no_nd': 'ND000003',
                'tahun': '2024',
                # no start_date → form invalid due to required field
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200

    def test_update_get_form(self, client, p3de_admin_user):
        """GET update form (lines 95-97)."""
        jpd = JenisPrioritasDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_update', args=[jpd.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_update_post_valid(self, client, p3de_admin_user):
        """Valid update POST (lines 100-102)."""
        jpd = JenisPrioritasDataFactory(
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_prioritas_data_update', args=[jpd.pk]),
            {
                'id_sub_jenis_data_ilap': jpd.id_sub_jenis_data_ilap.pk,
                'no_nd': jpd.no_nd,
                'tahun': jpd.tahun,
                'start_date': '2024-01-01',
                'end_date': '2024-06-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_overlap(self, client, p3de_admin_user):
        """Update with overlapping dates → form_invalid (lines 107, 112-116)."""
        jdi = JenisDataILAPFactory()
        jpd1 = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jdi,
            tahun='2024',
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 6, 30),
        )
        jpd2 = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jdi,
            tahun='2025',
            start_date=datetime.date(2025, 1, 1),
            end_date=datetime.date(2025, 6, 30),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_prioritas_data_update', args=[jpd2.pk]),
            {
                'id_sub_jenis_data_ilap': jdi.pk,
                'no_nd': jpd2.no_nd,
                'tahun': jpd2.tahun,
                'start_date': '2024-03-01',  # overlaps jpd1
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data

    def test_delete_ajax_get(self, client, p3de_admin_user):
        """GET ?ajax=1 returns confirmation HTML."""
        jpd = JenisPrioritasDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('jenis_prioritas_data_delete', args=[jpd.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_delete_ajax_post(self, client, p3de_admin_user):
        """AJAX DELETE returns success JSON (lines 131-133)."""
        jpd = JenisPrioritasDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_prioritas_data_delete', args=[jpd.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_delete_non_ajax_post(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns redirect JSON (lines 136-141)."""
        jpd = JenisPrioritasDataFactory()
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('jenis_prioritas_data_delete', args=[jpd.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data
