"""fix_tiket_selesai_res_cde: Selesai tikets of Res/CDE rows only → Dibatalkan."""

from datetime import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from diamond_web.constants.tiket_action_types import PICActionType
from diamond_web.constants.tiket_action_types import TiketActionType as A
from diamond_web.constants.tiket_status import STATUS_DIBATALKAN, STATUS_SELESAI
from diamond_web.models.notification import Notification
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory
from diamond_web.views.sync_tiket_update import (
    CATATAN_DIBATALKAN_AUTO_SYNC,
    CATATAN_DIKEMBALIKAN_AUTO_SYNC,
)

IDENTIFIKASI = datetime(2026, 3, 10)
TRANSFER = datetime(2026, 4, 2)

# The migration's trail for a tiket closed as Selesai (PD050070123092002).
TRAIL_SELESAI = [
    (A.DIREKAM, datetime(2026, 1, 5), 'tiket direkam (data migrasi)'),
    (A.IDENTIFIKASI, IDENTIFIKASI, 'Mulai proses identifikasi (data migrasi)'),
    (A.DITRANSFER_KE_PMDE, TRANSFER, 'Tiket ditransfer ke PMDE (data migrasi)'),
    (A.PENGENDALIAN_MUTU, TRANSFER, 'Tiket selesai pengendalian mutu (data migrasi, tanggal perkiraan)'),
    (A.SELESAI, TRANSFER, 'Tiket selesai diproses (data migrasi, tanggal perkiraan)'),
]


def _tiket(trail=TRAIL_SELESAI, pics=(TiketPIC.Role.PIDE, TiketPIC.Role.P3DE), **fields):
    values = dict(
        status_tiket=STATUS_SELESAI, tgl_rekam_pide=IDENTIFIKASI, tgl_transfer=TRANSFER,
        baris_i=0, baris_u=0, baris_res=4060, baris_cde=0, baris_lengkap=4060,
        sudah_qc=0, belum_qc=0,
    )
    values.update(fields)
    tiket = TiketFactory(**values)
    for role in pics:
        TiketPICFactory(id_tiket=tiket, role=role, active=True)
    user = UserFactory()
    for action, timestamp, catatan in trail:
        TiketAction.objects.create(id_tiket=tiket, id_user=user, action=action, timestamp=timestamp, catatan=catatan)
    return tiket


def _trail(tiket):
    return [(a.action, a.catatan) for a in TiketAction.objects.filter(id_tiket=tiket).order_by('id')]


def _run(*args):
    out = StringIO()
    call_command('fix_tiket_selesai_res_cde', *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestFix:

    @pytest.mark.parametrize('baris, jenis', [
        (dict(baris_res=4060, baris_cde=0), 'Res'),
        (dict(baris_res=0, baris_cde=4060), 'CDE'),
        (dict(baris_res=60, baris_cde=4000), 'Res+CDE'),
        (dict(baris_i=None, baris_u=None, baris_res=4060, baris_cde=None), 'Res'),
    ])
    def test_menjadi_dibatalkan(self, baris, jenis):
        tiket = _tiket(**baris)

        out = _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        assert tiket.tgl_dikembalikan == TRANSFER
        assert tiket.tgl_rekam_pide is None
        assert tiket.tgl_transfer == TRANSFER
        assert tiket.belum_qc is None
        assert (tiket.baris_res, tiket.baris_cde) == (baris['baris_res'], baris['baris_cde'])
        assert _trail(tiket) == [
            (A.DIREKAM, 'tiket direkam (data migrasi)'),
            (A.IDENTIFIKASI, 'Mulai proses identifikasi (data migrasi)'),
            (A.DIKEMBALIKAN, CATATAN_DIKEMBALIKAN_AUTO_SYNC),
            (A.DIBATALKAN, CATATAN_DIBATALKAN_AUTO_SYNC),
        ]
        actions = TiketAction.objects.filter(id_tiket=tiket, action__in=[A.DIKEMBALIKAN, A.DIBATALKAN])
        assert {a.timestamp for a in actions} == {TRANSFER}
        assert {a.id_user for a in actions} == {
            TiketPIC.objects.get(id_tiket=tiket, role=role).id_user
            for role in (TiketPIC.Role.PIDE, TiketPIC.Role.P3DE)
        }
        assert f'1 tiket diubah Selesai → Dibatalkan (1 {jenis}), 3 aksi penutupan dihapus' in out
        assert not Notification.objects.exists()

    def test_dry_run_tidak_menulis(self):
        tiket = _tiket()
        before = _trail(tiket)

        out = _run('--dry-run')

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_SELESAI
        assert _trail(tiket) == before
        assert 'DRY RUN' in out
        assert f'{tiket.nomor_tiket}: Res (Res 4060 + CDE 0, Baris Lengkap 4060)' in out
        assert '1 tiket akan diubah Selesai → Dibatalkan (1 Res), 3 aksi penutupan akan dihapus' in out

    def test_idempoten(self):
        _tiket()
        _run()
        assert 'Tidak ada tiket Selesai' in _run()

    @pytest.mark.parametrize('baris_lengkap', [None, 0, 4000, 5000])
    def test_tidak_sama_dengan_lengkap_hanya_dilaporkan(self, baris_lengkap):
        tiket = _tiket(baris_lengkap=baris_lengkap)

        out = _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_SELESAI
        assert '0 tiket diubah' in out
        assert 'Res + CDE ≠ Baris Lengkap, tidak diubah' in out
        assert tiket.nomor_tiket in out

    @pytest.mark.parametrize('baris', [dict(baris_i=5), dict(baris_u=5), dict(baris_res=0, baris_cde=0)])
    def test_bukan_res_cde_saja_tidak_disentuh(self, baris):
        tiket = _tiket(**baris)
        assert 'Tidak ada tiket Selesai' in _run()
        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_SELESAI

    def test_hanya_tiket_selesai(self):
        tiket = _tiket(status_tiket=STATUS_DIBATALKAN)
        assert 'Tidak ada tiket Selesai' in _run()
        assert len(_trail(tiket)) == len(TRAIL_SELESAI)

    def test_aksi_lain_setelah_penutupan_tetap(self):
        """PIC changes and isian edits are not workflow steps: kept, not a stop."""
        trail = TRAIL_SELESAI + [(PICActionType.DITAMBAHKAN, datetime(2026, 4, 5), 'PIC P3DE ditambahkan')]
        tiket = _tiket(trail=trail)

        _run()

        assert [a for a, _ in _trail(tiket)] == [
            A.DIREKAM, A.IDENTIFIKASI, PICActionType.DITAMBAHKAN, A.DIKEMBALIKAN, A.DIBATALKAN,
        ]
        # Stamped tgl_transfer: that day is earlier than the kept PIC action's, so not lifted.
        assert TiketAction.objects.get(id_tiket=tiket, action=A.DIKEMBALIKAN).timestamp == TRANSFER

    def test_waktu_digeser_setelah_aksi_hari_yang_sama(self):
        trail = [
            (A.IDENTIFIKASI, datetime(2026, 4, 2, 16, 42), 'Mulai proses identifikasi'),
            (A.DITRANSFER_KE_PMDE, TRANSFER, 'Tiket ditransfer ke PMDE'),
            (A.PENGENDALIAN_MUTU, TRANSFER, 'Tiket selesai pengendalian mutu'),
            (A.SELESAI, datetime(2026, 4, 3, 7), 'Tiket selesai diproses'),
        ]
        tiket = _tiket(trail=trail)

        _run()

        tiket.refresh_from_db()
        assert tiket.tgl_dikembalikan == datetime(2026, 4, 2, 16, 43)

    def test_tanpa_selesai_tidak_ada_aksi_dihapus(self):
        """Closed without a PMDE PIC (no Selesai action): nothing to delete."""
        tiket = _tiket(trail=TRAIL_SELESAI[:3])

        _run()

        assert A.DITRANSFER_KE_PMDE in [a for a, _ in _trail(tiket)]
        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN

    def test_tanpa_pic_aktif_dilaporkan(self):
        tiket = _tiket(pics=(TiketPIC.Role.PIDE,))

        out = _run()

        assert '[tanpa PIC P3DE aktif' in out
        assert [a for a, _ in _trail(tiket)][-1] == A.DIKEMBALIKAN

    def test_filter_tiket(self):
        satu, dua = _tiket(), _tiket()

        _run('--tiket', satu.nomor_tiket)

        satu.refresh_from_db()
        dua.refresh_from_db()
        assert (satu.status_tiket, dua.status_tiket) == (STATUS_DIBATALKAN, STATUS_SELESAI)
