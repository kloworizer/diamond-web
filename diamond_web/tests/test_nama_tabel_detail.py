"""Tests for the Nama Tabel detail page and its tiket DataTables endpoint.

A nama tabel is not a row of its own: it is a field repeated across every sub
jenis data feeding the same bank data table, and one table routinely collects
dozens of them. These tests pin the consequence — the page is keyed by the name
and aggregates across all of them, rather than being a second view of a single
sub jenis data.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils.dateformat import format as date_format

from diamond_web.tests.conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    PeriodeJenisDataFactory,
    PICFactory,
    TiketFactory,
    UserFactory,
)


def _logged_in(client):
    """Any logged in user: the page is open to everyone, like the ILAP profil."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    client.force_login(user)
    return user


def _tiket_in(nama_tabel, ilap=None, **kwargs):
    """A tiket whose sub jenis data lands in `nama_tabel`."""
    jenis_data = JenisDataILAPFactory(
        nama_tabel_I=nama_tabel, **({'id_ilap': ilap} if ilap else {})
    )
    periode_data = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
    return TiketFactory(id_periode_data=periode_data, **kwargs)


@pytest.mark.django_db
class TestNamaTabelDetailView:
    def test_requires_login(self, client):
        JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        resp = client.get(reverse('nama_tabel_detail', args=['KPDE_X']))
        assert resp.status_code == 302

    def test_open_to_any_logged_in_user(self, client):
        """No group needed: the catalogue behind the name is not restricted."""
        JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        client.force_login(UserFactory())
        assert client.get(reverse('nama_tabel_detail', args=['KPDE_X'])).status_code == 200

    def test_unknown_nama_tabel_is_404(self, client):
        _logged_in(client)
        assert client.get(
            reverse('nama_tabel_detail', args=['KPDE_TIDAK_ADA'])
        ).status_code == 404

    def test_aggregates_every_jenis_data_sharing_the_name(self, client):
        """The whole point of the page: one table, many sub jenis data."""
        ilap = ILAPFactory()
        for n in range(3):
            JenisDataILAPFactory(
                nama_tabel_I='KPDE_X', id_ilap=ilap, nama_sub_jenis_data=f'Bagian {n}'
            )
        JenisDataILAPFactory(nama_tabel_I='KPDE_LAIN')
        _logged_in(client)

        context = client.get(reverse('nama_tabel_detail', args=['KPDE_X'])).context
        assert context['nama_tabel'] == 'KPDE_X'
        assert context['jenis_data_total'] == 3
        assert [i.id_ilap for i in context['ilap_list']] == [ilap.id_ilap]

    def test_sub_jenis_data_list_is_distinct_by_name(self, client):
        """One table collects the same name many times over; the list shows it once."""
        for _ in range(4):
            JenisDataILAPFactory(nama_tabel_I='KPDE_X', nama_sub_jenis_data='Rekapitulasi')
        JenisDataILAPFactory(nama_tabel_I='KPDE_X', nama_sub_jenis_data='Penjualan')
        _logged_in(client)

        context = client.get(reverse('nama_tabel_detail', args=['KPDE_X'])).context
        entries = context['jenis_data_list']
        assert [e['nama'] for e in entries] == ['Penjualan', 'Rekapitulasi']
        assert context['jenis_data_total'] == 2
        # The count is what keeps the collapsed list from reading as the whole set.
        assert {e['nama']: e['count'] for e in entries} == {'Rekapitulasi': 4, 'Penjualan': 1}

    def test_distinct_entry_still_links_to_a_sub_jenis_data(self, client):
        first = JenisDataILAPFactory(nama_tabel_I='KPDE_X', nama_sub_jenis_data='Rekapitulasi')
        JenisDataILAPFactory(nama_tabel_I='KPDE_X', nama_sub_jenis_data='Rekapitulasi')
        _logged_in(client)

        resp = client.get(reverse('nama_tabel_detail', args=['KPDE_X']))
        entry = resp.context['jenis_data_list'][0]
        assert entry['jenis_data'].id_sub_jenis_data == first.id_sub_jenis_data
        assert reverse(
            'jenis_data_ilap_profil', args=[first.id_sub_jenis_data]
        ) in resp.content.decode()

    def test_tiket_total_counts_across_the_sub_jenis_data(self, client):
        _tiket_in('KPDE_X')
        _tiket_in('KPDE_X')
        _tiket_in('KPDE_LAIN')
        _logged_in(client)

        context = client.get(reverse('nama_tabel_detail', args=['KPDE_X'])).context
        assert context['tiket_total'] == 2

    def test_lookup_is_case_insensitive_but_shows_the_recorded_name(self, client):
        """The name arrives from a URL, so it is matched loosely and echoed exactly."""
        JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        _logged_in(client)
        resp = client.get(reverse('nama_tabel_detail', args=['kpde_x']))
        assert resp.status_code == 200
        assert resp.context['nama_tabel'] == 'KPDE_X'


@pytest.mark.django_db
class TestNamaTabelPIC:
    """The PIC section: the people behind the sub jenis data feeding the table."""

    def _groups(self, client, nama_tabel='KPDE_X'):
        resp = client.get(reverse('nama_tabel_detail', args=[nama_tabel]))
        return {group['tipe']: group['pics'] for group in resp.context['pic_groups']}

    def test_every_tipe_is_present_even_when_empty(self, client):
        JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        _logged_in(client)

        groups = self._groups(client)
        assert set(groups) == {'P3DE', 'PIDE', 'PMDE'}
        assert all(pics == [] for pics in groups.values())

    def test_pools_pics_across_the_sub_jenis_data_of_the_table(self, client):
        mine = PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
            id_user=UserFactory(first_name='Ani', last_name='Rahayu'),
        )
        PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_LAIN'),
        )
        _logged_in(client)

        assert [p['nama'] for p in self._groups(client)['P3DE']] == [
            mine.id_user.get_full_name()
        ]

    def test_a_person_holding_several_sub_jenis_data_is_listed_once(self, client):
        """One officer covering many feeders would otherwise repeat down the page."""
        user = UserFactory(first_name='Ani', last_name='Rahayu')
        for _ in range(3):
            PICFactory(
                id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
                id_user=user,
            )
        _logged_in(client)

        pics = self._groups(client)['P3DE']
        assert len(pics) == 1
        # The count is what keeps the collapsed entry from reading as one posting.
        assert pics[0]['count'] == 3

    def test_repeat_assignments_to_one_sub_jenis_data_count_once(self, client):
        """The count is of sub jenis data, not of the stretches of time."""
        jenis_data = JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        user = UserFactory()
        PICFactory(id_sub_jenis_data_ilap=jenis_data, id_user=user)
        PICFactory(id_sub_jenis_data_ilap=jenis_data, id_user=user, end_date=None)
        _logged_in(client)

        pics = self._groups(client)['P3DE']
        assert len(pics) == 1 and pics[0]['count'] == 1

    def test_still_active_when_any_assignment_is_open(self, client):
        user = UserFactory()
        PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
            id_user=user,
        )
        PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
            id_user=user,
            end_date=None,
        )
        _logged_in(client)

        assert self._groups(client)['P3DE'][0]['aktif'] is True

    def test_finished_assignments_are_not_active(self, client):
        PICFactory(id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'))
        _logged_in(client)

        assert self._groups(client)['P3DE'][0]['aktif'] is False

    def test_active_people_come_first_then_by_name(self, client):
        def pic(nama, **kwargs):
            PICFactory(
                id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
                id_user=UserFactory(first_name=nama, last_name=''),
                **kwargs,
            )

        pic('Ani')
        pic('Zainal', end_date=None)
        pic('Budi', end_date=None)
        _logged_in(client)

        assert [p['nama'] for p in self._groups(client)['P3DE']] == [
            'Budi', 'Zainal', 'Ani',
        ]

    def test_pics_are_grouped_by_tipe(self, client):
        jenis_data = JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        PICFactory(id_sub_jenis_data_ilap=jenis_data, tipe='PIDE')
        _logged_in(client)

        groups = self._groups(client)
        assert len(groups['PIDE']) == 1
        assert groups['P3DE'] == [] and groups['PMDE'] == []

    def test_names_are_rendered_on_the_page(self, client):
        PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
            id_user=UserFactory(first_name='Ani', last_name='Rahayu'),
        )
        _logged_in(client)

        body = client.get(reverse('nama_tabel_detail', args=['KPDE_X'])).content.decode()
        assert 'PIC Nama Tabel' in body
        assert 'Ani Rahayu' in body

    def test_username_stands_in_when_there_is_no_full_name(self, client):
        user = UserFactory(first_name='', last_name='')
        PICFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(nama_tabel_I='KPDE_X'),
            id_user=user,
        )
        _logged_in(client)

        assert self._groups(client)['P3DE'][0]['nama'] == user.username


@pytest.mark.django_db
class TestNamaTabelTiketData:
    url = 'nama_tabel_tiket_data'

    def _rows(self, client, nama_tabel, **params):
        query = {'draw': '1', 'start': '0', 'length': '10'}
        query.update(params)
        resp = client.get(reverse(self.url, args=[nama_tabel]), query)
        assert resp.status_code == 200
        return resp.json()

    def test_requires_login(self, client):
        JenisDataILAPFactory(nama_tabel_I='KPDE_X')
        resp = client.get(reverse(self.url, args=['KPDE_X']))
        assert resp.status_code == 302

    def test_unknown_nama_tabel_is_404(self, client):
        _logged_in(client)
        assert client.get(reverse(self.url, args=['KPDE_TIDAK_ADA'])).status_code == 404

    def test_lists_only_the_tikets_landing_in_the_table(self, client):
        mine = _tiket_in('KPDE_X')
        _tiket_in('KPDE_LAIN')
        _logged_in(client)

        payload = self._rows(client, 'KPDE_X')
        assert payload['recordsTotal'] == 1
        assert payload['recordsFiltered'] == 1
        assert mine.nomor_tiket in payload['data'][0]['nomor_tiket']

    def test_pools_tikets_from_every_sub_jenis_data_of_the_table(self, client):
        """Two different sub jenis data, one table, one list."""
        first = _tiket_in('KPDE_X')
        second = _tiket_in('KPDE_X')
        _logged_in(client)

        payload = self._rows(client, 'KPDE_X')
        assert payload['recordsTotal'] == 2
        nomor = ' '.join(row['nomor_tiket'] for row in payload['data'])
        assert first.nomor_tiket in nomor and second.nomor_tiket in nomor

    def test_row_carries_the_sub_jenis_data_it_came_from(self, client):
        """With many feeders pooled, the row has to say which one it is."""
        tiket = _tiket_in('KPDE_X')
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        _logged_in(client)

        row = self._rows(client, 'KPDE_X')['data'][0]
        assert jenis_data.id_sub_jenis_data in row['sub_jenis_data']
        assert reverse(
            'jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]
        ) in row['sub_jenis_data']
        assert jenis_data.id_ilap.nama_ilap in row['nama_ilap']
        assert reverse('tiket_detail', args=[tiket.pk]) in row['actions']

    def test_search_matches_nomor_tiket(self, client):
        tiket = _tiket_in('KPDE_X')
        _tiket_in('KPDE_X')
        _logged_in(client)

        payload = self._rows(client, 'KPDE_X', **{'search[value]': tiket.nomor_tiket})
        assert payload['recordsTotal'] == 2
        assert payload['recordsFiltered'] == 1

    def test_search_matches_the_sub_jenis_data_name(self, client):
        """The pooled rows differ by sub jenis data, so that is worth searching."""
        jenis_data = JenisDataILAPFactory(
            nama_tabel_I='KPDE_X', nama_sub_jenis_data='Penjualan Purwakarta'
        )
        TiketFactory(id_periode_data=PeriodeJenisDataFactory(
            id_sub_jenis_data_ilap=jenis_data))
        _tiket_in('KPDE_X')
        _logged_in(client)

        assert self._rows(
            client, 'KPDE_X', **{'search[value]': 'purwakarta'}
        )['recordsFiltered'] == 1

    def test_ordering_by_nomor_tiket_descends(self, client):
        _tiket_in('KPDE_X')
        _tiket_in('KPDE_X')
        _logged_in(client)

        payload = self._rows(client, 'KPDE_X', **{
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        nomor = [row['nomor_tiket'] for row in payload['data']]
        assert nomor == sorted(nomor, reverse=True)

    def test_invalid_order_column_falls_back(self, client):
        _tiket_in('KPDE_X')
        _logged_in(client)
        assert self._rows(client, 'KPDE_X', **{'order[0][column]': 'abc'})['draw'] == 1

    def test_tgl_terima_dip_is_a_date_without_a_time(self, client):
        """The clock time a DIP arrived is noise in a list this wide."""
        tiket = _tiket_in('KPDE_X')
        _logged_in(client)

        shown = self._rows(client, 'KPDE_X')['data'][0]['tgl_terima_dip']
        assert shown == date_format(tiket.tgl_terima_dip, 'd M Y')
        assert ':' not in shown
