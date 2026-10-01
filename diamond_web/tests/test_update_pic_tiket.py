"""Menu Sinkronisasi Data > Update PIC Tiket.

Tiket yang tidak punya PIC aktif untuk suatu role diisi dari tabel PIC; role
yang sudah punya PIC aktif tidak disentuh. Halaman hanya preview, PROSES yang menulis.
"""
from datetime import date, timedelta

import pytest
from django.urls import reverse

from diamond_web.constants.tiket_action_types import PICActionType
from diamond_web.constants.tiket_status import STATUS_DIBATALKAN, STATUS_SELESAI
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import (
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)

PAGE = 'update_pic_tiket_page'
PROSES = 'update_pic_tiket_proses'
TODAY = date.today()


def _pic(sub, tipe, user=None, start=None, end=None):
    return PICFactory(
        id_sub_jenis_data_ilap=sub, tipe=tipe, id_user=user or UserFactory(),
        start_date=start or TODAY - timedelta(days=30), end_date=end,
    )


def _active(tiket, role):
    return set(
        TiketPIC.objects.filter(id_tiket=tiket, role=role, active=True)
        .values_list('id_user__username', flat=True)
    )


@pytest.fixture
def skenario(db):
    """Satu tiket dengan tiga keadaan role sekaligus.

    - P3DE: kosong, tabel PIC punya 2 PIC aktif (+1 sudah berakhir, +1 belum mulai).
    - PIDE: sudah punya PIC aktif, berbeda dari tabel PIC -> tidak boleh disentuh.
    - PMDE: kosong, punya baris nonaktif untuk user yang sama dengan tabel PIC
      -> diaktifkan kembali, bukan baris ganda.
    """
    tiket = TiketFactory(status_tiket=STATUS_SELESAI)
    sub = tiket.id_periode_data.id_sub_jenis_data_ilap

    p3de_a = _pic(sub, 'P3DE').id_user
    p3de_b = _pic(sub, 'P3DE').id_user
    _pic(sub, 'P3DE', end=TODAY - timedelta(days=1))            # sudah berakhir
    _pic(sub, 'P3DE', start=TODAY + timedelta(days=5))          # belum mulai

    pide_lama = TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True).id_user
    _pic(sub, 'PIDE')

    pmde = _pic(sub, 'PMDE').id_user
    nonaktif = TiketPICFactory(id_tiket=tiket, id_user=pmde, role=TiketPIC.Role.PMDE, active=False)

    return {
        'tiket': tiket, 'p3de': {p3de_a.username, p3de_b.username},
        'pide_lama': pide_lama, 'pmde': pmde, 'nonaktif': nonaktif,
    }


@pytest.mark.django_db
class TestAkses:
    def test_non_admin_is_refused(self, client, authenticated_user):
        client.force_login(authenticated_user)
        assert client.get(reverse(PAGE)).status_code in (302, 403)
        assert client.post(reverse(PROSES)).status_code in (302, 403)
        assert not TiketAction.objects.exists()

    def test_proses_requires_post(self, client, admin_user):
        client.force_login(admin_user)
        assert client.get(reverse(PROSES)).status_code == 405

    def test_menu_follows_sinkronisasi_tarikan_tiket(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get(reverse(PAGE)).content.decode()
        tarikan = html.index('Sinkronisasi Tarikan Tiket</span>')
        menu = html.index('Update PIC Tiket</span>')
        status = html.index('Status Sinkronisasi</span>')
        assert tarikan < menu < status
        assert reverse(PAGE) in html


@pytest.mark.django_db
class TestPreview:
    def test_preview_lists_only_roles_without_active_pic(self, client, admin_user, skenario):
        client.force_login(admin_user)
        resp = client.get(reverse(PAGE))
        assert resp.status_code == 200
        ctx = resp.context

        rows = {r['role']: r for r in ctx['rows']}
        assert set(rows) == {'P3DE', 'PMDE'}
        assert {p['username'] for p in rows['P3DE']['pic']} == skenario['p3de']
        assert rows['PMDE']['pic'] == [{'username': skenario['pmde'].username, 'aktifkan': True}]
        assert (ctx['total_tiket'], ctx['total_celah'], ctx['total_pic']) == (1, 2, 3)

        per_role = {r['label']: r for r in ctx['per_role']}
        assert per_role['PIDE']['tanpa_pic'] == 0
        assert per_role['P3DE']['diisi'] == 1

    def test_preview_writes_nothing(self, client, admin_user, skenario):
        client.force_login(admin_user)
        before = TiketPIC.objects.count()
        client.get(reverse(PAGE))
        assert TiketPIC.objects.count() == before
        assert not TiketAction.objects.exists()
        assert _active(skenario['tiket'], TiketPIC.Role.P3DE) == set()

    def test_tiket_without_source_pic_is_listed_separately(self, client, admin_user):
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN)
        sub = tiket.id_periode_data.id_sub_jenis_data_ilap
        _pic(sub, 'P3DE', end=TODAY - timedelta(days=1))  # hanya PIC yang sudah berakhir
        client.force_login(admin_user)
        ctx = client.get(reverse(PAGE)).context

        assert ctx['rows'] == []
        assert ctx['total_tanpa_sumber'] == 3
        assert {(r['id_sub_jenis_data'], r['role_label'], r['jumlah_tiket']) for r in ctx['tanpa_sumber']} == {
            (sub.id_sub_jenis_data, 'P3DE', 1),
            (sub.id_sub_jenis_data, 'PIDE', 1),
            (sub.id_sub_jenis_data, 'PMDE', 1),
        }

    def test_page_renders_cleanly(self, client, admin_user, skenario):
        client.force_login(admin_user)
        html = client.get(reverse(PAGE)).content.decode()
        assert '{#' not in html and '{%' not in html and '{{' not in html
        assert 'id="upt-preview-table"' in html
        assert skenario['tiket'].nomor_tiket in html  # dalam json_script untuk DataTables

    def test_empty_state_disables_proses(self, client, admin_user):
        client.force_login(admin_user)
        html = client.get(reverse(PAGE)).content.decode()
        assert 'id="upt-empty"' in html
        assert 'id="upt-preview-table"' not in html
        btn = html[html.index('id="btn-upt-proses"'):]
        assert 'disabled' in btn[:btn.index('>')]


@pytest.mark.django_db
class TestProses:
    def test_fills_only_empty_roles_and_logs_actions(self, client, admin_user, skenario):
        tiket = skenario['tiket']
        client.force_login(admin_user)
        resp = client.post(reverse(PROSES), follow=True)
        assert resp.redirect_chain[-1][0] == reverse(PAGE)
        msg = [str(m) for m in resp.context['messages']]
        assert msg == ['PIC diisi pada 1 tiket: 2 PIC ditambahkan, 1 PIC diaktifkan kembali.']

        assert _active(tiket, TiketPIC.Role.P3DE) == skenario['p3de']
        # PIDE sudah punya PIC aktif: tetap PIC lama, PIC di tabel tidak ditambahkan.
        assert _active(tiket, TiketPIC.Role.PIDE) == {skenario['pide_lama'].username}
        # PMDE: baris lama diaktifkan, tidak ada baris ganda.
        assert TiketPIC.objects.filter(id_tiket=tiket, role=TiketPIC.Role.PMDE).count() == 1
        skenario['nonaktif'].refresh_from_db()
        assert skenario['nonaktif'].active is True

        actions = TiketAction.objects.filter(id_tiket=tiket)
        assert actions.count() == 3
        assert set(actions.values_list('id_user', flat=True)) == {admin_user.pk}
        assert actions.filter(action=PICActionType.DITAMBAHKAN).count() == 2
        reaktif = actions.get(action=PICActionType.DIAKTIFKAN_KEMBALI)
        assert reaktif.catatan == f"PIC PMDE {skenario['pmde'].username} diaktifkan kembali"

    def test_rerun_is_noop(self, client, admin_user, skenario):
        client.force_login(admin_user)
        client.post(reverse(PROSES), follow=True)  # follow: consume the success message
        pics, actions = TiketPIC.objects.count(), TiketAction.objects.count()

        resp = client.post(reverse(PROSES), follow=True)
        assert [str(m) for m in resp.context['messages']] == ['Tidak ada tiket yang perlu diisi PIC-nya.']
        assert (TiketPIC.objects.count(), TiketAction.objects.count()) == (pics, actions)
        assert resp.context['rows'] == []
