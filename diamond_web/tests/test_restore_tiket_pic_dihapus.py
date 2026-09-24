"""Tests for the ``restore_tiket_pic_dihapus`` command.

Deleting a PIC row deletes the tiket assignments outright and leaves only a
"PIC <tipe> <user> dihapus" action behind. What matters here is that the command
restores exactly those tikets and nothing else, that it takes the *current* pic
table as the answer to who goes back on, that the deletion history survives, and
that a dry run writes nothing.
"""
from datetime import date, datetime
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from diamond_web.constants.tiket_action_types import PICActionType
from diamond_web.models.pic import PIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC

from .conftest import (
    JenisDataILAPFactory,
    PeriodeJenisDataFactory,
    PeriodePengirimanFactory,
    PICFactory,
    TiketFactory,
    TiketPICFactory,
    UserFactory,
)

_SEQ = iter(range(1, 10_000))


def _run(*args):
    out = StringIO()
    call_command('restore_tiket_pic_dihapus', *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def _tiket(jenis_data, status=4):
    periode = PeriodeJenisDataFactory(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman=PeriodePengirimanFactory(
            periode_penyampaian=f'RESTORE {next(_SEQ)}'
        ),
    )
    return TiketFactory(id_periode_data=periode, status_tiket=status)


def _pic(jenis_data, tipe, user, end_date=None):
    return PICFactory(
        tipe=tipe, id_sub_jenis_data_ilap=jenis_data, id_user=user,
        start_date=date(2025, 1, 1), end_date=end_date,
    )


def _delete_action(tiket, tipe, username, admin):
    """The row PICDeleteView leaves behind when a PIC is deleted."""
    return TiketAction.objects.create(
        id_tiket=tiket,
        id_user=admin,
        timestamp=datetime(2026, 1, 5, 8, 0),
        action=PICActionType.TIDAK_AKTIF,
        catatan=f'{dict(PIC.TipePIC.choices)[tipe]} {username} dihapus',
    )


@pytest.fixture
def admin(db):
    """The `admin` account PICDeleteView credits its rows to (seeded by migration)."""
    user, _ = User.objects.get_or_create(username='admin')
    return user


@pytest.mark.django_db
class TestRestoreTiketPicDihapus:
    def test_restores_from_the_current_pic_table(self, admin):
        """The person deleted then may not be the PIC now — pic table decides."""
        jenis_data = JenisDataILAPFactory()
        dulu = UserFactory(username='pic_lama_pide')
        sekarang = UserFactory(username='pic_baru_pide')
        _pic(jenis_data, PIC.TipePIC.PIDE, sekarang)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, dulu.username, admin)

        out = _run()

        rows = TiketPIC.objects.filter(id_tiket=tiket, role=TiketPIC.Role.PIDE)
        assert [(r.id_user_id, r.active) for r in rows] == [(sekarang.pk, True)]
        assert 'Selesai: 1 penugasan dibuat' in out

    def test_only_tikets_with_a_delete_action_are_touched(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        kena = _tiket(jenis_data)
        _delete_action(kena, PIC.TipePIC.PIDE, pic_user.username, admin)
        tidak_kena = _tiket(jenis_data)  # same jenis data, no deletion recorded

        _run()

        assert TiketPIC.objects.filter(id_tiket=kena).count() == 1
        assert TiketPIC.objects.filter(id_tiket=tidak_kena).count() == 0

    def test_deletion_history_is_kept_and_the_restore_is_logged(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory(username='pic_dihapus_pide')
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        _run()

        catatan = list(
            TiketAction.objects.filter(id_tiket=tiket).values_list('action', 'catatan')
        )
        assert (PICActionType.TIDAK_AKTIF, 'PIC PIDE pic_dihapus_pide dihapus') in catatan
        assert (PICActionType.DITAMBAHKAN,
                'PIC PIDE pic_dihapus_pide ditambahkan (dikembalikan)') in catatan

    def test_dry_run_writes_nothing(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        out = _run('--dry-run')

        assert 'Akan dikembalikan : 1 penugasan' in out
        assert TiketPIC.objects.count() == 0
        assert TiketAction.objects.filter(action=PICActionType.DITAMBAHKAN).count() == 0

    def test_rerunning_is_a_no_op(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        _run()
        out = _run()

        assert TiketPIC.objects.filter(id_tiket=tiket).count() == 1
        assert 'sudah aktif     : 1' in out

    def test_an_inactive_row_is_reactivated_not_duplicated(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PMDE, pic_user)
        tiket = _tiket(jenis_data, status=6)
        TiketPICFactory(id_tiket=tiket, id_user=pic_user,
                        role=TiketPIC.Role.PMDE, active=False)
        _delete_action(tiket, PIC.TipePIC.PMDE, pic_user.username, admin)

        _run()

        rows = TiketPIC.objects.filter(id_tiket=tiket, role=TiketPIC.Role.PMDE)
        assert rows.count() == 1
        assert rows.first().active is True
        assert TiketAction.objects.filter(
            id_tiket=tiket, action=PICActionType.DIAKTIFKAN_KEMBALI
        ).exists()

    def test_two_open_pic_rows_for_one_person_restore_one_assignment(self, admin):
        """The pic table allows the same person twice; the tiket takes them once."""
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        _run()

        assert TiketPIC.objects.filter(id_tiket=tiket, id_user=pic_user).count() == 1
        assert TiketAction.objects.filter(
            id_tiket=tiket, action=PICActionType.DITAMBAHKAN
        ).count() == 1

    def test_a_closed_pic_is_not_a_reference(self, admin):
        """An end_date means the PIC is over; there is nobody to restore."""
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user, end_date=date(2025, 6, 30))
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        out = _run()

        assert TiketPIC.objects.count() == 0
        assert 'tidak bisa dikembalikan' in out

    def test_deactivation_actions_are_not_deletions(self, admin):
        """"tidak aktif" is the end_date path, which kept its TiketPIC row."""
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        TiketAction.objects.create(
            id_tiket=tiket, id_user=admin, timestamp=datetime(2026, 1, 5, 8, 0),
            action=PICActionType.TIDAK_AKTIF,
            catatan=f'PIC PIDE {pic_user.username} tidak aktif',
        )

        out = _run()

        assert TiketPIC.objects.count() == 0
        assert 'Tidak ada aksi' in out

    def test_tipe_filter_limits_the_scope(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_pide = UserFactory()
        pic_pmde = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_pide)
        _pic(jenis_data, PIC.TipePIC.PMDE, pic_pmde)
        tiket = _tiket(jenis_data, status=6)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_pide.username, admin)
        _delete_action(tiket, PIC.TipePIC.PMDE, pic_pmde.username, admin)

        _run('--tipe', 'PMDE')

        roles = set(TiketPIC.objects.filter(id_tiket=tiket).values_list('role', flat=True))
        assert roles == {TiketPIC.Role.PMDE}

    def test_user_filter_limits_the_scope(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory()
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        satu = _tiket(jenis_data)
        dua = _tiket(jenis_data)
        _delete_action(satu, PIC.TipePIC.PIDE, '910223210', admin)
        _delete_action(dua, PIC.TipePIC.PIDE, '111111111', admin)

        _run('--user', '910223210')

        assert TiketPIC.objects.filter(id_tiket=satu).count() == 1
        assert TiketPIC.objects.filter(id_tiket=dua).count() == 0

    def test_restored_catatan_fits_the_column(self, admin):
        jenis_data = JenisDataILAPFactory()
        pic_user = UserFactory(username='x' * 150)
        _pic(jenis_data, PIC.TipePIC.PIDE, pic_user)
        tiket = _tiket(jenis_data)
        _delete_action(tiket, PIC.TipePIC.PIDE, pic_user.username, admin)

        _run()

        catatan = TiketAction.objects.filter(
            id_tiket=tiket, action=PICActionType.DITAMBAHKAN
        ).values_list('catatan', flat=True).first()
        assert len(catatan) <= TiketAction._meta.get_field('catatan').max_length
