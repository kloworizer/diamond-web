"""Isi Otomatis PIC PMDE — mengambil PIC dari Sub Jenis Data satu Nama Tabel I.

Aturan yang diuji: Sub Jenis Data berawalan PV/PD yang tanpa PIC PMDE aktif
mengambil PIC PMDE dari Sub Jenis Data lain yang `nama_tabel_I`-nya sama, tetapi
hanya bila tabel itu punya tepat satu PIC PMDE aktif. Lebih dari satu berarti
tidak ada jawaban tunggal, jadi barisnya dilewati untuk di-assign manual.
"""
import json
from datetime import date
from itertools import count

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from diamond_web.models import PIC, TiketPIC
from diamond_web.tests.conftest import (
    JenisDataILAPFactory, PeriodeJenisDataFactory, PeriodePengirimanFactory,
    PICFactory, TiketFactory, UserFactory,
)

# id_sub_jenis_data harus unik dan awalannya menentukan lingkup fitur, jadi
# setiap baris dibuat dengan awalan yang diminta plus nomor urut sendiri.
_KODE_SEQ = count()


def _jenis_data(nama_tabel_I, prefix='PV'):
    return JenisDataILAPFactory(
        nama_tabel_I=nama_tabel_I,
        id_sub_jenis_data=f'{prefix}{next(_KODE_SEQ):07d}',
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
        sumber = _jenis_data('KPDE_PEMDA_KEBUN_IUP')
        _pic_pmde_aktif(sumber, pic_user)
        target = _jenis_data('KPDE_PEMDA_KEBUN_IUP')

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
        _pic_pmde_aktif(_jenis_data('TBL_AMBIGU'), UserFactory())
        _pic_pmde_aktif(_jenis_data('TBL_AMBIGU'), UserFactory())
        target = _jenis_data('TBL_AMBIGU')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_ambigu'] == 1
        group = data['ambigu'][0]
        assert group['nama_tabel_I'] == 'TBL_AMBIGU'
        assert [r['id_sub_jenis_data'] for r in group['sub_jenis_data']] == [target.id_sub_jenis_data]

        client.post(reverse('home_pmde_auto_assign_pic'))
        assert not PIC.objects.filter(id_sub_jenis_data_ilap=target).exists()

    def test_same_user_twice_on_table_is_still_unambiguous(self, client):
        """Dua baris PIC PMDE aktif dengan orang yang sama tetap satu jawaban."""
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_SAMA'), pic_user)
        _pic_pmde_aktif(_jenis_data('TBL_SAMA'), pic_user)
        _jenis_data('TBL_SAMA')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1
        assert data['total_ambigu'] == 0

    def test_closed_pic_does_not_count_as_source(self, client):
        _admin_pmde(client)
        PICFactory(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=_jenis_data('TBL_TUTUP'),
            id_user=UserFactory(),
            end_date='2024-01-01',
        )
        _jenis_data('TBL_TUTUP')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_tanpa_rujukan'] == 2  # sumber dan target sama-sama tanpa PIC

    def test_pic_of_other_tipe_is_not_borrowed(self, client):
        _admin_pmde(client)
        PICFactory(
            tipe=PIC.TipePIC.PIDE,
            id_sub_jenis_data_ilap=_jenis_data('TBL_PIDE'),
            id_user=UserFactory(),
            end_date=None,
        )
        _jenis_data('TBL_PIDE')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0

    def test_blank_nama_tabel_is_skipped(self, client):
        _admin_pmde(client)
        _pic_pmde_aktif(_jenis_data(''), UserFactory())
        _jenis_data('   ')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_tanpa_tabel'] == 1

    def test_table_name_matched_case_insensitively(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('kpde_pemda'), pic_user)
        _jenis_data(' KPDE_PEMDA ')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1

    def test_nothing_to_do_reports_zero(self, client):
        _admin_pmde(client)
        resp = client.post(reverse('home_pmde_auto_assign_pic'))
        body = json.loads(resp.content)
        assert body['success'] is True
        assert body['created'] == 0


@pytest.mark.django_db
class TestAutoAssignPrefixScope:
    """Hanya Sub Jenis Data berawalan PV dan PD yang diisi otomatis."""

    def test_pd_prefix_is_filled(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_PD', prefix='PD'), pic_user)
        target = _jenis_data('TBL_PD', prefix='PD')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1
        assert data['items'][0]['id_sub_jenis_data'] == target.id_sub_jenis_data

    @pytest.mark.parametrize('prefix', ['AS', 'LM', 'BU'])
    def test_other_prefixes_are_left_alone(self, client, prefix):
        _admin_pmde(client)
        _pic_pmde_aktif(_jenis_data('TBL_LUAR'), UserFactory())
        target = _jenis_data('TBL_LUAR', prefix=prefix)

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        # Di luar lingkup: tidak dihitung sebagai dilewati, tapi juga tidak diisi.
        assert data['total_tanpa_pic'] == 0

        client.post(reverse('home_pmde_auto_assign_pic'))
        assert not PIC.objects.filter(id_sub_jenis_data_ilap=target).exists()

    def test_source_may_come_from_any_prefix(self, client):
        """Batas PV/PD berlaku pada baris yang diisi, bukan pada sumber PIC-nya."""
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_CAMPUR', prefix='LM'), pic_user)
        target = _jenis_data('TBL_CAMPUR', prefix='PV')

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1
        assert data['items'][0]['id_sub_jenis_data'] == target.id_sub_jenis_data
        assert pic_user.username in data['items'][0]['pic']

    def test_preview_reports_the_prefixes_it_used(self, client):
        _admin_pmde(client)
        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['prefixes'] == ['PV', 'PD']


@pytest.mark.django_db
class TestAutoAssignStartDate:
    """Tanggal Mulai PIC hasil Isi Otomatis tetap 01-01-2015, bukan hari ini."""

    def test_created_pic_starts_2015_01_01(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_TANGGAL'), pic_user)
        target = _jenis_data('TBL_TANGGAL')

        client.post(reverse('home_pmde_auto_assign_pic'))

        pic = PIC.objects.get(
            tipe=PIC.TipePIC.PMDE, id_sub_jenis_data_ilap=target, id_user=pic_user
        )
        assert pic.start_date == date(2015, 1, 1)
        assert pic.end_date is None

    def test_audit_fields_still_record_today(self, client):
        """Tanggal Mulai tetap, tapi kolom audit tetap kapan barisnya dibuat."""
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_AUDIT'), pic_user)
        target = _jenis_data('TBL_AUDIT')

        client.post(reverse('home_pmde_auto_assign_pic'))

        pic = PIC.objects.get(
            tipe=PIC.TipePIC.PMDE, id_sub_jenis_data_ilap=target, id_user=pic_user
        )
        assert pic.create_date == timezone.now().date()
        assert pic.create_by

    def test_preview_shows_the_fixed_date(self, client):
        _admin_pmde(client)
        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['start_date'] == '01-01-2015'

    def test_closed_pic_on_the_same_date_is_not_duplicated(self, client):
        """Form assign manual menolak kombinasi user + sub jenis + start date yang
        sama, jadi jalur otomatis tidak boleh membuatnya diam-diam."""
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_BENTROK'), pic_user)
        target = _jenis_data('TBL_BENTROK')
        PICFactory(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=target,
            id_user=pic_user,
            start_date=date(2015, 1, 1),
            end_date=date(2020, 12, 31),
        )

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 0
        assert data['total_bentrok_tanggal'] == 1

        client.post(reverse('home_pmde_auto_assign_pic'))
        assert PIC.objects.filter(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=target,
            id_user=pic_user,
            start_date=date(2015, 1, 1),
        ).count() == 1

    def test_closed_pic_of_another_user_still_allows_assign(self, client):
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_LAIN'), pic_user)
        target = _jenis_data('TBL_LAIN')
        PICFactory(
            tipe=PIC.TipePIC.PMDE,
            id_sub_jenis_data_ilap=target,
            id_user=UserFactory(),
            start_date=date(2015, 1, 1),
            end_date=date(2020, 12, 31),
        )

        data = json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)
        assert data['total_assign'] == 1
        assert data['total_bentrok_tanggal'] == 0


@pytest.mark.django_db
class TestAutoAssignPropagation:
    def test_open_tiket_receives_the_pic(self, client):
        """PIC baru harus ikut menempel ke tiket yang masih berjalan.

        Sama seperti assign manual lewat PICCreateView; tanpa ini baris PIC ada
        tapi tiketnya tetap muncul di 'Tiket ... Belum Punya PIC'.
        """
        _admin_pmde(client)
        pic_user = UserFactory()
        _pic_pmde_aktif(_jenis_data('TBL_TIKET'), pic_user)
        target = _jenis_data('TBL_TIKET')
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


@pytest.mark.django_db
class TestAutoAssignRincianDilewati:
    """Preview merinci setiap baris yang dilewati, dikelompokkan per Nama Tabel I."""

    def _preview(self, client):
        return json.loads(client.get(reverse('home_pmde_auto_assign_pic_preview')).content)

    def test_ambigu_lists_each_pic_and_its_source_rows(self, client):
        _admin_pmde(client)
        user_a = UserFactory(first_name='Ani', last_name='', username='ani')
        user_b = UserFactory(first_name='Budi', last_name='', username='budi')
        sumber_a = _jenis_data('TBL_DUA')
        sumber_b = _jenis_data('TBL_DUA')
        _pic_pmde_aktif(sumber_a, user_a)
        _pic_pmde_aktif(sumber_b, user_b)
        _jenis_data('TBL_DUA')

        group = self._preview(client)['ambigu'][0]
        pic = {p['nama']: p['sumber'] for p in group['pic']}
        assert pic == {
            'Ani (ani)': [sumber_a.id_sub_jenis_data],
            'Budi (budi)': [sumber_b.id_sub_jenis_data],
        }

    def test_rows_of_one_table_share_one_group(self, client):
        _admin_pmde(client)
        _pic_pmde_aktif(_jenis_data('TBL_X'), UserFactory())
        _pic_pmde_aktif(_jenis_data('TBL_X'), UserFactory())
        _jenis_data('TBL_X')
        _jenis_data('tbl_x ')

        data = self._preview(client)
        assert data['total_ambigu'] == 2
        assert len(data['ambigu']) == 1
        assert len(data['ambigu'][0]['sub_jenis_data']) == 2

    def test_tanpa_rujukan_is_not_truncated(self, client):
        _admin_pmde(client)
        for i in range(60):
            _jenis_data(f'TBL_KOSONG_{i:02d}')

        data = self._preview(client)
        assert data['total_tanpa_rujukan'] == 60
        assert len(data['tanpa_rujukan']) == 60
        assert data['tanpa_rujukan'][0]['nama_tabel_I'] == 'TBL_KOSONG_00'

    def test_tanpa_tabel_lists_the_rows(self, client):
        _admin_pmde(client)
        target = _jenis_data('')

        data = self._preview(client)
        assert [r['id_sub_jenis_data'] for r in data['tanpa_tabel']] == [target.id_sub_jenis_data]
