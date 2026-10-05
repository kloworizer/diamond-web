"""Seksi P3DE dipecah menjadi P3DE dan P3DER.

Kedua seksi menjalankan tahap alur kerja yang sama (rekam, tanda terima,
penelitian, kirim ke PIDE), sehingga PIC dan TiketPIC keduanya tetap bertipe
`P3DE`. Yang membedakan adalah ILAP-nya: ILAP berkategori wilayah Regional
ditangani Seksi P3DER, ILAP Nasional dan Internasional ditangani Seksi P3DE.
Masing-masing seksi punya grup admin, user, dan kasi sendiri.
"""
import pytest
from django.contrib.auth.models import Group, User
from django.template.loader import render_to_string
from django.urls import reverse

from diamond_web.forms.pic import PICForm
from diamond_web.models.kategori_wilayah import KategoriWilayah
from diamond_web.models.pic import PIC
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
from diamond_web.views.mixins import (
    SEKSI_P3DE,
    SEKSI_P3DER,
    can_open_tiket,
    can_view_ilap_kontak,
    is_admin_p3de,
    is_kasi_p3de,
    p3de_seksi_of,
    p3de_seksi_of_user,
    tiket_pic_roles_managed_by,
)
from diamond_web.views.task_to_do import get_tiket_summary_for_user_p3de

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def _member(*group_names, **kwargs):
    user = UserFactory(**kwargs)
    for name in group_names:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _wilayah(deskripsi):
    return KategoriWilayah.objects.get_or_create(deskripsi=deskripsi)[0]


def _jenis_data(deskripsi):
    return JenisDataILAPFactory(id_ilap=ILAPFactory(id_kategori_wilayah=_wilayah(deskripsi)))


def _tiket(deskripsi, **kwargs):
    periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=_jenis_data(deskripsi))
    return TiketFactory(id_periode_data=periode, **kwargs)


@pytest.fixture
def regional(db):
    return _tiket('Regional')


@pytest.fixture
def nasional(db):
    return _tiket('Nasional')


@pytest.fixture
def internasional(db):
    return _tiket('Internasional')


@pytest.mark.django_db
class TestMigration:
    def test_groups_exist(self):
        for name in ('admin_p3der', 'user_p3der', 'kasi_p3der'):
            assert Group.objects.filter(name=name).exists()

    def test_placeholder_kasi_cannot_log_in_yet(self):
        kasi = User.objects.get(username='kasi_p3der')
        assert kasi.groups.filter(name='kasi_p3der').exists()
        assert not kasi.has_usable_password()


@pytest.mark.django_db
class TestSeksiOfIlap:
    def test_regional_belongs_to_p3der(self, regional):
        assert p3de_seksi_of(regional) == SEKSI_P3DER
        assert p3de_seksi_of(regional.id_periode_data.id_sub_jenis_data_ilap) == SEKSI_P3DER

    def test_nasional_and_internasional_belong_to_p3de(self, nasional, internasional):
        assert p3de_seksi_of(nasional) == SEKSI_P3DE
        assert p3de_seksi_of(internasional) == SEKSI_P3DE

    @pytest.mark.parametrize('groups, expected', [
        (('user_p3de',), {SEKSI_P3DE}),
        (('kasi_p3der',), {SEKSI_P3DER}),
        (('admin_p3de', 'user_p3der'), {SEKSI_P3DE, SEKSI_P3DER}),
        (('admin',), {SEKSI_P3DE, SEKSI_P3DER}),
        (('user_pide',), set()),
    ])
    def test_seksi_of_user(self, groups, expected):
        assert p3de_seksi_of_user(_member(*groups)) == expected


@pytest.mark.django_db
class TestSupervisorScope:
    def test_admin_p3der_administers_regional_only(self, regional, nasional):
        admin = _member('admin_p3der')
        assert is_admin_p3de(admin, regional)
        assert not is_admin_p3de(admin, nasional)
        assert tiket_pic_roles_managed_by(admin, regional) == [TiketPIC.Role.P3DE]
        assert tiket_pic_roles_managed_by(admin, nasional) == []

    def test_admin_p3de_administers_nasional_and_internasional(self, regional, nasional, internasional):
        admin = _member('admin_p3de')
        assert is_admin_p3de(admin, nasional)
        assert is_admin_p3de(admin, internasional)
        assert not is_admin_p3de(admin, regional)

    def test_kasi_opens_own_seksi_tikets_only(self, regional, nasional):
        kasi = _member('kasi_p3der')
        assert is_kasi_p3de(kasi, regional) and can_open_tiket(kasi, regional)
        assert not can_open_tiket(kasi, nasional)

    def test_kasi_pide_still_opens_every_tiket(self, regional, nasional):
        kasi = _member('kasi_pide')
        assert can_open_tiket(kasi, regional) and can_open_tiket(kasi, nasional)

    def test_kontak_follows_seksi(self, regional, nasional):
        kasi = _member('kasi_p3der')
        assert can_view_ilap_kontak(kasi, regional.id_periode_data.id_sub_jenis_data_ilap.id_ilap)
        assert not can_view_ilap_kontak(kasi, nasional.id_periode_data.id_sub_jenis_data_ilap.id_ilap)

    def test_detail_page(self, client, regional, nasional):
        client.force_login(_member('admin_p3der'))
        assert client.get(reverse('tiket_detail', args=[regional.pk])).status_code == 200
        assert client.get(reverse('tiket_detail', args=[nasional.pk])).status_code in (302, 403)

    def test_admin_p3der_edits_regional_tiket_at_any_status(self, client, regional, nasional):
        regional.status_tiket = nasional.status_tiket = 4
        regional.save(update_fields=['status_tiket'])
        nasional.save(update_fields=['status_tiket'])
        client.force_login(_member('admin_p3der'))
        assert client.get(reverse('edit_tiket', args=[regional.pk]), **AJAX).status_code == 200
        assert client.get(reverse('edit_tiket', args=[nasional.pk]), **AJAX).status_code == 403


@pytest.mark.django_db
class TestTiketList:
    def _ids(self, client):
        resp = client.get(reverse('tiket_data'), {'draw': 1, 'start': 0, 'length': 100})
        assert resp.status_code == 200
        return {row['id'] for row in resp.json()['data']}

    def test_kasi_p3der_lists_regional_tikets(self, client, regional, nasional, internasional):
        client.force_login(_member('kasi_p3der'))
        ids = self._ids(client)
        assert regional.pk in ids
        assert nasional.pk not in ids and internasional.pk not in ids

    def test_kasi_p3de_lists_nasional_and_internasional(self, client, regional, nasional, internasional):
        client.force_login(_member('kasi_p3de'))
        ids = self._ids(client)
        assert {nasional.pk, internasional.pk} <= ids
        assert regional.pk not in ids

    def test_kasi_also_keeps_own_pic_tikets(self, client, regional, nasional):
        kasi = _member('kasi_p3der')
        TiketPICFactory(id_tiket=nasional, id_user=kasi)
        client.force_login(kasi)
        assert {regional.pk, nasional.pk} <= self._ids(client)

    def test_user_p3der_lists_own_pic_tikets(self, client, regional, nasional):
        user = _member('user_p3der')
        TiketPICFactory(id_tiket=regional, id_user=user)
        client.force_login(user)
        assert self._ids(client) == {regional.pk}

    def test_kasi_summary_counts_own_seksi(self, regional, nasional):
        regional.backup = nasional.backup = False
        regional.save(update_fields=['backup'])
        nasional.save(update_fields=['backup'])
        summary = get_tiket_summary_for_user_p3de(_member('kasi_p3der'))
        assert summary['rekam_backup_data'] == 1


@pytest.mark.django_db
class TestPICP3DE:
    def test_regional_jenis_data_takes_a_p3der_user(self):
        jd = _jenis_data('Regional')
        data = {'tipe': PIC.TipePIC.P3DE, 'id_sub_jenis_data_ilap': jd.pk, 'start_date': '2026-01-01'}

        form = PICForm(data={**data, 'id_user': _member('user_p3de').pk}, tipe=PIC.TipePIC.P3DE)
        assert not form.is_valid()
        assert 'Seksi P3DER' in str(form.errors['id_user'])

        form = PICForm(data={**data, 'id_user': _member('user_p3der').pk}, tipe=PIC.TipePIC.P3DE)
        assert form.is_valid(), form.errors

    def test_nasional_jenis_data_takes_a_p3de_user(self):
        jd = _jenis_data('Nasional')
        data = {'tipe': PIC.TipePIC.P3DE, 'id_sub_jenis_data_ilap': jd.pk, 'start_date': '2026-01-01'}
        form = PICForm(data={**data, 'id_user': _member('user_p3der').pk}, tipe=PIC.TipePIC.P3DE)
        assert not form.is_valid()
        assert 'Seksi P3DE' in str(form.errors['id_user'])

    def test_admin_form_offers_own_seksi_only(self):
        regional, nasional = _jenis_data('Regional'), _jenis_data('Nasional')
        p3der_user, p3de_user = _member('user_p3der'), _member('user_p3de')
        form = PICForm(tipe=PIC.TipePIC.P3DE, p3de_seksi={SEKSI_P3DER})
        subs = set(form.fields['id_sub_jenis_data_ilap'].queryset)
        users = set(form.fields['id_user'].queryset)
        assert regional in subs and nasional not in subs
        assert p3der_user in users and p3de_user not in users

    def test_moved_user_can_still_be_closed(self):
        """A PIC whose user has moved to the other seksi can still be ended."""
        moved = _member('user_p3der')
        pic = PICFactory(id_sub_jenis_data_ilap=_jenis_data('Nasional'), id_user=moved,
                         start_date='2026-01-01', end_date=None)
        form = PICForm(instance=pic, tipe=PIC.TipePIC.P3DE, data={
            'id_user': moved.pk, 'start_date': '2026-01-01', 'end_date': '2026-02-01',
        })
        assert form.is_valid(), form.errors

    def test_data_endpoint_lists_own_seksi(self, client):
        regional = PICFactory(id_sub_jenis_data_ilap=_jenis_data('Regional'), end_date=None)
        nasional = PICFactory(id_sub_jenis_data_ilap=_jenis_data('Nasional'), end_date=None)
        client.force_login(_member('user_p3der'))
        resp = client.get(reverse('pic_p3de_data'), {'draw': 1, 'start': 0, 'length': 100})
        ids = {row['id'] for row in resp.json()['data']}
        assert regional.pk in ids and nasional.pk not in ids

    def test_admin_p3de_cannot_edit_regional_pic(self, client):
        pic = PICFactory(id_sub_jenis_data_ilap=_jenis_data('Regional'), end_date=None)
        client.force_login(_member('admin_p3de'))
        resp = client.get(reverse('pic_p3de_update', args=[pic.pk]), {'ajax': 1})
        assert resp.status_code == 404


@pytest.mark.django_db
class TestKelolaPICTiket:
    def test_admin_p3der_manages_regional_tiket(self, client, regional, nasional):
        client.force_login(_member('admin_p3der'))
        url = reverse('tiket_pic_tambah', kwargs={'pk': regional.pk}) + f'?role={int(TiketPIC.Role.P3DE)}'
        assert client.get(url, **AJAX).status_code == 200
        url = reverse('tiket_pic_tambah', kwargs={'pk': nasional.pk}) + f'?role={int(TiketPIC.Role.P3DE)}'
        assert client.get(url, **AJAX).status_code == 403

    def test_candidates_come_from_p3der(self, client, regional):
        p3der_user, p3de_user = _member('user_p3der'), _member('user_p3de')
        client.force_login(_member('admin'))
        url = reverse('tiket_pic_tambah', kwargs={'pk': regional.pk})
        resp = client.post(url, {'role': int(TiketPIC.Role.P3DE), 'id_user': p3de_user.pk}, **AJAX)
        assert resp.status_code == 400
        resp = client.post(url, {'role': int(TiketPIC.Role.P3DE), 'id_user': p3der_user.pk}, **AJAX)
        assert resp.json()['success'] is True


@pytest.mark.django_db
class TestMenus:
    def _navbar(self, user):
        return render_to_string('navbar.html', {'user': user})

    def test_user_p3der_navbar(self):
        html = self._navbar(_member('user_p3der'))
        assert '<label>P3DER</label>' in html
        assert 'PIC P3DER' in html
        assert 'Kirim Tiket ke PIDE' in html

    def test_admin_p3der_navbar(self):
        html = self._navbar(_member('admin_p3der'))
        assert '<label>Admin P3DER</label>' in html
        assert 'Kelola Referensi P3DE' in html

    def test_kasi_p3der_navbar(self):
        html = self._navbar(_member('kasi_p3der'))
        assert '<label>P3DER</label>' in html
        assert 'Kirim Tiket ke PIDE' not in html

    @pytest.mark.parametrize('url_name', ['tiket_rekam_create', 'kirim_tiket', 'backup_data_list',
                                          'tanda_terima_data_list', 'monitoring_penyampaian_data_list'])
    def test_user_p3der_reaches_p3de_workflow_menus(self, client, url_name):
        client.force_login(_member('user_p3der'))
        assert client.get(reverse(url_name)).status_code == 200

    @pytest.mark.parametrize('url_name', ['kategori_ilap_list', 'ilap_list', 'kpp_list', 'sequence_tanda_terima_list'])
    def test_admin_p3der_reaches_shared_reference_menus(self, client, url_name):
        client.force_login(_member('admin_p3der'))
        assert client.get(reverse(url_name)).status_code == 200

    def test_home_names_the_seksi(self, client):
        client.force_login(_member('user_p3der'))
        resp = client.get(reverse('home'))
        assert resp.context['is_p3de'] is True
        assert 'Pelaksana P3DER' in resp.content.decode()
