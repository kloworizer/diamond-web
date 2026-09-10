"""Isi Otomatis PIC PMDE — mengambil PIC dari Sub Jenis Data satu Nama Tabel I.

Aturan yang diuji: Sub Jenis Data tanpa PIC PMDE aktif mengambil PIC PMDE dari
Sub Jenis Data lain yang `nama_tabel_I`-nya sama, tetapi hanya bila tabel itu
punya tepat satu PIC PMDE aktif. Lebih dari satu berarti tidak ada jawaban
tunggal, jadi barisnya dilewati untuk di-assign manual.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models import PIC, TiketPIC
from diamond_web.tests.conftest import (
    JenisDataILAPFactory, PeriodeJenisDataFactory, PeriodePengirimanFactory,
    PICFactory, TiketFactory, UserFactory,
)


def _add_groups(user, *names):
    for name in names:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)


def _admin_pmde(client):
    user = UserFactory()
    _add_groups(user, 'admin_pmde')
    client.force_login(user)
    return user


def _pic_pmde_aktif(jenis_data, user):
    return PICFactory(
        tipe=PIC.TipePIC.PMDE,
        id_sub_jenis_data_ilap=jenis_data,
        id_user=user,
        end_date=None,
    )


@pytest.mark.django_db
class TestAutoAssignAccessControl:
    def test_preview_requires_login(self, client):
        resp = client.get(reverse('home_pmde_auto_assign_pic_preview'))
        assert resp.status_code == 302

    def test_preview_requires_admin_pmde(self, client):
        user = UserFactory()
        _add_groups(user, 'admin_pide')
        client.force_login(user)
        resp = client.get(reverse('home_pmde_auto_assign_pic_preview'))
        assert resp.status_code == 403

    def test_apply_requires_admin_pmde(self, client):
        user = UserFactory()
        _add_groups(user, 'user_pmde')
        client.force_login(user)
        resp = client.post(reverse('home_pmde_auto_assign_pic'))
        assert resp.status_code == 403

    def test_apply_rejects_get(self, client):
        _admin_pmde(client)
        resp = client.get(reverse('home_pmde_auto_assign_pic'))
        assert resp.status_code == 405


@pytest.mark.django_db
class TestAutoAssignPlan:
    def test_single_pic_on_table_is_borrowed(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        sumber = JenisDataILAPFactory(nama_tabel_I='KPDE_PEMDA_KEBUN_IUP')
        _pic_pmde_aktif(sumber, pic_user)
        target = JenisDataILAPFactory(nama_tabel_I='KPDE_PEMDA_KEBUN_IUP')

        resp = client.get(reverse('home_pmde_auto_assign_pic_preview'))
        data = json.loads(resp.content)
        assert data['total_assign'] == 1
        assert data['items'][0]['id_sub_jenis_data'] == target.id_sub_jenis_data
        assert pic_user.username in data['items'][0]['pic']

        resp = client.post(reverse('home_pmde_auto_assign_pic'))
        assert json.loads(resp.content)['created'] == 1
        assert PIC.objects.filter(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=target,
            id_user=pic_user,
            end_date__isnull=True,
        ).exists()

    def test_two_pics_on_table_are_skipped(self, client):
        _admin_pmde(client)
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='TBL_AMBIGU'), UserFactory())
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='TBL_AMBIGU'), UserFactory())
        target = JenisDataILAPFactory(nama_tabel_I='TBL_AMBIGU')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_ambigu'] == 1
        assert data['ambigu'][0]['id_sub_jenis_data'] == target.id_sub_jenis_data

        client.post(reverse('home_pmde_auto_assign_pic'))
        assert not PIC.objects.filter(id_sub_jenis_data_ilap=target).exists()

    def test_same_user_twice_on_table_is_still_unambiguous(self, client):
        """Dua baris PIC PMDE aktif dengan orang yang sama tetap satu jawaban."""
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='TBL_SAMA'), pic_user)
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='TBL_SAMA'), pic_user)
        target = JenisDataILAPFactory(nama_tabel_I='TBL_SAMA')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1
        assert data['total_ambigu'] == 0

    def test_closed_pic_does_not_count_as_source(self, client):
        _admin_pmde(client)
        PICFactory(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='TBL_TUTUP'),
            id_user=UserFactory(),
            end_date='2024-01-01',
        )
        JenisDataILAPFactory(nama_tabel_I='TBL_TUTUP')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_tanpa_rujukan'] == 2  # sumber dan target sama-sama tanpa PIC

    def test_pic_of_other_tipe_is_not_borrowed(self, client):
        _admin_pmde(client)
        PICFactory(
            tipe=PIC.TipePIC.PIDE,
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='TBL_PIDE'),
            id_user=UserFactory(),
            end_date=None,
        )
        JenisDataILAPFactory(nama_tabel_I='TBL_PIDE')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0

    def test_blank_nama_tabel_is_skipped(self, client):
        _admin_pmde(client)
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I=''), UserFactory())
        JenisDataILAPFactory(nama_tabel_I='   ')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_tanpa_tabel'] == 1

    def test_table_name_matched_case_insensitively(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='kpde_pemda'), pic_user)
        JenisDataILAPFactory(nama_tabel_I=' KPDE_PEMDA ')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1

    def test_nothing_to_do_reports_zero(self, client):
        _admin_pmde(client)
        resp = client.post(reverse('home_pmde_auto_assign_pic'))
        body = json.loads(resp.content)
        assert body['success'] is True
        assert body['created'] == 0


@pytest.mark.django_db
class TestAutoAssignPropagation:
    def test_open_tiket_receives_the_pic(self, client):
        """PIC baru harus ikut menempel ke tiket yang masih berjalan.

        Sama seperti assign manual lewat PICCreateView; tanpa ini baris PIC ada
        tapi tiketnya tetap muncul di 'Tiket ... Belum Punya PIC'.
        """
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(JenisDataILAPFactory(nama_tabel_I='TBL_TIKET'), pic_user)
        target = JenisDataILAPFactory(nama_tabel_I='TBL_TIKET')
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=target,
            id_periode_pengiriman=PeriodePengirimanFactory(
                periode_penyampaian='AUTO ASSIGN PMDE'
            ),
        )
        tiket = TiketFactory(id_periode_data=periode, status_tiket=6)

        client.post(reverse('home_pmde_auto_assign_pic'))

        assert TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=pic_user,
            role=TiketPIC.Role.PMDE,
            active=True,
        ).exists()
