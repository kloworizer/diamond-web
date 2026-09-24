"""Kasi P3DE/PIDE/PMDE see their seksi's PIC page the way its pelaksana do.

Read-only, like `user_*`: the tab and its data load, but Tambah/Edit/Hapus stay
behind the `admin_*` groups, and another seksi's tab stays hidden.
"""
import pytest
from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.tests.conftest import PICFactory, UserFactory, JenisDataILAPFactory

SEKSI = ['p3de', 'pide', 'pmde']


def _kasi(seksi):
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name=f'kasi_{seksi}')
    user.groups.add(group)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize('seksi', SEKSI)
def test_kasi_sees_own_seksi_pic_tab_read_only(client, seksi):
    client.force_login(_kasi(seksi))
    response = client.get(reverse('pic_unified_list'), {'tab': seksi})

    assert response.status_code == 200
    ctx = response.context
    assert ctx['default_tab'] == seksi
    for other in SEKSI:
        assert ctx[f'can_view_{other}'] is (other == seksi)
        assert ctx[f'is_admin_{other}'] is False
    assert reverse(f'pic_{seksi}_create') not in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize('seksi', SEKSI)
def test_kasi_pic_data_has_rows_without_actions(client, seksi):
    PICFactory(
        tipe=seksi.upper(),
        id_user=UserFactory(),
        id_sub_jenis_data_ilap=JenisDataILAPFactory(),
        start_date=date.today() - timedelta(days=30),
    )
    client.force_login(_kasi(seksi))
    response = client.get(reverse(f'pic_{seksi}_data'))

    assert response.status_code == 200
    rows = response.json()['data']
    assert len(rows) == 1
    assert rows[0]['actions'] == ''


@pytest.mark.django_db
@pytest.mark.parametrize('seksi', SEKSI)
def test_kasi_denied_other_seksi_pic_data(client, seksi):
    client.force_login(_kasi(seksi))
    for other in SEKSI:
        if other == seksi:
            continue
        response = client.get(reverse(f'pic_{other}_data'))
        assert response.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize('seksi', SEKSI)
def test_kasi_denied_pic_create(client, seksi):
    client.force_login(_kasi(seksi))
    response = client.get(reverse(f'pic_{seksi}_create'))
    assert response.status_code in (302, 403)


@pytest.mark.django_db
@pytest.mark.parametrize('seksi', SEKSI)
def test_navbar_lists_pic_menu_for_kasi_once(client, seksi):
    client.force_login(_kasi(seksi))
    html = client.get(reverse('home')).content.decode()

    assert html.count(f'?tab={seksi}"') == 1
    for other in SEKSI:
        if other != seksi:
            assert f'?tab={other}"' not in html


@pytest.mark.django_db
def test_navbar_no_duplicate_pic_p3de_for_kasi_who_is_also_user():
    from django.test import Client
    client = Client()
    user = _kasi('p3de')
    user.groups.add(Group.objects.get_or_create(name='user_p3de')[0])
    client.force_login(user)
    html = client.get(reverse('home')).content.decode()
    assert html.count('?tab=p3de"') == 1
