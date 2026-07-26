"""Tests for views/profil_ilap.py (list DataTables endpoint + detail view)."""
from datetime import date, datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import DasarHukum, KlasifikasiJenisData, PeriodePengiriman
from diamond_web.tests.conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    KategoriILAPFactory,
    KategoriWilayahFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    TiketFactory,
    UserFactory,
)


def _p3de_user():
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    return user


@pytest.mark.django_db
class TestProfilILAPListView:
    def test_get_denied_without_p3de_group(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('profil_ilap_list'))
        assert resp.status_code in (302, 403)

    def test_get_html(self, client):
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_list'))
        assert resp.status_code == 200
        assert 'text/html' in resp.get('Content-Type', '')

    def test_get_json_via_ajax_header(self, client):
        ilap = ILAPFactory(nama_ilap='Unique ILAP AJAX')
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('profil_ilap_list'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['recordsTotal'] >= 1
        assert any(row['nama'] == ilap.nama_ilap for row in payload['data'])

    def test_get_json_via_format_param(self, client):
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_list'), {'format': 'json'})
        assert resp.status_code == 200
        assert 'draw' in resp.json()

    def test_global_search(self, client):
        ilap = ILAPFactory(nama_ilap='Searchable ILAP XYZ')
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('profil_ilap_list'), {'format': 'json', 'search[value]': 'Searchable ILAP XYZ'}
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1
        assert payload['data'][0]['nama'] == ilap.nama_ilap

    @pytest.mark.parametrize('col_idx', [0, 1, 2, 3])
    def test_column_search(self, client, col_idx):
        kategori = KategoriILAPFactory(nama_kategori='UniqueKategoriX')
        wilayah = KategoriWilayahFactory(deskripsi='UniqueWilayahX')
        ilap = ILAPFactory(id_ilap='9', id_kategori=kategori, id_kategori_wilayah=wilayah,
                            nama_ilap='UniqueNamaX')
        search_values = {0: '9', 1: 'UniqueKategoriX', 2: 'UniqueNamaX', 3: 'UniqueWilayahX'}
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('profil_ilap_list'),
            {'format': 'json', f'columns[{col_idx}][search][value]': search_values[col_idx]},
        )
        payload = resp.json()
        assert any(row['nama'] == ilap.nama_ilap for row in payload['data'])

    @pytest.mark.parametrize('order_col,order_dir', [(0, 'asc'), (1, 'desc'), (2, 'asc'), (3, 'desc')])
    def test_ordering(self, client, order_col, order_dir):
        ILAPFactory()
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('profil_ilap_list'),
            {'format': 'json', 'order[0][column]': str(order_col), 'order[0][dir]': order_dir},
        )
        assert resp.status_code == 200

    def test_pagination(self, client):
        for _ in range(3):
            ILAPFactory()
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('profil_ilap_list'),
            {'format': 'json', 'draw': '5', 'start': '0', 'length': '2'},
        )
        payload = resp.json()
        assert payload['draw'] == 5
        assert len(payload['data']) <= 2
        assert 'actions' in payload['data'][0]


@pytest.mark.django_db
class TestProfilILAPDetailView:
    def test_get_denied_without_p3de_group(self, client):
        ilap = ILAPFactory()
        client.force_login(UserFactory())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert resp.status_code in (302, 403)

    def _bundle(self, periode_penyampaian, extra_tikets=0):
        ilap = ILAPFactory()
        jenis_data = JenisDataILAPFactory(id_ilap=ilap)
        # periode_penyampaian is unique and may already exist as seeded
        # reference data, so fetch-or-create rather than forcing a fresh row.
        periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=periode_penyampaian,
            defaults={'periode_penerimaan': periode_penyampaian},
        )
        periode_data = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman=periode_pengiriman,
        )
        dasar_hukum = DasarHukum.objects.create(deskripsi='DH Profil', kategori='PKS')
        KlasifikasiJenisData.objects.create(id_sub_jenis_data=jenis_data, id_klasifikasi_tabel=dasar_hukum)
        current_year = datetime.now().year
        for _ in range(extra_tikets):
            TiketFactory(id_periode_data=periode_data, tahun=current_year, periode=1)
        return ilap, jenis_data

    def test_detail_bulanan_periode(self, client):
        ilap, jenis_data = self._bundle('Bulanan', extra_tikets=2)
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert resp.status_code == 200
        details = resp.context['jenis_data_details']
        assert len(details) == 1
        assert details[0]['jenis_data'] == jenis_data
        assert 'DH Profil' in details[0]['dasar_hukum']
        current_year = datetime.now().year
        assert '/' in details[0]['year_data'][current_year]

    def test_detail_triwulan_periode(self, client):
        ilap, _ = self._bundle('Triwulan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert resp.status_code == 200
        assert len(resp.context['jenis_data_details']) == 1

    def test_detail_semester_periode(self, client):
        ilap, _ = self._bundle('Semester')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert len(resp.context['jenis_data_details']) == 1

    def test_detail_tahunan_periode(self, client):
        ilap, _ = self._bundle('Tahunan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert len(resp.context['jenis_data_details']) == 1

    def test_detail_unknown_periode_type_defaults_to_monthly(self, client):
        ilap, _ = self._bundle('Mingguan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert len(resp.context['jenis_data_details']) == 1

    def test_detail_jenis_data_without_periode_is_skipped(self, client):
        """A JenisDataILAP with no PeriodeJenisData is excluded from the details list."""
        ilap = ILAPFactory()
        JenisDataILAPFactory(id_ilap=ilap)
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        assert resp.context['jenis_data_details'] == []

    def test_detail_years_context(self, client):
        ilap, _ = self._bundle('Bulanan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.pk]))
        current_year = datetime.now().year
        assert resp.context['years'] == [
            current_year - 2, current_year - 1, current_year, current_year + 1
        ]
