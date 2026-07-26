"""Tests for laporan_detail_himpun_olah_data.py (view + data endpoint + export)."""
import pytest
from django.urls import reverse

from diamond_web.models import KlasifikasiJenisData
from diamond_web.tests.conftest import UserFactory
from diamond_web.tests.test_remaining_coverage_gaps import _make_bundle


def _pmde_admin_user():
    return UserFactory(is_superuser=True)


@pytest.mark.django_db
class TestLaporanDetailHimpunOlahDataView:
    def test_get_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('laporan_detail_himpun_olah_data'))
        assert resp.status_code == 403

    def test_get_success_with_filter_options(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_detail_himpun_olah_data'))
        assert resp.status_code == 200
        ilap_ids = [row['id'] for row in resp.context['filter_options']['ilap']]
        assert bundle['ilap'].id in ilap_ids


@pytest.mark.django_db
class TestLaporanDetailHimpunOlahDataDataEndpoint:
    url = 'laporan_detail_himpun_olah_data_data'

    def test_data_endpoint_basic(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        # Filter to just this ILAP - unfiltered results are dominated by
        # seeded reference JenisDataILAP rows ahead of this one in default
        # (unordered) pagination.
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'nama_ilap': str(bundle['ilap'].id)},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['draw'] == 1
        assert payload['recordsTotal'] >= 1
        row = next(
            r for r in payload['data']
            if r['nama_sub_jenis_data'] == bundle['jenis_data'].nama_sub_jenis_data
        )
        assert row['nama_ilap'] == bundle['ilap'].nama_ilap
        assert row['nama_jenis_data'] == bundle['jenis_data'].nama_jenis_data
        assert 'Dasar Hukum A' in row['dasar_hukum']
        assert row['periode_pengiriman']

    def test_data_endpoint_post_method(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.post(reverse(self.url), {'draw': '2', 'start': '0', 'length': '10'})
        assert resp.json()['draw'] == 2

    def test_data_endpoint_invalid_pagination_defaults(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': 'x', 'start': 'y', 'length': 'z'},
        )
        assert resp.json()['draw'] == 1

    def test_data_endpoint_filter_by_kategori_ilap(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'kategori_ilap': str(bundle['ilap'].id_kategori_id)},
        )
        assert resp.json()['recordsFiltered'] >= 1

    def test_data_endpoint_filter_by_nama_ilap(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'nama_ilap': str(bundle['ilap'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_dasar_hukum(self, client):
        bundle = _make_bundle()
        dasar_hukum = KlasifikasiJenisData.objects.get(
            id_sub_jenis_data=bundle['jenis_data']
        ).id_klasifikasi_tabel
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'dasar_hukum': str(dasar_hukum.id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_jenis_data(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'jenis_data': str(bundle['jenis_data'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_periode(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'periode': str(bundle['periode_data'].id_periode_pengiriman_id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_nama_tabel(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'nama_tabel': str(bundle['jenis_data'].id_jenis_tabel_id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_data_endpoint_filters_ignore_all_and_empty(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {
                # length large enough to include this record regardless of
                # how many seeded reference rows sort ahead of it.
                'draw': '1', 'start': '0', 'length': '10000',
                'kategori_ilap': 'all', 'nama_ilap': '', 'dasar_hukum': 'all',
                'jenis_data': '', 'periode': 'all', 'nama_tabel': '',
            },
        )
        payload = resp.json()
        assert any(
            r['nama_sub_jenis_data'] == bundle['jenis_data'].nama_sub_jenis_data
            for r in payload['data']
        )

    def test_data_endpoint_jenis_data_without_klasifikasi_or_periode(self, client):
        """A JenisDataILAP with no classification/periode still serializes cleanly."""
        from diamond_web.tests.conftest import JenisDataILAPFactory
        jenis_data = JenisDataILAPFactory()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'jenis_data': str(jenis_data.id)},
        )
        payload = resp.json()
        row = payload['data'][0]
        assert row['klasifikasi'] == ''
        assert row['dasar_hukum'] == ''
        assert row['periode_pengiriman'] == ''

    def test_data_endpoint_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestLaporanDetailHimpunOlahDataExport:
    url = 'laporan_detail_himpun_olah_data_export'

    def test_export_excel_default(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')
        assert '.xlsx' in resp['Content-Disposition']

    def test_export_excel_explicit(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url), {'format': 'excel'})
        assert resp.status_code == 200

    def test_export_pdf_falls_back_to_excel(self, client):
        """_export_detail_to_pdf is a stub that falls back to Excel."""
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url), {'format': 'pdf'})
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')

    def test_export_invalid_format_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url), {'format': 'csv'})
        assert resp.status_code == 400

    def test_export_post_method(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.post(reverse(self.url), {'format': 'excel'})
        assert resp.status_code == 200

    def test_export_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302
