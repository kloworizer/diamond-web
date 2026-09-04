"""Access control for the Data Prioritas menu.

Data Prioritas is the one admin reference the three seksi manage together —
P3DE sets the flag, PIDE and PMDE read it to order their queues — so all four
admin groups reach the same CRUD screens (RBAC_MATRIX.md, "Jenis Prioritas
Data"). These tests pin that down in both directions: every admin group gets
in, and a plain seksi user does not.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from .conftest import JenisPrioritasDataFactory, UserFactory

ADMIN_GROUPS = ['admin', 'admin_p3de', 'admin_pide', 'admin_pmde']


@pytest.fixture
def admin_of(db):
    """Build a user belonging to the named group."""
    def _make(group_name):
        user = UserFactory()
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        return user
    return _make


@pytest.mark.django_db
@pytest.mark.parametrize('group_name', ADMIN_GROUPS)
class TestEveryAdminGroupCanManagePrioritas:

    def test_list(self, client, admin_of, group_name):
        client.force_login(admin_of(group_name))
        assert client.get(reverse('jenis_prioritas_data_list')).status_code == 200

    def test_datatable_endpoint(self, client, admin_of, group_name):
        client.force_login(admin_of(group_name))
        assert client.get(reverse('jenis_prioritas_data_data')).status_code == 200

    def test_create_form(self, client, admin_of, group_name):
        client.force_login(admin_of(group_name))
        assert client.get(reverse('jenis_prioritas_data_create')).status_code == 200

    def test_update_form(self, client, admin_of, group_name):
        row = JenisPrioritasDataFactory()
        client.force_login(admin_of(group_name))
        url = reverse('jenis_prioritas_data_update', args=[row.pk])
        assert client.get(url).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('group_name', ['user_p3de', 'user_pide', 'user_pmde'])
def test_a_plain_seksi_user_is_still_shut_out(client, admin_of, group_name):
    client.force_login(admin_of(group_name))
    assert client.get(reverse('jenis_prioritas_data_list')).status_code == 403
    assert client.get(reverse('jenis_prioritas_data_data')).status_code in (302, 403)


@pytest.mark.django_db
@pytest.mark.parametrize('group_name', ADMIN_GROUPS)
def test_the_navbar_renders_no_stray_comment_text(client, admin_of, group_name):
    """Django's ``{# #}`` is single-line only: spread it over two lines and the
    template engine stops treating it as a comment and prints it to the page.
    The navbar explains the shared Data Prioritas entry in prose, so guard that
    none of it leaks into what a user sees."""
    client.force_login(admin_of(group_name))
    html = client.get(reverse('jenis_prioritas_data_list')).content.decode()

    assert '{#' not in html
    assert '{%' not in html
    for leak in ('dikelola bersama ketiga seksi', 'Menu bersama', 'blok Admin PIDE'):
        assert leak not in html
