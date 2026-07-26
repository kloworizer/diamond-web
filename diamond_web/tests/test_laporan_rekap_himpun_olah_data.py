"""Tests for laporan_rekap_himpun_olah_data.py (view + data endpoint + export)."""
import pytest
from django.urls import reverse

from diamond_web.models import DasarHukum, KlasifikasiJenisData
from diamond_web.tests.conftest import UserFactory
from diamond_web.tests.test_remaining_coverage_gaps import _make_bundle


def _pmde_admin_user():
    return UserFactory(is_superuser=True)


@pytest.mark.django_db
class TestLaporanRekapHimpunOlahDataView:
    def test_get_denied_for_non_pmde(self, client):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('laporan_rekap_himpun_olah_data'))
        assert resp.status_code == 403

    def test_get_success_with_filter_options(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_rekap_himpun_olah_data'))
        assert resp.status_code == 200
        ilap_ids = [row['id'] for row in resp.context['filter_options']['ilap']]
        assert bundle['ilap'].id in ilap_ids


@pytest.mark.django_db
class TestLaporanRekapHimpunOlahDataDataEndpoint:
    def test_data_endpoint_basic(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['draw'] == 1
        assert payload['recordsTotal'] >= 1
        row = next(r for r in payload['data'] if r['nama_ilap'] == bundle['ilap'].nama_ilap)
        assert row['jenis_data_wajib'] == 1
        assert row['jenis_data_kirim'] == 1
        assert row['jenis_data_tepat_waktu'] == 1
        assert row['jenis_data_lengkap'] == 1
        assert row['jumlah_data_kirim'] == 1
        assert row['jumlah_data_lengkap'] == 1
        assert row['persentase_kirim'] == 100.0

    def test_data_endpoint_post_method(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.post(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '2', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 2

    def test_data_endpoint_invalid_pagination_params_default(self, client):
        """Non-numeric draw/start/length fall back to defaults instead of erroring."""
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': 'abc', 'start': 'xyz', 'length': 'nope'},
        )
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_data_endpoint_filter_by_kategori_ilap(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'kategori_ilap': str(bundle['ilap'].id_kategori_id)},
        )
        payload = resp.json()
        assert any(r['nama_ilap'] == bundle['ilap'].nama_ilap for r in payload['data'])

    def test_data_endpoint_filter_by_nama_ilap(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'nama_ilap': str(bundle['ilap'].id)},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_dasar_hukum(self, client):
        bundle = _make_bundle()
        dasar_hukum = KlasifikasiJenisData.objects.get(
            id_sub_jenis_data=bundle['jenis_data']
        ).id_klasifikasi_tabel
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'dasar_hukum': str(dasar_hukum.id)},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_jenis_data(self, client):
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'jenis_data': str(bundle['jenis_data'].id)},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_periode(self, client):
        bundle = _make_bundle()
        periode_pengiriman_id = bundle['periode_data'].id_periode_pengiriman_id
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'periode': str(periode_pengiriman_id)},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1

    def test_data_endpoint_filter_by_nama_tabel(self, client):
        bundle = _make_bundle()
        jenis_tabel_id = bundle['jenis_data'].id_jenis_tabel_id
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'nama_tabel': str(jenis_tabel_id)},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1

    def test_data_endpoint_filters_ignore_all_and_empty(self, client):
        """'all' and '' filter values are treated as no filter."""
        bundle = _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'kategori_ilap': 'all', 'nama_ilap': '', 'dasar_hukum': 'all',
                'jenis_data': '', 'periode': 'all', 'nama_tabel': '',
            },
        )
        payload = resp.json()
        assert any(r['nama_ilap'] == bundle['ilap'].nama_ilap for r in payload['data'])

    def test_data_endpoint_zero_jenis_data_wajib_gives_zero_percent(self, client):
        """An ILAP with no JenisDataILAP yields 0% instead of dividing by zero."""
        from diamond_web.tests.conftest import ILAPFactory, KategoriILAPFactory
        ilap = ILAPFactory(id_kategori=KategoriILAPFactory())
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse('laporan_rekap_himpun_olah_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'nama_ilap': str(ilap.id)},
        )
        payload = resp.json()
        row = payload['data'][0]
        assert row['jenis_data_wajib'] == 0
        assert row['persentase_kirim'] == 0
        assert row['persentase_tepat_waktu'] == 0
        assert row['persentase_lengkap'] == 0

    def test_data_endpoint_denied_for_non_pmde(self, client):
        """@user_passes_test redirects (not 403) non-PMDE users."""
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_data'))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestLaporanRekapHimpunOlahDataExport:
    def test_export_excel_default(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_export'))
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')
        assert '.xlsx' in resp['Content-Disposition']

    def test_export_excel_explicit(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_export'), {'format': 'excel'})
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')

    def test_export_pdf_falls_back_to_excel_without_reportlab(self, client):
        """reportlab isn't installed in this environment, so pdf falls back to xlsx."""
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_export'), {'format': 'pdf'})
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')

    def test_export_invalid_format_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_export'), {'format': 'csv'})
        assert resp.status_code == 400

    def test_export_post_method(self, client):
        _make_bundle()
        client.force_login(_pmde_admin_user())
        resp = client.post(reverse('laporan_rekap_himpun_olah_data_export'), {'format': 'excel'})
        assert resp.status_code == 200

    def test_export_denied_for_non_pmde(self, client):
        """@user_passes_test redirects (not 403) non-PMDE users."""
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('laporan_rekap_himpun_olah_data_export'))
        assert resp.status_code == 302
