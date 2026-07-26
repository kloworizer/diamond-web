"""Tests for sequence_tanda_terima views + form (previously untested)."""
import json
from datetime import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.forms.sequence_tanda_terima import SequenceTandaTerimaForm
from diamond_web.models.sequence_tanda_terima import SequenceTandaTerima
from diamond_web.models.tanda_terima_data import TandaTerimaData
from diamond_web.tests.conftest import ILAPFactory, UserFactory


def _admin_p3de_user():
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='admin_p3de')
    user.groups.add(group)
    return user


def _lock_year(tahun):
    """Create a TandaTerimaData row for the given year to lock its sequence."""
    ilap = ILAPFactory()
    return TandaTerimaData.objects.create(
        nomor_tanda_terima=1,
        tahun_terima=tahun,
        tanggal_tanda_terima=datetime(tahun, 6, 1),
        id_ilap=ilap,
        id_perekam=UserFactory(),
        active=True,
    )


@pytest.mark.django_db
class TestSequenceTandaTerimaListView:
    def test_requires_login(self, client):
        resp = client.get(reverse('sequence_tanda_terima_list'))
        assert resp.status_code in (302, 403)

    def test_denied_without_admin_group(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('sequence_tanda_terima_list'))
        assert resp.status_code == 403

    def test_get_success(self, client):
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_list'))
        assert resp.status_code == 200

    def test_get_shows_delete_success_message(self, client):
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse('sequence_tanda_terima_list'),
            {'deleted': '1', 'name': 'Tahun+2020'},
            follow=True,
        )
        assert resp.status_code == 200
        messages_list = list(resp.context['messages'])
        assert any('berhasil dihapus' in str(m) for m in messages_list)


@pytest.mark.django_db
class TestSequenceTandaTerimaData:
    url = 'sequence_tanda_terima_data'

    def test_denied_without_group(self, client):
        """@user_passes_test redirects (not 403) non-admin users."""
        client.force_login(UserFactory())
        resp = client.get(reverse(self.url))
        assert resp.status_code == 302

    def test_data_endpoint_basic(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2019, nomor_terakhir=50)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        payload = resp.json()
        row = next(r for r in payload['data'] if r['tahun'] == seq.tahun)
        assert row['nomor_terakhir'] == 50
        assert row['nomor_berikutnya'] == 51
        assert 'Dapat Diubah' in row['status']
        assert "data-action='edit'" in row['actions']
        assert "data-action='delete'" in row['actions']

    def test_data_endpoint_locked_year_shows_disabled_actions(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2018, nomor_terakhir=10)
        _lock_year(2018)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse(self.url), {'draw': '1', 'start': '0', 'length': '10'})
        payload = resp.json()
        row = next(r for r in payload['data'] if r['tahun'] == seq.tahun)
        assert 'Terkunci' in row['status']
        assert 'disabled' in row['actions']

    def test_column_search_tahun(self, client):
        SequenceTandaTerima.objects.create(tahun=2017, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['2017']},
        )
        assert resp.json()['recordsFiltered'] == 1

    def test_column_search_nomor_terakhir(self, client):
        SequenceTandaTerima.objects.create(tahun=2016, nomor_terakhir=777)
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', '777']},
        )
        assert resp.json()['recordsFiltered'] == 1

    @pytest.mark.parametrize('order_col,order_dir', [(0, 'asc'), (1, 'desc'), (99, 'asc')])
    def test_ordering(self, client, order_col, order_dir):
        SequenceTandaTerima.objects.create(tahun=2015, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse(self.url),
            {'draw': '1', 'start': '0', 'length': '10',
             'order[0][column]': str(order_col), 'order[0][dir]': order_dir},
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSequenceTandaTerimaCreateView:
    def test_get_renders_form(self, client):
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_create'))
        assert resp.status_code == 200

    def test_post_creates(self, client):
        client.force_login(_admin_p3de_user())
        resp = client.post(
            reverse('sequence_tanda_terima_create'),
            {'tahun': 2014, 'nomor_terakhir': 5},
        )
        assert resp.status_code in (200, 302)
        assert SequenceTandaTerima.objects.filter(tahun=2014, nomor_terakhir=5).exists()

    def test_denied_without_group(self, client):
        client.force_login(UserFactory())
        resp = client.get(reverse('sequence_tanda_terima_create'))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestSequenceTandaTerimaUpdateView:
    def test_get_renders_form_when_unlocked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2013, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_update', args=[seq.pk]))
        assert resp.status_code == 200

    def test_get_blocked_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2012, nomor_terakhir=1)
        _lock_year(2012)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_update', args=[seq.pk]))
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is False

    def test_post_updates(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2011, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.post(
            reverse('sequence_tanda_terima_update', args=[seq.pk]),
            {'tahun': 2011, 'nomor_terakhir': 99},
        )
        assert resp.status_code in (200, 302)
        seq.refresh_from_db()
        assert seq.nomor_terakhir == 99

    def test_post_blocked_by_form_clean_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2010, nomor_terakhir=1)
        _lock_year(2010)
        client.force_login(_admin_p3de_user())
        resp = client.post(
            reverse('sequence_tanda_terima_update', args=[seq.pk]),
            {'tahun': 2010, 'nomor_terakhir': 99},
        )
        seq.refresh_from_db()
        assert seq.nomor_terakhir == 1


@pytest.mark.django_db
class TestSequenceTandaTerimaDeleteView:
    def test_get_confirmation(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2009, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_delete', args=[seq.pk]))
        assert resp.status_code == 200

    def test_get_ajax_confirmation(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2008, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse('sequence_tanda_terima_delete', args=[seq.pk]), {'ajax': '1'}
        )
        assert resp.status_code == 200
        assert 'html' in resp.json()

    def test_get_blocked_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2007, nomor_terakhir=1)
        _lock_year(2007)
        client.force_login(_admin_p3de_user())
        resp = client.get(reverse('sequence_tanda_terima_delete', args=[seq.pk]))
        assert resp.status_code == 200

    def test_get_ajax_blocked_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2006, nomor_terakhir=1)
        _lock_year(2006)
        client.force_login(_admin_p3de_user())
        resp = client.get(
            reverse('sequence_tanda_terima_delete', args=[seq.pk]), {'ajax': '1'}
        )
        data = resp.json()
        assert data['success'] is False

    def test_post_deletes(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2005, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.post(reverse('sequence_tanda_terima_delete', args=[seq.pk]))
        assert resp.status_code in (200, 302)
        assert not SequenceTandaTerima.objects.filter(pk=seq.pk).exists()

    def test_post_ajax_deletes(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2004, nomor_terakhir=1)
        client.force_login(_admin_p3de_user())
        resp = client.post(
            reverse('sequence_tanda_terima_delete', args=[seq.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert not SequenceTandaTerima.objects.filter(pk=seq.pk).exists()

    def test_post_blocked_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2003, nomor_terakhir=1)
        _lock_year(2003)
        client.force_login(_admin_p3de_user())
        resp = client.post(reverse('sequence_tanda_terima_delete', args=[seq.pk]))
        assert SequenceTandaTerima.objects.filter(pk=seq.pk).exists()

    def test_post_ajax_blocked_when_locked(self, client):
        seq = SequenceTandaTerima.objects.create(tahun=2002, nomor_terakhir=1)
        _lock_year(2002)
        client.force_login(_admin_p3de_user())
        resp = client.post(
            reverse('sequence_tanda_terima_delete', args=[seq.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        data = resp.json()
        assert data['success'] is False
        assert SequenceTandaTerima.objects.filter(pk=seq.pk).exists()


@pytest.mark.django_db
class TestSequenceTandaTerimaForm:
    def test_clean_tahun_out_of_range(self):
        form = SequenceTandaTerimaForm(data={'tahun': 1500, 'nomor_terakhir': 1})
        assert not form.is_valid()
        assert 'tahun' in form.errors

    def test_clean_tahun_valid(self):
        form = SequenceTandaTerimaForm(data={'tahun': 2020, 'nomor_terakhir': 1})
        assert form.is_valid()

    def test_clean_blocks_edit_when_locked(self):
        seq = SequenceTandaTerima.objects.create(tahun=2001, nomor_terakhir=1)
        _lock_year(2001)
        form = SequenceTandaTerimaForm(
            data={'tahun': 2001, 'nomor_terakhir': 5}, instance=seq
        )
        assert not form.is_valid()
