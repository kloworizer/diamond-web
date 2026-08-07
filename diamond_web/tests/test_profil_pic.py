"""Tests for the Profil PIC page and its tiket DataTables endpoint.

The page reads from a person towards their work, which is the opposite
direction of every other catalogue page. These tests pin that: the assignments
of one person are gathered across ILAPs, sub jenis data and bank data tables,
collapsed once per thing rather than once per assignment, and assignments that
have ended stay on the page instead of being dropped.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    PeriodeJenisDataFactory,
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)


def _logged_in(client):
    """Any logged in user: the page is open to everyone, like the ILAP profil."""
    user = UserFactory()
    client.force_login(user)
    return user


def _wilayah(deskripsi):
    """The KategoriWilayah named `deskripsi`, reusing the seeded row.

    ``deskripsi`` is unique and the seed already ships Nasional, Regional and
    Internasional, so these have to be fetched rather than made.
    """
    from diamond_web.models.kategori_wilayah import KategoriWilayah

    return KategoriWilayah.objects.get_or_create(deskripsi=deskripsi)[0]


def _pic_of(user, nama_tabel='KPDE_X', ilap=None, tipe='P3DE', end_date=None):
    """Make `user` the PIC of a fresh sub jenis data landing in `nama_tabel`."""
    jenis_data = JenisDataILAPFactory(
        nama_tabel_I=nama_tabel, **({'id_ilap': ilap} if ilap else {})
    )
    return PICFactory(
        id_user=user, id_sub_jenis_data_ilap=jenis_data, tipe=tipe, end_date=end_date
    )


@pytest.mark.django_db
class TestProfilPICDetailView:
    def test_requires_login(self, client):
        user = UserFactory()
        resp = client.get(reverse('profil_pic_detail', args=[user.username]))
        assert resp.status_code == 302

    def test_open_to_any_logged_in_user(self, client):
        """No group needed: who is PIC of what is not restricted knowledge."""
        pic_user = UserFactory()
        _logged_in(client)
        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))
        assert resp.status_code == 200

    def test_unknown_username_is_404(self, client):
        _logged_in(client)
        resp = client.get(reverse('profil_pic_detail', args=['tidak-ada']))
        assert resp.status_code == 404

    def test_username_matches_case_insensitively(self, client):
        """The username arrives from a URL a reader may have typed by hand."""
        pic_user = UserFactory(username='Budi')
        _logged_in(client)
        resp = client.get(reverse('profil_pic_detail', args=['BUDI']))
        assert resp.status_code == 200
        assert resp.context['pic_user'].pk == pic_user.pk

    def test_shows_name_and_seksi(self, client):
        pic_user = UserFactory(first_name='Siti', last_name='Rahayu')
        group, _ = Group.objects.get_or_create(name='user_pide')
        pic_user.groups.add(group)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        assert resp.context['display_name'] == 'Siti Rahayu'
        assert resp.context['initials'] == 'SR'
        # The group name is a permission check; the page names the unit.
        assert resp.context['seksi_list'] == ['Seksi PIDE']
        assert b'Siti Rahayu' in resp.content

    def test_account_details_are_not_shown(self, client):
        """The page is about the work, not about the account behind it."""
        pic_user = UserFactory(email='siti@pajak.go.id')
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        assert b'siti@pajak.go.id' not in resp.content
        assert b'Bergabung' not in resp.content
        assert b'Login terakhir' not in resp.content

    def test_falls_back_to_username_when_no_full_name(self, client):
        pic_user = UserFactory(username='anon', first_name='', last_name='')
        _logged_in(client)
        resp = client.get(reverse('profil_pic_detail', args=['anon']))
        assert resp.context['display_name'] == 'anon'

    def test_unknown_group_is_shown_as_recorded(self, client):
        """A group nobody has named yet must not vanish from the page."""
        pic_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='seksi_baru')
        pic_user.groups.add(group)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))
        assert resp.context['seksi_list'] == ['seksi_baru']

    def test_ilap_collapsed_once_and_counted(self, client):
        """Two sub jenis data of one ILAP make one entry counting both."""
        pic_user = UserFactory()
        ilap = ILAPFactory()
        _pic_of(pic_user, ilap=ilap, end_date=None)
        _pic_of(pic_user, ilap=ilap, end_date=None)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        ilap_list = resp.context['ilap_list']
        assert len(ilap_list) == 1
        assert ilap_list[0]['ilap'].pk == ilap.pk
        assert ilap_list[0]['count'] == 2
        # The sub jenis data behind them stay two entries of their own.
        assert len(resp.context['jenis_data_list']) == 2

    def test_nama_tabel_collapsed_and_blank_ones_left_out(self, client):
        """A blank nama tabel is a sub jenis data with no table, not a table."""
        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_A', end_date=None)
        _pic_of(pic_user, nama_tabel='KPDE_A', end_date=None)
        _pic_of(pic_user, nama_tabel='', end_date=None)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        nama_tabel_list = resp.context['nama_tabel_list']
        assert [e['nama_tabel'] for e in nama_tabel_list] == ['KPDE_A']
        assert nama_tabel_list[0]['count'] == 2

    def test_ended_assignments_stay_but_are_marked_inactive(self, client):
        """How a table used to be held is part of what the page is for."""
        import datetime

        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_LAMA', end_date=datetime.date(2024, 1, 1))
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        assert resp.context['nama_tabel_list'][0]['nama_tabel'] == 'KPDE_LAMA'
        assert resp.context['nama_tabel_list'][0]['aktif'] is False
        assert resp.context['ilap_list'][0]['aktif'] is False
        assert resp.context['jenis_data_list'][0]['aktif'] is False

    def test_active_entries_sort_ahead_of_ended_ones(self, client):
        import datetime

        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='ZZZ_AKTIF', end_date=None)
        _pic_of(pic_user, nama_tabel='AAA_SELESAI', end_date=datetime.date(2024, 1, 1))
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        names = [e['nama_tabel'] for e in resp.context['nama_tabel_list']]
        assert names == ['ZZZ_AKTIF', 'AAA_SELESAI']

    def test_assignments_of_every_tipe_are_gathered(self, client):
        """The page collects the person's work whatever tipe it was held under."""
        import datetime

        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_PIDE', tipe='PIDE', end_date=None)
        _pic_of(
            pic_user, nama_tabel='KPDE_PMDE', tipe='PMDE',
            end_date=datetime.date(2024, 1, 1),
        )
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        aktif = {e['nama_tabel']: e['aktif'] for e in resp.context['nama_tabel_list']}
        assert aktif == {'KPDE_PIDE': True, 'KPDE_PMDE': False}

    def test_tiket_total_counts_distinct_tikets(self, client):
        """Two roles on one tiket is one tiket, even though it is two rows."""
        pic_user = UserFactory()
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=TiketPIC.Role.P3DE)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=TiketPIC.Role.PIDE)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))
        assert resp.context['tiket_total'] == 1

    def test_page_without_any_assignment_still_renders(self, client):
        pic_user = UserFactory()
        _logged_in(client)

        resp = client.get(reverse('profil_pic_detail', args=[pic_user.username]))

        assert resp.status_code == 200
        assert resp.context['ilap_list'] == []
        assert resp.context['jenis_data_list'] == []
        assert resp.context['nama_tabel_list'] == []
        assert resp.context['tiket_total'] == 0


@pytest.mark.django_db
class TestSummaryBreakdowns:
    """The three splits under the summary tiles: what the totals are made of."""

    def _context(self, client, pic_user):
        return client.get(
            reverse('profil_pic_detail', args=[pic_user.username])
        ).context

    def test_ilap_split_by_kategori_wilayah(self, client):
        pic_user = UserFactory()
        for kategori, jumlah in (('Nasional', 1), ('Regional', 2), ('Internasional', 1)):
            wilayah = _wilayah(kategori)
            for _ in range(jumlah):
                _pic_of(pic_user, ilap=ILAPFactory(id_kategori_wilayah=wilayah))
        _logged_in(client)

        rows = self._context(client, pic_user)['ilap_wilayah']

        # Named in the order the reference table lists them, not by count.
        assert [(r['label'], r['count']) for r in rows] == [
            ('Nasional', 1), ('Regional', 2), ('Internasional', 1)
        ]
        assert sum(r['count'] for r in rows) == 4

    def test_ilap_split_leaves_out_kategori_nobody_holds(self, client):
        pic_user = UserFactory()
        wilayah = _wilayah('Regional')
        _pic_of(pic_user, ilap=ILAPFactory(id_kategori_wilayah=wilayah))
        _logged_in(client)

        rows = self._context(client, pic_user)['ilap_wilayah']

        assert [r['label'] for r in rows] == ['Regional']

    def test_an_unnamed_kategori_sorts_after_the_three(self, client):
        pic_user = UserFactory()
        for kategori in ('Zona Khusus', 'Nasional'):
            _pic_of(
                pic_user,
                ilap=ILAPFactory(
                    id_kategori_wilayah=_wilayah(kategori)
                ),
            )
        _logged_in(client)

        rows = self._context(client, pic_user)['ilap_wilayah']

        assert [r['label'] for r in rows] == ['Nasional', 'Zona Khusus']

    def test_nama_tabel_with_a_recent_tiket_is_aktif(self, client):
        import datetime

        pic_user = UserFactory()
        pic = _pic_of(pic_user, nama_tabel='KPDE_AKTIF')
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap
        )
        TiketFactory(
            id_periode_data=periode,
            tgl_terima_dip=datetime.datetime.now() - datetime.timedelta(days=30),
        )
        _logged_in(client)

        aktivitas = self._context(client, pic_user)['nama_tabel_aktivitas']

        assert aktivitas == {'aktif': 1, 'tidak_aktif': 0, 'tahun': 2}

    def test_nama_tabel_whose_last_tiket_is_older_is_tidak_aktif(self, client):
        import datetime

        pic_user = UserFactory()
        pic = _pic_of(pic_user, nama_tabel='KPDE_DORMANT')
        periode = PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap
        )
        TiketFactory(
            id_periode_data=periode,
            tgl_terima_dip=datetime.datetime.now() - datetime.timedelta(days=365 * 3),
        )
        _logged_in(client)

        aktivitas = self._context(client, pic_user)['nama_tabel_aktivitas']

        assert aktivitas['aktif'] == 0
        assert aktivitas['tidak_aktif'] == 1

    def test_nama_tabel_without_any_tiket_is_tidak_aktif(self, client):
        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_KOSONG')
        _logged_in(client)

        aktivitas = self._context(client, pic_user)['nama_tabel_aktivitas']

        assert aktivitas['aktif'] == 0
        assert aktivitas['tidak_aktif'] == 1

    def test_a_tiket_from_another_pic_still_makes_the_table_aktif(self, client):
        """Whether data flows into a table is a fact about the table."""
        import datetime

        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_SHARED')
        # A second sub jenis data feeding the same table, held by nobody here.
        other = JenisDataILAPFactory(nama_tabel_I='KPDE_SHARED')
        TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=other),
            tgl_terima_dip=datetime.datetime.now() - datetime.timedelta(days=10),
        )
        _logged_in(client)

        aktivitas = self._context(client, pic_user)['nama_tabel_aktivitas']

        assert aktivitas['aktif'] == 1

    def test_tiket_split_by_status_in_workflow_order(self, client):
        pic_user = UserFactory()
        for status in (8, 1, 6):
            TiketPICFactory(id_user=pic_user, id_tiket=TiketFactory(status_tiket=status))
        _logged_in(client)

        rows = self._context(client, pic_user)['tiket_status']

        assert [r['label'] for r in rows] == [
            'Direkam', 'Pengendalian Mutu', 'Selesai'
        ]
        assert all(r['count'] == 1 for r in rows)

    def test_tiket_split_counts_distinct_tikets(self, client):
        """Two roles on one tiket is one tiket, so the rows add up to the total."""
        pic_user = UserFactory()
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=TiketPIC.Role.P3DE)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=TiketPIC.Role.PIDE)
        _logged_in(client)

        context = self._context(client, pic_user)

        assert [r['count'] for r in context['tiket_status']] == [1]
        assert sum(r['count'] for r in context['tiket_status']) == context['tiket_total']

    def test_tiket_split_carries_the_status_colour(self, client):
        pic_user = UserFactory()
        TiketPICFactory(id_user=pic_user, id_tiket=TiketFactory(status_tiket=8))
        _logged_in(client)

        rows = self._context(client, pic_user)['tiket_status']

        # The badge class for Selesai is "bg-success"; a dot wants the
        # background alone, never a trailing text colour.
        assert rows[0]['dot_class'] == 'bg-success'
        assert ' ' not in rows[0]['dot_class']

    def test_breakdowns_are_empty_for_a_person_with_no_work(self, client):
        pic_user = UserFactory()
        _logged_in(client)

        context = self._context(client, pic_user)

        assert context['ilap_wilayah'] == []
        assert context['tiket_status'] == []
        assert context['nama_tabel_aktivitas']['aktif'] == 0
        assert context['nama_tabel_aktivitas']['tidak_aktif'] == 0


@pytest.mark.django_db
class TestProfilPICTiketData:
    def _tiket_for(self, pic_user, nomor_tiket='T-001', role=TiketPIC.Role.P3DE):
        jenis_data = JenisDataILAPFactory()
        periode_data = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
        tiket = TiketFactory(id_periode_data=periode_data, nomor_tiket=nomor_tiket)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=role)
        return tiket

    def test_requires_login(self, client):
        user = UserFactory()
        resp = client.get(reverse('profil_pic_tiket_data', args=[user.username]))
        assert resp.status_code == 302

    def test_unknown_username_is_404(self, client):
        _logged_in(client)
        resp = client.get(reverse('profil_pic_tiket_data', args=['tidak-ada']))
        assert resp.status_code == 404

    def test_lists_only_the_tikets_of_this_person(self, client):
        pic_user = UserFactory()
        self._tiket_for(pic_user, nomor_tiket='T-MINE')
        self._tiket_for(UserFactory(), nomor_tiket='T-THEIRS')
        _logged_in(client)

        resp = client.get(reverse('profil_pic_tiket_data', args=[pic_user.username]))
        payload = json.loads(resp.content)

        assert payload['recordsTotal'] == 1
        assert payload['data'][0]['nomor_tiket'] == 'T-MINE'

    def test_row_carries_the_role_of_the_assignment(self, client):
        pic_user = UserFactory()
        self._tiket_for(pic_user, role=TiketPIC.Role.PMDE)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_tiket_data', args=[pic_user.username]))
        payload = json.loads(resp.content)

        assert 'PMDE' in payload['data'][0]['peran']

    def test_same_tiket_under_two_roles_is_two_rows(self, client):
        """Each assignment is what a row is about, which is why it has a peran."""
        pic_user = UserFactory()
        tiket = self._tiket_for(pic_user, role=TiketPIC.Role.P3DE)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user, role=TiketPIC.Role.PIDE)
        _logged_in(client)

        resp = client.get(reverse('profil_pic_tiket_data', args=[pic_user.username]))
        payload = json.loads(resp.content)

        assert payload['recordsTotal'] == 2

    def test_search_filters_by_nomor_tiket(self, client):
        pic_user = UserFactory()
        self._tiket_for(pic_user, nomor_tiket='T-AAA')
        self._tiket_for(pic_user, nomor_tiket='T-BBB')
        _logged_in(client)

        resp = client.get(
            reverse('profil_pic_tiket_data', args=[pic_user.username]),
            {'search[value]': 'AAA'},
        )
        payload = json.loads(resp.content)

        assert payload['recordsTotal'] == 2
        assert payload['recordsFiltered'] == 1
        assert payload['data'][0]['nomor_tiket'] == 'T-AAA'

    def test_rows_link_to_the_related_profil_pages(self, client):
        pic_user = UserFactory()
        tiket = self._tiket_for(pic_user)
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        _logged_in(client)

        resp = client.get(reverse('profil_pic_tiket_data', args=[pic_user.username]))
        row = json.loads(resp.content)['data'][0]

        assert reverse(
            'jenis_data_ilap_profil', args=[sub_jenis_data.id_sub_jenis_data]
        ) in row['sub_jenis_data']
        assert reverse(
            'profil_ilap_detail', args=[sub_jenis_data.id_ilap.id_ilap]
        ) in row['nama_ilap']
        assert reverse('tiket_detail', args=[tiket.pk]) in row['actions']


@pytest.mark.django_db
class TestNamesLinkToProfilPIC:
    """Every page that prints a PIC name sends the reader to the same page."""

    def test_nama_tabel_detail_links_its_pic_names(self, client):
        pic_user = UserFactory()
        _pic_of(pic_user, nama_tabel='KPDE_LINK', end_date=None)
        _logged_in(client)

        resp = client.get(reverse('nama_tabel_detail', args=['KPDE_LINK']))

        assert reverse(
            'profil_pic_detail', args=[pic_user.username]
        ).encode() in resp.content

    def test_jenis_data_profil_links_its_pic_names(self, client):
        pic_user = UserFactory()
        pic = _pic_of(pic_user, end_date=None)
        _logged_in(client)

        resp = client.get(reverse(
            'jenis_data_ilap_profil',
            args=[pic.id_sub_jenis_data_ilap.id_sub_jenis_data],
        ))

        assert reverse(
            'profil_pic_detail', args=[pic_user.username]
        ).encode() in resp.content

    def test_pic_list_endpoint_links_the_full_name(self, client):
        """The PIC admin lists are the densest table of names in the app."""
        admin = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin')
        admin.groups.add(group)
        client.force_login(admin)

        pic_user = UserFactory()
        _pic_of(pic_user, tipe='PIDE', end_date=None)

        resp = client.get(reverse('pic_pide_data'))
        payload = json.loads(resp.content)

        assert reverse(
            'profil_pic_detail', args=[pic_user.username]
        ) in payload['data'][0]['full_name']
