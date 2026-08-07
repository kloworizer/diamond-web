"""Tests for the Profil PDE staff directory and the scoped PIC search.

Two features that pull in opposite directions and are deliberately allowed to:
the directory on the Profil PDE page lists the staff of all three seksi to
anyone who may open that page, while the header search only finds the people the
searcher supervises. The first answers "who works on this data", the second is
looking a colleague up by name, and only the second follows the line of
supervision.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.tests.conftest import UserFactory


def _in_groups(*names, **kwargs):
    """A user in every named group."""
    user = UserFactory(**kwargs)
    for name in names:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def _suggest(client, term):
    return client.get(reverse('navbar_search'), {'q': term}).json()['suggestions']


def _pic_suggestions(client, term):
    return [s for s in _suggest(client, term) if s['type'] == 'user']


# The seeded database ships staff in every group, with faker names, so the tests
# below name their own people after a token no seeded user can carry and search
# for that. Without it an assertion on the whole result list would be testing
# the seed data as much as the scope rule.
TOKEN = 'Zzqtest'


def _names_in(column):
    return [entry['nama'] for entry in column['users']]


@pytest.mark.django_db
class TestSeksiDirectory:
    def test_each_seksi_lists_its_own_staff(self, client):
        _in_groups('user_p3de', first_name=TOKEN, last_name='P3de')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pide')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Pmde')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        assert list(columns) == ['P3DE', 'PIDE', 'PMDE']
        # Each of the three lands in its own column and in no other.
        for kode in ('P3DE', 'PIDE', 'PMDE'):
            ours = [n for n in _names_in(columns[kode]) if n.startswith(TOKEN)]
            assert ours == [f'{TOKEN} {kode.capitalize()}']

    def test_entries_are_sorted_by_name(self, client):
        _in_groups('user_pide', first_name=TOKEN, last_name='Zulkifli')
        _in_groups('user_pide', first_name=TOKEN, last_name='Abdullah')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        ours = [n for n in _names_in(columns['PIDE']) if n.startswith(TOKEN)]
        assert ours == [f'{TOKEN} Abdullah', f'{TOKEN} Zulkifli']

    def test_inactive_accounts_are_left_out(self, client):
        _in_groups('user_pide', first_name=TOKEN, last_name='Aktif')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pindah', is_active=False)
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        ours = [n for n in _names_in(columns['PIDE']) if n.startswith(TOKEN)]
        assert ours == [f'{TOKEN} Aktif']

    def test_administrators_are_left_out_of_every_column(self, client):
        """An admin sits in all three staff groups, so reading them alone would
        put the same person at the top of all three columns."""
        _in_groups('admin', 'user_p3de', 'user_pide', 'user_pmde',
                   first_name=TOKEN, last_name='Admin')
        _in_groups('admin_pmde', 'user_pmde', first_name=TOKEN, last_name='AdminPmde')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Pelaksana')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        assert [n for n in _names_in(columns['PMDE']) if n.startswith(TOKEN)] == [
            f'{TOKEN} Pelaksana'
        ]
        for kode in ('P3DE', 'PIDE'):
            assert [n for n in _names_in(columns[kode]) if n.startswith(TOKEN)] == []

    def test_superusers_are_left_out(self, client):
        _in_groups('user_pide', first_name=TOKEN, last_name='Super', is_superuser=True)
        _in_groups('user_pide', first_name=TOKEN, last_name='Pelaksana')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        ours = [n for n in _names_in(columns['PIDE']) if n.startswith(TOKEN)]
        assert ours == [f'{TOKEN} Pelaksana']

    def test_a_kasi_who_is_also_staff_stays_listed(self, client):
        """Unlike an administrator, a kasi belongs to one seksi and holds its data."""
        _in_groups('kasi_pmde', 'user_pmde', first_name=TOKEN, last_name='Kasi')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))
        columns = {c['kode']: c for c in resp.context['seksi_columns']}

        ours = [n for n in _names_in(columns['PMDE']) if n.startswith(TOKEN)]
        assert ours == [f'{TOKEN} Kasi']

    def test_entries_link_to_the_profil_pic_page(self, client):
        staff = _in_groups('user_pide', first_name=TOKEN, last_name='Santoso')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'))

        assert reverse(
            'profil_pic_detail', args=[staff.username]
        ).encode() in resp.content

    def test_directory_is_not_built_for_the_datatables_request(self, client):
        """The ILAP table pages against this same URL and never renders it."""
        _in_groups('user_pide')
        client.force_login(_in_groups('user_p3de'))

        resp = client.get(reverse('profil_ilap_list'), {'format': 'json'})

        assert resp.status_code == 200
        assert 'data' in resp.json()

    def test_page_still_requires_p3de(self, client):
        """Adding the directory must not have widened who may open the page."""
        client.force_login(UserFactory())
        resp = client.get(reverse('profil_ilap_list'))
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestPICSearchScope:
    def test_plain_user_finds_only_themselves(self, client):
        me = _in_groups('user_pmde', first_name=TOKEN, last_name='Rahayu')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Nurbaya')
        client.force_login(me)

        suggestions = _pic_suggestions(client, TOKEN)

        assert [s['label'] for s in suggestions] == [f'{TOKEN} Rahayu']

    def test_kasi_finds_every_user_of_their_seksi(self, client):
        kasi = _in_groups('kasi_pmde', first_name='Kepala', last_name='Pmde')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Rahayu')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Nurbaya')
        client.force_login(kasi)

        labels = {s['label'] for s in _pic_suggestions(client, TOKEN)}

        assert labels == {f'{TOKEN} Rahayu', f'{TOKEN} Nurbaya'}

    def test_kasi_does_not_reach_another_seksi(self, client):
        kasi = _in_groups('kasi_pmde')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pide')
        client.force_login(kasi)

        assert _pic_suggestions(client, TOKEN) == []

    def test_kasi_finds_their_own_account(self, client):
        """A kasi is not a member of the staff group they supervise."""
        kasi = _in_groups('kasi_pide', first_name=TOKEN, last_name='Kasi')
        client.force_login(kasi)

        assert [s['label'] for s in _pic_suggestions(client, TOKEN)] == [f'{TOKEN} Kasi']

    def test_admin_of_a_seksi_reaches_that_seksi(self, client):
        admin_pide = _in_groups('admin_pide')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pide')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Pmde')
        client.force_login(admin_pide)

        labels = {s['label'] for s in _pic_suggestions(client, TOKEN)}

        assert labels == {f'{TOKEN} Pide'}

    def test_global_admin_reaches_everyone(self, client):
        admin = _in_groups('admin')
        _in_groups('user_pide', first_name=TOKEN, last_name='Pide')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Pmde')
        client.force_login(admin)

        labels = {s['label'] for s in _pic_suggestions(client, TOKEN)}

        assert labels == {f'{TOKEN} Pide', f'{TOKEN} Pmde'}

    def test_superuser_reaches_everyone(self, client):
        superuser = UserFactory(is_superuser=True)
        _in_groups('user_pide', first_name=TOKEN, last_name='Pide')
        client.force_login(superuser)

        assert [s['label'] for s in _pic_suggestions(client, TOKEN)] == [f'{TOKEN} Pide']

    def test_inactive_colleagues_are_not_suggested(self, client):
        kasi = _in_groups('kasi_pmde')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Pindah', is_active=False)
        client.force_login(kasi)

        assert _pic_suggestions(client, TOKEN) == []

    def test_suggestion_points_at_the_profil_pic_page(self, client):
        me = _in_groups('user_pmde', first_name=TOKEN, last_name='Rahayu')
        client.force_login(me)

        suggestion = _pic_suggestions(client, TOKEN)[0]

        assert suggestion['url'] == reverse('profil_pic_detail', args=[me.username])
        assert suggestion['type_label'] == 'PIC'
        # The seksi tells two colleagues with similar names apart.
        assert suggestion['sublabel'] == 'Seksi PMDE'

    def test_search_by_username(self, client):
        me = _in_groups('user_pmde', username='sitirahayu', first_name='', last_name='')
        client.force_login(me)

        assert [s['label'] for s in _pic_suggestions(client, 'sitirahayu')] == [
            'sitirahayu'
        ]

    def test_multi_word_term_requires_every_word(self, client):
        kasi = _in_groups('kasi_pmde')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Rahayu')
        _in_groups('user_pmde', first_name=TOKEN, last_name='Nurbaya')
        client.force_login(kasi)

        labels = [s['label'] for s in _pic_suggestions(client, f'{TOKEN} Rahayu')]

        assert labels == [f'{TOKEN} Rahayu']

    def test_the_catalogue_groups_stay_unscoped(self, client):
        """Only the people group follows supervision; ILAP stays open to all."""
        from diamond_web.tests.conftest import ILAPFactory

        ilap = ILAPFactory(nama_ilap='Pemda Kabupaten Purwakarta')
        client.force_login(_in_groups('user_pmde'))

        urls = [s['url'] for s in _suggest(client, 'purwakarta')]

        assert reverse('profil_ilap_detail', args=[ilap.id_ilap]) in urls
