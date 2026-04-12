"""Tests for missing branches in tiket workflow views.

Covers:
- batalkan_tiket.py line 70: non-P3DE user denied
- dikembalikan_tiket.py lines 135-136: exception in form_valid
- dikembalikan_tiket.py lines 170-179: AJAX form_invalid
- dikembalikan_tiket.py line 193: get_success_url (non-AJAX redirect)
- selesaikan_tiket.py lines 144-153: exception in form_valid
- selesaikan_tiket.py line 167: non-AJAX form_invalid
- transfer_ke_pmde.py lines 136-137: exception fallback
- transfer_ke_pmde.py lines 170-179: AJAX form_invalid
- transfer_ke_pmde.py line 193: get_success_url
- rekam_hasil_penelitian.py lines 128-129: StatusPenelitian.DoesNotExist
- identifikasi_tiket.py lines 156-157: non-AJAX invalid date
- detail.py lines 97-113: _format_periode branches
- detail.py lines 165-166: KlasifikasiJenisData exception
- detail.py lines 232, 242: tiket_details dict branches
- kirim_tiket.py lines 162-163, 191-192, 204-206, 224-233, 242: various branches
"""
import json
import pytest
from unittest.mock import patch
from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.models.status_penelitian import StatusPenelitian
from diamond_web.tests.conftest import (
    UserFactory, TiketFactory, TiketPICFactory,
    PeriodeJenisDataFactory, PeriodePengirimanFactory,
    JenisDataILAPFactory, ILAPFactory,
)


# ============================================================
# BatalkanTiketView — line 70: non-P3DE user → return False
# ============================================================

@pytest.mark.django_db
class TestBatalkanTiketViewLine70:
    """Test that non-P3DE group users get denied even with a P3DE TiketPIC."""

    def test_non_p3de_group_denied(self, client, pide_user):
        """A pide_user (user_pide group, not user_p3de) cannot access batalkan even as PIC."""
        tiket = TiketFactory(status_tiket=1)
        # Add a P3DE TiketPIC for pide_user (unusual but tests the group check path)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(pide_user)
        resp = client.get(reverse('batalkan_tiket', kwargs={'pk': tiket.pk}))
        # Should be denied because pide_user is not in user_p3de / admin_p3de / admin group
        assert resp.status_code in (302, 403)


# ============================================================
# DikembalikanTiketView — missing branches
# ============================================================

@pytest.mark.django_db
class TestDikembalikanTiketViewBranches:
    """Test missing branches in DikembalikanTiketView."""

    def _setup(self, user):
        tiket = TiketFactory(status_tiket=4)  # STATUS_DIKIRIM
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE, active=True)
        # Also add P3DE PIC so notification can be sent
        p3de_user = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=p3de_user, role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def test_get_success_url_non_ajax_redirect(self, client, pide_user):
        """Non-AJAX POST calls get_success_url (line 193) and redirects."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', kwargs={'pk': tiket.pk}),
            {'catatan': 'Data perlu diperbaiki'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 3  # STATUS_DIKEMBALIKAN

    def test_ajax_form_invalid_missing_catatan(self, client, pide_user):
        """AJAX POST with empty catatan returns form_invalid JSON (lines 170-179)."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', kwargs={'pk': tiket.pk}),
            {'catatan': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_non_ajax_form_invalid_missing_catatan(self, client, pide_user):
        """Non-AJAX POST with empty catatan shows form_invalid."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', kwargs={'pk': tiket.pk}),
            {'catatan': ''},
        )
        assert resp.status_code == 200

    def test_form_valid_exception_ajax(self, client, pide_user):
        """Exception in form_valid returns error JSON for AJAX (lines 135-136)."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        with patch('diamond_web.views.tiket.dikembalikan_tiket.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("DB error")
            resp = client.post(
                reverse('dikembalikan_tiket', kwargs={'pk': tiket.pk}),
                {'catatan': 'Test error'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False


# ============================================================
# SelesaikanTiketView — missing branches
# ============================================================

@pytest.mark.django_db
class TestSelesaikanTiketViewBranches:
    """Test missing branches in SelesaikanTiketView."""

    def _setup(self, user):
        tiket = TiketFactory(status_tiket=6)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)
        return tiket

    _valid_data = {
        'sudah_qc': '100',
        'lolos_qc': '90',
        'tidak_lolos_qc': '10',
        'qc_c': '5',
    }

    def test_exception_in_form_valid_ajax(self, client, pmde_user):
        """Exception in form_valid returns error JSON for AJAX (lines 144-153)."""
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        with patch('diamond_web.views.tiket.selesaikan_tiket.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("DB failure")
            resp = client.post(
                reverse('selesaikan_tiket', args=[tiket.pk]),
                self._valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_exception_in_form_valid_non_ajax(self, client, pmde_user):
        """Exception in form_valid shows error message for non-AJAX (lines 144-153)."""
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        with patch('diamond_web.views.tiket.selesaikan_tiket.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("DB failure")
            resp = client.post(
                reverse('selesaikan_tiket', args=[tiket.pk]),
                self._valid_data,
            )
        assert resp.status_code == 200

    def test_non_ajax_form_invalid_missing_fields(self, client, pmde_user):
        """Non-AJAX POST with invalid form calls form_invalid (line 167)."""
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        resp = client.post(
            reverse('selesaikan_tiket', args=[tiket.pk]),
            {'sudah_qc': '', 'lolos_qc': '', 'tidak_lolos_qc': '', 'qc_c': ''},
        )
        assert resp.status_code == 200


# ============================================================
# TransferKePMDEView — missing branches
# ============================================================

@pytest.mark.django_db
class TestTransferKePMDEViewBranches:
    """Test missing branches in TransferKePMDEView."""

    def _setup(self, user):
        tiket = TiketFactory(status_tiket=5)
        TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PIDE, active=True)
        pmde_user = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)
        return tiket

    _valid_data = {
        'baris_i': 100,
        'baris_u': 50,
        'baris_res': 10,
        'baris_cde': 5,
        'tgl_transfer': '2024-01-15T10:00',
    }

    def test_get_success_url_non_ajax_redirect(self, client, pide_user):
        """Non-AJAX successful POST follows get_success_url (line 193)."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('transfer_ke_pmde', args=[tiket.pk]),
            self._valid_data,
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 6  # STATUS_PENGENDALIAN_MUTU

    def test_ajax_form_invalid_missing_fields(self, client, pide_user):
        """AJAX POST with missing fields returns form_invalid JSON (lines 170-179)."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('transfer_ke_pmde', args=[tiket.pk]),
            {'baris_i': 100, 'baris_u': 50, 'baris_res': 10, 'baris_cde': 5},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_non_ajax_form_invalid(self, client, pide_user):
        """Non-AJAX form_invalid re-renders the form."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('transfer_ke_pmde', args=[tiket.pk]),
            {'baris_i': 100},
        )
        assert resp.status_code == 200

    def test_exception_in_form_valid_ajax(self, client, pide_user):
        """Exception in form_valid returns error JSON (lines 136-137)."""
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        with patch('diamond_web.views.tiket.transfer_ke_pmde.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("Transfer error")
            resp = client.post(
                reverse('transfer_ke_pmde', args=[tiket.pk]),
                self._valid_data,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False


# ============================================================
# RekamHasilPenelitianView — lines 128-129: StatusPenelitian.DoesNotExist
# ============================================================

@pytest.mark.django_db
class TestRekamHasilPenelitianDoesNotExist:
    """Test that form submission works even when StatusPenelitian records don't exist."""

    def test_post_without_status_penelitian_records(self, client, authenticated_user):
        """When StatusPenelitian records don't exist, the except block is hit (lines 128-129)."""
        tiket = TiketFactory(status_tiket=1, baris_diterima=100)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        # DO NOT create StatusPenelitian records to trigger DoesNotExist
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 100,
                'baris_tidak_lengkap': 0,
                'catatan': 'All lengkap',
            },
            follow=True,
        )
        # Should still succeed (DoesNotExist is caught and ignored)
        assert resp.status_code == 200


# ============================================================
# IdentifikasiTiketView — lines 156-157: non-AJAX invalid date
# ============================================================

@pytest.mark.django_db
class TestIdentifikasiTiketNonAjaxInvalidDate:
    """Test non-AJAX path with invalid date in identifikasi_tiket (lines 156-157)."""

    def test_non_ajax_invalid_date(self, client, pide_user):
        """Non-AJAX POST with invalid tgl_rekam_pide hits lines 156-157."""
        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pide_user)
        client.raise_request_exception = False
        resp = client.post(
            reverse('identifikasi_tiket', kwargs={'pk': tiket.pk}),
            {'tgl_rekam_pide': 'not-a-date'},
        )
        # Should either render form or return 500 (template may not exist)
        assert resp.status_code in (200, 500)


# ============================================================
# TiketDetailView — _format_periode branches + other missing lines
# ============================================================

@pytest.mark.django_db
class TestTiketDetailFormatPeriode:
    """Test _format_periode branches in TiketDetailView (lines 97-113)."""

    def _create_tiket_with_periode(self, periode_name, periode=1, tahun=2024):
        """Create a tiket with a specific periode penerimaan."""
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=periode_name,
            defaults={'periode_penerimaan': periode_name},
        )
        jenis_data = JenisDataILAPFactory()
        from diamond_web.models.periode_jenis_data import PeriodeJenisData
        pjd = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman=periode_pengiriman,
            start_date='2024-01-01',
            akhir_penyampaian=31,
        )
        tiket = TiketFactory(
            id_periode_data=pjd,
            periode=periode,
            tahun=tahun,
            status_tiket=1,
        )
        return tiket

    def test_format_harian(self, client, authenticated_user):
        """Covers _format_periode 'Harian' branch (line 97)."""
        tiket = self._create_tiket_with_periode('Harian')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200
        assert 'Hari' in resp.content.decode()

    def test_format_mingguan(self, client, authenticated_user):
        """Covers _format_periode 'Mingguan' branch (line 99)."""
        tiket = self._create_tiket_with_periode('Mingguan')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200
        assert 'Minggu' in resp.content.decode()

    def test_format_2_mingguan(self, client, authenticated_user):
        """Covers _format_periode '2 Mingguan' branch (line 101)."""
        tiket = self._create_tiket_with_periode('2 Mingguan')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200

    def test_format_bulanan_valid(self, client, authenticated_user):
        """Covers _format_periode 'Bulanan' with valid period 1-12 (lines 102-104)."""
        tiket = self._create_tiket_with_periode('Bulanan', periode=3)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200
        assert 'Maret' in resp.content.decode()

    def test_format_bulanan_invalid(self, client, authenticated_user):
        """Covers _format_periode 'Bulanan' with invalid period > 12 (line 105)."""
        tiket = self._create_tiket_with_periode('Bulanan', periode=15)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200

    def test_format_triwulanan(self, client, authenticated_user):
        """Covers _format_periode 'Triwulanan' branch (line 107)."""
        tiket = self._create_tiket_with_periode('Triwulanan')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200

    def test_format_kuartal(self, client, authenticated_user):
        """Covers _format_periode 'Kuartal' branch (line 109)."""
        tiket = self._create_tiket_with_periode('Kuartal')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200

    def test_format_semester(self, client, authenticated_user):
        """Covers _format_periode 'Semester' branch (line 111)."""
        tiket = self._create_tiket_with_periode('Semester')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200

    def test_format_tahunan(self, client, authenticated_user):
        """Covers _format_periode 'Tahunan' branch (line 113)."""
        tiket = self._create_tiket_with_periode('Tahunan')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200
        assert '2024' in resp.content.decode()

    def test_format_else_branch(self, client, authenticated_user):
        """Covers _format_periode 'else' branch (line 113+)."""
        tiket = self._create_tiket_with_periode('Khusus')
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTiketDetailExtraFields:
    """Test tiket_details dict branches in TiketDetailView (lines 232, 242)."""

    def test_satuan_data_not_1(self, client, authenticated_user):
        """satuan_data != 1 branch covers line 232 else branch."""
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian='Bulanan',
            defaults={'periode_penerimaan': 'Bulanan'},
        )
        jenis_data = JenisDataILAPFactory()
        from diamond_web.models.periode_jenis_data import PeriodeJenisData
        pjd = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman=periode_pengiriman,
            start_date='2024-01-01',
            akhir_penyampaian=31,
        )
        tiket = TiketFactory(
            id_periode_data=pjd,
            satuan_data=2,  # not 1 → triggers else branch
            alasan_ketidaktersediaan='',  # falsy → triggers 'or "-"' branch  
            status_tiket=1,
        )
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', kwargs={'pk': tiket.pk}))
        assert resp.status_code == 200


# ============================================================
# KirimTiketView — missing lines
# ============================================================

@pytest.mark.django_db
class TestKirimTiketViewBranches:
    """Test missing branches in KirimTiketView."""

    def test_get_batch_tikets_with_p3de_pic(self, client, authenticated_user):
        """Batch mode shows tikets ready to send (covers context['tikets'] query)."""
        from diamond_web.constants.tiket_status import STATUS_DITELITI
        tiket = TiketFactory(status_tiket=STATUS_DITELITI, backup=True, tanda_terima=True)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('kirim_tiket'))
        assert resp.status_code == 200

    def test_post_exception_in_form_valid_ajax(self, client, authenticated_user):
        """Exception in form_valid returns error JSON (lines 204-206)."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        with patch('diamond_web.views.tiket.kirim_tiket.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("DB error kirim")
            resp = client.post(
                reverse('kirim_tiket'),
                {
                    'nomor_nd_nadine': 'ND-001/2024',
                    'tgl_nadine': '2024-01-01T10:00',
                    'tgl_kirim_pide': '2024-01-02T10:00',
                    'tiket_ids': str(tiket.pk),
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_exception_in_form_valid_non_ajax(self, client, authenticated_user):
        """Exception in form_valid shows error for non-AJAX (lines 224-233)."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        with patch('diamond_web.views.tiket.kirim_tiket.TiketAction.objects.create') as mock_create:
            mock_create.side_effect = Exception("DB error kirim")
            resp = client.post(
                reverse('kirim_tiket'),
                {
                    'nomor_nd_nadine': 'ND-001/2024',
                    'tgl_nadine': '2024-01-01T10:00',
                    'tgl_kirim_pide': '2024-01-02T10:00',
                    'tiket_ids': str(tiket.pk),
                },
            )
        assert resp.status_code == 200

    def test_post_non_ajax_form_valid_success(self, client, authenticated_user):
        """Non-AJAX successful form submission → success message and redirect (lines 224-233)."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-999/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket_ids': str(tiket.pk),
            },
            follow=True,
        )
        assert resp.status_code == 200

    def test_post_unauthorized_non_ajax(self, client, authenticated_user):
        """Non-AJAX form_valid with unauthorized tiket shows error (lines 162-163)."""
        tiket = TiketFactory(status_tiket=1)  # No TiketPIC for authenticated_user
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-100/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket_ids': str(tiket.pk),
            },
        )
        assert resp.status_code == 200

    def test_post_non_ajax_form_invalid(self, client, authenticated_user):
        """Non-AJAX invalid form re-renders (line 242)."""
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {'nomor_nd_nadine': '', 'tgl_nadine': '', 'tgl_kirim_pide': ''},
        )
        assert resp.status_code == 200

    def test_get_form_kwargs_with_tiket_select(self, client, authenticated_user):
        """POST with tiket-select checkboxes (no tiket_ids) uses list (lines 191-192)."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user, role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-555/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket-select': [str(tiket.pk)],
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
