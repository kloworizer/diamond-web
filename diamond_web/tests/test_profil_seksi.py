"""Tests for the Ringkasan Seksi page.

A row of the page is a Profil PIC page laid flat, so the tests pin two things:
the figures agree with the tiles of the Profil PIC page they link to, and the
page is scoped the way those pages are — by the line of supervision.
"""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)


# The seeded database ships staff in every group, so the people these tests
# make carry a name no seeded user can, and the assertions look for them alone.
TOKEN = 'Zzqseksi'


def _in_groups(*names, **kwargs):
    user = UserFactory(**kwargs)
    for name in names:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def _staff(last_name, seksi='user_pide'):
    return _in_groups(seksi, first_name=TOKEN, last_name=last_name)


def _wilayah(deskripsi):
    from diamond_web.models.kategori_wilayah import KategoriWilayah

    return KategoriWilayah.objects.get_or_create(deskripsi=deskripsi)[0]


def _pic_of(user, nama_tabel='KPDE_X', ilap=None, tipe='PIDE', end_date=None):
    jenis_data = JenisDataILAPFactory(
        nama_tabel_I=nama_tabel, **({'id_ilap': ilap} if ilap else {})
    )
    PICFactory(
        id_user=user, id_sub_jenis_data_ilap=jenis_data, tipe=tipe, end_date=end_date
    )
    return jenis_data


def _prioritas(jenis_data, tahun=None):
    tahun = tahun or date.today().year
    return JenisPrioritasDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        start_date=date(tahun, 1, 1),
        end_date=date(tahun, 12, 31),
        tahun=str(tahun),
    )


def _rows(client, kode='pide'):
    resp = client.get(reverse('profil_seksi_detail', args=[kode]))
    assert resp.status_code == 200
    return [r for r in resp.context['rows'] if r['nama'].startswith(TOKEN)]


def _row(client, user, kode='pide'):
    return next(r for r in _rows(client, kode) if r['user'].pk == user.pk)


@pytest.mark.django_db
class TestAccess:
    def test_requires_login(self, client):
        resp = client.get(reverse('profil_seksi_detail', args=['pide']))
        assert resp.status_code == 302

    def test_unknown_seksi_is_404(self, client):
        client.force_login(_in_groups('admin'))
        resp = client.get(reverse('profil_seksi_detail', args=['xyz']))
        assert resp.status_code == 404

    def test_kode_matches_case_insensitively(self, client):
        client.force_login(_in_groups('admin'))
        resp = client.get(reverse('profil_seksi_detail', args=['PiDe']))
        assert resp.status_code == 200
        assert resp.context['seksi']['kode'] == 'PIDE'

    @pytest.mark.parametrize('group', ['admin', 'kasi_pide', 'admin_pide'])
    def test_supervisors_may_open(self, client, group):
        client.force_login(_in_groups(group))
        resp = client.get(reverse('profil_seksi_detail', args=['pide']))
        assert resp.status_code == 200

    def test_superuser_may_open(self, client):
        client.force_login(UserFactory(is_superuser=True))
        resp = client.get(reverse('profil_seksi_detail', args=['pmde']))
        assert resp.status_code == 200

    @pytest.mark.parametrize('group', ['user_pide', 'kasi_pmde', 'admin_p3de'])
    def test_others_are_refused(self, client, group):
        client.force_login(_in_groups(group))
        resp = client.get(reverse('profil_seksi_detail', args=['pide']))
        assert resp.status_code == 403

    def test_directory_links_only_the_seksi_the_viewer_may_open(self, client):
        client.force_login(_in_groups('kasi_pide'))
        html = client.get(reverse('profil_ilap_list')).content.decode()

        assert reverse('profil_seksi_detail', args=['pide']) in html
        assert reverse('profil_seksi_detail', args=['p3de']) not in html
        assert reverse('profil_seksi_detail', args=['pmde']) not in html


@pytest.mark.django_db
class TestRows:
    @pytest.fixture(autouse=True)
    def _admin(self, client):
        client.force_login(_in_groups('admin'))

    def test_lists_only_the_active_staff_of_the_seksi_by_name(self, client):
        _staff('Zulkifli')
        _staff('Abdullah')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pindah', is_active=False)
        _staff('Lain', seksi='user_pmde')

        names = [r['nama'] for r in _rows(client)]

        assert names == [f'{TOKEN} Abdullah', f'{TOKEN} Zulkifli']

    def test_ilap_counted_once_and_split_by_wilayah(self, client):
        user = _staff('Ilap')
        nasional = ILAPFactory(id_kategori_wilayah=_wilayah('Nasional'))
        regional = ILAPFactory(id_kategori_wilayah=_wilayah('Regional'))
        _pic_of(user, ilap=nasional)
        _pic_of(user, ilap=nasional)
        _pic_of(user, ilap=regional)

        row = _row(client, user)

        assert row['ilap'] == 2
        assert row['ilap_wilayah'] == [1, 1, 0]

    def test_jenis_data_and_nama_tabel_counts(self, client):
        user = _staff('Tabel')
        _pic_of(user, nama_tabel='KPDE_A')
        _pic_of(user, nama_tabel='KPDE_A')
        _pic_of(user, nama_tabel='')
        # An ended assignment still counts, as on the Profil PIC page.
        _pic_of(user, nama_tabel='KPDE_B', end_date=date(2020, 1, 1))

        row = _row(client, user)

        assert row['jenis_data'] == 4
        assert row['nama_tabel'] == 2

    def test_prioritas_counts_only_the_current_year(self, client):
        user = _staff('Prioritas')
        _prioritas(_pic_of(user, nama_tabel='KPDE_P'))
        _prioritas(_pic_of(user, nama_tabel='KPDE_P'))
        _pic_of(user, nama_tabel='KPDE_BIASA')
        _prioritas(_pic_of(user, nama_tabel='KPDE_LAMPAU'), tahun=date.today().year - 1)

        row = _row(client, user)

        assert row['jenis_data'] == 4
        assert row['nama_tabel'] == 3
        assert row['nama_tabel_prioritas'] == 1

    def test_tiket_split_by_every_status_counting_distinct_tikets(self, client):
        user = _staff('Tiket')
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE)
        TiketPICFactory(id_user=user, id_tiket=TiketFactory(status_tiket=8))
        TiketPICFactory(id_user=user, id_tiket=TiketFactory(status_tiket=8))

        row = _row(client, user)

        assert row['tiket'] == 3
        assert row['tiket_status'] == [1, 0, 0, 0, 0, 0, 0, 2]

    def test_person_without_work_gets_zeros(self, client):
        user = _staff('Kosong')

        row = _row(client, user)

        assert row['ilap'] == row['jenis_data'] == row['nama_tabel'] == row['tiket'] == 0
        assert row['ilap_wilayah'] == [0, 0, 0]
        assert row['tiket_status'] == [0] * 8

    def test_figures_agree_with_the_profil_pic_tiles(self, client):
        user = _staff('Sama')
        _pic_of(user, ilap=ILAPFactory(id_kategori_wilayah=_wilayah('Internasional')))
        _pic_of(user, nama_tabel='KPDE_S')
        TiketPICFactory(id_user=user, id_tiket=TiketFactory(status_tiket=6))

        row = _row(client, user)
        pic = client.get(reverse('profil_pic_detail', args=[user.username])).context

        assert row['ilap'] == len(pic['ilap_list'])
        assert row['jenis_data'] == len(pic['jenis_data_list'])
        assert row['nama_tabel'] == len(pic['nama_tabel_list'])
        assert row['tiket'] == pic['tiket_total']

    def test_total_counts_shared_things_once(self, client):
        """Two people on one ILAP and one tiket: the seksi holds one of each."""
        from diamond_web.views.profil_seksi import build_ringkasan_seksi

        a, b = _staff('Satu'), _staff('Dua')
        ilap = ILAPFactory(id_kategori_wilayah=_wilayah('Nasional'))
        _prioritas(_pic_of(a, ilap=ilap, nama_tabel='KPDE_BERSAMA'))
        _pic_of(b, ilap=ilap, nama_tabel='KPDE_BERSAMA')
        tiket = TiketFactory(status_tiket=5)
        TiketPICFactory(id_tiket=tiket, id_user=a, role=TiketPIC.Role.PIDE)
        TiketPICFactory(id_tiket=tiket, id_user=b, role=TiketPIC.Role.PIDE)

        entries = [{'user': u, 'nama': u.get_full_name()} for u in (a, b)]
        rows, total = build_ringkasan_seksi(entries)

        assert [r['ilap'] for r in rows] == [1, 1]
        assert total['ilap'] == 1
        assert total['ilap_wilayah'] == [1, 0, 0]
        assert total['jenis_data'] == 2
        assert total['nama_tabel'] == 1
        assert total['nama_tabel_prioritas'] == 1
        assert total['tiket'] == 1
        assert total['tiket_status'][4] == 1

    def test_page_renders_names_as_profile_links(self, client):
        user = _staff('Tautan')

        html = client.get(reverse('profil_seksi_detail', args=['pide'])).content.decode()

        assert reverse('profil_pic_detail', args=[user.username]) in html
