"""Tests for the bulk PIC Pemda/Provinsi page (views/pic_bulk_pemda.py)."""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import ILAP, PIC, TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import (
    ILAPFactory, JenisDataILAPFactory, PeriodeJenisDataFactory, PICFactory,
    TiketFactory, TiketPICFactory, UserFactory,
)

START = date(2025, 1, 1)


def _user(*groups):
    user = UserFactory()
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _jd(code, nama='Tanda Daftar Perusahaan'):
    ilap = (ILAP.objects.filter(id_ilap=code[:5]).first()
            or ILAPFactory(id_ilap=code[:5], nama_ilap=f'Pemda {code[:5]}'))
    return JenisDataILAPFactory(
        id_ilap=ilap,
        id_jenis_data=code[:7],
        id_sub_jenis_data=code,
        nama_sub_jenis_data=nama,
    )


def _pic(jd, user, tipe='P3DE', start=START, end=None):
    return PICFactory(tipe=tipe, id_sub_jenis_data_ilap=jd, id_user=user,
                      start_date=start, end_date=end)


def _open_tiket(jd):
    return TiketFactory(id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jd),
                        status_tiket=1)


def _post(client, name, **data):
    return client.post(reverse(name), data)


@pytest.fixture
def pemda(db):
    """Three rows of kode 4101 (two PD, one PV) plus two that must never match."""
    return {
        'pd1': _jd('PD0014101'),
        'pd2': _jd('PD0024101'),
        'pv1': _jd('PV0014101'),
        'other_kode': _jd('PD0014102'),
        'other_prefix': _jd('KM0014101'),
    }


@pytest.fixture
def admin_p3der(client):
    user = _user('admin_p3der')
    client.force_login(user)
    return user


@pytest.mark.django_db
class TestAccess:
    def test_non_admin_forbidden(self, client):
        client.force_login(_user('user_p3der'))
        assert client.get(reverse('pic_bulk_pemda')).status_code == 403
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101', mode='hapus')
        assert resp.status_code == 403

    def test_admin_p3de_forbidden(self, client):
        """Every Pemda/Provinsi ILAP is Regional, so its PIC P3DE is Seksi P3DER's."""
        client.force_login(_user('admin_p3de'))
        assert client.get(reverse('pic_bulk_pemda')).status_code == 403
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101', mode='hapus')
        assert resp.status_code == 403

    def test_user_p3de_not_offered_as_new_pic(self, client, admin_p3der, pemda):
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101',
                     mode='tambah', user_baru=_user('user_p3de').pk, start_date='2025-06-01')
        assert resp.status_code == 400

    def test_admin_limited_to_own_tipe(self, client, admin_p3der, pemda):
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='PIDE', kode='4101', mode='hapus')
        assert resp.status_code == 400
        assert 'tidak berwenang' in resp.json()['message']

    def test_page_lists_kode_across_pd_and_pv(self, client, admin_p3der, pemda):
        resp = client.get(reverse('pic_bulk_pemda'))
        assert resp.status_code == 200
        kode = {o['kode']: o for o in resp.context['bulk_options']['kode']}
        assert kode['4101']['PD'] == 2 and kode['4101']['PV'] == 1
        assert kode['4102']['PD'] == 1
        assert [t for t, _ in resp.context['tipes']] == ['P3DE']


@pytest.mark.django_db
class TestTambah:
    def test_preview_writes_nothing(self, client, admin_p3der, pemda):
        new = _user('user_p3der')
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101', scope='ALL',
                     mode='tambah', user_baru=new.pk, start_date='2025-06-01')
        body = resp.json()
        assert body['total_ok'] == 3
        assert {r['id_sub_jenis_data'] for r in body['rows']} == {'PD0014101', 'PD0024101', 'PV0014101'}
        assert not PIC.objects.exists()

    def test_creates_pic_and_assigns_open_tikets(self, client, admin_p3der, pemda):
        new = _user('user_p3der')
        existing = _user('user_p3der')
        _pic(pemda['pd2'], new)  # already active there -> skipped
        _pic(pemda['pd1'], existing)
        tiket = _open_tiket(pemda['pd1'])

        resp = _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', scope='ALL',
                     mode='tambah', user_baru=new.pk, start_date='2025-06-01',
                     selected=[f'jd-{pemda[k].pk}' for k in ('pd1', 'pd2', 'pv1')])
        assert resp.json()['applied'] == 2
        assert resp.json()['skipped'] == 1

        assert set(PIC.objects.filter(id_user=new, end_date__isnull=True)
                   .values_list('id_sub_jenis_data_ilap__id_sub_jenis_data', flat=True)) == {
            'PD0014101', 'PD0024101', 'PV0014101'}
        # The other holder is untouched, the tiket gains the new PIC.
        assert PIC.objects.get(id_user=existing).end_date is None
        assert TiketPIC.objects.filter(id_tiket=tiket, id_user=new, active=True).exists()
        assert PIC.objects.get(id_user=new, id_sub_jenis_data_ilap=pemda['pv1']).create_by == admin_p3der.username[:9]

    def test_scope_pd_only(self, client, admin_p3der, pemda):
        new = _user('user_p3der')
        body = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101', scope='PD',
                     mode='tambah', user_baru=new.pk, start_date='2025-06-01').json()
        assert {r['id_sub_jenis_data'] for r in body['rows']} == {'PD0014101', 'PD0024101'}

    def test_user_outside_tipe_group_rejected(self, client, admin_p3der, pemda):
        outsider = _user('user_pide')
        resp = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101',
                     mode='tambah', user_baru=outsider.pk, start_date='2025-06-01')
        assert resp.status_code == 400

    def test_only_selected_rows_applied(self, client, admin_p3der, pemda):
        new = _user('user_p3der')
        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='tambah',
              user_baru=new.pk, start_date='2025-06-01', selected=[f'jd-{pemda["pv1"].pk}'])
        assert list(PIC.objects.values_list('id_sub_jenis_data_ilap', flat=True)) == [pemda['pv1'].pk]


@pytest.mark.django_db
class TestGanti:
    def test_hand_over_from_specific_user(self, client, admin_p3der, pemda):
        old, other, new = _user('user_p3der'), _user('user_p3der'), _user('user_p3der')
        p1 = _pic(pemda['pd1'], old)
        p2 = _pic(pemda['pv1'], old)
        p3 = _pic(pemda['pd2'], other)
        tiket = _open_tiket(pemda['pd1'])
        TiketPICFactory(id_tiket=tiket, id_user=old, role=TiketPIC.Role.P3DE, active=True)

        preview = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101',
                        mode='ganti', user_lama=old.pk, user_baru=new.pk).json()
        keys = [r['key'] for r in preview['rows']]
        assert sorted(keys) == sorted([f'pic-{p1.pk}', f'pic-{p2.pk}'])

        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101',
              mode='ganti', user_lama=old.pk, user_baru=new.pk, selected=keys)

        p1.refresh_from_db(); p2.refresh_from_db(); p3.refresh_from_db()
        assert p1.id_user == new and p2.id_user == new and p1.end_date is None
        assert p3.id_user == other
        assert not TiketPIC.objects.get(id_tiket=tiket, id_user=old).active
        assert TiketPIC.objects.get(id_tiket=tiket, id_user=new).active
        assert TiketAction.objects.filter(id_tiket=tiket, catatan__contains='diganti').exists()

    def test_new_user_already_active_closes_old(self, client, admin_p3der, pemda):
        old, new = _user('user_p3der'), _user('user_p3der')
        p_old = _pic(pemda['pd1'], old)
        p_new = _pic(pemda['pd1'], new)

        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='ganti',
              user_baru=new.pk, selected=[f'pic-{p_old.pk}', f'pic-{p_new.pk}'])

        p_old.refresh_from_db(); p_new.refresh_from_db()
        assert p_old.id_user == old and p_old.end_date is not None
        assert p_new.end_date is None
        assert PIC.objects.filter(id_user=new, end_date__isnull=True).count() == 1

    def test_two_old_pics_on_one_row_do_not_duplicate_new_user(self, client, admin_p3der, pemda):
        a, b, new = _user('user_p3der'), _user('user_p3der'), _user('user_p3der')
        pa = _pic(pemda['pd1'], a)
        pb = _pic(pemda['pd1'], b, start=date(2025, 2, 1))

        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='ganti',
              user_baru=new.pk, selected=[f'pic-{pa.pk}', f'pic-{pb.pk}'])

        active = PIC.objects.filter(id_sub_jenis_data_ilap=pemda['pd1'], end_date__isnull=True)
        assert list(active.values_list('id_user', flat=True)) == [new.pk]


@pytest.mark.django_db
class TestAkhiri:
    def test_sets_end_date_and_deactivates_tikets(self, client, admin_p3der, pemda):
        old = _user('user_p3der')
        p1 = _pic(pemda['pd1'], old)
        p_late = _pic(pemda['pv1'], old, start=date(2026, 1, 1))
        tiket = _open_tiket(pemda['pd1'])
        TiketPICFactory(id_tiket=tiket, id_user=old, role=TiketPIC.Role.P3DE, active=True)

        preview = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101',
                        mode='akhiri', end_date='2025-12-31').json()
        by_key = {r['key']: r for r in preview['rows']}
        assert by_key[f'pic-{p1.pk}']['ok']
        assert not by_key[f'pic-{p_late.pk}']['ok']  # end before start

        resp = _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='akhiri',
                     end_date='2025-12-31', selected=list(by_key))
        assert resp.json()['applied'] == 1

        p1.refresh_from_db(); p_late.refresh_from_db()
        assert p1.end_date == date(2025, 12, 31)
        assert p_late.end_date is None
        assert not TiketPIC.objects.get(id_tiket=tiket, id_user=old).active


@pytest.mark.django_db
class TestHapus:
    def test_deletes_active_only_by_default(self, client, admin_p3der, pemda):
        old = _user('user_p3der')
        active = _pic(pemda['pd1'], old)
        closed = _pic(pemda['pd2'], old, end=date(2025, 3, 1))
        untouched = _pic(pemda['other_kode'], old)
        tiket = _open_tiket(pemda['pd1'])
        TiketPICFactory(id_tiket=tiket, id_user=old, role=TiketPIC.Role.P3DE, active=True)

        preview = _post(client, 'pic_bulk_pemda_preview', tipe='P3DE', kode='4101',
                        mode='hapus', user_lama=old.pk).json()
        assert [r['key'] for r in preview['rows']] == [f'pic-{active.pk}']

        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='hapus',
              user_lama=old.pk, selected=[f'pic-{active.pk}', f'pic-{closed.pk}'])

        assert not PIC.objects.filter(pk=active.pk).exists()
        assert PIC.objects.filter(pk=closed.pk).exists()  # not in the active-only plan
        assert PIC.objects.filter(pk=untouched.pk).exists()
        assert not TiketPIC.objects.filter(id_tiket=tiket, id_user=old).exists()

    def test_include_closed(self, client, admin_p3der, pemda):
        old = _user('user_p3der')
        closed = _pic(pemda['pd2'], old, end=date(2025, 3, 1))
        _post(client, 'pic_bulk_pemda_execute', tipe='P3DE', kode='4101', mode='hapus',
              hanya_aktif='0', selected=[f'pic-{closed.pk}'])
        assert not PIC.objects.filter(pk=closed.pk).exists()


@pytest.mark.django_db
def test_holders_counts(client, admin_p3der, pemda):
    a, b = _user('user_p3der'), _user('user_p3der')
    _pic(pemda['pd1'], a)
    _pic(pemda['pv1'], a)
    _pic(pemda['pd2'], b, end=date(2025, 3, 1))
    body = client.get(reverse('pic_bulk_pemda_holders'),
                      {'tipe': 'P3DE', 'kode': '4101', 'scope': 'ALL'}).json()
    assert body['total_jenis_data'] == 3
    assert body['tanpa_pic_aktif'] == 1
    assert body['holders'][0]['id'] == a.pk and body['holders'][0]['aktif'] == 2
