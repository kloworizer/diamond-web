"""Tests for the Oracle tiket-update sync status transitions from DIKIRIM_KE_PIDE (4).

Covers the tgl_rekam_pide (Oracle tgl_load) backfill rules:
  - 4 + tgl_rekam_pide lokal null + tgl_transfer null      → 5 (Identifikasi)
  - 4 + tgl_rekam_pide lokal null + tgl_transfer not null  → 6 (Pengendalian Mutu)
"""
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
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
