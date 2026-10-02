"""Kelola PIC Tiket: admin seksi menambah/mengubah/menghapus PIC satu tiket.

Perubahan hanya berlaku di baris TiketPIC tiket itu: tabel PIC dan tiket lain
tidak disentuh. Hak aksesnya sama dengan menu PIC, dan setiap perubahan tercatat di
TiketAction atas nama admin yang melakukannya.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.constants.tiket_action_types import PICActionType
from diamond_web.models.pic import PIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import (
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
P3DE, PIDE, PMDE = TiketPIC.Role.P3DE, TiketPIC.Role.PIDE, TiketPIC.Role.PMDE


def _member(group_name, **kwargs):
    user = UserFactory(**kwargs)
    user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    return user


def _tambah_url(tiket, role):
    return reverse('tiket_pic_tambah', kwargs={'pk': tiket.pk}) + f'?role={int(role)}'


def _ubah_url(pic):
    return reverse('tiket_pic_ubah', kwargs={'pk': pic.id_tiket_id, 'pic_pk': pic.pk})


def _hapus_url(pic):
    return reverse('tiket_pic_hapus', kwargs={'pk': pic.id_tiket_id, 'pic_pk': pic.pk})


@pytest.fixture
def tiket(db):
    return TiketFactory(status_tiket=1)


@pytest.fixture
def p3de_pic(tiket):
    """The tiket's current P3DE PIC, as the PIC menu would have put them there."""
    return TiketPICFactory(
        id_tiket=tiket, id_user=_member('user_p3de'), role=P3DE, active=True,
    )


@pytest.mark.django_db
class TestAkses:
    def test_regular_user_is_refused(self, client, tiket, p3de_pic, authenticated_user):
        client.force_login(authenticated_user)
        assert client.get(_tambah_url(tiket, P3DE), **AJAX).status_code == 403
        assert client.post(_hapus_url(p3de_pic), **AJAX).status_code == 403
        assert TiketPIC.objects.filter(pk=p3de_pic.pk).exists()
        assert not TiketAction.objects.exists()

    def test_kasi_is_refused(self, client, tiket, p3de_pic, kasi_p3de_user):
        client.force_login(kasi_p3de_user)
        assert client.post(_hapus_url(p3de_pic), **AJAX).status_code == 403

    def test_seksi_admin_manages_only_own_role(self, client, tiket, p3de_pic, pide_admin_user):
        client.force_login(pide_admin_user)
        assert client.get(_tambah_url(tiket, P3DE), **AJAX).status_code == 403
        assert client.get(_ubah_url(p3de_pic), **AJAX).status_code == 403
        assert client.post(_hapus_url(p3de_pic), **AJAX).status_code == 403
        assert client.get(_tambah_url(tiket, PIDE), **AJAX).status_code == 200
        assert TiketPIC.objects.filter(pk=p3de_pic.pk).exists()

    def test_role_param_is_validated(self, client, tiket, admin_user):
        client.force_login(admin_user)
        url = reverse('tiket_pic_tambah', kwargs={'pk': tiket.pk})
        assert client.get(url, **AJAX).status_code == 403
        assert client.get(url + '?role=9', **AJAX).status_code == 403
        assert client.get(url + '?role=x', **AJAX).status_code == 403

    def test_global_admin_manages_every_role(self, client, tiket, admin_user):
        client.force_login(admin_user)
        for role in (P3DE, PIDE, PMDE):
            assert client.get(_tambah_url(tiket, role), **AJAX).status_code == 200

    def test_pic_of_another_tiket_is_404(self, client, tiket, admin_user):
        other = TiketPICFactory(role=P3DE)
        client.force_login(admin_user)
        url = reverse('tiket_pic_hapus', kwargs={'pk': tiket.pk, 'pic_pk': other.pk})
        assert client.post(url, **AJAX).status_code == 404
        assert TiketPIC.objects.filter(pk=other.pk).exists()


@pytest.mark.django_db
class TestTambah:
    def test_adds_active_pic_and_logs_it(self, client, tiket, p3de_admin_user):
        baru = _member('user_p3de')
        pic_count = PIC.objects.count()
        client.force_login(p3de_admin_user)

        resp = client.post(_tambah_url(tiket, P3DE), {'role': 1, 'id_user': baru.pk}, **AJAX)

        assert resp.status_code == 200 and resp.json()['success']
        row = TiketPIC.objects.get(id_tiket=tiket, id_user=baru, role=P3DE)
        assert row.active and row.timestamp is not None
        action = TiketAction.objects.get(id_tiket=tiket)
        assert action.action == PICActionType.DITAMBAHKAN
        assert action.id_user == p3de_admin_user
        assert action.catatan == f'PIC P3DE {baru.username} ditambahkan langsung di tiket'
        assert PIC.objects.count() == pic_count

    def test_reuses_an_inactive_row_instead_of_duplicating(self, client, tiket, p3de_admin_user):
        lama = TiketPICFactory(id_tiket=tiket, id_user=_member('user_p3de'), role=P3DE, active=False)
        client.force_login(p3de_admin_user)

        resp = client.post(_tambah_url(tiket, P3DE), {'role': 1, 'id_user': lama.id_user_id}, **AJAX)

        assert resp.json()['success']
        assert TiketPIC.objects.filter(id_tiket=tiket, id_user=lama.id_user, role=P3DE).count() == 1
        lama.refresh_from_db()
        assert lama.active
        assert TiketAction.objects.get().action == PICActionType.DIAKTIFKAN_KEMBALI

    def test_choices_are_the_role_group_minus_active_pics(self, client, tiket, p3de_pic, p3de_admin_user):
        lain = _member('user_p3de')
        pide = _member('user_pide')
        client.force_login(p3de_admin_user)
        html = client.get(_tambah_url(tiket, P3DE), **AJAX).content.decode()
        assert f'value="{lain.pk}"' in html
        assert f'value="{p3de_pic.id_user_id}"' not in html
        assert f'value="{pide.pk}"' not in html

    def test_superusers_are_not_offered(self, client, tiket, p3de_admin_user):
        superuser = _member('user_p3de', is_superuser=True, is_staff=True)
        biasa = _member('user_p3de')
        client.force_login(p3de_admin_user)
        html = client.get(_tambah_url(tiket, P3DE), **AJAX).content.decode()
        assert f'value="{biasa.pk}"' in html
        assert f'value="{superuser.pk}"' not in html

    def test_existing_superuser_pic_can_still_be_switched_off(self, client, tiket, p3de_admin_user):
        pic = TiketPICFactory(
            id_tiket=tiket, role=P3DE, active=True,
            id_user=_member('user_p3de', is_superuser=True, is_staff=True),
        )
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(pic), {'id_user': pic.id_user_id}, **AJAX)
        assert resp.json()['success']
        pic.refresh_from_db()
        assert not pic.active

    @pytest.mark.parametrize('kind', ['already_active', 'other_group', 'superuser'])
    def test_rejects_invalid_user(self, client, tiket, p3de_pic, p3de_admin_user, kind):
        user = {
            'already_active': lambda: p3de_pic.id_user,
            'other_group': lambda: _member('user_pide'),
            'superuser': lambda: _member('user_p3de', is_superuser=True),
        }[kind]()
        client.force_login(p3de_admin_user)

        resp = client.post(_tambah_url(tiket, P3DE), {'role': 1, 'id_user': user.pk}, **AJAX)

        assert resp.status_code == 400
        assert not resp.json()['success'] and '<form' in resp.json()['html']
        assert TiketPIC.objects.filter(id_tiket=tiket).count() == 1
        assert not TiketAction.objects.exists()


@pytest.mark.django_db
class TestUbah:
    def test_deactivate(self, client, p3de_pic, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(p3de_pic), {'id_user': p3de_pic.id_user_id}, **AJAX)

        assert resp.json()['success']
        p3de_pic.refresh_from_db()
        assert not p3de_pic.active
        action = TiketAction.objects.get()
        assert action.action == PICActionType.TIDAK_AKTIF
        assert action.catatan.endswith('dinonaktifkan langsung di tiket')

    def test_reactivate(self, client, tiket, p3de_admin_user):
        pic = TiketPICFactory(id_tiket=tiket, id_user=_member('user_p3de'), role=P3DE, active=False)
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(pic), {'id_user': pic.id_user_id, 'active': 'on'}, **AJAX)

        assert resp.json()['success']
        pic.refresh_from_db()
        assert pic.active
        assert TiketAction.objects.get().action == PICActionType.DIAKTIFKAN_KEMBALI

    def test_no_change_is_rejected(self, client, p3de_pic, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(p3de_pic), {'id_user': p3de_pic.id_user_id, 'active': 'on'}, **AJAX)

        assert resp.status_code == 400
        assert resp.json()['message'] == 'Tidak ada perubahan.'
        p3de_pic.refresh_from_db()
        assert p3de_pic.active
        assert not TiketAction.objects.exists()

    def test_changing_user_hands_over(self, client, tiket, p3de_pic, p3de_admin_user):
        lama = p3de_pic.id_user
        baru = _member('user_p3de')
        client.force_login(p3de_admin_user)

        resp = client.post(_ubah_url(p3de_pic), {'id_user': baru.pk, 'active': 'on'}, **AJAX)

        assert resp.json()['success']
        p3de_pic.refresh_from_db()
        assert p3de_pic.id_user == lama and not p3de_pic.active
        new_row = TiketPIC.objects.get(id_tiket=tiket, id_user=baru, role=P3DE)
        assert new_row.active
        catatan = list(TiketAction.objects.order_by('id').values_list('action', 'catatan'))
        assert catatan == [
            (PICActionType.TIDAK_AKTIF,
             f'PIC P3DE {lama.username} diganti oleh {baru.username} langsung di tiket'),
            (PICActionType.DITAMBAHKAN,
             f'PIC P3DE {baru.username} ditambahkan langsung di tiket (menggantikan {lama.username})'),
        ]

    def test_hand_over_to_inactive_user_is_rejected(self, client, p3de_pic, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(p3de_pic), {'id_user': _member('user_p3de').pk}, **AJAX)

        assert resp.status_code == 400
        assert 'PIC pengganti harus berstatus aktif.' in resp.json()['html']
        assert TiketPIC.objects.count() == 1

    def test_current_user_stays_selectable_after_leaving_group(self, client, p3de_pic, p3de_admin_user):
        p3de_pic.id_user.groups.clear()
        client.force_login(p3de_admin_user)
        resp = client.post(_ubah_url(p3de_pic), {'id_user': p3de_pic.id_user_id}, **AJAX)
        assert resp.json()['success']


@pytest.mark.django_db
class TestHapus:
    def test_deletes_row_and_logs(self, client, tiket, p3de_pic, p3de_admin_user):
        username = p3de_pic.id_user.username
        client.force_login(p3de_admin_user)

        html = client.get(_hapus_url(p3de_pic), **AJAX).content.decode()
        assert 'satu-satunya PIC P3DE aktif' in html

        resp = client.post(_hapus_url(p3de_pic), **AJAX)

        assert resp.json()['success']
        assert not TiketPIC.objects.filter(pk=p3de_pic.pk).exists()
        action = TiketAction.objects.get(id_tiket=tiket)
        assert action.action == PICActionType.TIDAK_AKTIF
        assert action.id_user == p3de_admin_user
        assert action.catatan == f'PIC P3DE {username} dihapus langsung di tiket'


@pytest.mark.django_db
class TestHanyaTiketIni:
    def test_pic_table_and_other_tikets_untouched(self, client, tiket, p3de_admin_user):
        sub = tiket.id_periode_data.id_sub_jenis_data_ilap
        other = TiketFactory(status_tiket=1, id_periode_data=tiket.id_periode_data)
        PICFactory(tipe='P3DE', id_sub_jenis_data_ilap=sub, end_date=None)
        pic_rows = list(PIC.objects.values_list('id', 'id_user', 'end_date'))
        baru = _member('user_p3de')
        client.force_login(p3de_admin_user)

        client.post(_tambah_url(tiket, P3DE), {'role': 1, 'id_user': baru.pk}, **AJAX)

        assert TiketPIC.objects.filter(id_tiket=tiket, id_user=baru).exists()
        assert list(PIC.objects.values_list('id', 'id_user', 'end_date')) == pic_rows
        assert not TiketPIC.objects.filter(id_tiket=other).exists()
        assert not TiketAction.objects.filter(id_tiket=other).exists()


@pytest.mark.django_db
class TestDetailPage:
    def test_seksi_admin_sees_controls_for_own_role_only(self, client, tiket, p3de_pic, p3de_admin_user):
        pide = TiketPICFactory(id_tiket=tiket, id_user=_member('user_pide'), role=PIDE)
        client.force_login(p3de_admin_user)

        html = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk})).content.decode()

        assert 'id="kelolaPicTiketModal"' in html
        assert 'id="edit-pic-tiket-toggle"' in html
        assert 'id="tambah-pic-tiket-btn"' in html
        assert _tambah_url(tiket, P3DE) in html
        assert _ubah_url(p3de_pic) in html and _hapus_url(p3de_pic) in html
        assert _ubah_url(pide) not in html and _hapus_url(pide) not in html
        assert '{#' not in html and '{%' not in html

    def test_global_admin_gets_role_dropdown(self, client, tiket, admin_user):
        client.force_login(admin_user)
        html = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk})).content.decode()
        for role in (P3DE, PIDE, PMDE):
            assert _tambah_url(tiket, role) in html

    def test_non_admin_sees_no_controls(self, client, tiket, p3de_pic):
        client.force_login(p3de_pic.id_user)
        html = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk})).content.decode()
        assert 'id="kelolaPicTiketModal"' not in html
        assert 'id="tambah-pic-tiket-btn"' not in html
        assert 'id="edit-pic-tiket-toggle"' not in html
        assert _hapus_url(p3de_pic) not in html
