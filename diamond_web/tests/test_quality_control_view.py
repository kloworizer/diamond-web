"""Tests for views/quality_control.py (view + data endpoint)."""
from datetime import date, datetime, timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.constants.tiket_status import STATUS_PENGENDALIAN_MUTU
from diamond_web.models import DasarHukum, KlasifikasiJenisData, TiketPIC
from diamond_web.tests.conftest import (
    DurasiJatuhTempoFactory,
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    JenisTabelFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)


def _pmde_admin_user():
    return UserFactory(is_superuser=True)


def _qc_bundle(with_durasi=True, with_prioritas=False, tgl_transfer=None):
    jenis_tabel = JenisTabelFactory()
    jenis_data = JenisDataILAPFactory(id_jenis_tabel=jenis_tabel)
    periode_data = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
    tgl_transfer = tgl_transfer or datetime.now() - timedelta(days=5)
    tiket = TiketFactory(
        id_periode_data=periode_data,
        status_tiket=STATUS_PENGENDALIAN_MUTU,
        tgl_transfer=tgl_transfer,
        tgl_rematch=tgl_transfer + timedelta(hours=2),
        baris_i=100,
        sudah_qc=40,
        belum_qc=60,
    )
    pmde_user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_pmde')
    pmde_user.groups.add(group)
    TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)

    if with_durasi:
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis_data,
            seksi=group,
            durasi=10,
            start_date=date(2000, 1, 1),
            end_date=None,
        )

    if with_prioritas:
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis_data,
            start_date=(tiket.tgl_terima_dip - timedelta(days=30)).date(),
            end_date=(tiket.tgl_terima_dip + timedelta(days=30)).date(),
        )

    dasar_hukum = DasarHukum.objects.create(deskripsi='DH QC', kategori='PKS')
    KlasifikasiJenisData.objects.create(id_sub_jenis_data=jenis_data, id_klasifikasi_tabel=dasar_hukum)

    return {
        'tiket': tiket,
        'jenis_data': jenis_data,
        'jenis_tabel': jenis_tabel,
        'pmde_user': pmde_user,
        'group': group,
        'dasar_hukum': dasar_hukum,
    }


@pytest.mark.django_db
class TestQualityControlView:
    def test_get_denied_for_non_pmde(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('quality_control'))
        assert resp.status_code == 403

    def test_get_success(self, client):
        client.force_login(_pmde_admin_user())
        resp = client.get(reverse('quality_control'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestQualityControlData:
    url = 'quality_control_data'

    def test_data_endpoint_basic_row(self, client):
        bundle = _qc_bundle(with_durasi=True, with_prioritas=True)
        client.force_login(bundle['pmde_user'])
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload['recordsFiltered'] >= 1
        row = next(r for r in payload['data'] if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)
        assert row['prioritas'] == 'Ya'
        assert row['jml_baris_i'] == 100
        assert row['jml_selesai'] == 40
        assert row['jml_progress'] == 60
        assert row['deadline']['display'] != '-'
        assert row['sisa_hari'] is not None
        assert row['klasifikasi'] == 'PKS'

    def test_data_endpoint_no_durasi_no_prioritas(self, client):
        bundle = _qc_bundle(with_durasi=False, with_prioritas=False)
        client.force_login(bundle['pmde_user'])
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        payload = resp.json()
        row = next(r for r in payload['data'] if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)
        assert row['prioritas'] == 'Tidak'
        assert row['deadline']['display'] == '-'
        assert row['sisa_hari'] is None

    def test_data_endpoint_post_method(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.post(reverse(self.url), {'draw': '2', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        assert resp.json()['draw'] == 2

    def test_data_endpoint_only_shows_own_pmde_tikets(self, client):
        _qc_bundle()
        other_pmde = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_pmde')
        other_pmde.groups.add(group)
        client.force_login(other_pmde)
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.json()['recordsFiltered'] == 0

    @pytest.mark.parametrize('idx,key', [
        (0, 'nama_tabel_I'),
        (2, 'nomor_tiket'),
        (3, 'nama_ilap'),
        (4, 'nama_sub_jenis_data'),
        (5, 'jenis_tabel'),
    ])
    def test_columns_search_text_fields(self, client, idx, key):
        bundle = _qc_bundle()
        columns_search = ['' for _ in range(16)]
        if key == 'nomor_tiket':
            value = bundle['tiket'].nomor_tiket
        elif key == 'nama_ilap':
            value = bundle['jenis_data'].id_ilap.nama_ilap
        elif key == 'nama_sub_jenis_data':
            value = bundle['jenis_data'].nama_sub_jenis_data
        elif key == 'jenis_tabel':
            value = bundle['jenis_tabel'].deskripsi
        else:
            value = bundle['jenis_data'].nama_tabel_I
        columns_search[idx] = value
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.status_code == 200
        assert resp.json()['recordsFiltered'] == 1

    def test_columns_search_tgl_transfer_and_rematch(self, client):
        bundle = _qc_bundle()
        year = str(bundle['tiket'].tgl_transfer.year)
        columns_search = ['' for _ in range(16)]
        columns_search[7] = year
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.status_code == 200

        columns_search = ['' for _ in range(16)]
        columns_search[8] = year
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.status_code == 200

    def test_columns_search_prioritas_ya(self, client):
        bundle = _qc_bundle(with_prioritas=True)
        columns_search = ['' for _ in range(16)]
        columns_search[10] = 'ya'
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_columns_search_prioritas_tidak(self, client):
        bundle = _qc_bundle(with_prioritas=False)
        columns_search = ['' for _ in range(16)]
        columns_search[10] = 'tidak'
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_columns_search_baris_i_qc_fields(self, client):
        bundle = _qc_bundle()
        for idx in (12, 13, 14):
            columns_search = ['' for _ in range(16)]
            columns_search[idx] = '100' if idx == 12 else ('40' if idx == 13 else '60')
            client.force_login(bundle['pmde_user'])
            resp = client.get(
                reverse(self.url),
                {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
            )
            assert resp.status_code == 200

    @pytest.mark.parametrize('order_col,order_dir', [
        (0, 'asc'), (1, 'desc'), (9, 'asc'), (10, 'desc'), (11, 'asc'), (99, 'asc'),
    ])
    def test_ordering(self, client, order_col, order_dir):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': str(order_col), 'order[0][dir]': order_dir},
        )
        assert resp.status_code == 200

    def test_ordering_invalid_column_falls_back(self, client):
        bundle = _qc_bundle()
        client.force_login(bundle['pmde_user'])
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'abc'},
        )
        assert resp.status_code == 200

    def test_denied_for_non_pmde(self, client):
        """@user_passes_test redirects (not 403) non-PMDE users."""
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302
