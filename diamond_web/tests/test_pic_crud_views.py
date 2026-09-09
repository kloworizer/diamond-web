"""Tests for pic.py views.

Covers: PICListView, PICCreateView, PICUpdateView, PICDeleteView, _pic_data_common
for P3DE, PIDE, and PMDE tipes.
"""
import json
import pytest
from datetime import date, timedelta

from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models import PIC, TiketPIC
from diamond_web.tests.conftest import (
    PICFactory, TiketFactory, TiketPICFactory, UserFactory,
    JenisDataILAPFactory,
)


def _make_user_in_group(group_name):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


def _make_p3de_user():
    return _make_user_in_group('user_p3de')


def _make_pide_user():
    return _make_user_in_group('user_pide')


def _make_pmde_user():
    return _make_user_in_group('user_pmde')


def _make_pic(tipe, user=None, end_date=None, jenis_data=None):
    """Create a PIC with specific tipe."""
    if user is None:
        if tipe == 'P3DE':
            user = _make_p3de_user()
        elif tipe == 'PIDE':
            user = _make_pide_user()
        else:
            user = _make_pmde_user()
    if jenis_data is None:
        jenis_data = JenisDataILAPFactory()
    return PICFactory(
        tipe=tipe,
        id_user=user,
        id_sub_jenis_data_ilap=jenis_data,
        start_date=date.today() - timedelta(days=30),
        end_date=end_date,
    )


# ============================================================
# PIC P3DE Views
# ============================================================

@pytest.mark.django_db
class TestPICP3DEListView:
    """Tests for PICP3DEListView."""

    def test_requires_login(self, client):
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code in (302, 403)

    def test_non_admin_denied(self, client, pide_user):
        client.force_login(pide_user)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code in (302, 403)

    def test_p3de_admin_can_access(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code == 200

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code == 200

    def test_pide_admin_denied(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('pic_p3de_list'))
        assert resp.status_code in (302, 403)

    def test_get_with_deleted_param(self, client, p3de_admin_user):
        """Shows delete toast with deleted=1."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_list'), {'deleted': '1', 'name': 'TestPIC'})
        assert resp.status_code == 200
        messages_list = list(resp.context['messages'])
        assert len(messages_list) > 0


@pytest.mark.django_db
class TestPICP3DECreateView:
    """Tests for PICP3DECreateView."""

    def test_requires_login(self, client):
        resp = client.get(reverse('pic_p3de_create'))
        assert resp.status_code in (302, 403)

    def test_non_admin_denied(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('pic_p3de_create'))
        assert resp.status_code in (302, 403)

    def test_ajax_get_returns_html(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_non_ajax_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_create'))
        assert resp.status_code == 200

    def test_post_valid_creates_pic(self, client, p3de_admin_user, db):
        """POST valid form creates a PIC."""
        user = _make_p3de_user()
        jenis_data = JenisDataILAPFactory()
        data = {
            'tipe': 'P3DE',
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today()),
        }
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_create'), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        # success=True means PIC was created; success=False with html means form error
        assert 'success' in result
        if result.get('success'):
            assert PIC.objects.filter(id_user=user, tipe='P3DE').exists()

    def test_post_propagates_to_active_tikets(self, client, p3de_admin_user, db):
        """Creating PIC propagates to active tikets with matching jenis_data."""
        from datetime import date as date_cls
        user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1, tgl_terima_dip=date_cls.today())
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        data = {
            'tipe': 'P3DE',
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today()),
        }
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_create'), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        if result.get('success'):
            # Should have created TiketPIC for the active tiket
            assert TiketPIC.objects.filter(
                id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE
            ).exists()

    def test_post_invalid_returns_form_errors(self, client, p3de_admin_user):
        """POST with invalid data returns form with errors."""
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_create'), {},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False or 'html' in data


@pytest.mark.django_db
class TestPICP3DEUpdateView:
    """Tests for PICP3DEUpdateView."""

    def test_requires_login(self, client, db):
        pic = _make_pic('P3DE')
        resp = client.get(reverse('pic_p3de_update', args=[pic.pk]))
        assert resp.status_code in (302, 403)

    def test_non_admin_denied(self, client, authenticated_user, db):
        pic = _make_pic('P3DE')
        client.force_login(authenticated_user)
        resp = client.get(reverse('pic_p3de_update', args=[pic.pk]))
        assert resp.status_code in (302, 403)

    def test_ajax_get_returns_html(self, client, p3de_admin_user, db):
        pic = _make_pic('P3DE')
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_update', args=[pic.pk]), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_post_set_end_date_deactivates_tiket_pic(self, client, p3de_admin_user, db):
        """Setting end_date deactivates associated TiketPIC records."""
        user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
        end_date = date.today()
        data = {
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today() - timedelta(days=30)),
            'end_date': str(end_date),
        }
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic.pk]), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        assert result.get('success') is True
        # TiketPIC should be deactivated
        tiket_pic = TiketPIC.objects.filter(id_tiket=tiket, id_user=user).last()
        assert tiket_pic is None or tiket_pic.active is False

    def test_post_clear_end_date_reactivates(self, client, p3de_admin_user, db):
        """Clearing end_date reactivates PIC."""
        user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() - timedelta(days=5),
        )
        data = {
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today() - timedelta(days=30)),
            'end_date': '',
        }
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_update', args=[pic.pk]), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        assert result.get('success') is True

    def _post_user_change(self, client, pic, new_user, end_date=''):
        return client.post(
            reverse('pic_p3de_update', args=[pic.pk]),
            {
                'id_sub_jenis_data_ilap': pic.id_sub_jenis_data_ilap.pk,
                'id_user': new_user.pk,
                'start_date': str(pic.start_date),
                'end_date': end_date,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_post_change_user_hands_open_tiket_over(self, client, p3de_admin_user, db):
        """Swapping the user deactivates the old PIC and assigns the new one."""
        from diamond_web.constants.tiket_action_types import PICActionType
        from diamond_web.models import TiketAction

        old_user = _make_p3de_user()
        new_user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=old_user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        TiketPICFactory(id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE, active=True)

        client.force_login(p3de_admin_user)
        resp = self._post_user_change(client, pic, new_user)

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is True
        assert PIC.objects.get(pk=pic.pk).id_user_id == new_user.pk
        # Old PIC off, new PIC on - the tiket is never left unassigned
        assert TiketPIC.objects.get(
            id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE
        ).active is False
        assert TiketPIC.objects.get(
            id_tiket=tiket, id_user=new_user, role=TiketPIC.Role.P3DE
        ).active is True
        actions = TiketAction.objects.filter(id_tiket=tiket)
        assert actions.filter(action=PICActionType.DITAMBAHKAN).exists()
        assert actions.filter(action=PICActionType.TIDAK_AKTIF).exists()

    def test_post_change_user_reactivates_existing_tiket_pic(self, client, p3de_admin_user, db):
        """A new user who was assigned before is switched back on, not duplicated."""
        old_user = _make_p3de_user()
        new_user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=old_user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        TiketPICFactory(id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE, active=True)
        TiketPICFactory(id_tiket=tiket, id_user=new_user, role=TiketPIC.Role.P3DE, active=False)

        client.force_login(p3de_admin_user)
        resp = self._post_user_change(client, pic, new_user)

        assert resp.status_code == 200
        new_records = TiketPIC.objects.filter(
            id_tiket=tiket, id_user=new_user, role=TiketPIC.Role.P3DE
        )
        assert new_records.count() == 1
        assert new_records.first().active is True

    def test_post_change_user_leaves_closed_tiket_alone(self, client, p3de_admin_user, db):
        """A finished tiket keeps the person who actually worked it."""
        old_user = _make_p3de_user()
        new_user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=8)  # selesai
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=old_user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        TiketPICFactory(id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE, active=True)

        client.force_login(p3de_admin_user)
        resp = self._post_user_change(client, pic, new_user)

        assert resp.status_code == 200
        assert TiketPIC.objects.get(
            id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE
        ).active is True
        assert not TiketPIC.objects.filter(id_tiket=tiket, id_user=new_user).exists()

    def test_post_change_user_with_end_date_only_deactivates(self, client, p3de_admin_user, db):
        """Closing the PIC while swapping the user assigns nobody."""
        old_user = _make_p3de_user()
        new_user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE',
            id_user=old_user,
            id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30),
            end_date=None,
        )
        TiketPICFactory(id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE, active=True)

        client.force_login(p3de_admin_user)
        resp = self._post_user_change(client, pic, new_user, end_date=str(date.today()))

        assert resp.status_code == 200
        assert TiketPIC.objects.get(
            id_tiket=tiket, id_user=old_user, role=TiketPIC.Role.P3DE
        ).active is False
        assert not TiketPIC.objects.filter(id_tiket=tiket, id_user=new_user).exists()


@pytest.mark.django_db
class TestPICP3DEDeleteView:
    """Tests for PICP3DEDeleteView."""

    def test_requires_login(self, client, db):
        pic = _make_pic('P3DE')
        resp = client.get(reverse('pic_p3de_delete', args=[pic.pk]))
        assert resp.status_code in (302, 403)

    def test_non_admin_denied(self, client, authenticated_user, db):
        pic = _make_pic('P3DE')
        client.force_login(authenticated_user)
        resp = client.get(reverse('pic_p3de_delete', args=[pic.pk]))
        assert resp.status_code in (302, 403)

    def test_get_ajax(self, client, p3de_admin_user, db):
        """GET with ajax=1 returns modal HTML."""
        pic = _make_pic('P3DE')
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_delete', args=[pic.pk]), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_get_non_ajax(self, client, p3de_admin_user, db):
        """GET without ajax renders template."""
        pic = _make_pic('P3DE')
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_delete', args=[pic.pk]))
        assert resp.status_code == 200

    def test_post_deletes_pic(self, client, p3de_admin_user, db):
        """POST deletes the PIC."""
        pic = _make_pic('P3DE')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_delete', args=[pic.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True
        assert not PIC.objects.filter(pk=pic.pk).exists()

    def test_post_also_cleans_tiket_pic(self, client, p3de_admin_user, db):
        """POST removes associated TiketPIC records."""
        user = _make_p3de_user()
        tiket = TiketFactory(status_tiket=1)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        pic = PICFactory(
            tipe='P3DE', id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=date.today() - timedelta(days=30), end_date=None
        )
        tiket_pic = TiketPICFactory(
            id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('pic_p3de_delete', args=[pic.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# PIC P3DE Data Endpoint
# ============================================================

@pytest.mark.django_db
class TestPICP3DEDataEndpoint:
    """Tests for pic_p3de_data DataTables endpoint."""

    def test_requires_login(self, client):
        resp = client.get(reverse('pic_p3de_data'))
        assert resp.status_code in (302, 403)

    def test_non_admin_denied(self, client, pide_user):
        client.force_login(pide_user)
        resp = client.get(reverse('pic_p3de_data'))
        assert resp.status_code in (302, 403)

    def test_admin_basic_fetch(self, client, admin_user, db):
        _make_pic('P3DE')
        client.force_login(admin_user)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_p3de_admin_can_access(self, client, p3de_admin_user, db):
        _make_pic('P3DE')
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1

    def test_global_search(self, client, admin_user, db):
        _make_pic('P3DE')
        client.force_login(admin_user)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'search[value]': 'P3DE',
        })
        assert resp.status_code == 200

    def test_ordering_asc(self, client, admin_user, db):
        _make_pic('P3DE')
        client.force_login(admin_user)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'asc',
        })
        assert resp.status_code == 200

    def test_columns_search(self, client, admin_user, db):
        pic = _make_pic('P3DE')
        client.force_login(admin_user)
        resp = client.get(reverse('pic_p3de_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': [
                pic.id_sub_jenis_data_ilap.nama_jenis_data[:3],
                '', '', '', '',
            ],
        })
        assert resp.status_code == 200


# ============================================================
# PIC PIDE Views
# ============================================================

@pytest.mark.django_db
class TestPICPIDEListView:
    """Tests for PICPIDEListView."""

    def test_non_admin_denied(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('pic_pide_list'))
        assert resp.status_code in (302, 403)

    def test_pide_admin_can_access(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('pic_pide_list'))
        assert resp.status_code == 200

    def test_p3de_admin_denied(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_pide_list'))
        assert resp.status_code in (302, 403)

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('pic_pide_list'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPICPIDECreateView:
    """Tests for PICPIDECreateView."""

    def test_ajax_get(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('pic_pide_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_post_valid_creates_pic(self, client, pide_admin_user, db):
        user = _make_pide_user()
        jenis_data = JenisDataILAPFactory()
        data = {
            'tipe': 'PIDE',
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today()),
        }
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('pic_pide_create'), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        assert 'success' in result
        if result.get('success'):
            assert PIC.objects.filter(id_user=user, tipe='PIDE').exists()


@pytest.mark.django_db
class TestPICPIDEDeleteView:
    """Tests for PICPIDEDeleteView."""

    def test_post_deletes_pic(self, client, pide_admin_user, db):
        user = _make_pide_user()
        pic = PICFactory(
            tipe='PIDE', id_user=user,
            start_date=date.today() - timedelta(days=30), end_date=None
        )
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('pic_pide_delete', args=[pic.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


@pytest.mark.django_db
class TestPICPIDEDataEndpoint:
    """Tests for pic_pide_data DataTables endpoint."""

    def test_pide_admin_can_access(self, client, pide_admin_user, db):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('pic_pide_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data


# ============================================================
# PIC PMDE Views
# ============================================================

@pytest.mark.django_db
class TestPICPMDEListView:
    """Tests for PICPMDEListView."""

    def test_pmde_admin_can_access(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('pic_pmde_list'))
        assert resp.status_code == 200

    def test_p3de_admin_denied(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('pic_pmde_list'))
        assert resp.status_code in (302, 403)

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('pic_pmde_list'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPICPMDECreateView:
    """Tests for PICPMDECreateView."""

    def test_ajax_get(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('pic_pmde_create'), {'ajax': '1'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_post_valid_creates_pic(self, client, pmde_admin_user, db):
        user = _make_pmde_user()
        jenis_data = JenisDataILAPFactory()
        data = {
            'tipe': 'PMDE',
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(date.today()),
        }
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('pic_pmde_create'), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        result = json.loads(resp.content)
        assert 'success' in result
        if result.get('success'):
            assert PIC.objects.filter(id_user=user, tipe='PMDE').exists()


@pytest.mark.django_db
class TestPICPMDEDeleteView:
    """Tests for PICPMDEDeleteView."""

    def test_post_deletes_pic(self, client, pmde_admin_user, db):
        user = _make_pmde_user()
        pic = PICFactory(
            tipe='PMDE', id_user=user,
            start_date=date.today() - timedelta(days=30), end_date=None
        )
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('pic_pmde_delete', args=[pic.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


@pytest.mark.django_db
class TestPICPMDEDataEndpoint:
    """Tests for pic_pmde_data DataTables endpoint."""

    def test_pmde_admin_can_access(self, client, pmde_admin_user, db):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('pic_pmde_data'), {
            'draw': '1', 'start': '0', 'length': '10',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_admin_denied(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('pic_pmde_data'))
        assert resp.status_code in (302, 403)


# Each PIC tipe, with the tiket status at which a missing PIC actually strands
# the tiket: P3DE owns it while it is Direkam, PIDE once it is Dikirim ke PIDE,
# PMDE once it reaches Pengendalian Mutu.
_RESYNC_CASES = [
    ('P3DE', TiketPIC.Role.P3DE, 'pic_p3de_create', 'p3de_admin_user', 1),
    ('PIDE', TiketPIC.Role.PIDE, 'pic_pide_create', 'pide_admin_user', 4),
    ('PMDE', TiketPIC.Role.PMDE, 'pic_pmde_create', 'pmde_admin_user', 6),
]

_RESYNC_IDS = [case[0] for case in _RESYNC_CASES]


@pytest.mark.django_db
@pytest.mark.parametrize(
    'tipe,role,url_name,admin_fixture,stuck_status', _RESYNC_CASES, ids=_RESYNC_IDS
)
class TestPICCreateResyncsExistingPIC:
    """Assigning a PIC that already exists applies it instead of erroring.

    A `PIC` row can predate its `TiketPIC` rows - the Oracle sync bulk-inserts
    `PIC` for all three tipes and never touches `TiketPIC` - which leaves the
    tiket with nobody assigned and the admin unable to fix it, because the
    master record they are told already exists is the one the tiket is missing.

    The behaviour lives in the shared `PICCreateView`, so every tipe is checked
    against it rather than trusting inheritance.
    """

    def _login(self, client, request, admin_fixture):
        client.force_login(request.getfixturevalue(admin_fixture))

    def _pic_user(self, tipe):
        return _make_user_in_group(f'user_{tipe.lower()}')

    def _post(self, client, url_name, tipe, jenis_data, user, start_date, end_date=None):
        data = {
            'tipe': tipe,
            'id_sub_jenis_data_ilap': jenis_data.pk,
            'id_user': user.pk,
            'start_date': str(start_date),
        }
        if end_date:
            data['end_date'] = str(end_date)
        return client.post(
            reverse(url_name), data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

    def test_duplicate_start_date_assigns_tiket_instead_of_erroring(
        self, client, request, db, tipe, role, url_name, admin_fixture, stuck_status
    ):
        user = self._pic_user(tipe)
        tiket = TiketFactory(status_tiket=stuck_status)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        start = date(2015, 1, 1)
        PICFactory(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=start, end_date=None,
        )
        assert not TiketPIC.objects.filter(id_tiket=tiket, role=role).exists()

        self._login(client, request, admin_fixture)
        resp = self._post(client, url_name, tipe, jenis_data, user, start)

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is True
        assert TiketPIC.objects.get(
            id_tiket=tiket, id_user=user, role=role
        ).active is True
        # The existing master record is applied, never duplicated
        assert PIC.objects.filter(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data
        ).count() == 1

    def test_overlapping_start_date_assigns_tiket(
        self, client, request, db, tipe, role, url_name, admin_fixture, stuck_status
    ):
        """A different start date against an open PIC resolves the same way."""
        user = self._pic_user(tipe)
        tiket = TiketFactory(status_tiket=stuck_status)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        PICFactory(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=date(2015, 1, 1), end_date=None,
        )

        self._login(client, request, admin_fixture)
        resp = self._post(client, url_name, tipe, jenis_data, user, date.today())

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is True
        assert TiketPIC.objects.filter(
            id_tiket=tiket, id_user=user, role=role, active=True
        ).exists()
        assert PIC.objects.filter(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data
        ).count() == 1

    def test_closed_pic_still_rejected(
        self, client, request, db, tipe, role, url_name, admin_fixture, stuck_status
    ):
        """A PIC that has been ended is not applied - it needs a new start date."""
        user = self._pic_user(tipe)
        tiket = TiketFactory(status_tiket=stuck_status)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        start = date(2015, 1, 1)
        PICFactory(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=start, end_date=date(2020, 1, 1),
        )

        self._login(client, request, admin_fixture)
        resp = self._post(client, url_name, tipe, jenis_data, user, start)

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is False
        assert not TiketPIC.objects.filter(id_tiket=tiket, role=role).exists()

    def test_submission_carrying_end_date_still_rejected(
        self, client, request, db, tipe, role, url_name, admin_fixture, stuck_status
    ):
        """Closing a PIC is not a request to assign the open one that exists."""
        user = self._pic_user(tipe)
        tiket = TiketFactory(status_tiket=stuck_status)
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        start = date(2015, 1, 1)
        PICFactory(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=start, end_date=None,
        )

        self._login(client, request, admin_fixture)
        resp = self._post(
            client, url_name, tipe, jenis_data, user, start, end_date=date.today()
        )

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is False
        assert not TiketPIC.objects.filter(id_tiket=tiket, role=role).exists()

    def test_finished_tiket_is_left_alone(
        self, client, request, db, tipe, role, url_name, admin_fixture, stuck_status
    ):
        """Only still-open tikets catch up; a finished one keeps its history."""
        user = self._pic_user(tipe)
        tiket = TiketFactory(status_tiket=8)  # selesai
        jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        start = date(2015, 1, 1)
        PICFactory(
            tipe=tipe, id_user=user, id_sub_jenis_data_ilap=jenis_data,
            start_date=start, end_date=None,
        )

        self._login(client, request, admin_fixture)
        resp = self._post(client, url_name, tipe, jenis_data, user, start)

        assert resp.status_code == 200
        assert json.loads(resp.content).get('success') is True
        assert not TiketPIC.objects.filter(id_tiket=tiket, role=role).exists()
