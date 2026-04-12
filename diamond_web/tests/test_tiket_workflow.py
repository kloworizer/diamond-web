"""Tests for tiket workflow action views.

Covers: batalkan_tiket, dikembalikan_tiket, selesaikan_tiket,
        transfer_ke_pmde, rekam_hasil_penelitian, kirim_tiket
"""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models import TiketPIC, StatusPenelitian
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory


# ============================================================
# BatalkanTiketView
# ============================================================

@pytest.mark.django_db
class TestBatalkanTiketView:
    """BatalkanTiketView – P3DE cancel a tiket.

    test_func requires: user_p3de/admin_p3de/admin group AND active P3DE TiketPIC.
    """

    def _setup(self, authenticated_user):
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('batalkan_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, authenticated_user, tiket):
        """user_p3de user without active P3DE TiketPIC is denied."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('batalkan_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_get_with_pic(self, client, authenticated_user):
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('batalkan_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_post_cancels_tiket(self, client, authenticated_user):
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('batalkan_tiket', args=[tiket.pk]),
            {'catatan': 'Data tidak valid'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 7  # STATUS_DIBATALKAN

    def test_admin_can_cancel(self, client, admin_user):
        """Admin needs a P3DE TiketPIC — test_func checks TiketPIC even for superusers."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=admin_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(admin_user)
        resp = client.post(
            reverse('batalkan_tiket', args=[tiket.pk]),
            {'catatan': 'Admin cancel'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 7

    def test_post_invalid_empty_catatan_returns_form(self, client, authenticated_user):
        """Empty catatan is required, form re-renders on invalid submission."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('batalkan_tiket', args=[tiket.pk]),
            {'catatan': ''},
        )
        assert resp.status_code == 200  # re-render form
        tiket.refresh_from_db()
        assert tiket.status_tiket != 7  # not cancelled


# ============================================================
# DikembalikanTiketView
# ============================================================

@pytest.mark.django_db
class TestDikembalikanTiketView:
    """DikembalikanTiketView – PIDE return tiket to P3DE.

    test_func requires: active PIDE TiketPIC (no group check due to override).
    """

    def _setup(self, pide_user):
        tiket = TiketFactory(status_tiket=4)  # DIKIRIM_KE_PIDE
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        # P3DE PIC for notification target
        p3de = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=p3de,
                        role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('dikembalikan_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, pide_user, tiket):
        """pide_user without an active PIDE TiketPIC for this tiket is denied."""
        client.force_login(pide_user)
        resp = client.get(reverse('dikembalikan_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_get_with_pic(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('dikembalikan_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_post_returns_tiket(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', args=[tiket.pk]),
            {'catatan': 'Data tidak lengkap'},
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 3  # STATUS_DIKEMBALIKAN

    def test_ajax_form_valid(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', args=[tiket.pk]),
            {'catatan': 'Perlu revisi'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_ajax_form_invalid_empty_catatan(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('dikembalikan_tiket', args=[tiket.pk]),
            {'catatan': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data['success'] is False


# ============================================================
# SelesaikanTiketView
# ============================================================

@pytest.mark.django_db
class TestSelesaikanTiketView:
    """SelesaikanTiketView – PMDE complete tiket with QC.

    test_func requires: active PMDE TiketPIC AND status_tiket == 6.
    """

    def _setup(self, pmde_user):
        tiket = TiketFactory(status_tiket=6)  # STATUS_PENGENDALIAN_MUTU
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user,
                        role=TiketPIC.Role.PMDE, active=True)
        return tiket

    _valid_data = {
        'sudah_qc': 100,
        'lolos_qc': 90,
        'tidak_lolos_qc': 10,
        'qc_c': 5,
    }

    def test_requires_login(self, client, tiket):
        resp = client.post(reverse('selesaikan_tiket', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_denied_wrong_status(self, client, pmde_user):
        """PMDE PIC for a tiket with wrong status is denied."""
        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user,
                        role=TiketPIC.Role.PMDE, active=True)
        client.force_login(pmde_user)
        resp = client.post(reverse('selesaikan_tiket', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, pmde_user):
        tiket = TiketFactory(status_tiket=6)
        client.force_login(pmde_user)
        resp = client.post(reverse('selesaikan_tiket', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_get_with_pic(self, client, pmde_user):
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        resp = client.get(reverse('selesaikan_tiket', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_post_completes_tiket(self, client, pmde_user):
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        resp = client.post(
            reverse('selesaikan_tiket', args=[tiket.pk]),
            self._valid_data,
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 8  # STATUS_SELESAI

    def test_ajax_form_valid(self, client, pmde_user):
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        resp = client.post(
            reverse('selesaikan_tiket', args=[tiket.pk]),
            self._valid_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_ajax_form_invalid_missing_fields(self, client, pmde_user):
        tiket = self._setup(pmde_user)
        client.force_login(pmde_user)
        resp = client.post(
            reverse('selesaikan_tiket', args=[tiket.pk]),
            {'sudah_qc': '', 'lolos_qc': '', 'tidak_lolos_qc': '', 'qc_c': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code in (200, 400)
        data = json.loads(resp.content)
        assert data['success'] is False


# ============================================================
# TransferKePMDEView
# ============================================================

@pytest.mark.django_db
class TestTransferKePMDEView:
    """TransferKePMDEView – PIDE transfer tiket to PMDE.

    test_func requires: active PIDE TiketPIC AND status_tiket == 5.
    """

    def _setup(self, pide_user):
        tiket = TiketFactory(status_tiket=5)  # STATUS_IDENTIFIKASI
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        pmde = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=pmde,
                        role=TiketPIC.Role.PMDE, active=True)
        return tiket

    _valid_data = {
        'baris_i': 100,
        'baris_u': 50,
        'baris_res': 10,
        'baris_cde': 5,
        'tgl_transfer': '2024-01-15T10:00',
    }

    def test_requires_login(self, client, tiket):
        resp = client.post(reverse('transfer_ke_pmde', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_denied_wrong_status(self, client, pide_user):
        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pide_user)
        resp = client.post(reverse('transfer_ke_pmde', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, pide_user):
        tiket = TiketFactory(status_tiket=5)
        client.force_login(pide_user)
        resp = client.post(reverse('transfer_ke_pmde', args=[tiket.pk]), self._valid_data)
        assert resp.status_code in (302, 403)

    def test_get_with_pic(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('transfer_ke_pmde', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_post_transfers_tiket(self, client, pide_user):
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

    def test_ajax_form_valid(self, client, pide_user):
        tiket = self._setup(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('transfer_ke_pmde', args=[tiket.pk]),
            self._valid_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_ajax_form_invalid_missing_tgl(self, client, pide_user):
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


# ============================================================
# RekamHasilPenelitianView
# ============================================================

@pytest.mark.django_db
class TestRekamHasilPenelitianView:
    """RekamHasilPenelitianView – P3DE record research results.

    test_func requires: active P3DE TiketPIC (no group check due to override).
    """

    def _setup(self, user):
        tiket = TiketFactory(status_tiket=1, baris_diterima=100)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.P3DE, active=True)
        StatusPenelitian.objects.get_or_create(deskripsi='Lengkap')
        StatusPenelitian.objects.get_or_create(deskripsi='Tidak Lengkap')
        StatusPenelitian.objects.get_or_create(deskripsi='Lengkap Sebagian')
        return tiket

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('rekam_hasil_penelitian', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_pic(self, client, authenticated_user, tiket):
        client.force_login(authenticated_user)
        resp = client.get(reverse('rekam_hasil_penelitian', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_get_with_pic(self, client, authenticated_user):
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('rekam_hasil_penelitian', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_post_records_lengkap(self, client, authenticated_user):
        """baris_lengkap == baris_diterima → StatusPenelitian 'Lengkap'."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 100,
                'baris_tidak_lengkap': 0,
                'catatan': 'Semua data lengkap',
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 2  # STATUS_DITELITI

    def test_post_records_tidak_lengkap(self, client, authenticated_user):
        """baris_lengkap == 0 → StatusPenelitian 'Tidak Lengkap'."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 0,
                'baris_tidak_lengkap': 100,
                'catatan': 'Data tidak lengkap',
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 2

    def test_post_records_sebagian_lengkap(self, client, authenticated_user):
        """Mixed baris → StatusPenelitian 'Lengkap Sebagian'."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '2',
                'baris_lengkap': 60,
                'baris_tidak_lengkap': 40,
                'catatan': 'Sebagian besar lengkap',
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 2

    def test_ajax_form_valid(self, client, authenticated_user):
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 100,
                'baris_tidak_lengkap': 0,
                'catatan': 'Lengkap',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_ajax_form_invalid_mismatched_baris(self, client, authenticated_user):
        """baris total ≠ baris_diterima triggers validation error."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 50,
                'baris_tidak_lengkap': 30,  # 50+30 ≠ 100
                'catatan': 'Wrong total',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_form_invalid_mismatched_baris(self, client, authenticated_user):
        """Non-AJAX invalid form re-renders the page."""
        tiket = self._setup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('rekam_hasil_penelitian', args=[tiket.pk]),
            {
                'tgl_teliti': '2024-01-01T10:00',
                'kesesuaian_data': '1',
                'baris_lengkap': 50,
                'baris_tidak_lengkap': 30,
                'catatan': 'Wrong total',
            },
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket != 2  # not changed


# ============================================================
# KirimTiketView
# ============================================================

@pytest.mark.django_db
class TestKirimTiketView:
    """KirimTiketView – P3DE send tikets to PIDE.

    Only group check (UserP3DERequiredMixin) applies via MRO.
    form_valid also checks active P3DE TiketPIC per tiket internally.
    """

    def test_requires_login(self, client):
        resp = client.get(reverse('kirim_tiket'))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('kirim_tiket'))
        assert resp.status_code in (302, 403)

    def test_get_batch_mode(self, client, authenticated_user):
        """user_p3de can access the batch-kirim page."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('kirim_tiket'))
        assert resp.status_code == 200

    def test_get_single_tiket_mode(self, client, authenticated_user):
        """user_p3de can access the single-tiket kirim page."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('kirim_tiket_from_tiket', kwargs={'tiket_pk': tiket.pk})
        )
        assert resp.status_code == 200

    def test_post_form_valid_sends_tikets(self, client, authenticated_user):
        """form_valid sends tiket to PIDE (status → 4) when user is active P3DE PIC."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-001/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket_ids': str(tiket.pk),
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 4  # STATUS_DIKIRIM_KE_PIDE

    def test_post_ajax_form_valid(self, client, authenticated_user):
        """AJAX POST sends tiket to PIDE and returns JSON success."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-002/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket_ids': str(tiket.pk),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_post_ajax_unauthorized_pic(self, client, authenticated_user):
        """form_valid rejects tikets where user is not active P3DE PIC."""
        tiket = TiketFactory(status_tiket=1)  # No TiketPIC for authenticated_user
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {
                'nomor_nd_nadine': 'ND-003/2024',
                'tgl_nadine': '2024-01-01T10:00',
                'tgl_kirim_pide': '2024-01-02T10:00',
                'tiket_ids': str(tiket.pk),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_ajax_form_invalid_missing_fields(self, client, authenticated_user):
        """Missing required fields returns AJAX error."""
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('kirim_tiket'),
            {'nomor_nd_nadine': '', 'tgl_nadine': '', 'tgl_kirim_pide': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False
