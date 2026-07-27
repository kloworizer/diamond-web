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
    PICFactory,
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


def _bundle(periode_penerimaan, extra_tikets=0, start_date=None, end_date=None,
            tiket_year=None):
    """Create an ILAP with one sub jenis data, one periode and optional tikets."""
    current_year = datetime.now().year
    ilap = ILAPFactory()
    jenis_data = JenisDataILAPFactory(id_ilap=ilap)
    # periode_penyampaian is unique and may already exist as seeded
    # reference data, so fetch-or-create rather than forcing a fresh row.
    periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
        periode_penyampaian=periode_penerimaan,
        defaults={'periode_penerimaan': periode_penerimaan},
    )
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=periode_pengiriman,
        start_date=start_date or date(current_year - 1, 1, 1),
        end_date=end_date,
    )
    dasar_hukum = DasarHukum.objects.create(deskripsi='DH Profil', kategori='PKS')
    KlasifikasiJenisData.objects.create(id_sub_jenis_data=jenis_data, id_klasifikasi_tabel=dasar_hukum)
    for _ in range(extra_tikets):
        TiketFactory(
            id_periode_data=periode_data,
            tahun=tiket_year or current_year,
            periode=1,
        )
    return ilap, jenis_data


@pytest.mark.django_db
class TestProfilILAPDetailView:
    def test_get_denied_without_p3de_group(self, client):
        ilap = ILAPFactory()
        client.force_login(UserFactory())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.status_code in (302, 403)

    def test_detail_is_looked_up_by_id_ilap(self, client):
        ilap, _ = _bundle('Bulanan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.status_code == 200
        assert resp.context['ilap'] == ilap

    def test_detail_unknown_id_ilap_returns_404(self, client):
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=['ZZ999']))
        assert resp.status_code == 404

    def test_detail_bulanan_periode(self, client):
        ilap, jenis_data = _bundle('Bulanan', extra_tikets=2)
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.status_code == 200
        details = resp.context['jenis_data_details']
        assert len(details) == 1
        assert details[0]['jenis_data'] == jenis_data
        assert 'DH Profil' in details[0]['dasar_hukum']
        assert details[0]['periode_label'] == 'Bulanan - Bulanan'
        current_year = datetime.now().year
        assert details[0]['year_data'][current_year]['label'] == '2/12'

    @pytest.mark.parametrize('periode_penerimaan,total', [
        ('Bulanan', 12),
        ('Triwulanan', 4),
        ('Semesteran', 2),
        ('Tahunan', 1),
    ])
    def test_detail_periode_penerimaan_drives_the_denominator(self, client, periode_penerimaan, total):
        ilap, _ = _bundle(periode_penerimaan, extra_tikets=1)
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        current_year = datetime.now().year
        cell = resp.context['jenis_data_details'][0]['year_data'][current_year]
        assert cell == {'count': 1, 'total': total, 'label': f'1/{total}', 'complete': 1 >= total}

    def test_detail_unknown_periode_type_defaults_to_monthly(self, client):
        ilap, _ = _bundle('Mingguan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        current_year = datetime.now().year
        assert resp.context['jenis_data_details'][0]['year_data'][current_year]['total'] == 12

    def test_detail_jenis_data_without_periode_is_skipped(self, client):
        """A JenisDataILAP with no PeriodeJenisData is excluded from the details list."""
        ilap = ILAPFactory()
        JenisDataILAPFactory(id_ilap=ilap)
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.context['jenis_data_details'] == []
        assert resp.context['years'] == []

    def test_years_run_from_start_date_to_current_year_when_open(self, client):
        current_year = datetime.now().year
        ilap, _ = _bundle('Bulanan', start_date=date(current_year - 2, 3, 1))
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        expected = [current_year - 2, current_year - 1, current_year]
        assert resp.context['years'] == expected
        assert resp.context['jenis_data_details'][0]['years'] == expected

    def test_years_stop_at_end_date_year(self, client):
        current_year = datetime.now().year
        ilap, _ = _bundle(
            'Bulanan',
            start_date=date(current_year - 3, 1, 1),
            end_date=date(current_year - 2, 12, 31),
        )
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.context['years'] == [current_year - 3, current_year - 2]

    def test_years_header_is_the_union_across_rows(self, client):
        """Rows with different start dates share one header spanning every year."""
        current_year = datetime.now().year
        ilap, _ = _bundle('Bulanan', start_date=date(current_year - 2, 1, 1))
        other = JenisDataILAPFactory(id_ilap=ilap)
        periode_pengiriman, _created = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian='Tahunan', defaults={'periode_penerimaan': 'Tahunan'},
        )
        PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=other,
            id_periode_pengiriman=periode_pengiriman,
            start_date=date(current_year, 1, 1),
            end_date=None,
        )
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        assert resp.context['years'] == [current_year - 2, current_year - 1, current_year]
        details = {d['jenis_data'].pk: d for d in resp.context['jenis_data_details']}
        assert details[other.pk]['years'] == [current_year]

    def test_sub_jenis_data_id_links_to_its_own_page(self, client):
        ilap, jenis_data = _bundle('Bulanan')
        client.force_login(_p3de_user())
        resp = client.get(reverse('profil_ilap_detail', args=[ilap.id_ilap]))
        expected = reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data])
        assert expected in resp.content.decode()


@pytest.mark.django_db
class TestJenisDataILAPProfilView:
    def test_get_denied_without_p3de_group(self, client):
        _, jenis_data = _bundle('Bulanan')
        client.force_login(UserFactory())
        resp = client.get(reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]))
        assert resp.status_code in (302, 403)

    def test_unknown_sub_jenis_data_returns_404(self, client):
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_profil', args=['ZZZ999999']))
        assert resp.status_code == 404

    def test_detail_context(self, client):
        _, jenis_data = _bundle('Bulanan', extra_tikets=3)
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]))
        assert resp.status_code == 200
        assert resp.context['jenis_data'] == jenis_data
        assert resp.context['tiket_total'] == 3
        assert [d.deskripsi for d in resp.context['dasar_hukum_list']] == ['DH Profil']
        assert len(resp.context['periode_list']) == 1
        current_year = datetime.now().year
        assert resp.context['summary']['year_data'][current_year]['label'] == '3/12'

    def test_pic_groups_cover_every_tipe(self, client):
        _, jenis_data = _bundle('Bulanan')
        pic = PICFactory(
            tipe='PIDE', id_sub_jenis_data_ilap=jenis_data, end_date=None,
        )
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]))
        groups = {g['tipe']: g for g in resp.context['pic_groups']}
        assert set(groups) == {'P3DE', 'PIDE', 'PMDE'}
        assert groups['PIDE']['pics'] == [pic]
        assert groups['P3DE']['pics'] == []

    def test_sub_jenis_data_without_periode_renders_empty_summary(self, client):
        jenis_data = JenisDataILAPFactory()
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]))
        assert resp.status_code == 200
        assert resp.context['summary'] is None
        assert resp.context['years'] == []
        assert resp.context['periode_list'] == []


@pytest.mark.django_db
class TestJenisDataILAPTiketData:
    """Server-side DataTables endpoint backing the Daftar Tiket table."""

    def test_denied_without_p3de_group(self, client):
        _, jenis_data = _bundle('Bulanan')
        client.force_login(UserFactory())
        resp = client.get(reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data]))
        assert resp.status_code in (302, 403)

    def test_unknown_sub_jenis_data_returns_404(self, client):
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_tiket_data', args=['ZZZ999999']))
        assert resp.status_code == 404

    def test_rows_are_paginated_and_sorted_by_nomor_tiket(self, client):
        _, jenis_data = _bundle('Bulanan', extra_tikets=4)
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data]),
            {'draw': '3', 'start': '0', 'length': '2'},
        )
        payload = resp.json()
        assert payload['draw'] == 3
        assert payload['recordsTotal'] == 4
        assert payload['recordsFiltered'] == 4
        nomors = [row['nomor_tiket'] for row in payload['data']]
        assert len(nomors) == 2
        assert nomors == sorted(nomors)

    def test_row_shape(self, client):
        _, jenis_data = _bundle('Bulanan', extra_tikets=1)
        client.force_login(_p3de_user())
        resp = client.get(reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data]))
        row = resp.json()['data'][0]
        assert set(row) == {
            'nomor_tiket', 'periode', 'tahun', 'status', 'tgl_terima_dip', 'actions',
        }
        assert 'Direkam' in row['status']
        assert '/tiket/' in row['actions']

    def test_search_matches_status_label(self, client):
        _, jenis_data = _bundle('Bulanan', extra_tikets=2)
        client.force_login(_p3de_user())
        url = reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data])
        assert client.get(url, {'search[value]': 'Direkam'}).json()['recordsFiltered'] == 2
        assert client.get(url, {'search[value]': 'Dibatalkan'}).json()['recordsFiltered'] == 0

    def test_search_matches_nomor_tiket(self, client):
        _, jenis_data = _bundle('Bulanan', extra_tikets=2)
        client.force_login(_p3de_user())
        url = reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data])
        target = client.get(url).json()['data'][0]['nomor_tiket']
        payload = client.get(url, {'search[value]': target}).json()
        assert payload['recordsTotal'] == 2
        assert payload['recordsFiltered'] == 1

    def test_ordering_by_column_index(self, client):
        current_year = datetime.now().year
        _, jenis_data = _bundle('Bulanan', extra_tikets=2, tiket_year=current_year)
        TiketFactory(
            id_periode_data=jenis_data.periodejenisdata_set.first(),
            tahun=current_year - 1,
            periode=1,
        )
        client.force_login(_p3de_user())
        resp = client.get(
            reverse('jenis_data_ilap_tiket_data', args=[jenis_data.id_sub_jenis_data]),
            {'order[0][column]': '2', 'order[0][dir]': 'desc'},
        )
        tahuns = [row['tahun'] for row in resp.json()['data']]
        assert tahuns == sorted(tahuns, reverse=True)


@pytest.mark.django_db
class TestNavbarSearch:
    """Header search resolver for ID ILAP and ID sub jenis data."""

    def test_login_required(self, client):
        resp = client.get(reverse('navbar_search'), {'q': 'BI001'})
        assert resp.status_code == 302

    def test_resolves_id_ilap(self, client):
        ilap = ILAPFactory()
        client.force_login(_p3de_user())
        payload = client.get(reverse('navbar_search'), {'q': ilap.id_ilap}).json()
        assert payload['match'] == 'ilap'
        assert payload['url'] == reverse('profil_ilap_detail', args=[ilap.id_ilap])
        assert ilap.nama_ilap in payload['label']

    def test_resolves_id_sub_jenis_data(self, client):
        jenis_data = JenisDataILAPFactory()
        client.force_login(_p3de_user())
        payload = client.get(reverse('navbar_search'), {'q': jenis_data.id_sub_jenis_data}).json()
        assert payload['match'] == 'jenis_data'
        assert payload['url'] == reverse(
            'jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]
        )

    def test_match_is_case_insensitive(self, client):
        """The stored casing is what gets linked, so the detail URL still resolves."""
        ilap = ILAPFactory(id_ilap='xy001')
        client.force_login(_p3de_user())
        payload = client.get(reverse('navbar_search'), {'q': 'XY001'}).json()
        assert payload['url'] == reverse('profil_ilap_detail', args=['xy001'])
        assert client.get(payload['url']).context['ilap'] == ilap

    @pytest.mark.parametrize('term', ['', '   ', 'tidak-ada'])
    def test_no_match_returns_null(self, client, term):
        client.force_login(_p3de_user())
        assert client.get(reverse('navbar_search'), {'q': term}).json() == {'match': None}

    def test_users_without_profil_ilap_access_get_no_match(self, client):
        """Non-P3DE users fall through to the nomor tiket search instead of a 403."""
        ilap = ILAPFactory()
        client.force_login(UserFactory())
        assert client.get(reverse('navbar_search'), {'q': ilap.id_ilap}).json() == {'match': None}
