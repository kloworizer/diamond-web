"""fix_tiket_dikembalikan_sync: repair tikets returned by the sync's Aturan 4."""

from datetime import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from diamond_web.constants.tiket_action_types import TiketActionType as A
from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKEMBALIKAN,
    STATUS_SELESAI,
)
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import TiketFactory, UserFactory

REKAM = datetime(2026, 7, 10, 8, 48)
IDENTIFIKASI = datetime(2026, 9, 14, 16, 42)
TRANSFER = datetime(2026, 9, 14, 0, 0)
CLOSE = datetime(2026, 9, 15, 7, 0)

AUTO_SYNC_PAIR = [
    (A.DIKEMBALIKAN, TRANSFER, 'Tiket dikembalikan oleh PIDE (auto-sync)'),
    (A.DIBATALKAN, TRANSFER, 'Tiket dibatalkan (dikembalikan oleh PIDE: auto-sync)'),
]
ATURAN_3 = [
    (A.DITRANSFER_KE_PMDE, TRANSFER, 'Tiket ditransfer ke PMDE'),
    (A.PENGENDALIAN_MUTU, TRANSFER, 'Tiket selesai pengendalian mutu'),
    (A.SELESAI, CLOSE, 'Tiket selesai diproses'),
]
AWAL = [
    (A.DIREKAM, REKAM, 'tiket direkam'),
    (A.IDENTIFIKASI, IDENTIFIKASI, 'Mulai proses identifikasi'),
]


def _tiket(trail, status=STATUS_DIKEMBALIKAN):
    """A tiket whose actions are written in `trail` order, as the sync wrote them."""
    tiket = TiketFactory(status_tiket=status)
    user = UserFactory()
    for action, timestamp, catatan in trail:
        TiketAction.objects.create(
            id_tiket=tiket, id_user=user, action=action, timestamp=timestamp, catatan=catatan,
        )
    return tiket


def _trail(tiket):
    return list(TiketAction.objects.filter(id_tiket=tiket).order_by('id').values_list('action', flat=True))


def _run(*args):
    out = StringIO()
    call_command('fix_tiket_dikembalikan_sync', *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestFix:
    def test_aturan_3_dan_4_bersamaan(self):
        """PV034050126071001: the Selesai round goes, the returned pair stays."""
        tiket = _tiket(AWAL + ATURAN_3 + AUTO_SYNC_PAIR)

        _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        assert _trail(tiket) == [A.DIREKAM, A.IDENTIFIKASI, A.DIKEMBALIKAN, A.DIBATALKAN]

    def test_aturan_4_saja_hanya_status(self):
        tiket = _tiket(AWAL + AUTO_SYNC_PAIR)

        _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        assert _trail(tiket) == [A.DIREKAM, A.IDENTIFIKASI, A.DIKEMBALIKAN, A.DIBATALKAN]

    @pytest.mark.parametrize('ada', ['pmde_saja', 'pide_saja'])
    def test_sebagian_pic_tidak_aktif(self, ada):
        """Aturan 3 skipped the actions of a role with no active PIC."""
        aturan_3 = ATURAN_3[1:] if ada == 'pmde_saja' else ATURAN_3[:1]
        tiket = _tiket(AWAL + aturan_3 + AUTO_SYNC_PAIR)

        _run()

        assert _trail(tiket) == [A.DIREKAM, A.IDENTIFIKASI, A.DIKEMBALIKAN, A.DIBATALKAN]

    def test_putaran_asli_sebelumnya_tidak_disentuh(self):
        """A genuine earlier round directly below the pair is not Aturan 3's."""
        asli = [
            (A.DITRANSFER_KE_PMDE, datetime(2026, 8, 1), 'Tiket ditransfer ke PMDE'),
            (A.PENGENDALIAN_MUTU, datetime(2026, 8, 1), 'Tiket selesai pengendalian mutu'),
            (A.SELESAI, datetime(2026, 8, 2), 'Tiket selesai diproses'),
        ]
        tiket = _tiket(AWAL + asli + AUTO_SYNC_PAIR)

        _run()

        assert len(_trail(tiket)) == 7

    def test_status_dikembalikan_tanpa_aksi_auto_sync_dilaporkan(self):
        tiket = _tiket(AWAL)

        out = _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        assert 'periksa manual' in out

    def test_tiket_lain_tidak_disentuh(self):
        tiket = _tiket(AWAL + ATURAN_3, status=STATUS_SELESAI)

        assert 'Tidak ada tiket' in _run()
        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_SELESAI
        assert len(_trail(tiket)) == 5

    def test_dry_run_tidak_menulis(self):
        tiket = _tiket(AWAL + ATURAN_3 + AUTO_SYNC_PAIR)

        out = _run('--dry-run')

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIKEMBALIKAN
        assert len(_trail(tiket)) == 7
        assert 'DRY RUN' in out
        assert '3 aksi Aturan 3 akan dihapus' in out

    def test_idempoten(self):
        tiket = _tiket(AWAL + ATURAN_3 + AUTO_SYNC_PAIR)
        _run()

        assert 'Tidak ada tiket' in _run()
        assert len(_trail(tiket)) == 4

    def test_filter_tiket(self):
        target = _tiket(AWAL + ATURAN_3 + AUTO_SYNC_PAIR)
        lain = _tiket(AWAL + ATURAN_3 + AUTO_SYNC_PAIR)

        _run('--tiket', target.nomor_tiket)

        assert len(_trail(target)) == 4
        assert len(_trail(lain)) == 7
