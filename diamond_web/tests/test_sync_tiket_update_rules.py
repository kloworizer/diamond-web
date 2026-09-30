"""Tests for the Oracle tiket-update sync status transitions from DIKIRIM_KE_PIDE (4)
and the two reopen-from-Selesai rules.

Covers the tgl_rekam_pide (Oracle tgl_load) backfill rules:
  - 4 + tgl_rekam_pide lokal null + tgl_transfer null      → 5 (Identifikasi)
  - 4 + tgl_rekam_pide lokal null + tgl_transfer not null  → 6 (Pengendalian Mutu)

The rematch rule:
  - 8 + tgl_rematch not null + belum_qc > 0                → 6 (Pengendalian Mutu)

And the revisi-tarikan rule (PIDE transfer ulang dengan baris_i terisi):
  - 8 + tgl_rematch null + tgl_transfer berubah + i > 0 + belum_qc != 0
                                                          → 6 (Pengendalian Mutu)
"""
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.views.sync_tiket_update import (
    _check_tiket_update_data,
    _update_tiket_data,
)

from .conftest import TiketFactory, TiketPICFactory

# Column order matches _TIKET_UPDATE_ORACLE_SQL
COLUMNS = [
    'nomor_tiket', 'tgl_rekam_pide', 'baris_i', 'baris_u', 'baris_res',
    'baris_cde', 'tgl_transfer', 'tgl_rematch', 'tgl_close_tiket',
    'sudah_qc', 'belum_qc', 'lolos_qc', 'tidak_lolos_qc',
    'qc_p', 'qc_x', 'qc_w', 'qc_f', 'qc_a', 'qc_c', 'qc_n',
    'qc_y', 'qc_z', 'qc_u', 'qc_e', 'qc_v', 'qc_r', 'qc_d',
]

TGL_LOAD = datetime(2026, 3, 2, 8, 0)
TGL_TRANSFER = datetime(2026, 3, 10, 9, 30)
TGL_TRANSFER_BARU = datetime(2026, 3, 24, 11, 0)
TGL_REMATCH = datetime(2026, 4, 1, 14, 15)


def _row(nomor_tiket, tgl_rekam_pide=TGL_LOAD, tgl_transfer=None, **overrides):
    """Build one Oracle result row with sane defaults."""
    values = {c: 0 for c in COLUMNS}
    values.update({
        'nomor_tiket': nomor_tiket,
        'tgl_rekam_pide': tgl_rekam_pide,
        'tgl_transfer': tgl_transfer,
        'tgl_rematch': None,
        'tgl_close_tiket': None,
        'belum_qc': 5,
    })
    values.update(overrides)
    return tuple(values[c] for c in COLUMNS)


def _service(rows):
    """Return a fake OracleDataSyncService yielding *rows* for the sync query."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = [(c.upper(),) for c in COLUMNS]

    @contextmanager
    def _cursor_cm():
        yield cursor

    conn = MagicMock()
    conn.cursor.side_effect = _cursor_cm

    @contextmanager
    def _connect(_which):
        yield conn

    service = MagicMock()
    service._connect_oracle.side_effect = _connect
    return service


@pytest.fixture
def tiket_di_pide(db):
    """Tiket at status 4 with no tgl_rekam_pide yet, plus an active PIDE PIC."""
    tiket = TiketFactory(
        status_tiket=STATUS_DIKIRIM_KE_PIDE,
        tgl_rekam_pide=None,
        tgl_transfer=None,
    )
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    return tiket


@pytest.mark.django_db
class TestTransisiDariDikirimKePide:
    """Status 4 → 5 / 6 based on tgl_rekam_pide and tgl_transfer."""

    def test_tanpa_tgl_transfer_menjadi_identifikasi(self, tiket_di_pide):
        result = _update_tiket_data(_service([_row(tiket_di_pide.nomor_tiket)]))

        tiket_di_pide.refresh_from_db()
        assert tiket_di_pide.status_tiket == STATUS_IDENTIFIKASI
        assert tiket_di_pide.tgl_rekam_pide == TGL_LOAD
        assert tiket_di_pide.tgl_transfer is None
        assert result['status_to_identifikasi'] == 1
        assert result['status_to_pmde'] == 0

        actions = list(TiketAction.objects.filter(id_tiket=tiket_di_pide))
        assert [a.action for a in actions] == [TiketActionType.IDENTIFIKASI]
        assert actions[0].timestamp == TGL_LOAD

    def test_dengan_tgl_transfer_menjadi_pengendalian_mutu(self, tiket_di_pide):
        result = _update_tiket_data(_service([
            _row(tiket_di_pide.nomor_tiket, tgl_transfer=TGL_TRANSFER)
        ]))

        tiket_di_pide.refresh_from_db()
        assert tiket_di_pide.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert tiket_di_pide.tgl_rekam_pide == TGL_LOAD
        assert tiket_di_pide.tgl_transfer == TGL_TRANSFER
        assert result['status_to_pmde'] == 1
        assert result['status_to_identifikasi'] == 0

        actions = TiketAction.objects.filter(id_tiket=tiket_di_pide).order_by('timestamp')
        assert [a.action for a in actions] == [
            TiketActionType.IDENTIFIKASI,
            TiketActionType.DITRANSFER_KE_PMDE,
        ]
        assert [a.timestamp for a in actions] == [TGL_LOAD, TGL_TRANSFER]

    def test_tgl_rekam_pide_lokal_sudah_terisi_tidak_pindah_status(self, tiket_di_pide):
        tiket_di_pide.tgl_rekam_pide = datetime(2026, 2, 1, 7, 0)
        tiket_di_pide.save(update_fields=['tgl_rekam_pide'])

        _update_tiket_data(_service([
            _row(tiket_di_pide.nomor_tiket, tgl_transfer=TGL_TRANSFER)
        ]))

        tiket_di_pide.refresh_from_db()
        assert tiket_di_pide.status_tiket == STATUS_DIKIRIM_KE_PIDE
        assert tiket_di_pide.tgl_rekam_pide == datetime(2026, 2, 1, 7, 0)
        assert not TiketAction.objects.filter(id_tiket=tiket_di_pide).exists()

    def test_tgl_load_oracle_null_tidak_pindah_status(self, tiket_di_pide):
        _update_tiket_data(_service([
            _row(tiket_di_pide.nomor_tiket, tgl_rekam_pide=None, tgl_transfer=TGL_TRANSFER)
        ]))

        tiket_di_pide.refresh_from_db()
        assert tiket_di_pide.status_tiket == STATUS_DIKIRIM_KE_PIDE
        assert tiket_di_pide.tgl_rekam_pide is None

    def test_tanpa_pic_pide_status_tetap_berubah(self, db):
        tiket = TiketFactory(
            status_tiket=STATUS_DIKIRIM_KE_PIDE, tgl_rekam_pide=None, tgl_transfer=None
        )

        _update_tiket_data(_service([_row(tiket.nomor_tiket)]))

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_IDENTIFIKASI
        assert tiket.tgl_rekam_pide == TGL_LOAD
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()


@pytest.fixture
def tiket_selesai(db):
    """Tiket already closed at status 8, plus an active PIDE PIC."""
    tiket = TiketFactory(
        status_tiket=STATUS_SELESAI,
        tgl_rekam_pide=TGL_LOAD,
        tgl_transfer=TGL_TRANSFER,
    )
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    return tiket


@pytest.mark.django_db
class TestTransisiRematchDariSelesai:
    """Status 8 → 6 when Oracle reports a rematch with QC still outstanding."""

    def test_rematch_dengan_belum_qc_membuka_pengendalian_mutu(self, tiket_selesai):
        result = _update_tiket_data(_service([
            _row(
                tiket_selesai.nomor_tiket,
                tgl_transfer=TGL_TRANSFER,
                tgl_rematch=TGL_REMATCH,
                belum_qc=3,
            )
        ]))

        tiket_selesai.refresh_from_db()
        assert tiket_selesai.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert tiket_selesai.tgl_rematch == TGL_REMATCH
        assert result['status_to_rematch'] == 1

        actions = list(TiketAction.objects.filter(id_tiket=tiket_selesai))
        assert [a.action for a in actions] == [TiketActionType.REMATCH]
        assert actions[0].timestamp == TGL_REMATCH

    def test_belum_qc_nol_tetap_selesai(self, tiket_selesai):
        result = _update_tiket_data(_service([
            _row(
                tiket_selesai.nomor_tiket,
                tgl_transfer=TGL_TRANSFER,
                tgl_rematch=TGL_REMATCH,
                belum_qc=0,
            )
        ]))

        tiket_selesai.refresh_from_db()
        assert tiket_selesai.status_tiket == STATUS_SELESAI
        assert result['status_to_rematch'] == 0
        assert not TiketAction.objects.filter(id_tiket=tiket_selesai).exists()

    def test_tanpa_tgl_rematch_tetap_selesai(self, tiket_selesai):
        result = _update_tiket_data(_service([
            _row(
                tiket_selesai.nomor_tiket,
                tgl_transfer=TGL_TRANSFER,
                tgl_rematch=None,
                belum_qc=3,
            )
        ]))

        tiket_selesai.refresh_from_db()
        assert tiket_selesai.status_tiket == STATUS_SELESAI
        assert result['status_to_rematch'] == 0
        assert not TiketAction.objects.filter(id_tiket=tiket_selesai).exists()

    def test_tanpa_pic_pide_status_tetap_berubah(self, db):
        tiket = TiketFactory(
            status_tiket=STATUS_SELESAI,
            tgl_rekam_pide=TGL_LOAD,
            tgl_transfer=TGL_TRANSFER,
        )

        _update_tiket_data(_service([
            _row(
                tiket.nomor_tiket,
                tgl_transfer=TGL_TRANSFER,
                tgl_rematch=TGL_REMATCH,
                belum_qc=3,
            )
        ]))

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()

    def test_dry_run_menghitung_calon_rematch(self, tiket_selesai):
        result = _check_tiket_update_data(_service([
            _row(
                tiket_selesai.nomor_tiket,
                tgl_transfer=TGL_TRANSFER,
                tgl_rematch=TGL_REMATCH,
                belum_qc=3,
            )
        ]))

        assert result['would_rematch'] == 1
        assert result['would_update'] == 1

        tiket_selesai.refresh_from_db()
        assert tiket_selesai.status_tiket == STATUS_SELESAI


@pytest.mark.django_db
class TestCekDryRunDariDikirimKePide:
    """The dry-run check mirrors the sync counters without touching the DB."""

    def test_menghitung_calon_identifikasi(self, tiket_di_pide):
        result = _check_tiket_update_data(_service([_row(tiket_di_pide.nomor_tiket)]))

        assert result['would_identifikasi'] == 1
        assert result['would_pmde'] == 0
        assert result['would_update'] == 1

        tiket_di_pide.refresh_from_db()
        assert tiket_di_pide.status_tiket == STATUS_DIKIRIM_KE_PIDE

    def test_menghitung_calon_pengendalian_mutu(self, tiket_di_pide):
        result = _check_tiket_update_data(_service([
            _row(tiket_di_pide.nomor_tiket, tgl_transfer=TGL_TRANSFER)
        ]))

        assert result['would_pmde'] == 1
        assert result['would_identifikasi'] == 0


@pytest.fixture
def tiket_selesai_baris_u(db):
    """Tiket closed straight from Identifikasi by Aturan 5A — baris_u only.

    This is the state the re-transfer case starts from: PIDE transferred a
    tarikan with no identification rows, so the tiket skipped PMDE entirely.
    """
    tiket = TiketFactory(
        status_tiket=STATUS_SELESAI,
        tgl_rekam_pide=TGL_LOAD,
        tgl_transfer=TGL_TRANSFER,
        baris_i=0, baris_u=400, baris_res=0, baris_cde=0,
        belum_qc=0,
    )
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    return tiket


def _revisi_row(nomor_tiket, **overrides):
    """Oracle row for a revised tarikan: new transfer date, baris_i now filled."""
    values = dict(
        tgl_transfer=TGL_TRANSFER_BARU, tgl_rematch=None,
        baris_i=250, baris_u=400, belum_qc=151,
    )
    values.update(overrides)
    return _row(nomor_tiket, **values)


@pytest.mark.django_db
class TestTransisiTransferUlangDariSelesai:
    """Status 8 → 6 when PIDE revises the tarikan and baris_i is now > 0."""

    def test_revisi_dengan_baris_i_membuka_pengendalian_mutu(self, tiket_selesai_baris_u):
        result = _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket)
        ]))

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert tiket_selesai_baris_u.tgl_transfer == TGL_TRANSFER_BARU
        assert tiket_selesai_baris_u.baris_i == 250
        assert tiket_selesai_baris_u.belum_qc == 151
        assert result['status_to_transfer_ulang'] == 1
        assert result['status_to_rematch'] == 0

        actions = list(TiketAction.objects.filter(id_tiket=tiket_selesai_baris_u))
        assert [a.action for a in actions] == [TiketActionType.DITRANSFER_KE_PMDE]
        assert actions[0].timestamp == TGL_TRANSFER_BARU

    def test_tgl_transfer_sama_tetap_selesai(self, tiket_selesai_baris_u):
        """Guards the ~3.4k already-closed tikets carrying a stale belum_qc."""
        result = _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket, tgl_transfer=TGL_TRANSFER)
        ]))

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_SELESAI
        assert result['status_to_transfer_ulang'] == 0
        assert not TiketAction.objects.filter(id_tiket=tiket_selesai_baris_u).exists()

    def test_revisi_tetap_baris_u_saja_tetap_selesai(self, tiket_selesai_baris_u):
        """Same composition Aturan 5A closes on — re-transfer must not reopen."""
        result = _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket, baris_i=0, baris_u=600)
        ]))

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_SELESAI
        assert tiket_selesai_baris_u.baris_u == 600
        assert result['status_to_transfer_ulang'] == 0

    def test_belum_qc_nol_tetap_selesai(self, tiket_selesai_baris_u):
        result = _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket, belum_qc=0)
        ]))

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_SELESAI
        assert result['status_to_transfer_ulang'] == 0

    def test_rematch_menang_atas_transfer_ulang(self, tiket_selesai_baris_u):
        """Both triggers present: the rematch rule owns the transition."""
        result = _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket, tgl_rematch=TGL_REMATCH)
        ]))

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert result['status_to_rematch'] == 1
        assert result['status_to_transfer_ulang'] == 0

        actions = list(TiketAction.objects.filter(id_tiket=tiket_selesai_baris_u))
        assert [a.action for a in actions] == [TiketActionType.REMATCH]

    def test_tanpa_pic_pide_status_tetap_berubah(self, db):
        tiket = TiketFactory(
            status_tiket=STATUS_SELESAI, tgl_rekam_pide=TGL_LOAD,
            tgl_transfer=TGL_TRANSFER, baris_i=0, baris_u=400, belum_qc=0,
        )

        _update_tiket_data(_service([_revisi_row(tiket.nomor_tiket)]))

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()

    def test_riwayat_putaran_lama_tetap_utuh(self, tiket_selesai_baris_u):
        """The closed round's audit trail survives the reopen untouched."""
        pic = TiketPIC.objects.get(id_tiket=tiket_selesai_baris_u)
        for action in (TiketActionType.DITRANSFER_KE_PMDE,
                       TiketActionType.PENGENDALIAN_MUTU,
                       TiketActionType.SELESAI):
            TiketAction.objects.create(
                id_tiket=tiket_selesai_baris_u, id_user=pic.id_user,
                timestamp=TGL_TRANSFER, action=action, catatan='putaran lama'
            )

        _update_tiket_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket)
        ]))

        lama = TiketAction.objects.filter(
            id_tiket=tiket_selesai_baris_u, catatan='putaran lama'
        )
        assert lama.count() == 3
        assert TiketAction.objects.filter(
            id_tiket=tiket_selesai_baris_u, timestamp=TGL_TRANSFER_BARU,
            action=TiketActionType.DITRANSFER_KE_PMDE,
        ).count() == 1

    def test_dry_run_menghitung_calon_transfer_ulang(self, tiket_selesai_baris_u):
        result = _check_tiket_update_data(_service([
            _revisi_row(tiket_selesai_baris_u.nomor_tiket)
        ]))

        assert result['would_transfer_ulang'] == 1
        assert result['would_update'] == 1

        tiket_selesai_baris_u.refresh_from_db()
        assert tiket_selesai_baris_u.status_tiket == STATUS_SELESAI


TGL_CLOSE = datetime(2026, 3, 11, 7, 0)


@pytest.fixture
def tiket_identifikasi(db):
    """Tiket at status 5 with an active PIDE, PMDE and P3DE PIC."""
    tiket = TiketFactory(
        status_tiket=STATUS_IDENTIFIKASI,
        tgl_rekam_pide=TGL_LOAD,
        tgl_transfer=None,
    )
    for role in (TiketPIC.Role.PIDE, TiketPIC.Role.PMDE, TiketPIC.Role.P3DE):
        TiketPICFactory(id_tiket=tiket, role=role, active=True)
    return tiket


def _cde_only_row(nomor_tiket):
    """PIDE found only CDE rows: nothing to QC, so belum_qc is 0."""
    return _row(
        nomor_tiket, tgl_transfer=TGL_TRANSFER, tgl_close_tiket=TGL_CLOSE,
        baris_i=0, baris_u=0, baris_res=0, baris_cde=10, belum_qc=0,
    )


@pytest.mark.django_db
class TestAturan4HanyaCde:
    """Identifikasi + rows CDE only → Dibatalkan, and Aturan 3 stays out of it."""

    def test_menjadi_dibatalkan_bukan_selesai(self, tiket_identifikasi):
        result = _update_tiket_data(_service([_cde_only_row(tiket_identifikasi.nomor_tiket)]))

        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_DIBATALKAN
        assert tiket_identifikasi.tgl_dikembalikan == TGL_TRANSFER
        assert tiket_identifikasi.tgl_rekam_pide is None
        assert result['status_to_dikembalikan'] == 1
        assert result['status_to_selesai'] == 0

        actions = TiketAction.objects.filter(id_tiket=tiket_identifikasi).order_by('id')
        assert [a.action for a in actions] == [
            TiketActionType.DIKEMBALIKAN,
            TiketActionType.DIBATALKAN,
        ]

    def test_waktu_pengembalian_setelah_identifikasi_hari_yang_sama(self, tiket_identifikasi):
        """tgl_transfer is date-only: the return must not read as before the identifikasi."""
        transfer_tanpa_jam = datetime(2026, 3, 10)
        identifikasi = TiketAction.objects.create(
            id_tiket=tiket_identifikasi, id_user=TiketPIC.objects.filter(
                id_tiket=tiket_identifikasi, role=TiketPIC.Role.PIDE,
            ).first().id_user,
            timestamp=datetime(2026, 3, 10, 16, 42),
            action=TiketActionType.IDENTIFIKASI, catatan='Mulai proses identifikasi',
        )
        row = list(_cde_only_row(tiket_identifikasi.nomor_tiket))
        row[COLUMNS.index('tgl_transfer')] = transfer_tanpa_jam

        _update_tiket_data(_service([tuple(row)]))

        tiket_identifikasi.refresh_from_db()
        setelah = datetime(2026, 3, 10, 16, 43)
        assert tiket_identifikasi.tgl_dikembalikan == setelah
        assert tiket_identifikasi.tgl_transfer == transfer_tanpa_jam
        actions = TiketAction.objects.filter(id_tiket=tiket_identifikasi).exclude(pk=identifikasi.pk)
        assert [a.timestamp for a in actions] == [setelah, setelah]

    def test_belum_qc_nol_tanpa_cde_tetap_selesai(self, tiket_identifikasi):
        """Aturan 3 still closes a tiket whose QC is really done."""
        _update_tiket_data(_service([_row(
            tiket_identifikasi.nomor_tiket, tgl_transfer=TGL_TRANSFER, tgl_close_tiket=TGL_CLOSE,
            baris_i=0, baris_u=0, baris_res=4, baris_cde=10, belum_qc=0,
        )]))

        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_SELESAI

    def test_dry_run_hanya_menghitung_dikembalikan(self, tiket_identifikasi):
        result = _check_tiket_update_data(_service([_cde_only_row(tiket_identifikasi.nomor_tiket)]))

        assert result['would_dikembalikan'] == 1
        assert result['would_selesai'] == 0
        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_IDENTIFIKASI


@pytest.fixture
def tiket_pengendalian_mutu(db):
    """Tiket at status 6 with 609 I rows still to QC, and an active PMDE PIC."""
    tiket = TiketFactory(
        status_tiket=STATUS_PENGENDALIAN_MUTU, tgl_rekam_pide=TGL_LOAD, tgl_transfer=TGL_TRANSFER,
        baris_i=609, baris_u=1112, belum_qc=609, sudah_qc=0,
    )
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PMDE, active=True)
    return tiket


@pytest.mark.django_db
class TestQcLengkapRekapSetengahJadi:
    """Aturan 2 and 3 close only on a rekap where every I row is QC'd.

    A half-built PVPTD.ZA_REKAP_TARIKAN can read Belum QC 0 while QC is still
    open; a complete one always has sudah_qc + belum_qc == baris_i.
    """

    @pytest.mark.parametrize('rekap', [
        dict(baris_i=609, baris_u=1112, sudah_qc=0, belum_qc=0),     # QC counts missing
        dict(baris_i=609, baris_u=1112, sudah_qc=200, belum_qc=0),   # part of them
        dict(baris_cde=15, belum_qc=0),                               # CDE rows alone
    ])
    def test_aturan_2_tidak_menutup(self, tiket_pengendalian_mutu, rekap):
        row = _row(tiket_pengendalian_mutu.nomor_tiket, tgl_transfer=TGL_TRANSFER, **rekap)
        assert _check_tiket_update_data(_service([row]))['would_selesai'] == 0

        result = _update_tiket_data(_service([row]))

        tiket_pengendalian_mutu.refresh_from_db()
        assert tiket_pengendalian_mutu.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert result['status_to_selesai'] == 0
        assert not TiketAction.objects.filter(id_tiket=tiket_pengendalian_mutu).exists()

    def test_aturan_2_menutup_bila_qc_lengkap(self, tiket_pengendalian_mutu):
        row = _row(tiket_pengendalian_mutu.nomor_tiket, tgl_transfer=TGL_TRANSFER,
                   baris_i=609, baris_u=1112, sudah_qc=609, belum_qc=0)
        assert _check_tiket_update_data(_service([row]))['would_selesai'] == 1
        _update_tiket_data(_service([row]))
        tiket_pengendalian_mutu.refresh_from_db()
        assert tiket_pengendalian_mutu.status_tiket == STATUS_SELESAI

    def test_aturan_3_tidak_menutup(self, tiket_identifikasi):
        row = _row(tiket_identifikasi.nomor_tiket, tgl_transfer=TGL_TRANSFER,
                   baris_i=609, baris_u=1112, sudah_qc=0, belum_qc=0)
        _update_tiket_data(_service([row]))
        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_IDENTIFIKASI
