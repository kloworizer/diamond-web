"""The daily tiket update sync refreshes KD Tahap for the tikets it changed."""
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from diamond_web.constants.tiket_status import STATUS_DIKIRIM_KE_PIDE
from diamond_web.views.sync_tiket_update import _update_tiket_data

from .conftest import TiketFactory
from .test_sync_tiket_update_rules import _row, _service

COMMAND = 'diamond_web.management.commands.sync_tiket_update'


@pytest.fixture(autouse=True)
def _sync_logs_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr('diamond_web.views.sync_tiket_update.SYNC_LOGS_DIR', str(tmp_path))


@pytest.mark.django_db
def test_update_lists_every_changed_tiket_and_only_those():
    berubah = TiketFactory(status_tiket=STATUS_DIKIRIM_KE_PIDE, tgl_rekam_pide=None, tgl_transfer=None)
    tetap = TiketFactory(status_tiket=STATUS_DIKIRIM_KE_PIDE, tgl_rekam_pide=None, tgl_transfer=None)
    _update_tiket_data(_service([_row(tetap.nomor_tiket)]))  # first run brings it in sync

    summary = _update_tiket_data(_service([_row(berubah.nomor_tiket), _row(tetap.nomor_tiket)]))

    assert summary['changed_tikets'] == [berubah.nomor_tiket]
    assert summary['unchanged'] == 1


def _run(summary, **kwargs):
    out = StringIO()
    with patch(f'{COMMAND}.OracleDataSyncService', return_value=MagicMock()), \
            patch(f'{COMMAND}._update_tiket_data', return_value=summary), \
            patch(f'{COMMAND}.call_command') as kd:
        call_command('sync_tiket_update', stdout=out, **kwargs)
    return out.getvalue(), kd


def _summary(changed):
    return {'updated_rows': len(changed), 'errors': [], 'updated_keys': changed[:5], 'changed_tikets': changed}


def test_kd_tahap_refreshed_for_changed_tikets():
    out, kd = _run(_summary(['T0000000000000001', 'T0000000000000002']))

    kd.assert_called_once()
    assert kd.call_args.args == ('sync_tiket_kd_tahap',)
    assert kd.call_args.kwargs['tiket'] == 'T0000000000000001,T0000000000000002'
    assert 'Sinkronisasi KD Tahap untuk 2 tiket yang berubah' in out


def test_kd_tahap_skipped_without_changes_or_when_disabled():
    out, kd = _run(_summary([]))
    kd.assert_not_called()
    assert 'tidak ada tiket yang berubah' in out

    out, kd = _run(_summary(['T0000000000000001']), tanpa_kd_tahap=True)
    kd.assert_not_called()


def test_kd_tahap_failure_leaves_the_update_successful():
    out = StringIO()
    with patch(f'{COMMAND}.OracleDataSyncService', return_value=MagicMock()), \
            patch(f'{COMMAND}._update_tiket_data', return_value=_summary(['T0000000000000001'])), \
            patch(f'{COMMAND}.call_command', side_effect=CommandError("Koneksi Oracle 'secondary' gagal")):
        call_command('sync_tiket_update', stdout=out)  # does not raise

    assert 'Update tiket selesai.' in out.getvalue()
    assert "Sinkronisasi KD Tahap gagal: Koneksi Oracle 'secondary' gagal" in out.getvalue()
