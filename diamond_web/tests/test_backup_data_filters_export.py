"""Tests for the uncovered filter, export, filter-options, and tiket-info
branches of diamond_web/views/backup_data.py.
"""
from datetime import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import BackupData, TiketPIC
from diamond_web.tests.conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    KategoriILAPFactory,
    MediaBackupFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)


def _backup_bundle(tahun=2019, **tiket_extra):
    """Create a Tiket + BackupData with a fully resolvable relation chain."""
    kategori_ilap = KategoriILAPFactory()
    ilap = ILAPFactory(id_kategori=kategori_ilap)
    jenis_data = JenisDataILAPFactory(id_ilap=ilap)
    periode_pengiriman = PeriodePengirimanFactory()
    periode_data = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=periode_pengiriman,
    )
    tiket_extra.setdefault('tgl_terima_dip', datetime(tahun, 6, 1))
    tiket = TiketFactory(
        id_periode_data=periode_data,
        tahun=tahun,
        backup=True,
        **tiket_extra,
    )
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
    media = MediaBackupFactory()
    backup = BackupData.objects.create(
        id_tiket=tiket,
        id_user=user,
        id_media_backup=media,
        lokasi_backup='/mnt/backup/test',
    )
    return {
        'tiket': tiket,
        'ilap': ilap,
        'kategori_ilap': kategori_ilap,
        'jenis_data': jenis_data,
        'periode_data': periode_data,
        'periode_pengiriman': periode_pengiriman,
        'user': user,
        'media': media,
        'backup': backup,
    }


@pytest.mark.django_db
class TestBackupDataDataFilters:
    def test_filter_by_tahun(self, client, admin_user):
        bundle = _backup_bundle(tahun=2019)
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'tahun': '2019'},
        )
        data = resp.json()
        assert any(row['nomor_tiket'] == bundle['tiket'].nomor_tiket for row in data['data'])

    def test_filter_by_tahun_invalid_is_ignored(self, client, admin_user):
        _backup_bundle(tahun=2019)
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'tahun': 'abc'},
        )
        assert resp.status_code == 200

    def test_filter_by_id_ilap(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'id_ilap': str(bundle['ilap'].id)},
        )
        data = resp.json()
        assert data['recordsFiltered'] == 1

    def test_filter_by_id_jenis_data(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_jenis_data': str(bundle['jenis_data'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_sub_jenis_data_ilap(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_sub_jenis_data_ilap': str(bundle['jenis_data'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_kategori_ilap(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_kategori_ilap': str(bundle['kategori_ilap'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_periode_data(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_periode_data': str(bundle['periode_data'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_periode_pengiriman(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_periode_pengiriman': str(bundle['periode_pengiriman'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_media_backup(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_media_backup': str(bundle['media'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_filter_by_id_pic_p3de(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'id_pic_p3de': str(bundle['user'].id)},
        )
        assert resp.json()['recordsFiltered'] == 1

    @pytest.mark.parametrize('idx,value', [
        (0, None),   # kategori -- set via bundle
        (1, None),   # ilap
        (2, None),   # jenis_data
        (3, None),   # subjenis_data
        (5, None),   # nomor_tiket
        (6, None),   # media
        (7, None),   # lokasi
        (8, None),   # pic name
    ])
    def test_columns_search_matches(self, client, admin_user, idx, value):
        bundle = _backup_bundle()
        search_values = {
            0: bundle['kategori_ilap'].nama_kategori,
            1: bundle['ilap'].nama_ilap,
            2: bundle['jenis_data'].nama_jenis_data,
            3: bundle['jenis_data'].nama_sub_jenis_data,
            5: bundle['tiket'].nomor_tiket,
            6: bundle['media'].deskripsi,
            7: 'test',
            8: bundle['user'].username,
        }
        columns_search = ['' for _ in range(10)]
        columns_search[idx] = search_values[idx]
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.status_code == 200
        assert resp.json()['recordsFiltered'] >= 1

    def test_columns_search_periode_digit_branch(self, client, admin_user):
        bundle = _backup_bundle()
        columns_search = ['' for _ in range(10)]
        columns_search[4] = str(bundle['tiket'].periode)
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        assert resp.status_code == 200

    def test_columns_search_baris_diterima_digit_branch(self, client, admin_user):
        bundle = _backup_bundle(baris_diterima=555)
        columns_search = ['' for _ in range(10)]
        columns_search[9] = '555'
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': columns_search},
        )
        data = resp.json()
        assert any(row['nomor_tiket'] == bundle['tiket'].nomor_tiket for row in data['data'])

    @pytest.mark.parametrize('order_col,order_dir', [
        (0, 'asc'), (4, 'desc'), (9, 'asc'), (99, 'asc'),
    ])
    def test_ordering_columns(self, client, admin_user, order_col, order_dir):
        _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': str(order_col), 'order[0][dir]': order_dir},
        )
        assert resp.status_code == 200

    def test_actions_rendered_for_active_pic_below_dikirim_status(self, client):
        bundle = _backup_bundle()
        client.force_login(bundle['user'])
        resp = client.get(reverse('backup_data_data'), {'draw': '1', 'start': '0', 'length': '10'})
        data = resp.json()
        row = next(r for r in data['data'] if r['nomor_tiket'] == bundle['tiket'].nomor_tiket)
        assert 'data-action=\'edit\'' in row['actions']
        assert 'data-action=\'delete\'' in row['actions']


@pytest.mark.django_db
class TestBackupDataFilterOptions:
    def test_no_id_ilap_returns_empty_options(self, client, admin_user):
        _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_filter_options'))
        data = resp.json()
        assert data['filter_options']['jenis_data'] == []
        assert 'media_backup_list' in data

    def test_with_id_ilap_returns_populated_options(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_filter_options'),
            {'id_ilap': str(bundle['ilap'].id)},
        )
        data = resp.json()
        opts = data['filter_options']
        assert any(j['id'] == bundle['jenis_data'].id for j in opts['jenis_data'])
        assert any(s['id'] == bundle['jenis_data'].id for s in opts['subjenis_data'])
        assert any(k['id'] == bundle['kategori_ilap'].id for k in opts['kategori_ilap'])
        assert any(p['id'] == bundle['periode_data'].id for p in opts['periode_data'])
        assert any(p['id'] == bundle['periode_pengiriman'].id for p in opts['periode_pengiriman'])
        assert any(m['id'] == bundle['media'].id for m in opts['media_backup'])
        assert any(p['id'] == bundle['user'].id for p in opts['pic_p3de'])

    def test_with_all_sub_filters_applied(self, client, admin_user):
        bundle = _backup_bundle(tahun=2019)
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_filter_options'),
            {
                'id_ilap': str(bundle['ilap'].id),
                'tahun': '2019',
                'id_jenis_data': str(bundle['jenis_data'].id),
                'id_sub_jenis_data_ilap': str(bundle['jenis_data'].id),
                'id_kategori_ilap': str(bundle['kategori_ilap'].id),
                'id_periode_data': str(bundle['periode_data'].id),
                'id_periode_pengiriman': str(bundle['periode_pengiriman'].id),
                'id_pic_p3de': str(bundle['user'].id),
            },
        )
        assert resp.status_code == 200
        opts = resp.json()['filter_options']
        assert any(j['id'] == bundle['jenis_data'].id for j in opts['jenis_data'])

    def test_invalid_tahun_ignored(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_filter_options'),
            {'id_ilap': str(bundle['ilap'].id), 'tahun': 'xx'},
        )
        assert resp.status_code == 200

    def test_denied_without_group(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('backup_data_filter_options'))
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestBackupDataExport:
    def test_export_excel(self, client, admin_user):
        bundle = _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_export_excel'))
        assert resp.status_code == 200
        assert 'spreadsheetml' in resp.get('Content-Type', '')

    def test_export_excel_with_filters(self, client, admin_user):
        bundle = _backup_bundle(tahun=2019)
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_export_excel'), {'tahun': '2019'})
        assert resp.status_code == 200

    def test_export_pdf(self, client, admin_user):
        _backup_bundle()
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_export_pdf'))
        assert resp.status_code == 200
        assert resp.get('Content-Type') == 'application/pdf'
        assert resp.content.startswith(b'%PDF-1.4')

    def test_export_pdf_many_rows_paginates(self, client, admin_user):
        """_build_simple_table_pdf splits rows across multiple PDF pages."""
        bundle = _backup_bundle()
        # Reuse the same periode/ilap chain to avoid exhausting unique
        # PeriodePengiriman.periode_penyampaian values across iterations.
        for _ in range(80):
            tiket = TiketFactory(id_periode_data=bundle['periode_data'], backup=True)
            BackupData.objects.create(
                id_tiket=tiket,
                id_user=bundle['user'],
                id_media_backup=bundle['media'],
                lokasi_backup='/mnt/backup/many',
            )
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_export_pdf'))
        assert resp.status_code == 200
        assert resp.content.count(b'/Type /Page ') >= 2 or resp.content.count(b'/Type /Page') >= 2

    def test_export_denied_without_group(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('backup_data_export_excel'))
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestBackupDataTiketInfo:
    """backup_data_tiket_info isn't wired to any urls.py route, so it's
    exercised by calling the view function directly with RequestFactory.
    """

    def test_success(self, admin_user):
        from django.test import RequestFactory
        from diamond_web.views.backup_data import backup_data_tiket_info

        bundle = _backup_bundle()
        request = RequestFactory().get('/backup-data/tiket-info/')
        request.user = admin_user
        resp = backup_data_tiket_info(request, tiket_pk=bundle['tiket'].pk)
        assert resp.status_code == 200
        import json
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['ilap'] == bundle['ilap'].nama_ilap

    def test_not_found(self, admin_user, db):
        from django.test import RequestFactory
        from diamond_web.views.backup_data import backup_data_tiket_info

        request = RequestFactory().get('/backup-data/tiket-info/')
        request.user = admin_user
        resp = backup_data_tiket_info(request, tiket_pk=999999)
        assert resp.status_code == 404
        import json
        assert json.loads(resp.content)['success'] is False
