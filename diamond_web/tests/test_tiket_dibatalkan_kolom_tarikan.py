"""A cancelled tiket keeps no tarikan counts (baris I/U, QC).

PIDE deletes a void tarikan from Oracle, so the counts the tiket update sync
copied from it must go with it: every way of cancelling clears them, the sync
never copies them back onto a cancelled tiket, and the detail page's
Sinkronisasi clears the ones an earlier cancel left behind. baris_res and
baris_cde stay, synced from Oracle: they are what PIDE handed back.
"""
import re
from datetime import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse

from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_DIREKAM,
    STATUS_IDENTIFIKASI,
)
from diamond_web.models.notification import Notification
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.utils.tiket_dibatalkan import KOLOM_TARIKAN_DIBATALKAN
from diamond_web.views.sync_tiket_update import _check_tiket_update_data, _update_tiket_data

from .conftest import TiketFactory, TiketPICFactory, UserFactory
from .test_sync_tiket_update_rules import TGL_TRANSFER, _row, _service

SERVICE = 'diamond_web.views.tiket.sinkronisasi_tiket.OracleDataSyncService'

# What the sync had copied before the tarikan was voided (LM031010126082801).
TERISI = dict(baris_i=19, baris_u=2033, baris_res=7, baris_cde=4,
              sudah_qc=0, belum_qc=19, lolos_qc=0, tidak_lolos_qc=0, qc_c=0)


@pytest.fixture(autouse=True)
def _sync_logs_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr('diamond_web.views.sync_tiket_update.SYNC_LOGS_DIR', str(tmp_path))


def _assert_dikosongkan(tiket, baris_cde=4, baris_res=7):
    tiket.refresh_from_db()
    for field in KOLOM_TARIKAN_DIBATALKAN:
        assert getattr(tiket, field) is None, field
    assert (tiket.baris_res, tiket.baris_cde) == (baris_res, baris_cde)


def _rekap(nomor_tiket, **overrides):
    """Oracle still holds a tarikan with I/U rows and counts."""
    values = dict(tgl_transfer=TGL_TRANSFER, baris_i=19, baris_u=2033, belum_qc=19, baris_cde=4)
    values.update(overrides)
    return _row(nomor_tiket, **values)


@pytest.mark.django_db
class TestPembatalanManual:

    def test_batalkan_p3de(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=STATUS_DIREKAM, **TERISI)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        client.post(reverse('batalkan_tiket', args=[tiket.pk]), {'catatan': 'Salah rekam'})

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        _assert_dikosongkan(tiket)

    def test_dikembalikan_pide(self, client, pide_user):
        tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, tgl_transfer=TGL_TRANSFER, **TERISI)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)
        TiketPICFactory(id_tiket=tiket, id_user=UserFactory(), role=TiketPIC.Role.P3DE, active=True)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', args=[tiket.pk]), {'catatan': 'Salah tarik'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.json()['success'] is True

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        assert tiket.tgl_transfer == TGL_TRANSFER
        _assert_dikosongkan(tiket)


@pytest.mark.django_db
class TestSinkronisasiMassal:

    def test_rekap_hanya_cde_tidak_membatalkan(self, db):
        """CDE ≠ Baris Lengkap, so Aturan 4 does not cancel: the counts are synced, the status left to the PIC."""
        tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, **TERISI)
        _update_tiket_data(_service([_row(
            tiket.nomor_tiket, tgl_transfer=TGL_TRANSFER,
            baris_i=0, baris_u=0, baris_res=0, baris_cde=10, belum_qc=0,
        )]))

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_IDENTIFIKASI
        assert (tiket.baris_i, tiket.baris_u, tiket.baris_cde, tiket.belum_qc) == (0, 0, 10, 0)

    def test_aturan_4_mengosongkan(self, db):
        """Res + CDE == Baris Lengkap: cancelled, keeping Res and CDE as Oracle has them."""
        tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, **dict(TERISI, baris_lengkap=14))
        _update_tiket_data(_service([_row(
            tiket.nomor_tiket, tgl_transfer=TGL_TRANSFER,
            baris_i=0, baris_u=0, baris_res=4, baris_cde=10, belum_qc=0,
        )]))

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        _assert_dikosongkan(tiket, baris_cde=10, baris_res=4)

    def test_tidak_disalin_ulang_ke_tiket_dibatalkan(self, db):
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, tgl_transfer=TGL_TRANSFER)
        result = _update_tiket_data(_service([_rekap(tiket.nomor_tiket, baris_res=3)]))

        tiket.refresh_from_db()
        assert tiket.baris_i is None and tiket.belum_qc is None
        assert (tiket.baris_res, tiket.baris_cde) == (3, 4)
        assert result['updated_rows'] == 1  # baris_res and baris_cde only

    def test_sisa_lama_tidak_disentuh_sinkronisasi_massal(self, db):
        """The nightly run leaves old counts alone; only the detail page clears them."""
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, tgl_transfer=TGL_TRANSFER, **TERISI)
        result = _update_tiket_data(_service([_rekap(tiket.nomor_tiket, baris_i=25, baris_res=7)]))

        tiket.refresh_from_db()
        assert tiket.baris_i == 19
        assert result['unchanged'] == 1

    def test_dry_run_tidak_menghitung_kolom_tarikan(self, db):
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, tgl_transfer=TGL_TRANSFER, baris_res=0, baris_cde=4)
        result = _check_tiket_update_data(_service([_rekap(tiket.nomor_tiket)]))
        assert result['would_unchanged'] == 1
        assert result['would_update'] == 0


def _url(tiket):
    return reverse('sinkronisasi_tiket', args=[tiket.pk])


def _fingerprint(html):
    return re.search(r'name="fingerprint" value="([0-9a-f]*)"', html).group(1)


@pytest.mark.django_db
class TestPerbaikanDiHalamanDetail:
    """Sinkronisasi dari Oracle repairs a cancelled tiket's leftover counts."""

    def _sync(self, client, tiket, rows):
        with patch(SERVICE, return_value=_service(rows)):
            html = client.get(_url(tiket)).json()['html']
            data = client.post(_url(tiket), {'fingerprint': _fingerprint(html)}).json()
        return html, data

    def test_tidak_ada_di_oracle_tetap_dikosongkan(self, client, pmde_admin_user):
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, **dict(TERISI, baris_res=6))
        TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(pmde_admin_user)
        html, data = self._sync(client, tiket, [])

        assert 'data-sync-state="kosongkan"' in html
        assert 'belum ada di rekap tarikan' in html
        assert 'Baris I' in html and '2.033' in html
        assert 'sinkronisasi-kosongkan-note' in html
        assert 'type="submit"' in html
        assert data['success'] is True

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_DIBATALKAN
        _assert_dikosongkan(tiket, baris_res=6)  # Res is kept, as CDE is
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()
        # Clearing the other counts is not an update from Oracle: P3DE is not told.
        assert 'sinkronisasi-notif-res-cde' not in html
        assert not Notification.objects.filter(title='Update Baris Res/CDE').exists()

    def test_masih_ada_di_oracle_dikosongkan(self, client, pmde_admin_user):
        """Oracle still holds a CDE-only rekap, which does not undo the cancel."""
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, tgl_transfer=TGL_TRANSFER, **TERISI)
        client.force_login(pmde_admin_user)
        html, data = self._sync(client, tiket, [_row(
            tiket.nomor_tiket, tgl_transfer=TGL_TRANSFER,
            baris_i=0, baris_u=0, baris_res=0, baris_cde=4, belum_qc=0,
        )])

        assert 'data-sync-state="preview"' in html
        assert data['success'] is True
        _assert_dikosongkan(tiket, baris_res=0)  # Res follows Oracle

    def test_nilai_nol_hanya_dihitung_di_pratinjau(self, client, pmde_admin_user):
        """Migrated tikets carry 0 in every count: cleared too, but not listed row by row."""
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, **dict.fromkeys(KOLOM_TARIKAN_DIBATALKAN, 0))
        client.force_login(pmde_admin_user)
        html, data = self._sync(client, tiket, [])

        assert 'data-sync-state="kosongkan"' in html
        assert f'termasuk {len(KOLOM_TARIKAN_DIBATALKAN)} kolom yang bernilai 0' in html
        assert 'sinkronisasi-field-table' not in html
        assert 'Tidak ada kolom yang berubah' not in html
        assert data['success'] is True
        _assert_dikosongkan(tiket, baris_cde=None, baris_res=None)

    def test_sudah_kosong_tidak_ada_yang_dilakukan(self, client, pmde_admin_user):
        tiket = TiketFactory(status_tiket=STATUS_DIBATALKAN, baris_cde=4)
        client.force_login(pmde_admin_user)
        html, data = self._sync(client, tiket, [])

        assert 'data-sync-state="not-found"' in html
        assert 'type="submit"' not in html
        assert data['success'] is False

    def test_tiket_aktif_tanpa_rekap_tidak_disentuh(self, client, pmde_admin_user):
        tiket = TiketFactory(status_tiket=STATUS_DIKIRIM_KE_PIDE, **TERISI)
        client.force_login(pmde_admin_user)
        html, data = self._sync(client, tiket, [])

        assert 'data-sync-state="not-found"' in html
        assert data['success'] is False
        tiket.refresh_from_db()
        assert tiket.baris_i == 19

    def test_pratinjau_rekap_hanya_cde_status_manual(self, client, pmde_admin_user):
        tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, baris_i=7)
        TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pmde_admin_user)
        with patch(SERVICE, return_value=_service([_row(
            tiket.nomor_tiket, tgl_transfer=TGL_TRANSFER,
            baris_i=0, baris_u=0, baris_res=0, baris_cde=10, belum_qc=0,
        )])):
            html = client.get(_url(tiket)).json()['html']

        assert 'Aturan 4' not in html
        assert 'id="sinkronisasi-status-manual"' in html
        assert 'sinkronisasi-notif-res-cde' not in html  # no active P3DE PIC
        assert 'dikirim ke 1 PIC PIDE/PMDE aktif' in html
        rows = re.findall(r'<tr>\s*<td>([^<]+)</td>', html.split('sinkronisasi-field-table')[1].split('</table>')[0])
        assert 'Baris I' in rows and 'Baris CDE' in rows
