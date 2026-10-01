"""Tests for Sinkronisasi Tiket — Admin PMDE runs the tiket update sync for one
tiket from its detail page, with a preview first.

The single-tiket path must land exactly where the bulk sync (`_update_tiket_data`)
lands: same fields, same status, same audit trail.
"""
import re
from datetime import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.models.notification import Notification
from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.utils.oracle_sync import OracleSyncConfigError
from diamond_web.utils.tiket_dibatalkan import KOLOM_TARIKAN_DIBATALKAN
from diamond_web.views.sync_tiket_update import (
    CATATAN_DIBATALKAN_AUTO_SYNC,
    CATATAN_DIKEMBALIKAN_AUTO_SYNC,
    TiketUpdateRowError,
    _fetch_tiket_update_row,
    _update_tiket_data,
)

from .conftest import TiketFactory, TiketPICFactory
from .test_sync_tiket_update_rules import TGL_LOAD, _row, _service

TGL_TRANSFER = datetime(2026, 3, 10, 9, 30)
SERVICE = 'diamond_web.views.tiket.sinkronisasi_tiket.OracleDataSyncService'


@pytest.fixture(autouse=True)
def _sync_logs_in_tmp(tmp_path, monkeypatch):
    """Keep the result CSVs the sync writes out of the real sync_logs/."""
    monkeypatch.setattr('diamond_web.views.sync_tiket_update.SYNC_LOGS_DIR', str(tmp_path))


@pytest.fixture
def tiket_identifikasi(db):
    """Tiket at status 5 with an active PIDE and PMDE PIC."""
    tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, tgl_rekam_pide=datetime(2026, 3, 2))
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PIDE, active=True)
    TiketPICFactory(id_tiket=tiket, role=TiketPIC.Role.PMDE, active=True)
    return tiket


def _aturan_1_row(nomor_tiket):
    """Transferred with identification rows still to QC: Aturan 1, 5 → 6."""
    return _row(nomor_tiket, tgl_transfer=TGL_TRANSFER, baris_i=7, baris_u=2, belum_qc=7)


def _oracle(*rows):
    return patch(SERVICE, return_value=_service(list(rows)))


def _fingerprint(html):
    return re.search(r'name="fingerprint" value="([0-9a-f]*)"', html).group(1)


def _url(tiket):
    return reverse('sinkronisasi_tiket', args=[tiket.pk])


@pytest.mark.django_db
class TestAkses:
    """Only Admin PMDE (and superuser/admin) may preview or sync."""

    @pytest.mark.parametrize('fixture', ['pmde_admin_user', 'admin_user'])
    def test_admin_pmde_boleh(self, client, request, fixture, tiket_identifikasi):
        client.force_login(request.getfixturevalue(fixture))
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            resp = client.get(_url(tiket_identifikasi))
        assert resp.status_code == 200

    @pytest.mark.parametrize('fixture', ['pide_admin_user', 'p3de_admin_user', 'kasi_pmde_user', 'pmde_user'])
    def test_selain_admin_pmde_ditolak(self, client, request, fixture, tiket_identifikasi):
        user = request.getfixturevalue(fixture)
        # Holding the tiket as its PMDE PIC does not grant the sync either.
        TiketPICFactory(id_tiket=tiket_identifikasi, id_user=user, role=TiketPIC.Role.PMDE, active=True)
        client.force_login(user)
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            assert client.get(_url(tiket_identifikasi)).status_code == 403
            assert client.post(_url(tiket_identifikasi), {'fingerprint': 'x'}).status_code == 403
        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_IDENTIFIKASI

    def test_anonim_diarahkan_ke_login(self, client, tiket_identifikasi):
        assert client.get(_url(tiket_identifikasi)).status_code == 302

    def test_tombol_hanya_untuk_admin_pmde(self, client, pmde_admin_user, pide_admin_user, tiket_identifikasi):
        detail = reverse('tiket_detail', args=[tiket_identifikasi.pk])
        client.force_login(pmde_admin_user)
        resp = client.get(detail)
        assert resp.context['user_can_sync_tiket'] is True
        assert b'id="sinkronisasi-tiket-btn"' in resp.content

        client.force_login(pide_admin_user)
        resp = client.get(detail)
        assert resp.context['user_can_sync_tiket'] is False
        assert b'id="sinkronisasi-tiket-btn"' not in resp.content
        assert b'id="sinkronisasiTiketModal"' not in resp.content


@pytest.mark.django_db
class TestPratinjau:
    """GET shows what the sync would do and writes nothing."""

    def test_menampilkan_transisi_kolom_dan_aksi(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            html = client.get(_url(tiket_identifikasi)).json()['html']

        assert 'data-sync-state="preview"' in html
        assert 'Aturan 1' in html
        assert 'Pengendalian Mutu' in html
        assert 'Tanggal Transfer' in html and '10/03/2026 09:30' in html
        assert 'Baris I' in html
        assert 'Ditransfer ke PMDE' in html
        assert 'Tiket ditransfer ke PMDE' in html

        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_IDENTIFIKASI
        assert tiket_identifikasi.tgl_transfer is None
        assert not TiketAction.objects.filter(id_tiket=tiket_identifikasi).exists()

    def test_aksi_tanpa_pic_ditandai_dilewati(self, client, pmde_admin_user):
        tiket = TiketFactory(status_tiket=STATUS_IDENTIFIKASI)
        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row(tiket.nomor_tiket)):
            html = client.get(_url(tiket)).json()['html']
        assert 'Dilewati: tidak ada PIC PIDE aktif' in html

    def test_tidak_ada_di_oracle(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row('TIKET-LAIN')):
            html = client.get(_url(tiket_identifikasi)).json()['html']
        assert 'data-sync-state="not-found"' in html
        assert 'type="submit"' not in html

    def test_sudah_sinkron(self, client, pmde_admin_user, tiket_identifikasi):
        row = _aturan_1_row(tiket_identifikasi.nomor_tiket)
        _update_tiket_data(_service([row]))
        client.force_login(pmde_admin_user)
        with _oracle(row):
            html = client.get(_url(tiket_identifikasi)).json()['html']
        assert 'data-sync-state="unchanged"' in html
        assert 'type="submit"' not in html

    def test_oracle_belum_dikonfigurasi(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with patch(SERVICE, side_effect=OracleSyncConfigError('Konfigurasi Oracle belum lengkap.')):
            html = client.get(_url(tiket_identifikasi)).json()['html']
        assert 'data-sync-state="error"' in html
        assert 'Konfigurasi Oracle belum lengkap.' in html


@pytest.mark.django_db
class TestSinkronisasi:
    """POST applies the previewed plan — exactly what the bulk sync would do."""

    def test_hasil_sama_dengan_sinkronisasi_massal(self, client, pmde_admin_user, tiket_identifikasi):
        # A twin handled by the bulk sync is the reference.
        twin = TiketFactory(status_tiket=STATUS_IDENTIFIKASI, tgl_rekam_pide=datetime(2026, 3, 2))
        for role in (TiketPIC.Role.PIDE, TiketPIC.Role.PMDE):
            TiketPICFactory(id_tiket=twin, role=role, active=True)
        _update_tiket_data(_service([_aturan_1_row(twin.nomor_tiket)]))

        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            fingerprint = _fingerprint(client.get(_url(tiket_identifikasi)).json()['html'])
            data = client.post(_url(tiket_identifikasi), {'fingerprint': fingerprint}).json()
        assert data['success'] is True

        tiket_identifikasi.refresh_from_db()
        twin.refresh_from_db()
        assert tiket_identifikasi.status_tiket == twin.status_tiket == STATUS_PENGENDALIAN_MUTU
        for field in ('tgl_transfer', 'baris_i', 'baris_u', 'belum_qc', 'tgl_rekam_pide'):
            assert getattr(tiket_identifikasi, field) == getattr(twin, field), field

        def trail(t):
            return [
                (a.action, a.timestamp, a.catatan,
                 TiketPIC.objects.get(id_tiket=t, id_user=a.id_user).role)
                for a in TiketAction.objects.filter(id_tiket=t).order_by('id')
            ]
        assert trail(tiket_identifikasi) == trail(twin) == [
            (TiketActionType.DITRANSFER_KE_PMDE, TGL_TRANSFER, 'Tiket ditransfer ke PMDE', TiketPIC.Role.PIDE),
        ]

    def test_data_berubah_setelah_pratinjau_tidak_disimpan(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            fingerprint = _fingerprint(client.get(_url(tiket_identifikasi)).json()['html'])

        # Oracle moved on: QC is now complete, so the sync would close the tiket.
        selesai = _row(tiket_identifikasi.nomor_tiket, tgl_transfer=TGL_TRANSFER, baris_i=7, belum_qc=0, sudah_qc=7)
        with _oracle(selesai):
            data = client.post(_url(tiket_identifikasi), {'fingerprint': fingerprint}).json()

        assert data['success'] is False
        assert 'Aturan 3' in data['html']
        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_IDENTIFIKASI
        assert not TiketAction.objects.filter(id_tiket=tiket_identifikasi).exists()

        # The fresh preview carries the new fingerprint, which does go through.
        with _oracle(selesai):
            data = client.post(_url(tiket_identifikasi), {'fingerprint': _fingerprint(data['html'])}).json()
        assert data['success'] is True
        tiket_identifikasi.refresh_from_db()
        assert tiket_identifikasi.status_tiket == STATUS_SELESAI

    def test_kirim_ulang_tidak_menggandakan_aksi(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with _oracle(_aturan_1_row(tiket_identifikasi.nomor_tiket)):
            fingerprint = _fingerprint(client.get(_url(tiket_identifikasi)).json()['html'])
            assert client.post(_url(tiket_identifikasi), {'fingerprint': fingerprint}).json()['success'] is True
            assert client.post(_url(tiket_identifikasi), {'fingerprint': fingerprint}).json()['success'] is False
        assert TiketAction.objects.filter(id_tiket=tiket_identifikasi).count() == 1

    def test_tidak_ada_di_oracle(self, client, pmde_admin_user, tiket_identifikasi):
        client.force_login(pmde_admin_user)
        with _oracle():
            data = client.post(_url(tiket_identifikasi), {'fingerprint': ''}).json()
        assert data['success'] is False


class TestAmbilBarisOracle:
    """_fetch_tiket_update_row narrows the bulk query to one tiket."""

    def test_query_disaring_ke_nomor_tiket(self):
        service = _service([_aturan_1_row('PV034050126071001')])
        row = _fetch_tiket_update_row(service, 'PV034050126071001')
        assert row['nomor_tiket'] == 'PV034050126071001'

        cursor = service._connect_oracle('primary').__enter__().cursor().__enter__()
        sql, binds = cursor.execute.call_args.args
        assert 'WHERE no_tiket IN (:no_tiket_0)' in sql
        assert binds == {'no_tiket_0': 'PV034050126071001'}

    def test_nomor_ei_juga_mencari_bentuk_e(self):
        service = _service([_aturan_1_row('EI123456789012345')])
        _fetch_tiket_update_row(service, 'EI123456789012345')

        cursor = service._connect_oracle('primary').__enter__().cursor().__enter__()
        sql, binds = cursor.execute.call_args.args
        assert binds == {'no_tiket_0': 'EI123456789012345', 'no_tiket_1': 'E123456789012345'}

    def test_dua_baris_untuk_satu_tiket_ditolak(self):
        service = _service([_aturan_1_row('EI123456789012345'), _aturan_1_row('EI123456789012345')])
        with pytest.raises(TiketUpdateRowError):
            _fetch_tiket_update_row(service, 'EI123456789012345')

    def test_tidak_ada_baris(self):
        assert _fetch_tiket_update_row(_service([]), 'PV034050126071001') is None


TGL_IDENTIFIKASI = datetime(2026, 3, 2, 8, 0)


@pytest.fixture
def tiket_dibatalkan_sync(tiket_identifikasi):
    """Tiket Aturan 4 cancelled while Oracle's rekap held only its CDE rows.

    The sync no longer cancels such a tiket (the status of a Res/CDE-only
    tarikan is left to the PIC), so this is the state it left on tikets it
    cancelled before: written here as Aturan 4 wrote it.
    """
    pide = TiketPIC.objects.get(id_tiket=tiket_identifikasi, role=TiketPIC.Role.PIDE).id_user
    p3de = TiketPICFactory(id_tiket=tiket_identifikasi, role=TiketPIC.Role.P3DE, active=True).id_user
    for user, timestamp, action, catatan in (
        (pide, TGL_IDENTIFIKASI, TiketActionType.IDENTIFIKASI, 'Mulai proses identifikasi (data migrasi)'),
        (pide, TGL_TRANSFER, TiketActionType.DIKEMBALIKAN, CATATAN_DIKEMBALIKAN_AUTO_SYNC),
        (p3de, TGL_TRANSFER, TiketActionType.DIBATALKAN, CATATAN_DIBATALKAN_AUTO_SYNC),
    ):
        TiketAction.objects.create(
            id_tiket=tiket_identifikasi, id_user=user, timestamp=timestamp, action=action, catatan=catatan,
        )
    Tiket.objects.filter(pk=tiket_identifikasi.pk).update(
        status_tiket=STATUS_DIBATALKAN, tgl_dikembalikan=TGL_TRANSFER, tgl_rekam_pide=None,
        tgl_transfer=TGL_TRANSFER, baris_cde=15,
        **dict.fromkeys(KOLOM_TARIKAN_DIBATALKAN),
    )
    tiket_identifikasi.refresh_from_db()
    return tiket_identifikasi


def _rekap_hanya_cde(nomor_tiket):
    """The rekap only half built: nothing but the CDE rows came through."""
    return _row(nomor_tiket, tgl_transfer=TGL_TRANSFER, baris_cde=15, belum_qc=0)


def _rekap_lengkap(nomor_tiket):
    """The same tarikan once the rekap is complete."""
    return _row(nomor_tiket, tgl_transfer=TGL_TRANSFER, baris_i=8530, baris_u=93, baris_cde=15, belum_qc=8530)


def _trail(tiket):
    return [(a.action, a.catatan) for a in TiketAction.objects.filter(id_tiket=tiket).order_by('id')]


@pytest.mark.django_db
class TestKoreksiPembatalan:
    """A tiket Aturan 4 cancelled on a half-built rekap goes on from Identifikasi."""

    def test_pratinjau_menampilkan_koreksi(self, client, pmde_admin_user, tiket_dibatalkan_sync):
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_lengkap(tiket_dibatalkan_sync.nomor_tiket)):
            html = client.get(_url(tiket_dibatalkan_sync)).json()['html']

        assert 'id="sinkronisasi-koreksi"' in html
        assert 'Riwayat Aksi yang Akan Dihapus' in html
        assert 'Tiket dikembalikan oleh PIDE (auto-sync)' in html
        assert 'Tiket dibatalkan (dikembalikan oleh PIDE: auto-sync)' in html
        assert 'Aturan 1' in html

        tiket_dibatalkan_sync.refresh_from_db()
        assert tiket_dibatalkan_sync.status_tiket == STATUS_DIBATALKAN
        assert len(_trail(tiket_dibatalkan_sync)) == 3

    def test_menjadi_pengendalian_mutu(self, client, pmde_admin_user, tiket_dibatalkan_sync):
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_lengkap(tiket_dibatalkan_sync.nomor_tiket)):
            fingerprint = _fingerprint(client.get(_url(tiket_dibatalkan_sync)).json()['html'])
            data = client.post(_url(tiket_dibatalkan_sync), {'fingerprint': fingerprint}).json()
        assert data['success'] is True

        tiket = tiket_dibatalkan_sync
        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert tiket.tgl_rekam_pide == TGL_LOAD
        assert tiket.tgl_dikembalikan is None
        assert (tiket.baris_i, tiket.baris_u, tiket.baris_cde, tiket.belum_qc) == (8530, 93, 15, 8530)
        assert _trail(tiket) == [
            (TiketActionType.IDENTIFIKASI, 'Mulai proses identifikasi (data migrasi)'),
            (TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE'),
        ]
        p3de = TiketPIC.objects.get(id_tiket=tiket, role=TiketPIC.Role.P3DE).id_user
        assert Notification.objects.filter(recipient=p3de, title='Pembatalan Tiket Dikoreksi').count() == 1

        # A second sync finds nothing left to correct.
        with _oracle(_rekap_lengkap(tiket.nomor_tiket)):
            assert 'data-sync-state="unchanged"' in client.get(_url(tiket)).json()['html']

    def test_qc_sudah_lengkap_langsung_selesai(self, client, pmde_admin_user, tiket_dibatalkan_sync):
        """The rules run again from Identifikasi, so Aturan 3 applies as usual."""
        row = _row(tiket_dibatalkan_sync.nomor_tiket, tgl_transfer=TGL_TRANSFER,
                   baris_i=8530, baris_cde=15, sudah_qc=8530, belum_qc=0)
        client.force_login(pmde_admin_user)
        with _oracle(row):
            fingerprint = _fingerprint(client.get(_url(tiket_dibatalkan_sync)).json()['html'])
            assert client.post(_url(tiket_dibatalkan_sync), {'fingerprint': fingerprint}).json()['success']
        tiket_dibatalkan_sync.refresh_from_db()
        assert tiket_dibatalkan_sync.status_tiket == STATUS_SELESAI

    def test_sinkronisasi_massal_tidak_mengoreksi(self, tiket_dibatalkan_sync):
        _update_tiket_data(_service([_rekap_lengkap(tiket_dibatalkan_sync.nomor_tiket)]))
        tiket_dibatalkan_sync.refresh_from_db()
        assert tiket_dibatalkan_sync.status_tiket == STATUS_DIBATALKAN
        assert len(_trail(tiket_dibatalkan_sync)) == 3

    def test_rekap_masih_hanya_cde(self, client, pmde_admin_user, tiket_dibatalkan_sync):
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_hanya_cde(tiket_dibatalkan_sync.nomor_tiket)):
            html = client.get(_url(tiket_dibatalkan_sync)).json()['html']
        assert 'data-sync-state="unchanged"' in html

    def test_aksi_setelah_pembatalan_tidak_ditimpa(self, client, pmde_admin_user, tiket_dibatalkan_sync):
        TiketAction.objects.create(
            id_tiket=tiket_dibatalkan_sync, id_user=pmde_admin_user, timestamp=datetime(2026, 3, 12),
            action=TiketActionType.DIBATALKAN, catatan='Dibatalkan manual',
        )
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_lengkap(tiket_dibatalkan_sync.nomor_tiket)):
            html = client.get(_url(tiket_dibatalkan_sync)).json()['html']
        assert 'id="sinkronisasi-koreksi"' not in html

    def test_dibatalkan_manual_tidak_dikoreksi(self, client, pmde_admin_user, tiket_identifikasi):
        tiket_identifikasi.status_tiket = STATUS_DIBATALKAN
        tiket_identifikasi.save(update_fields=['status_tiket'])
        TiketAction.objects.create(
            id_tiket=tiket_identifikasi, id_user=pmde_admin_user, timestamp=datetime(2026, 3, 12),
            action=TiketActionType.DIBATALKAN, catatan='Dibatalkan oleh P3DE',
        )
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_lengkap(tiket_identifikasi.nomor_tiket)):
            html = client.get(_url(tiket_identifikasi)).json()['html']
        assert 'id="sinkronisasi-koreksi"' not in html


TGL_SELESAI = datetime(2026, 9, 28)


def _aksi(tiket, role, action, catatan, timestamp):
    user = TiketPIC.objects.get(id_tiket=tiket, role=role).id_user
    return TiketAction.objects.create(
        id_tiket=tiket, id_user=user, timestamp=timestamp, action=action, catatan=catatan,
    )


@pytest.fixture
def tiket_ditutup_aturan_2(tiket_identifikasi):
    """Tiket Aturan 2 closed while Oracle's rekap wrongly read Belum QC 0.

    Written by hand: the guard in Aturan 2 no longer lets the sync do it.
    """
    tiket = tiket_identifikasi
    tiket.status_tiket = STATUS_SELESAI
    tiket.tgl_transfer = TGL_TRANSFER
    tiket.save(update_fields=['status_tiket', 'tgl_transfer'])
    _aksi(tiket, TiketPIC.Role.PIDE, TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE', TGL_TRANSFER)
    _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.PENGENDALIAN_MUTU, 'Tiket selesai pengendalian mutu', TGL_TRANSFER)
    _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.SELESAI, 'Tiket selesai diproses)', TGL_SELESAI)
    return tiket


def _rekap_belum_qc(nomor_tiket, **overrides):
    """The complete rekap: I rows still waiting for QC."""
    values = dict(tgl_transfer=TGL_TRANSFER, baris_i=609, baris_u=1112, belum_qc=609)
    values.update(overrides)
    return _row(nomor_tiket, **values)


def _sync(client, tiket, row):
    with _oracle(row):
        fingerprint = _fingerprint(client.get(_url(tiket)).json()['html'])
        return client.post(_url(tiket), {'fingerprint': fingerprint}).json()


@pytest.mark.django_db
class TestKoreksiPenutupan:
    """A tiket the sync closed on a half-built rekap goes back to QC."""

    def test_pratinjau(self, client, pmde_admin_user, tiket_ditutup_aturan_2):
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_belum_qc(tiket_ditutup_aturan_2.nomor_tiket)):
            html = client.get(_url(tiket_ditutup_aturan_2)).json()['html']
        assert 'Koreksi Penutupan' in html
        assert 'Riwayat Aksi yang Akan Dihapus' in html
        assert 'Tiket selesai diproses)' in html
        assert 'Pembatalan Tiket Dikoreksi' not in html
        tiket_ditutup_aturan_2.refresh_from_db()
        assert tiket_ditutup_aturan_2.status_tiket == STATUS_SELESAI

    def test_aturan_2_kembali_ke_pengendalian_mutu(self, client, pmde_admin_user, tiket_ditutup_aturan_2):
        tiket = tiket_ditutup_aturan_2
        client.force_login(pmde_admin_user)
        assert _sync(client, tiket, _rekap_belum_qc(tiket.nomor_tiket))['success'] is True

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert (tiket.baris_i, tiket.baris_u, tiket.belum_qc) == (609, 1112, 609)
        # The transfer came from Aturan 1 in an earlier run and stays.
        assert _trail(tiket) == [(TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE')]
        with _oracle(_rekap_belum_qc(tiket.nomor_tiket)):
            assert 'data-sync-state="unchanged"' in client.get(_url(tiket)).json()['html']

    def test_aturan_3_kembali_ke_identifikasi_lalu_aturan_1(self, client, pmde_admin_user, tiket_identifikasi):
        tiket = tiket_identifikasi
        tiket.status_tiket = STATUS_SELESAI
        tiket.tgl_transfer = TGL_TRANSFER
        tiket.save(update_fields=['status_tiket', 'tgl_transfer'])
        _aksi(tiket, TiketPIC.Role.PIDE, TiketActionType.IDENTIFIKASI, 'Mulai proses identifikasi', TGL_IDENTIFIKASI)
        _aksi(tiket, TiketPIC.Role.PIDE, TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE', TGL_TRANSFER)
        _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.PENGENDALIAN_MUTU, 'Tiket selesai pengendalian mutu', TGL_TRANSFER)
        _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.SELESAI, 'Tiket selesai diproses', TGL_SELESAI)

        client.force_login(pmde_admin_user)
        assert _sync(client, tiket, _rekap_belum_qc(tiket.nomor_tiket))['success'] is True

        tiket.refresh_from_db()
        assert tiket.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert _trail(tiket) == [
            (TiketActionType.IDENTIFIKASI, 'Mulai proses identifikasi'),
            (TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE'),
        ]

    def test_ubah_isian_setelah_selesai_tidak_menghalangi(self, client, pmde_admin_user, tiket_ditutup_aturan_2):
        TiketAction.objects.create(
            id_tiket=tiket_ditutup_aturan_2, id_user=pmde_admin_user, timestamp=datetime(2026, 9, 29),
            action=TiketActionType.DIUBAH, catatan='isian tiket diubah',
        )
        client.force_login(pmde_admin_user)
        assert _sync(client, tiket_ditutup_aturan_2, _rekap_belum_qc(tiket_ditutup_aturan_2.nomor_tiket))['success']
        tiket_ditutup_aturan_2.refresh_from_db()
        assert tiket_ditutup_aturan_2.status_tiket == STATUS_PENGENDALIAN_MUTU
        assert TiketAction.objects.filter(id_tiket=tiket_ditutup_aturan_2, action=TiketActionType.DIUBAH).exists()

    @pytest.mark.parametrize('overrides', [
        {'belum_qc': 0, 'sudah_qc': 609},                  # QC really is done
        {'tgl_transfer': datetime(2026, 9, 20)},           # a new tarikan: Aturan 9
        {'tgl_rematch': datetime(2026, 9, 29)},            # a rematch: Aturan 8
    ])
    def test_tidak_dikoreksi(self, client, pmde_admin_user, tiket_ditutup_aturan_2, overrides):
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_belum_qc(tiket_ditutup_aturan_2.nomor_tiket, **overrides)):
            html = client.get(_url(tiket_ditutup_aturan_2)).json()['html']
        assert 'Koreksi Penutupan' not in html

    def test_data_migrasi_tidak_dikoreksi(self, client, pmde_admin_user, tiket_identifikasi):
        tiket = tiket_identifikasi
        tiket.status_tiket = STATUS_SELESAI
        tiket.tgl_transfer = TGL_TRANSFER
        tiket.save(update_fields=['status_tiket', 'tgl_transfer'])
        _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.PENGENDALIAN_MUTU,
              'Tiket selesai pengendalian mutu (data migrasi, tanggal perkiraan)', TGL_TRANSFER)
        _aksi(tiket, TiketPIC.Role.PMDE, TiketActionType.SELESAI,
              'Tiket selesai diproses (data migrasi, tanggal perkiraan)', TGL_SELESAI)
        client.force_login(pmde_admin_user)
        with _oracle(_rekap_belum_qc(tiket.nomor_tiket)):
            html = client.get(_url(tiket)).json()['html']
        assert 'Koreksi Penutupan' not in html

    def test_sinkronisasi_massal_tidak_mengoreksi(self, tiket_ditutup_aturan_2):
        _update_tiket_data(_service([_rekap_belum_qc(tiket_ditutup_aturan_2.nomor_tiket)]))
        tiket_ditutup_aturan_2.refresh_from_db()
        assert tiket_ditutup_aturan_2.status_tiket == STATUS_SELESAI
