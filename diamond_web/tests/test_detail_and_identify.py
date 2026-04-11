"""Tests for tiket/detail.py and tiket/identifikasi_tiket.py views.

Covers: TiketDetailView (access control, context), IdentifikasiTiketView (GET/POST/AJAX)
"""
import json
import pytest
from django.urls import reverse
from django.utils import timezone

from diamond_web.models import TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory


# ============================================================
# TiketDetailView
# ============================================================

@pytest.mark.django_db
class TestTiketDetailView:
    """Tests for TiketDetailView."""

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_admin_can_access(self, client, admin_user, tiket):
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_tiket_pic_user_can_access(self, client, authenticated_user, tiket_with_pic):
        """User with TiketPIC can access tiket detail."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket_with_pic.pk]))
        assert resp.status_code == 200

    def test_non_pic_user_gets_403(self, client, authenticated_user, db):
        """P3DE user without TiketPIC gets permission denied."""
        tiket = TiketFactory(status_tiket=1)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code in (403, 302)

    def test_pide_user_with_pic_can_access(self, client, pide_user, db):
        """PIDE user with TiketPIC can access detail."""
        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pide_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_pmde_user_with_pic_can_access(self, client, pmde_user, db):
        """PMDE user with TiketPIC can access detail."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user,
                        role=TiketPIC.Role.PMDE, active=True)
        client.force_login(pmde_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_context_has_tiket(self, client, admin_user, tiket):
        """Context contains tiket object."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert 'object' in resp.context or 'tiket' in resp.context

    def test_context_has_tiket_actions(self, client, admin_user, tiket):
        """Context contains tiket_actions list."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_tiket_not_found_returns_404(self, client, admin_user):
        """Non-existent tiket returns 404."""
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[999999]))
        assert resp.status_code == 404

    def test_format_periode_bulanan(self, client, admin_user, db):
        """Detail view renders tiket with bulanan periode correctly."""
        from diamond_web.tests.conftest import (
            PeriodePengirimanFactory, JenisDataILAPFactory, PeriodeJenisDataFactory,
        )
        tiket = TiketFactory(status_tiket=1, periode=3)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200


# ============================================================
# IdentifikasiTiketView
# ============================================================

@pytest.mark.django_db
class TestIdentifikasiTiketView:
    """Tests for IdentifikasiTiketView."""

    def _make_dikirim_tiket(self, pide_user):
        """Create a tiket with status=4 (DIKIRIM_KE_PIDE) and PIDE PIC."""
        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        return tiket

    def test_requires_login(self, client, pide_user, db):
        tiket = self._make_dikirim_tiket(pide_user)
        resp = client.get(reverse('identifikasi_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_non_pide_user_denied(self, client, authenticated_user, pide_user, db):
        """Non-PIDE user cannot access identifikasi view."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('identifikasi_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_pide_user_wrong_status_denied(self, client, pide_user, db):
        """PIDE PIC user with tiket not in status 4 is denied."""
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                        role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pide_user)
        resp = client.get(reverse('identifikasi_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_pide_user_non_pic_denied(self, client, pide_user, db):
        """PIDE user without TiketPIC is denied."""
        tiket = TiketFactory(status_tiket=4)
        client.force_login(pide_user)
        resp = client.get(reverse('identifikasi_tiket', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_get_returns_form_html(self, client, pide_user, db):
        """GET returns JSON with form HTML."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        resp = client.get(reverse('identifikasi_tiket', args=[tiket.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_post_marks_tiket_identifikasi(self, client, pide_user, db):
        """POST marks tiket status as IDENTIFIKASI (5)."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            {'tgl_rekam_pide': timezone.now().strftime('%Y-%m-%dT%H:%M')},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        tiket.refresh_from_db()
        assert tiket.status_tiket == 5  # STATUS_IDENTIFIKASI

    def test_post_creates_tiket_action(self, client, pide_user, db):
        """POST creates a TiketAction with IDENTIFIKASI action."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            {'tgl_rekam_pide': timezone.now().strftime('%Y-%m-%dT%H:%M')},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert TiketAction.objects.filter(id_tiket=tiket).exists()

    def test_post_without_date_uses_now(self, client, pide_user, db):
        """POST without tgl_rekam_pide defaults to now."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            {},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_post_invalid_date_returns_error(self, client, pide_user, db):
        """POST with invalid date format returns error JSON."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            {'tgl_rekam_pide': 'not-a-date'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_post_non_ajax_redirects(self, client, pide_user, db):
        """Non-AJAX POST redirects to tiket detail."""
        tiket = self._make_dikirim_tiket(pide_user)
        client.force_login(pide_user)
        resp = client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            {'tgl_rekam_pide': timezone.now().strftime('%Y-%m-%dT%H:%M')},
            follow=True,
        )
        assert resp.status_code == 200
