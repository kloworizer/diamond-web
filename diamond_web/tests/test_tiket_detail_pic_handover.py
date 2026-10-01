"""Who may open a tiket's detail page after the PIC of its jenis data changes.

A handover in the PIC menu closes the old PIC with an end date and adds the new
one, but the new PIC only reaches tikets that are still open. Both of them must
still be able to read every tiket of the sub jenis data; the workflow actions
stay with whoever holds an active TiketPIC on the tiket itself.
"""
import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from diamond_web.constants.tiket_status import STATUS_DIREKAM, STATUS_SELESAI
from diamond_web.models import TiketPIC
from diamond_web.tests.conftest import (
    JenisDataILAPFactory,
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)
from diamond_web.views.pic import _assign_pic_to_open_tikets, _propagate_pic_update


def _handover(sub, old_user, new_user, admin):
    """Close `old_user`'s P3DE PIC on `sub` and open one for `new_user`.

    Goes through the same propagation the PIC menu uses, so the TiketPIC rows
    end up exactly as they do in production.
    """
    now = timezone.now()
    today = now.date()
    old_pic = PICFactory(tipe='P3DE', id_sub_jenis_data_ilap=sub, id_user=old_user,
                         start_date=today - datetime.timedelta(days=365), end_date=None)
    _propagate_pic_update(old_pic, old_user, today, admin, now)
    old_pic.end_date = today
    old_pic.save()

    PICFactory(tipe='P3DE', id_sub_jenis_data_ilap=sub, id_user=new_user,
               start_date=today, end_date=None)
    _assign_pic_to_open_tikets(new_user, TiketPIC.Role.P3DE, sub, 'PIC P3DE', admin, now)


@pytest.fixture
def handover(db):
    """A finished and an open tiket of one sub jenis data, handed over from A to B."""
    sub = JenisDataILAPFactory()
    pic_a, pic_b, admin = UserFactory(), UserFactory(), UserFactory()
    selesai = TiketFactory(status_tiket=STATUS_SELESAI, id_periode_data__id_sub_jenis_data_ilap=sub)
    direkam = TiketFactory(status_tiket=STATUS_DIREKAM, id_periode_data__id_sub_jenis_data_ilap=sub)
    for tiket in (selesai, direkam):
        TiketPICFactory(id_tiket=tiket, id_user=pic_a, role=TiketPIC.Role.P3DE, active=True)
    _handover(sub, pic_a, pic_b, admin)
    return {'sub': sub, 'a': pic_a, 'b': pic_b, 'selesai': selesai, 'direkam': direkam}


def _get(client, user, tiket):
    client.force_login(user)
    return client.get(reverse('tiket_detail', args=[tiket.pk]))


def _assert_read_only(resp):
    assert resp.status_code == 200
    assert resp.context['user_is_active_pic'] is False
    assert resp.context['user_can_edit_tiket'] is False
    assert resp.context['user_can_edit_special_request'] is False


@pytest.mark.django_db
class TestDetailAfterPicHandover:

    def test_handover_leaves_new_pic_off_the_finished_tiket(self, handover):
        """The data shape that caused the 403: B never gets a TiketPIC on it."""
        assert not TiketPIC.objects.filter(id_tiket=handover['selesai'], id_user=handover['b']).exists()

    def test_new_pic_opens_finished_tiket_read_only(self, client, handover):
        _assert_read_only(_get(client, handover['b'], handover['selesai']))

    def test_old_pic_opens_finished_tiket_read_only(self, client, handover):
        _assert_read_only(_get(client, handover['a'], handover['selesai']))

    def test_old_pic_opens_open_tiket_read_only(self, client, handover):
        _assert_read_only(_get(client, handover['a'], handover['direkam']))

    def test_new_pic_keeps_actions_on_open_tiket(self, client, handover):
        resp = _get(client, handover['b'], handover['direkam'])
        assert resp.status_code == 200
        assert resp.context['user_is_active_pic_p3de'] is True

    def test_new_pic_finds_finished_tiket_in_navbar_search(self, client, handover):
        client.force_login(handover['b'])
        resp = client.get(reverse('navbar_search'), {'q': handover['selesai'].nomor_tiket})
        assert resp.json()['match'] == 'tiket'


@pytest.mark.django_db
class TestDetailAccessByJenisDataPic:

    @pytest.mark.parametrize('tipe', ['P3DE', 'PIDE', 'PMDE'])
    def test_active_pic_of_sub_jenis_data_opens_tiket(self, client, tipe):
        tiket = TiketFactory(status_tiket=STATUS_SELESAI)
        user = UserFactory()
        PICFactory(tipe=tipe, id_sub_jenis_data_ilap=tiket.id_periode_data.id_sub_jenis_data_ilap,
                   id_user=user, end_date=None)
        _assert_read_only(_get(client, user, tiket))

    def test_ended_pic_without_tiket_pic_is_refused(self, client):
        """A PIC closed before the tiket existed never worked it."""
        tiket = TiketFactory(status_tiket=STATUS_SELESAI)
        user = UserFactory()
        PICFactory(id_sub_jenis_data_ilap=tiket.id_periode_data.id_sub_jenis_data_ilap,
                   id_user=user, end_date=timezone.now().date())
        assert _get(client, user, tiket).status_code == 403

    def test_active_pic_of_another_sub_jenis_data_is_refused(self, client):
        tiket = TiketFactory(status_tiket=STATUS_SELESAI)
        user = UserFactory()
        PICFactory(id_sub_jenis_data_ilap=JenisDataILAPFactory(), id_user=user, end_date=None)
        assert _get(client, user, tiket).status_code == 403

    def test_navbar_search_hides_tiket_from_unrelated_user(self, client):
        tiket = TiketFactory(status_tiket=STATUS_SELESAI)
        client.force_login(UserFactory())
        resp = client.get(reverse('navbar_search'), {'q': tiket.nomor_tiket})
        assert resp.json()['match'] is None
