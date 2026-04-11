"""Tests for tiket/list.py – TiketListView and tiket_data endpoint."""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models import TiketPIC
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory, PeriodePengirimanFactory,
    ILAPFactory, KategoriILAPFactory, KategoriWilayahFactory,
    JenisDataILAPFactory, PeriodeJenisDataFactory, JenisPrioritasDataFactory,
    PICFactory, DurasiJatuhTempoFactory, KanwilFactory, KPPFactory,
    BentukDataFactory, CaraPenyampaianFactory,
)


# ============================================================
# TiketListView
# ============================================================

@pytest.mark.django_db
class TestTiketListView:
    """Tests for TiketListView."""

    def test_requires_login(self, client):
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code in (302, 403)

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200

    def test_p3de_user_with_pic_can_access(self, client, authenticated_user, tiket):
        """user_p3de with active TiketPIC can access."""
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200

    def test_p3de_user_without_pic_can_access(self, client, authenticated_user):
        """user_p3de without TiketPIC can still access tiket list (any user_p3de is allowed)."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200

    def test_pide_user_can_access(self, client, pide_user):
        """user_pide can access tiket list."""
        client.force_login(pide_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200

    def test_pmde_user_can_access(self, client, pmde_user):
        """user_pmde can access tiket list."""
        client.force_login(pmde_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200

    def test_p3de_admin_user_can_access(self, client, p3de_admin_user):
        """admin_p3de can access tiket list."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('tiket_list'))
        assert resp.status_code == 200


# ============================================================
# tiket_data endpoint
# ============================================================

@pytest.mark.django_db
class TestTiketDataEndpoint:
    """Tests for tiket_data DataTables endpoint."""

    def test_requires_login(self, client):
        resp = client.get(reverse('tiket_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code in (302, 403)

    def test_admin_basic_fetch(self, client, admin_user, tiket):
        """Admin can fetch tiket data with basic params."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'draw' in data
        assert 'data' in data
        assert data['draw'] == 1

    def test_non_admin_only_sees_own_tikets(self, client, authenticated_user, tiket):
        """Non-admin user only sees tikets where they are TiketPIC."""
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] >= 1

    def test_get_filter_options(self, client, admin_user, tiket):
        """Filter options endpoint returns expected keys."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data
        opts = data['filter_options']
        assert 'tahun' in opts
        assert 'status' in opts
        assert 'kategori_ilap' in opts
        assert 'ilap' in opts
        assert 'jenis_data' in opts
        assert 'sub_jenis_data' in opts
        assert 'periode' in opts
        assert 'kanwil' in opts
        assert 'kpp' in opts
        assert 'kategori_wilayah' in opts
        assert 'jenis_tabel' in opts
        assert 'dasar_hukum' in opts

    def test_get_filter_options_with_tahun_filter(self, client, admin_user, tiket):
        """Filter options with tahun param."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
            'tahun': str(tiket.tahun),
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data

    def test_get_filter_options_with_kategori_ilap_filter(self, client, admin_user, tiket):
        """Filter options with kategori_ilap param."""
        client.force_login(admin_user)
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        kategori_id = ilap.id_kategori.id
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
            'kategori_ilap': str(kategori_id),
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data

    def test_get_filter_options_with_ilap_filter(self, client, admin_user, tiket):
        """Filter options with ilap param."""
        client.force_login(admin_user)
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
            'ilap': str(ilap.id),
        })
        assert resp.status_code == 200

    def test_filter_by_nomor_tiket(self, client, admin_user, tiket):
        """Filter tiket by nomor_tiket."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'nomor_tiket': tiket.nomor_tiket,
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] >= 1

    def test_filter_by_tahun(self, client, admin_user, tiket):
        """Filter tiket by tahun."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'tahun': str(tiket.tahun),
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] >= 1

    def test_filter_by_status(self, client, admin_user, tiket):
        """Filter tiket by status."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'status': str(tiket.status_tiket),
        })
        assert resp.status_code == 200

    def test_filter_by_invalid_tahun(self, client, admin_user):
        """Invalid tahun value returns empty results."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'tahun': 'invalid',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 0

    def test_filter_by_invalid_status(self, client, admin_user):
        """Invalid status value returns empty results."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'status': 'invalid',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 0

    def test_filter_by_periode_bulanan(self, client, admin_user, tiket):
        """Filter tiket by periode with bulanan type."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'periode': f'bulanan:{tiket.periode}',
        })
        assert resp.status_code == 200

    def test_filter_by_periode_triwulanan(self, client, admin_user, tiket):
        """Filter tiket by periode with triwulanan type."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'periode': 'triwulanan:1',
        })
        assert resp.status_code == 200

    def test_filter_by_periode_invalid(self, client, admin_user):
        """Invalid periode value returns empty results."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'periode': 'bulanan:invalid',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] == 0

    def test_filter_by_kategori_ilap(self, client, admin_user, tiket):
        """Filter tiket by kategori ilap id."""
        client.force_login(admin_user)
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'kategori_ilap': str(ilap.id_kategori.id),
        })
        assert resp.status_code == 200

    def test_filter_by_ilap(self, client, admin_user, tiket):
        """Filter tiket by ilap id."""
        client.force_login(admin_user)
        ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'ilap': str(ilap.id),
        })
        assert resp.status_code == 200

    def test_filter_by_jenis_data(self, client, admin_user, tiket):
        """Filter tiket by jenis_data."""
        client.force_login(admin_user)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap.id_jenis_data
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'jenis_data': jenis_data,
        })
        assert resp.status_code == 200

    def test_filter_by_sub_jenis_data(self, client, admin_user, tiket):
        """Filter tiket by sub_jenis_data."""
        client.force_login(admin_user)
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'sub_jenis_data': sub_jenis_data,
        })
        assert resp.status_code == 200

    def test_filter_by_pic_p3de(self, client, admin_user, tiket, authenticated_user):
        """Filter tiket by pic_p3de user id."""
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'pic_p3de': str(authenticated_user.id),
        })
        assert resp.status_code == 200

    def test_filter_by_pic_pide(self, client, admin_user, tiket, pide_user):
        """Filter tiket by pic_pide user id."""
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'pic_pide': str(pide_user.id),
        })
        assert resp.status_code == 200

    def test_filter_by_pic_pmde(self, client, admin_user, tiket, pmde_user):
        """Filter tiket by pic_pmde user id."""
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user,
                        role=TiketPIC.Role.PMDE, active=True)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'pic_pmde': str(pmde_user.id),
        })
        assert resp.status_code == 200

    def test_filter_by_periode_pengiriman(self, client, admin_user, tiket):
        """Filter tiket by periode_pengiriman."""
        client.force_login(admin_user)
        periode_penyampaian = tiket.id_periode_data.id_periode_pengiriman.periode_penyampaian
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'periode_pengiriman': periode_penyampaian,
        })
        assert resp.status_code == 200

    def test_filter_by_periode_penerimaan(self, client, admin_user, tiket):
        """Filter tiket by periode_penerimaan."""
        client.force_login(admin_user)
        periode_penerimaan = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'periode_penerimaan': periode_penerimaan,
        })
        assert resp.status_code == 200

    def test_ordering_ascending(self, client, admin_user, tiket):
        """Ordering by column ascending."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '1',
            'order[0][dir]': 'asc',
        })
        assert resp.status_code == 200

    def test_ordering_descending(self, client, admin_user, tiket):
        """Ordering by column descending."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0',
            'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_filter_terlambat_ya(self, client, admin_user, tiket):
        """Filter tiket yang terlambat (Ya)."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'terlambat': 'Ya',
        })
        assert resp.status_code == 200

    def test_filter_terlambat_tidak(self, client, admin_user, tiket):
        """Filter tiket yang tidak terlambat (Tidak)."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'terlambat': 'Tidak',
        })
        assert resp.status_code == 200

    def test_filter_options_pic_p3de_with_pic(self, client, admin_user, tiket, authenticated_user):
        """Filter options includes PIC P3DE when assigned."""
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
        })
        assert resp.status_code == 200

    def test_get_filter_options_with_jenis_data_filter(self, client, admin_user, tiket):
        """Filter options with jenis_data param returns sub_jenis_data options."""
        client.force_login(admin_user)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap.id_jenis_data
        resp = client.get(reverse('tiket_data'), {
            'get_filter_options': '1',
            'jenis_data': jenis_data,
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'filter_options' in data
