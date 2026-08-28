"""Tests for the retroactive fix of tikets stranded at Selesai by a tarikan revision.

Reproduces the reported state: a tiket closed on 23/07 whose tgl_transfer was
later revised to 28/07 by PIDE, bringing baris_i with it. The sync had already
copied the new date in, so Aturan 9 can never fire on it again.
"""
from datetime import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC

from .conftest import TiketFactory, TiketPICFactory

TGL_TRANSFER_LAMA = datetime(2026, 7, 22, 0, 0)
TGL_SELESAI = datetime(2026, 7, 23, 7, 0)
TGL_TRANSFER_BARU = datetime(2026, 7, 28, 0, 0)


def _run(*args):
    out = StringIO()
    call_command('fix_tiket_transfer_ulang', *args, stdout=out, stderr=out)
    return out.getvalue()


@pytest.fixture
def tiket_tertahan(db):
    """The reported state: closed 23/07, tgl_transfer since revised to 28/07."""
    tiket = TiketFactory(
        status_tiket=STATUS_SELESAI,
        tgl_transfer=TGL_TRANSFER_BARU,
        tgl_rematch=None,
        baris_i=71, baris_u=221, baris_res=0, baris_cde=0,
        belum_qc=71,
    )
    pide = TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    pmde = TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PMDE, active=True)

    # Jejak putaran lama — transfer 22/07, ditutup 23/07.
    TiketAction.objects.create(
        id_tiket=tiket, id_user=pide.id_user, timestamp=TGL_TRANSFER_LAMA,
        action=TiketActionType.DITRANSFER_KE_PMDE, catatan='Tiket ditransfer ke PMDE')
    TiketAction.objects.create(
        id_tiket=tiket, id_user=pmde.id_user, timestamp=TGL_TRANSFER_LAMA,
        action=TiketActionType.PENGENDALIAN_MUTU, catatan='Tiket selesai pengendalian mutu')
    TiketAction.objects.create(
        id_tiket=tiket, id_user=pmde.id_user, timestamp=TGL_SELESAI,
        action=TiketActionType.SELESAI, catatan='Tiket selesai diproses')
    return tiket


@pytest.mark.django_db
class TestFixTiketTransferUlang:

    def test_membuka_kembali_ke_pengendalian_mutu(self, tiket_tertahan):
        _run()

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_PENGENDALIAN_MUTU

    def test_mencatat_transfer_baru_di_tiket_action(self, tiket_tertahan):
        _run()

        baru = TiketAction.objects.get(
            id_tiket=tiket_tertahan,
            action=TiketActionType.DITRANSFER_KE_PMDE,
            timestamp=TGL_TRANSFER_BARU,
        )
        assert baru.id_user == TiketPIC.objects.get(
            id_tiket=tiket_tertahan, role=TiketPIC.Role.PIDE).id_user
        assert 'revisi tarikan' in baru.catatan
        assert 'I:71' in baru.catatan and 'U:221' in baru.catatan

    def test_riwayat_lama_tidak_dihapus_atau_diubah(self, tiket_tertahan):
        _run()

        lama = TiketAction.objects.filter(
            id_tiket=tiket_tertahan, timestamp__in=[TGL_TRANSFER_LAMA, TGL_SELESAI]
        )
        assert lama.count() == 3
        assert TiketAction.objects.filter(
            id_tiket=tiket_tertahan, action=TiketActionType.SELESAI,
            timestamp=TGL_SELESAI,
        ).exists()

    def test_dry_run_tidak_mengubah_apa_pun(self, tiket_tertahan):
        out = _run('--dry-run')

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_SELESAI
        assert TiketAction.objects.filter(id_tiket=tiket_tertahan).count() == 3
        assert tiket_tertahan.nomor_tiket in out
        assert 'DRY RUN' in out

    def test_idempoten(self, tiket_tertahan):
        _run()
        out = _run()

        assert TiketAction.objects.filter(
            id_tiket=tiket_tertahan, action=TiketActionType.DITRANSFER_KE_PMDE,
            timestamp=TGL_TRANSFER_BARU,
        ).count() == 1
        assert 'Tidak ada tiket' in out

    def test_tiket_sehat_dengan_jejak_konsisten_dilewati(self, tiket_tertahan):
        """A migrated tiket whose trail matches AND whose closure follows the transfer."""
        pide = TiketPIC.objects.get(id_tiket=tiket_tertahan, role=TiketPIC.Role.PIDE)
        TiketAction.objects.create(
            id_tiket=tiket_tertahan, id_user=pide.id_user,
            timestamp=TGL_TRANSFER_BARU,
            action=TiketActionType.DITRANSFER_KE_PMDE,
            catatan='Tiket ditransfer ke PMDE (data migrasi)')
        # Ditutup SETELAH transfer — kronologi yang wajar.
        TiketAction.objects.filter(
            id_tiket=tiket_tertahan, action=TiketActionType.SELESAI
        ).update(timestamp=datetime(2026, 7, 30, 8, 0))

        _run()

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_SELESAI

    def test_transfer_lebih_baru_dari_penutupan_tetap_tertangkap(self, tiket_tertahan):
        """PD508040123120801's shape: the backfill re-dated the transfer action.

        Running backfill_old_db_tiket_actions after PIDE revised tgl_transfer
        leaves a transfer action sitting on the revised date, so the trail looks
        intact. The chronology still gives it away — closed 23/07, transferred
        28/07 — and nothing may be duplicated on that date.
        """
        pide = TiketPIC.objects.get(id_tiket=tiket_tertahan, role=TiketPIC.Role.PIDE)
        TiketAction.objects.create(
            id_tiket=tiket_tertahan, id_user=pide.id_user,
            timestamp=TGL_TRANSFER_BARU,
            action=TiketActionType.DITRANSFER_KE_PMDE,
            catatan='Tiket ditransfer ke PMDE (data migrasi)')

        out = _run('--verbose')

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert TiketAction.objects.filter(
            id_tiket=tiket_tertahan,
            action=TiketActionType.DITRANSFER_KE_PMDE,
            timestamp=TGL_TRANSFER_BARU,
        ).count() == 1
        assert 'tidak diduplikasi' in out

    def test_belum_qc_nol_dilewati(self, tiket_tertahan):
        tiket_tertahan.belum_qc = 0
        tiket_tertahan.save(update_fields=['belum_qc'])

        _run()

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_SELESAI

    def test_baris_i_nol_dilewati(self, tiket_tertahan):
        """i=0, u>0 is what Aturan 5A closes on — must stay closed."""
        tiket_tertahan.baris_i = 0
        tiket_tertahan.save(update_fields=['baris_i'])

        _run()

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_SELESAI

    def test_rematch_dilewati(self, tiket_tertahan):
        """Aturan 8 owns rematched tikets; this command must not touch them."""
        tiket_tertahan.tgl_rematch = datetime(2026, 8, 1, 0, 0)
        tiket_tertahan.save(update_fields=['tgl_rematch'])

        _run()

        tiket_tertahan.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_SELESAI

    def test_filter_nomor_tiket(self, tiket_tertahan, db):
        lain = TiketFactory(
            status_tiket=STATUS_SELESAI, tgl_transfer=TGL_TRANSFER_BARU,
            baris_i=10, baris_u=5, belum_qc=10,
        )

        _run('--tiket', tiket_tertahan.nomor_tiket)

        tiket_tertahan.refresh_from_db()
        lain.refresh_from_db()
        assert tiket_tertahan.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert lain.status_tiket == STATUS_SELESAI

    def test_tanpa_pic_pide_status_tetap_berubah(self, db):
        tiket = TiketFactory(
            status_tiket=STATUS_SELESAI, tgl_transfer=TGL_TRANSFER_BARU,
            baris_i=71, baris_u=221, belum_qc=71,
        )

        out = _run()

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()
        assert 'tanpa PIC PIDE aktif' in out
