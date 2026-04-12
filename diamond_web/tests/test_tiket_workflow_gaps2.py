"""Tests for remaining coverage gaps in tiket workflow views.

Covers:
- dikembalikan_tiket.py: lines 135-136, 178-179 (non-AJAX success / exception)
- transfer_ke_pmde.py: lines 136-137, 178-179
- kirim_tiket.py: lines 191-192, 204-206
- rekam_hasil_penelitian.py: lines 128-129
- tiket/detail.py: lines 97, 99, 101, 165-166, 232, 242
- pic.py: lines 199-200, 210-211, 393-395
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime
from django.urls import reverse
from django.contrib.auth.models import Group
from django.test import RequestFactory

from diamond_web.models import TiketPIC, StatusPenelitian
from diamond_web.views.tiket.dikembalikan_tiket import DikembalikanTiketView
from diamond_web.views.tiket.transfer_ke_pmde import TransferKePMDEView
from diamond_web.views.tiket.rekam_hasil_penelitian import RekamHasilPenelitianView
from diamond_web.views.tiket.kirim_tiket import KirimTiketView
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory, PICFactory,
    JenisDataILAPFactory, PeriodeJenisDataFactory, PeriodePengirimanFactory,
)


# ============================================================
# DikembalikanTiketView – non-AJAX success/exception paths
# ============================================================

@pytest.mark.django_db
class TestDikembalikanTiketNonAjaxPaths:
    """Cover lines 135-136 (non-AJAX success) and 178-179 (exception handler)."""

    def _setup_pide(self):
        """Create tiket + PIDE user + P3DE notification target."""
        pide_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_pide')
        pide_user.groups.add(group)

        tiket = TiketFactory(status_tiket=4)
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)

        # P3DE PIC to receive notification
        p3de_user = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=p3de_user, role=TiketPIC.Role.P3DE, active=True)
        return tiket, pide_user

    def test_build_absolute_uri_exception_lines_135_136(self, client):
        """build_absolute_uri raises → fallback to reverse() alone (lines 135-136)."""
        tiket, pide_user = self._setup_pide()
        client.force_login(pide_user)

        from django.http import HttpRequest

        def raise_exception(self_req, url=None):
            raise Exception('build_absolute_uri failed')

        original_build = HttpRequest.build_absolute_uri
        HttpRequest.build_absolute_uri = raise_exception
        try:
            with patch.object(DikembalikanTiketView, 'get_success_url', return_value='/'):
                resp = client.post(
                    reverse('dikembalikan_tiket', args=[tiket.pk]),
                    {'catatan': 'Data tidak lengkap untuk non-ajax'},
                )
        finally:
            HttpRequest.build_absolute_uri = original_build

        # Lines 135-136 executed (except handler), form_valid succeeds, redirect to /
        assert resp.status_code in (200, 302)

    def test_non_ajax_exception_lines_178_179(self, client):
        """Non-AJAX exception in form_valid → messages.error + form_invalid."""
        tiket, pide_user = self._setup_pide()
        client.force_login(pide_user)

        # Patch TiketAction.objects.create to raise an exception
        with patch(
            'diamond_web.views.tiket.dikembalikan_tiket.TiketAction.objects.create',
            side_effect=Exception('Forced DB error')
        ):
            resp = client.post(
                reverse('dikembalikan_tiket', args=[tiket.pk]),
                {'catatan': 'Catatan valid'},
            )
        # form_invalid re-renders the form at 200
        assert resp.status_code == 200


# ============================================================
# TransferKePMDEView – non-AJAX success/exception paths
# ============================================================

@pytest.mark.django_db
class TestTransferKePMDENonAjaxPaths:
    """Cover lines 136-137 (non-AJAX success) and 178-179 (exception handler)."""

    def _setup_pide(self):
        """Create tiket in IDENTIFIKASI status + PIDE user + PMDE notification target."""
        pide_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_pide')
        pide_user.groups.add(group)

        tiket = TiketFactory(status_tiket=5)  # STATUS_IDENTIFIKASI
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)

        # PMDE PIC to receive notification
        pmde_user = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=pmde_user, role=TiketPIC.Role.PMDE, active=True)
        return tiket, pide_user

    def test_non_ajax_success_lines_136_137(self, client):
        """Non-AJAX valid POST → messages.success + super().form_valid."""
        tiket, pide_user = self._setup_pide()
        client.force_login(pide_user)

        with patch.object(TransferKePMDEView, 'get_success_url', return_value='/'):
            resp = client.post(
                reverse('transfer_ke_pmde', args=[tiket.pk]),
                {
                    'baris_i': 10,
                    'baris_u': 5,
                    'baris_res': 2,
                    'baris_cde': 1,
                    'tgl_transfer': '2024-01-15T10:00',
                },
            )
        assert resp.status_code == 302
        tiket.refresh_from_db()
        assert tiket.status_tiket == 6  # STATUS_PENGENDALIAN_MUTU

    def test_build_absolute_uri_exception_lines_136_137(self, client):
        """build_absolute_uri raises → fallback to reverse() alone (lines 136-137)."""
        tiket, pide_user = self._setup_pide()
        client.force_login(pide_user)

        from django.http import HttpRequest

        def raise_exception(self_req, url=None):
            raise Exception('build_absolute_uri failed')

        original_build = HttpRequest.build_absolute_uri
        HttpRequest.build_absolute_uri = raise_exception
        try:
            with patch.object(TransferKePMDEView, 'get_success_url', return_value='/'):
                resp = client.post(
                    reverse('transfer_ke_pmde', args=[tiket.pk]),
                    {'baris_i': 10, 'baris_u': 5, 'baris_res': 2, 'baris_cde': 1,
                     'tgl_transfer': '2024-01-15T10:00'},
                )
        finally:
            HttpRequest.build_absolute_uri = original_build
        assert resp.status_code in (200, 302)

    def test_non_ajax_exception_lines_178_179(self, client):
        """Non-AJAX exception in form_valid → messages.error + form_invalid."""
        tiket, pide_user = self._setup_pide()
        client.force_login(pide_user)

        with patch(
            'diamond_web.views.tiket.transfer_ke_pmde.TiketAction.objects.create',
            side_effect=Exception('Forced DB error')
        ):
            resp = client.post(
                reverse('transfer_ke_pmde', args=[tiket.pk]),
                {'baris_i': 10, 'baris_u': 5, 'baris_res': 2, 'baris_cde': 1,
                 'tgl_transfer': '2024-01-15T10:00'},
            )
        assert resp.status_code == 200


# ============================================================
# KirimTiketView – non-AJAX success/exception paths
# ============================================================

@pytest.mark.django_db
class TestKirimTiketNonAjaxPaths:
    """Cover lines 191-192 (non-AJAX success) and 204-206 (non-AJAX exception)."""

    def _setup_p3de(self):
        """Create tiket ready for kirim + P3DE user + PIDE PIC."""
        p3de_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_p3de')
        p3de_user.groups.add(group)

        tiket = TiketFactory(status_tiket=2, backup=True, tanda_terima=True)  # STATUS_DITELITI
        TiketPICFactory(id_tiket=tiket, id_user=p3de_user, role=TiketPIC.Role.P3DE, active=True)

        pide_user = UserFactory()
        TiketPICFactory(id_tiket=tiket, id_user=pide_user, role=TiketPIC.Role.PIDE, active=True)
        return tiket, p3de_user

    def test_non_ajax_success_lines_191_192(self, client):
        """Non-AJAX valid POST → messages.success + super().form_valid."""
        tiket, p3de_user = self._setup_p3de()
        client.force_login(p3de_user)

        with patch.object(KirimTiketView, 'success_url', new='/', create=True):
            resp = client.post(
                reverse('kirim_tiket'),
                {
                    'tiket_ids': str(tiket.pk),
                    'nomor_nd_nadine': 'ND-TEST-001',
                    'tgl_nadine': '2024-01-15',
                    'tgl_kirim_pide': '2024-01-15',
                },
            )
        assert resp.status_code in (200, 302)
        tiket.refresh_from_db()
        assert tiket.status_tiket == 4  # STATUS_DIKIRIM_KE_PIDE

    def test_build_absolute_uri_exception_lines_191_192(self, client):
        """build_absolute_uri raises → fallback reverse() (lines 191-192)."""
        tiket, p3de_user = self._setup_p3de()
        client.force_login(p3de_user)

        from django.http import HttpRequest

        def raise_exception(self_req, url=None):
            raise Exception('build_absolute_uri failed')

        original_build = HttpRequest.build_absolute_uri
        HttpRequest.build_absolute_uri = raise_exception
        try:
            with patch.object(KirimTiketView, 'success_url', new='/', create=True):
                resp = client.post(
                    reverse('kirim_tiket'),
                    {
                        'tiket_ids': str(tiket.pk),
                        'nomor_nd_nadine': 'ND-TEST-003',
                        'tgl_nadine': '2024-01-15',
                        'tgl_kirim_pide': '2024-01-15',
                    },
                )
        finally:
            HttpRequest.build_absolute_uri = original_build
        assert resp.status_code in (200, 302)

    def test_non_ajax_exception_lines_204_206(self, client):
        """Non-AJAX exception → messages.error + form_invalid (lines 204-206)."""
        tiket, p3de_user = self._setup_p3de()
        client.force_login(p3de_user)

        with patch(
            'diamond_web.views.tiket.kirim_tiket.TiketAction.objects.create',
            side_effect=Exception('Forced error')
        ):
            resp = client.post(
                reverse('kirim_tiket'),
                {
                    'tiket_ids': str(tiket.pk),
                    'nomor_nd_nadine': 'ND-TEST-002',
                    'tgl_nadine': '2024-01-15',
                    'tgl_kirim_pide': '2024-01-15',
                },
            )
        assert resp.status_code == 200


# ============================================================
# RekamHasilPenelitianView – non-AJAX success path
# ============================================================

@pytest.mark.django_db
class TestRekamHasilPenelitianNonAjax:
    """Cover lines 128-129 (non-AJAX success: messages.success + super().form_valid)."""

    def _setup_p3de(self):
        p3de_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_p3de')
        p3de_user.groups.add(group)

        tiket = TiketFactory(status_tiket=1, baris_diterima=10)
        TiketPICFactory(id_tiket=tiket, id_user=p3de_user, role=TiketPIC.Role.P3DE, active=True)

        # Ensure StatusPenelitian entries exist
        StatusPenelitian.objects.get_or_create(deskripsi='Lengkap')
        StatusPenelitian.objects.get_or_create(deskripsi='Tidak Lengkap')
        StatusPenelitian.objects.get_or_create(deskripsi='Lengkap Sebagian')

        return tiket, p3de_user

    def test_non_ajax_success_lines_128_129(self, client):
        """Non-AJAX valid POST → messages.success + super().form_valid."""
        tiket, p3de_user = self._setup_p3de()
        client.force_login(p3de_user)

        with patch.object(RekamHasilPenelitianView, 'get_success_url', return_value='/'):
            resp = client.post(
                reverse('rekam_hasil_penelitian', args=[tiket.pk]),
                {
                    'tgl_teliti': '2024-01-15T10:00',
                    'kesesuaian_data': 1,
                    'baris_lengkap': 10,
                    'baris_tidak_lengkap': 0,
                    'catatan': 'Hasil penelitian direkam',
                },
            )
        assert resp.status_code == 302
        tiket.refresh_from_db()
        assert tiket.status_tiket == 2  # STATUS_DITELITI

    def test_status_penelitian_does_not_exist_lines_128_129(self, client):
        """StatusPenelitian.DoesNotExist → except: pass (lines 128-129)."""
        p3de_user = UserFactory()
        group, _ = Group.objects.get_or_create(name='user_p3de')
        p3de_user.groups.add(group)

        # Create tiket WITHOUT creating StatusPenelitian objects → DoesNotExist
        tiket = TiketFactory(status_tiket=1, baris_diterima=10)
        TiketPICFactory(id_tiket=tiket, id_user=p3de_user, role=TiketPIC.Role.P3DE, active=True)
        # Ensure StatusPenelitian does NOT exist
        StatusPenelitian.objects.all().delete()

        client.force_login(p3de_user)
        with patch.object(RekamHasilPenelitianView, 'get_success_url', return_value='/'):
            resp = client.post(
                reverse('rekam_hasil_penelitian', args=[tiket.pk]),
                {
                    'tgl_teliti': '2024-01-15T10:00',
                    'kesesuaian_data': 1,
                    'baris_lengkap': 10,
                    'baris_tidak_lengkap': 0,
                    'catatan': 'Hasil penelitian direkam',
                },
            )
        # Should still succeed (except passes silently) and redirect
        assert resp.status_code in (200, 302)


# ============================================================
# TiketDetailView – _format_periode branches
# ============================================================

@pytest.mark.django_db
class TestTiketDetailFormatPeriode:
    """Cover lines 97 (Harian), 99 (Mingguan), 101 (2 Mingguan) in _format_periode.
    Also line 165-166 (exception in klasifikasi lookup) and line 232, 242 (role=None path).
    """

    def _make_tiket_with_periode(self, periode_penerimaan):
        """Create a tiket whose periode data uses the given periode_penerimaan."""
        from diamond_web.tests.conftest import PeriodePengirimanFactory
        admin = UserFactory()
        admin.is_superuser = True
        admin.save()

        # Create PeriodePengiriman with specific periode_penerimaan
        pp = PeriodePengirimanFactory(periode_penerimaan=periode_penerimaan)
        pd = PeriodeJenisDataFactory(id_periode_pengiriman=pp)
        tiket = TiketFactory(id_periode_data=pd, periode=1, tahun=2024)
        TiketPICFactory(id_tiket=tiket, id_user=admin, role=TiketPIC.Role.P3DE, active=True)
        return tiket, admin

    def test_format_periode_harian_line_97(self, client):
        """Harian period → 'Hari X - Y' (line 97)."""
        tiket, admin = self._make_tiket_with_periode('Harian')
        client.force_login(admin)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert 'Hari' in resp.content.decode()

    def test_format_periode_mingguan_line_99(self, client):
        """Mingguan period → 'Minggu X - Y' (line 99)."""
        tiket, admin = self._make_tiket_with_periode('Mingguan')
        client.force_login(admin)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200
        assert 'Minggu' in resp.content.decode()

    def test_format_periode_2_mingguan_line_101(self, client):
        """2 Mingguan period → '2 Minggu X - Y' (line 101)."""
        tiket, admin = self._make_tiket_with_periode('2 Mingguan')
        client.force_login(admin)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_detail_exception_in_klasifikasi_lines_165_166(self, client):
        """Exception in klasifikasi lookup → empty list (lines 165-166)."""
        from diamond_web.tests.conftest import PeriodePengirimanFactory
        admin = UserFactory()
        admin.is_superuser = True
        admin.save()

        pp = PeriodePengirimanFactory(periode_penerimaan='Bulanan')
        pd = PeriodeJenisDataFactory(id_periode_pengiriman=pp)
        tiket = TiketFactory(id_periode_data=pd, periode=1, tahun=2024)
        TiketPICFactory(id_tiket=tiket, id_user=admin, role=TiketPIC.Role.P3DE, active=True)

        client.force_login(admin)
        with patch(
            'diamond_web.views.tiket.detail.KlasifikasiJenisData.objects.filter',
            side_effect=Exception('DB error')
        ):
            resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200

    def test_detail_tiket_pic_unknown_role_lines_232_242(self, client):
        """TiketPIC with a role not in P3DE/PIDE/PMDE → tipe=None → is_pic_active=False."""
        from diamond_web.tests.conftest import PeriodePengirimanFactory
        admin = UserFactory()
        admin.is_superuser = True
        admin.save()

        pp = PeriodePengirimanFactory(periode_penerimaan='Bulanan')
        pd = PeriodeJenisDataFactory(id_periode_pengiriman=pp)
        tiket = TiketFactory(id_periode_data=pd, periode=6, tahun=2024)

        # Create a TiketPIC then update its role to an unknown value (99) via DB
        tp = TiketPICFactory(id_tiket=tiket, id_user=admin, role=TiketPIC.Role.P3DE, active=True)
        TiketPIC.objects.filter(pk=tp.pk).update(role=99)  # Unknown role → else branch

        client.force_login(admin)
        resp = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert resp.status_code == 200


# ============================================================
# PICUpdateView – reactivation path (lines 393-395)
# ============================================================

@pytest.mark.django_db
class TestPICUpdateReactivationPaths:
    """Cover lines 199-200, 210-211 (PICCreateView: existing active TiketPIC with null timestamp)
    and lines 393-395 (PICUpdateView: reactivation path, existing TiketPIC with null timestamp)."""

    def _create_admin(self):
        admin = UserFactory()
        group, _ = Group.objects.get_or_create(name='admin_p3de')
        admin.groups.add(group)
        admin.is_superuser = True
        admin.save()
        return admin

    def _make_fake_tiket_pic(self, active=True, timestamp=None):
        """Build a MagicMock TiketPIC with the given active/timestamp values."""
        fake_tp = MagicMock(spec=TiketPIC)
        fake_tp.active = active
        fake_tp.timestamp = timestamp
        fake_qs = MagicMock()
        fake_qs.first.return_value = fake_tp
        return fake_tp, fake_qs

    def test_pic_create_active_tiket_pic_with_null_timestamp_lines_199_200_210_211(self, client):
        """PICCreateView form_valid: existing ACTIVE TiketPIC with timestamp=None
        covers lines 199-200 (fill timestamp) and 210-211 (log DITAMBAHKAN, not DIAKTIFKAN_KEMBALI).

        The DB has NOT NULL on timestamp, so we mock TiketPIC.objects.filter to return
        a fake object with active=True and timestamp=None to exercise the legacy-data branch.

        Root cause of previous failure: pic_user must be in 'user_p3de' group because
        PICForm filters id_user queryset by group — without it the form is invalid and
        form_valid is never called.
        """
        from diamond_web.models.pic import PIC

        admin = self._create_admin()
        jdi = JenisDataILAPFactory()
        pic_user = UserFactory()
        # CRITICAL: add to 'user_p3de' so the PICForm queryset accepts this user
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        pic_user.groups.add(grp)

        # Create an active tiket so active_tikets is non-empty (triggers the loop)
        pp = PeriodePengirimanFactory()
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp)
        tiket = TiketFactory(
            id_periode_data=pd,
            status_tiket=1,
            tgl_terima_dip=datetime(2024, 1, 15),
        )

        # Fake TiketPIC: active=True (was_inactive=False), timestamp=None → lines 199-200, 210-211
        fake_tp, fake_qs = self._make_fake_tiket_pic(active=True, timestamp=None)

        real_filter = TiketPIC.objects.filter

        def side_effect_fn(*args, **kwargs):
            # Intercept only the per-tiket existing_pic lookup (has id_tiket + id_user + role)
            if kwargs.get('id_user') == pic_user and 'role' in kwargs and 'id_tiket' in kwargs:
                return fake_qs
            return real_filter(*args, **kwargs)

        client.force_login(admin)
        with patch.object(TiketPIC.objects, 'filter', side_effect=side_effect_fn):
            resp = client.post(
                reverse('pic_p3de_create'),
                {
                    'tipe': PIC.TipePIC.P3DE,
                    'id_sub_jenis_data_ilap': jdi.pk,
                    'id_user': pic_user.pk,
                    'start_date': '2024-01-01',
                    'end_date': '',
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_pic_update_reactivation_null_timestamp_lines_393_395(self, client):
        """PICUpdateView form_valid reactivation: existing TiketPIC with active=True and
        timestamp=None covers lines 393-395 (fill timestamp + filled_timestamp=True).

        Strategy: clear end_date → triggers reactivation path → for each active tiket the
        view calls TiketPIC.objects.filter(id_tiket, id_user, role).first().  We intercept
        that call and return a MagicMock with timestamp=None, exercising the null-timestamp
        branch without violating the DB NOT NULL constraint.
        """
        from diamond_web.models.pic import PIC

        admin = self._create_admin()
        jdi = JenisDataILAPFactory()
        pic_user = UserFactory()
        # For the UPDATE form, id_user is disabled (uses instance), but add group for safety
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        pic_user.groups.add(grp)

        # PIC has end_date set → original_pic.end_date is not None
        pic = PICFactory(
            tipe=PIC.TipePIC.P3DE,
            id_sub_jenis_data_ilap=jdi,
            id_user=pic_user,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        # Active tiket so active_tikets query returns results
        pp = PeriodePengirimanFactory()
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp)
        tiket = TiketFactory(
            id_periode_data=pd,
            status_tiket=1,
            tgl_terima_dip=datetime(2024, 1, 15),
        )

        # Fake TiketPIC: active=True, timestamp=None → is_reactivation=False, filled_timestamp=True
        # → lines 393-395 covered; then TiketAction.objects.create logs the change
        fake_tp, fake_qs = self._make_fake_tiket_pic(active=True, timestamp=None)

        real_filter = TiketPIC.objects.filter

        def side_effect_fn(*args, **kwargs):
            if kwargs.get('id_user') == pic_user and 'role' in kwargs and 'id_tiket' in kwargs:
                return fake_qs
            return real_filter(*args, **kwargs)

        client.force_login(admin)
        with patch.object(TiketPIC.objects, 'filter', side_effect=side_effect_fn):
            resp = client.post(
                reverse('pic_p3de_update', args=[pic.pk]),
                {
                    'tipe': PIC.TipePIC.P3DE,
                    'id_sub_jenis_data_ilap': jdi.pk,
                    'id_user': pic_user.pk,
                    'start_date': '2024-01-01',
                    'end_date': '',  # Clear end_date → reactivation path
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_pic_create_no_existing_tiket_pic_else_branch(self, client):
        """PICCreateView form_valid: no existing TiketPIC → else branch creates new TiketPIC.

        pic_user must be in 'user_p3de' group so PICForm accepts the submitted user.
        """
        from diamond_web.models.pic import PIC

        admin = self._create_admin()
        jdi = JenisDataILAPFactory()
        pic_user = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        pic_user.groups.add(grp)

        # Create an active tiket; no TiketPIC for pic_user → else branch
        pp = PeriodePengirimanFactory()
        pd = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jdi, id_periode_pengiriman=pp)
        TiketFactory(
            id_periode_data=pd,
            status_tiket=1,
            tgl_terima_dip=datetime(2024, 1, 15),
        )

        client.force_login(admin)
        resp = client.post(
            reverse('pic_p3de_create'),
            {
                'tipe': PIC.TipePIC.P3DE,
                'id_sub_jenis_data_ilap': jdi.pk,
                'id_user': pic_user.pk,
                'start_date': '2024-01-01',
                'end_date': '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
