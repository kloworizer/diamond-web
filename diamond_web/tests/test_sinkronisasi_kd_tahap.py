"""Sinkronisasi Tiket also refreshes the tiket's rows per KD_TAHAP.

For a tiket that is, or that the sync leaves, at Pengendalian Mutu or Selesai,
the preview shows the KD Tahap rows that change and the sync replaces the
stored TiketKdTahap rows with Oracle's counts.
"""
from unittest.mock import patch

import pytest

from diamond_web.constants.tiket_status import (
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.models.tiket_kd_tahap import TiketKdTahap
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.utils.tiket_kd_tahap import KdTahapError

from .conftest import TiketFactory, TiketPICFactory
from .test_sinkronisasi_tiket import _aturan_1_row, _fingerprint, _oracle, _url

VIEW = 'diamond_web.views.tiket.sinkronisasi_tiket'


@pytest.fixture(autouse=True)
def _sync_logs_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr('diamond_web.views.sync_tiket_update.SYNC_LOGS_DIR', str(tmp_path))


def _kd_oracle(hasil):
    """Stub the tabel I query: *hasil* is the counts, or an exception to raise."""
    if isinstance(hasil, Exception):
        return patch(f'{VIEW}.ambil_kd_tahap_tiket', side_effect=hasil)
    return patch(f'{VIEW}.ambil_kd_tahap_tiket', return_value=hasil)


def _tanpa_rekap():
    """No rekap row in Oracle: the tiket update itself changes nothing."""
    return patch(f'{VIEW}._fetch_row', return_value=(None, None))


def _simpanan(tiket):
    return dict(TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'jumlah_baris'))


@pytest.fixture
def tiket_selesai(db):
    tiket = TiketFactory(status_tiket=STATUS_SELESAI)
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PMDE, active=True)
    return tiket


@pytest.mark.django_db
def test_preview_lists_changed_kd_tahap_and_writes_nothing(client, pmde_admin_user, tiket_selesai):
    TiketKdTahap.objects.create(id_tiket=tiket_selesai, kd_tahap='A', jumlah_baris=5)
    TiketKdTahap.objects.create(id_tiket=tiket_selesai, kd_tahap='B', jumlah_baris=2)
    client.force_login(pmde_admin_user)

    with _tanpa_rekap(), _kd_oracle({'A': 5, 'C': 1500}):
        html = client.get(_url(tiket_selesai)).json()['html']

    assert 'data-kd-state="changed"' in html
    assert 'Total baris\n                7 → <strong>1.505</strong>; 2 KD Tahap berubah' in html
    assert '>B<' in html and '>C<' in html and '>A<' not in html  # A is unchanged
    assert 'type="submit"' in html
    assert _simpanan(tiket_selesai) == {'A': 5, 'B': 2}


@pytest.mark.django_db
def test_sync_saves_kd_tahap_then_reports_in_sync(client, pmde_admin_user, tiket_selesai):
    TiketKdTahap.objects.create(id_tiket=tiket_selesai, kd_tahap='B', jumlah_baris=2)
    client.force_login(pmde_admin_user)

    with _tanpa_rekap(), _kd_oracle({'A': 5, None: 3}):
        fingerprint = _fingerprint(client.get(_url(tiket_selesai)).json()['html'])
        data = client.post(_url(tiket_selesai), {'fingerprint': fingerprint}).json()
        assert data['success'] is True
        assert _simpanan(tiket_selesai) == {'A': 5, None: 3}

        html = client.get(_url(tiket_selesai)).json()['html']
        assert 'data-sync-state="not-found"' in html  # no rekap row, and KD Tahap now in sync
        assert 'data-kd-state="unchanged"' in html
        assert 'type="submit"' not in html
        assert client.post(_url(tiket_selesai), {'fingerprint': fingerprint}).json()['success'] is False


@pytest.mark.django_db
def test_kd_tahap_changed_after_preview_is_not_saved(client, pmde_admin_user, tiket_selesai):
    client.force_login(pmde_admin_user)

    with _tanpa_rekap(), _kd_oracle({'A': 5}):
        fingerprint = _fingerprint(client.get(_url(tiket_selesai)).json()['html'])
    with _tanpa_rekap(), _kd_oracle({'A': 6}):
        data = client.post(_url(tiket_selesai), {'fingerprint': fingerprint}).json()

    assert data['success'] is False
    assert 'Data berubah' in data['message']
    assert _simpanan(tiket_selesai) == {}


@pytest.mark.django_db
def test_kd_tahap_error_is_shown_and_keeps_stored_rows(client, pmde_admin_user, tiket_selesai):
    TiketKdTahap.objects.create(id_tiket=tiket_selesai, kd_tahap='A', jumlah_baris=5)
    client.force_login(pmde_admin_user)

    with _tanpa_rekap(), _kd_oracle(KdTahapError('BANKDATAPDE.X: ORA-00942: table or view does not exist')):
        html = client.get(_url(tiket_selesai)).json()['html']

    assert 'data-kd-state="error"' in html and 'ORA-00942' in html
    assert 'type="submit"' not in html  # nothing else to sync
    assert _simpanan(tiket_selesai) == {'A': 5}


@pytest.mark.django_db
def test_tiket_staying_before_pengendalian_mutu_skips_kd_tahap(client, pmde_admin_user):
    tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI)
    client.force_login(pmde_admin_user)

    with _tanpa_rekap(), _kd_oracle({'A': 5}) as ambil:
        html = client.get(_url(tiket)).json()['html']

    ambil.assert_not_called()
    assert 'sinkronisasi-kd-tahap' not in html


@pytest.mark.django_db
def test_transition_to_pengendalian_mutu_also_saves_kd_tahap(client, pmde_admin_user):
    tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI)
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PMDE, active=True)
    client.force_login(pmde_admin_user)

    with _oracle(_aturan_1_row(tiket.nomor_tiket)), _kd_oracle({'A': 7}):
        html = client.get(_url(tiket)).json()['html']
        assert 'Aturan 1' in html and 'data-kd-state="changed"' in html
        data = client.post(_url(tiket), {'fingerprint': _fingerprint(html)}).json()

    assert data['success'] is True
    tiket.refresh_from_db()
    assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
    assert _simpanan(tiket) == {'A': 7}
