"""Tests for the `kasubdit_pde` navigation rule in `templates/navbar.html`.

Kasubdit PDE reads the work of the three seksi rather than doing it, so the
navigation stops at the four entries every authenticated user gets. Membership
sits alongside a seksi group — that is where the data scope comes from — which
is exactly why the seksi sections have to be suppressed by name here: without
this rule the companion group would open them.
"""
import pytest
from django.contrib.auth.models import Group
from django.template.loader import render_to_string

from diamond_web.tests.conftest import UserFactory


# The four entries that survive, and the section captions that must not.
TOP_LEVEL_ENTRIES = ['Home', 'Dashboard', 'Daftar Tiket', 'Profil ILAP']
SECTION_CAPTIONS = [
    '<label>P3DE</label>',
    '<label>PIDE</label>',
    '<label>PMDE</label>',
    '<label>Admin P3DE</label>',
    '<label>Admin PIDE</label>',
    '<label>Admin PMDE</label>',
    '<label>Sinkronisasi Data</label>',
]


def _user(*group_names):
    user = UserFactory()
    for name in group_names:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return user


def _navbar(user):
    return render_to_string('navbar.html', {'user': user})


@pytest.mark.django_db
class TestKasubditPDENavbar:

    def test_kasubdit_keeps_only_the_four_top_level_entries(self):
        html = _navbar(_user('kasubdit_pde', 'user_p3de'))
        for entry in TOP_LEVEL_ENTRIES:
            assert f'>{entry}</span>' in html
        for caption in SECTION_CAPTIONS:
            assert caption not in html

    @pytest.mark.parametrize('companion', [
        'user_p3de', 'user_pide', 'user_pmde',
        'kasi_p3de', 'kasi_pide', 'kasi_pmde',
        'admin_p3de', 'admin_pide', 'admin_pmde',
        'admin',
    ])
    def test_kasubdit_suppresses_every_companion_group_section(self, companion):
        """No companion group re-opens a section for a kasubdit."""
        html = _navbar(_user('kasubdit_pde', companion))
        for caption in SECTION_CAPTIONS:
            assert caption not in html

    def test_the_companion_group_alone_still_gets_its_sections(self):
        """The rule keys on kasubdit_pde only — nothing else changes."""
        html = _navbar(_user('user_p3de'))
        assert '<label>P3DE</label>' in html
        assert 'Kirim Tiket ke PIDE' in html

    def test_admin_alone_still_gets_every_section(self):
        html = _navbar(_user('admin', 'admin_p3de', 'admin_pide', 'admin_pmde'))
        for caption in SECTION_CAPTIONS:
            assert caption in html

    def test_kasi_pide_alone_still_gets_identifikasi(self):
        html = _navbar(_user('kasi_pide'))
        assert '<label>PIDE</label>' in html
        assert 'Identifikasi' in html

    def test_kasubdit_loses_identifikasi_and_quality_control(self):
        """The two entries a kasi sees without an admin or user group."""
        html = _navbar(_user('kasubdit_pde', 'kasi_pide', 'kasi_pmde'))
        assert 'Identifikasi' not in html
        assert 'Quality Control' not in html
