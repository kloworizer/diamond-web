"""Status prioritas tiket mengikuti tabel Data Prioritas.

Tombol Sinkronisasi Prioritas menyelaraskan seluruh tiket; tambah/ubah/hapus
lewat form menyelaraskan tiket Sub Jenis Data yang disentuh.
"""
from datetime import date, datetime
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.models import JenisPrioritasData, Tiket
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import (
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    TiketFactory,
    UserFactory,
)

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


@pytest.fixture
def admin_p3de(db):
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name='admin_p3de')[0])
    return user


@pytest.mark.django_db
class TestTiketBackfill:
    def _setup(self):
        tiket_isi = TiketFactory(id_jenis_prioritas_data=None, tgl_terima_dip=datetime(2026, 8, 7, 9, 0))
        record = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=tiket_isi.id_periode_data.id_sub_jenis_data_ilap,
            tahun='2026', start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        tiket_kosongkan = TiketFactory(tgl_terima_dip=datetime(2019, 1, 1))
        stale = tiket_kosongkan.id_jenis_prioritas_data
        stale.start_date, stale.end_date = date(2026, 1, 1), None
        stale.save()
        return tiket_isi, record, tiket_kosongkan

    def test_non_admin_is_refused(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('jenis_prioritas_data_tiket_backfill'), **AJAX)
        assert resp.status_code in (302, 403)

    def test_preview_then_apply(self, client, admin_p3de):
        tiket_isi, record, tiket_kosongkan = self._setup()
        client.force_login(admin_p3de)

        preview = client.get(reverse('jenis_prioritas_data_tiket_backfill_preview')).json()
        assert (preview['total_tiket'], preview['diisi'], preview['dikosongkan']) == (2, 1, 1)
        assert Tiket.objects.get(pk=tiket_isi.pk).id_jenis_prioritas_data_id is None

        resp = client.post(reverse('jenis_prioritas_data_tiket_backfill'), **AJAX)
        assert resp.json()['updated'] == 2
        assert Tiket.objects.get(pk=tiket_isi.pk).id_jenis_prioritas_data_id == record.pk
        assert Tiket.objects.get(pk=tiket_kosongkan.pk).id_jenis_prioritas_data_id is None

        action = TiketAction.objects.get(id_tiket=tiket_isi, action=TiketActionType.DIUBAH)
        assert action.id_user == admin_p3de
        assert 'penyesuaian jenis prioritas data' in action.catatan

        rerun = client.post(reverse('jenis_prioritas_data_tiket_backfill'), **AJAX).json()
        assert rerun['updated'] == 0


def _tiket(sub, tanggal, jpd=None):
    """Tiket untuk Sub Jenis Data `sub` yang diterima DIP pada `tanggal`."""
    tiket = TiketFactory(id_jenis_prioritas_data=jpd, tgl_terima_dip=tanggal)
    periode = tiket.id_periode_data
    periode.id_sub_jenis_data_ilap = sub
    periode.save()
    return tiket


def _fk(tiket):
    return Tiket.objects.values_list('id_jenis_prioritas_data', flat=True).get(pk=tiket.pk)


def _form(sub, tahun, start, end, no_nd='ND-1'):
    return {
        'id_sub_jenis_data_ilap': sub.pk, 'no_nd': no_nd, 'tahun': tahun,
        'start_date': start, 'end_date': end,
    }


@pytest.mark.django_db
class TestCrudSelaraskanTiket:
    """Tambah/ubah/hapus Data Prioritas langsung menyesuaikan tiket Sub Jenis Data-nya."""

    def test_create_marks_tikets_inside_window(self, client, admin_p3de):
        sub = JenisDataILAPFactory()
        di_dalam = _tiket(sub, datetime(2026, 8, 7, 9, 0))
        di_luar = _tiket(sub, datetime(2025, 12, 31, 23, 0))
        sub_lain = TiketFactory(id_jenis_prioritas_data=None, tgl_terima_dip=datetime(2026, 8, 7))

        client.force_login(admin_p3de)
        resp = client.post(
            reverse('jenis_prioritas_data_create'),
            _form(sub, '2026', '2026-01-01', '2026-12-31'), **AJAX,
        )

        assert resp.json()['success'] is True
        record = JenisPrioritasData.objects.get(id_sub_jenis_data_ilap=sub, tahun='2026')
        assert _fk(di_dalam) == record.pk
        assert _fk(di_luar) is None
        assert _fk(sub_lain) is None
        assert '1 tiket menjadi prioritas' in resp.json()['message']
        action = TiketAction.objects.get(id_tiket=di_dalam, action=TiketActionType.DIUBAH)
        assert action.id_user == admin_p3de

    def test_update_moves_tikets_in_and_out_of_window(self, client, admin_p3de):
        sub = JenisDataILAPFactory()
        record = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub, tahun='2026',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        keluar = _tiket(sub, datetime(2026, 3, 1), jpd=record)
        tetap = _tiket(sub, datetime(2026, 8, 7), jpd=record)
        masuk = _tiket(sub, datetime(2027, 2, 1))

        client.force_login(admin_p3de)
        resp = client.post(
            reverse('jenis_prioritas_data_update', args=[record.pk]),
            _form(sub, '2026', '2026-07-01', '2027-06-30'), **AJAX,
        )

        assert resp.json()['success'] is True
        assert _fk(keluar) is None
        assert _fk(tetap) == record.pk
        assert _fk(masuk) == record.pk
        assert '1 tiket menjadi prioritas, 1 tiket tidak lagi prioritas' in resp.json()['message']

    def test_update_to_other_sub_clears_the_old_subs_tikets(self, client, admin_p3de):
        sub_lama, sub_baru = JenisDataILAPFactory(), JenisDataILAPFactory()
        record = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_lama, tahun='2026',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        ditinggal = _tiket(sub_lama, datetime(2026, 8, 7), jpd=record)
        baru = _tiket(sub_baru, datetime(2026, 8, 7))

        client.force_login(admin_p3de)
        client.post(
            reverse('jenis_prioritas_data_update', args=[record.pk]),
            _form(sub_baru, '2026', '2026-01-01', '2026-12-31'), **AJAX,
        )

        assert _fk(ditinggal) is None
        assert _fk(baru) == record.pk

    def test_invalid_form_changes_no_tiket(self, client, admin_p3de):
        sub = JenisDataILAPFactory()
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub, tahun='2026',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        tiket = _tiket(sub, datetime(2026, 8, 7))

        client.force_login(admin_p3de)
        resp = client.post(
            reverse('jenis_prioritas_data_create'),
            _form(sub, '2027', '2026-06-01', '2027-12-31'), **AJAX,  # bertumpuk
        )

        assert resp.json()['success'] is False
        assert _fk(tiket) is None

    def test_delete_makes_tikets_not_prioritas(self, client, admin_p3de):
        tiket = TiketFactory()
        record = tiket.id_jenis_prioritas_data
        client.force_login(admin_p3de)

        confirm = client.get(reverse('jenis_prioritas_data_delete', args=[record.pk]), {'ajax': '1'})
        assert '1 tiket' in confirm.json()['html']

        resp = client.post(reverse('jenis_prioritas_data_delete', args=[record.pk]), **AJAX)

        assert resp.json()['success'] is True
        assert '1 tiket tidak lagi prioritas' in resp.json()['message']
        assert not JenisPrioritasData.objects.filter(pk=record.pk).exists()
        assert _fk(tiket) is None
        assert TiketAction.objects.filter(id_tiket=tiket, action=TiketActionType.DIUBAH).exists()

    def test_failed_delete_restores_tikets(self, client, admin_p3de):
        tiket = TiketFactory()
        record = tiket.id_jenis_prioritas_data
        client.force_login(admin_p3de)
        with mock.patch.object(JenisPrioritasData, 'delete', side_effect=RuntimeError('boom')):
            resp = client.post(reverse('jenis_prioritas_data_delete', args=[record.pk]), **AJAX)

        assert resp.status_code == 400
        assert _fk(tiket) == record.pk
        assert not TiketAction.objects.filter(id_tiket=tiket, action=TiketActionType.DIUBAH).exists()
