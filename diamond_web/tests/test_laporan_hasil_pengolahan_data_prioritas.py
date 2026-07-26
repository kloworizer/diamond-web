"""Tests for laporan_hasil_pengolahan_data_prioritas.py (view + data + export)."""
from datetime import datetime

import pytest
from django.urls import reverse

from diamond_web.constants.jenis_tabel import (
    JENIS_TABEL_DIIDENTIFIKASI,
    JENIS_TABEL_TIDAK_DIIDENTIFIKASI,
)
from diamond_web.models.jenis_tabel import JenisTabel
from diamond_web.tests.conftest import (
    TiketFactory,
    UserFactory,
)
from diamond_web.tests.test_remaining_coverage_gaps import _make_bundle


def _pmde_admin_user():
    return UserFactory(is_superuser=True)


def _tiket_with_transfer(jenis_tabel_id=None, tgl_kirim_pide=None, **extra):
    bundle = _make_bundle()
    tiket = bundle['tiket']
    if jenis_tabel_id is not None:
        # These ids are seeded as fixed reference rows (DB_SEED_ENABLED=1
        # migrations may already have created them), so fetch-or-create
        # rather than forcing a fresh row that would collide on the PK.
        jenis_tabel, _ = JenisTabel.objects.get_or_create(
            id=jenis_tabel_id,
            defaults={'deskripsi': f'JenisTabel_{jenis_tabel_id}'},
        )
        bundle['jenis_data'].id_jenis_tabel = jenis_tabel
        bundle['jenis_data'].save(update_fields=['id_jenis_tabel'])
    if tgl_kirim_pide is not None:
        tiket.tgl_kirim_pide = tgl_kirim_pide
    for field, value in extra.items():
        setattr(tiket, field, value)
    tiket.save()
    return tiket


@pytest.mark.django_db
class TestLaporanHasilPengolahanDataPrioritasView:
    def test_get_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('laporan_hasil_pengolahan_data_prioritas'))
        assert resp.status_code == 403

    def test_get_success_includes_years_and_form(self, client):
        _tiket_with_transfer(tahun=2020)
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('laporan_hasil_pengolahan_data_prioritas'))
        assert resp.status_code == 200
        assert 2020 in resp.context['years']
        assert datetime.now().year in resp.context['years']
        assert resp.context['form'] is not None


@pytest.mark.django_db
class TestLaporanHasilPengolahanDataPrioritasDataEndpoint:
    url = 'laporan_hasil_pengolahan_data_prioritas_data'

    def test_missing_required_params_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload == {'draw': 1, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []}

    def test_invalid_tahun_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': 'abc'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_bulanan_filter(self, client):
        tiket = _tiket_with_transfer(
            jenis_tabel_id=JENIS_TABEL_DIIDENTIFIKASI,
            tgl_kirim_pide=datetime(2019, 3, 15),
            tahun=2019,
        )
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': '3', 'tahun': '2019',
             'draw': '1', 'start': '0', 'length': '10'},
        )
        payload = resp.json()
        assert payload['recordsFiltered'] == 1
        row = payload['data'][0]
        assert row['id_tiket'] == tiket.nomor_tiket
        assert row['data_teridentifikasi'] == tiket.baris_i
        assert row['data_belum_diidentifikasi'] == max(
            0, tiket.baris_diterima - (tiket.baris_i + tiket.baris_u)
        )

    def test_bulanan_december_wraps_to_next_year(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 12, 20), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': '12', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_bulanan_invalid_month_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': '13', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_bulanan_non_numeric_periode_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': 'abc', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    @pytest.mark.parametrize('triwulan,month', [(1, 2), (4, 11)])
    def test_triwulanan_filter(self, client, triwulan, month):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, month, 10), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': str(triwulan), 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_triwulanan_invalid_quarter_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': '9', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_triwulanan_non_numeric_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': 'x', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    @pytest.mark.parametrize('semester,month', [(1, 3), (2, 9)])
    def test_semester_filter(self, client, semester, month):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, month, 10), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': str(semester), 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_semester_invalid_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': '3', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_semester_non_numeric_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': 'x', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_tahunan_filter(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 6, 1), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_invalid_periode_type_returns_empty(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'harian', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 0

    def test_jenis_tabel_tidak_diidentifikasi_branch(self, client):
        tiket = _tiket_with_transfer(
            jenis_tabel_id=JENIS_TABEL_TIDAK_DIIDENTIFIKASI,
            tgl_kirim_pide=datetime(2019, 6, 1),
            tahun=2019,
        )
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': '2019'},
        )
        row = resp.json()['data'][0]
        assert row['data_tidak_diidentifikasi'] == tiket.baris_i
        assert row['data_teridentifikasi'] == 0

    def test_post_method(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 6, 1), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.post(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302


@pytest.mark.django_db
class TestLaporanHasilPengolahanDataPrioritasExport:
    url = 'laporan_hasil_pengolahan_data_prioritas_export'

    def test_missing_params_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 400

    def test_invalid_tahun_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': 'x'},
        )
        assert resp.status_code == 400

    def test_bulanan_export_success(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 3, 15), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': '3', 'tahun': '2019'},
        )
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')
        assert 'Maret_2019' in resp['Content-Disposition']

    def test_bulanan_invalid_month_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': '99', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_bulanan_non_numeric_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'bulanan', 'periode': 'x', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_triwulanan_export_success(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 2, 1), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.status_code == 200
        assert 'Triwulan_1_2019' in resp['Content-Disposition']

    def test_triwulanan_invalid_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': '9', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_triwulanan_non_numeric_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'triwulanan', 'periode': 'x', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_semester_export_success(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 8, 1), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': '2', 'tahun': '2019'},
        )
        assert resp.status_code == 200
        assert 'Semester_2_2019' in resp['Content-Disposition']

    def test_semester_invalid_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': '9', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_semester_non_numeric_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'semester', 'periode': 'x', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_tahunan_export_success(self, client):
        _tiket_with_transfer(tgl_kirim_pide=datetime(2019, 5, 1), tahun=2019)
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'tahunan', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.status_code == 200
        assert '2019.xlsx' in resp['Content-Disposition']

    def test_invalid_periode_type_returns_400(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(
            reverse(self.url),
            {'periode_type': 'harian', 'periode': '1', 'tahun': '2019'},
        )
        assert resp.status_code == 400

    def test_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302
