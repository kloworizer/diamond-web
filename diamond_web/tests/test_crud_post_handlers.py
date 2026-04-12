"""Tests for simple CRUD view POST handlers (create/update/delete non-AJAX paths).

Covers missing lines:
- bentuk_data.py:       26-27 (list with deleted toast), 90 (no-order branch), 121-122 (non-AJAX delete)
- cara_penyampaian.py:  26-27, 90, 121-122
- dasar_hukum.py:       36-37, 116 (no-order branch), 157-158, 175-176
- jenis_tabel.py:       97 (non-AJAX delete path)
- kanwil.py:            27-28 (list toast), 96, 127 (non-AJAX delete)
- kpp.py:               27-28, 96 (no-order branch), 142-143 (non-AJAX delete)
- status_data.py:       36-37, 116, 157-158, 175-176
- media_backup.py:      26-27, 90, 121-122, 139-140
- kategori_wilayah.py:  36-37, 115, 169-170
- klasifikasi_jenis_data.py: 36-37, 116, 158, 173-174
- periode_pengiriman.py: 36-37, 116, 157, 172-173
- status_penelitian.py: 26-27, 119-120
- ilap.py:              38-39, 60-78, 115, 119, 242-244, 252
"""
import pytest
import json
from django.urls import reverse

from diamond_web.tests.conftest import UserFactory


# Shared fixture helper
def get_p3de_admin(p3de_admin_user):
    return p3de_admin_user


# ============================================================
# BentukData
# ============================================================

@pytest.mark.django_db
class TestBentukDataCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with ?deleted=true&name=X shows success toast (lines 26-27)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('bentuk_data_list'),
            {'deleted': 'true', 'name': 'TestBentuk'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET jenis_tabel_data without order[0][column] → else branch (line 90)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('bentuk_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns JSON redirect (lines 121-122)."""
        from diamond_web.models.bentuk_data import BentukData
        obj = BentukData.objects.create(deskripsi='ToDelete')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('bentuk_data_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        """AJAX POST creates BentukData."""
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('bentuk_data_create'),
            {'deskripsi': 'NewBentuk99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        """AJAX POST updates BentukData."""
        from diamond_web.models.bentuk_data import BentukData
        obj = BentukData.objects.create(deskripsi='OldName')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('bentuk_data_update', args=[obj.pk]),
            {'deskripsi': 'NewName'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# CaraPenyampaian
# ============================================================

@pytest.mark.django_db
class TestCaraPenyampaianCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('cara_penyampaian_list'),
            {'deleted': 'true', 'name': 'TestCara'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        from diamond_web.models.cara_penyampaian import CaraPenyampaian
        obj = CaraPenyampaian.objects.create(deskripsi='ToDelete')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('cara_penyampaian_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('cara_penyampaian_create'),
            {'deskripsi': 'NewCara99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.cara_penyampaian import CaraPenyampaian
        obj = CaraPenyampaian.objects.create(deskripsi='OldCara')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('cara_penyampaian_update', args=[obj.pk]),
            {'deskripsi': 'UpdatedCara'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# DasarHukum
# ============================================================

@pytest.mark.django_db
class TestDasarHukumCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('dasar_hukum_list'),
            {'deleted': 'true', 'name': 'TestDasar'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('dasar_hukum_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_redirects(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns redirect (lines 157-158 or similar)."""
        from diamond_web.models.dasar_hukum import DasarHukum
        obj = DasarHukum.objects.create(deskripsi='Test Dasar')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('dasar_hukum_delete', args=[obj.pk]))
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('dasar_hukum_create'),
            {'deskripsi': 'New DasarHukum 999'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.dasar_hukum import DasarHukum
        obj = DasarHukum.objects.create(deskripsi='Old DasarHukum')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('dasar_hukum_update', args=[obj.pk]),
            {'deskripsi': 'Updated DasarHukum'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# JenisTabel
# ============================================================

@pytest.mark.django_db
class TestJenisTabelCRUDPOST:

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX DELETE success returns JSON redirect (line 97 non-AJAX path)."""
        from diamond_web.models.jenis_tabel import JenisTabel
        obj = JenisTabel.objects.create(deskripsi='TestJT_nonajax')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('jenis_tabel_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_tabel_create'),
            {'deskripsi': 'NewJT99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.jenis_tabel import JenisTabel
        obj = JenisTabel.objects.create(deskripsi='OldJT')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('jenis_tabel_update', args=[obj.pk]),
            {'deskripsi': 'UpdatedJT'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# Kanwil
# ============================================================

@pytest.mark.django_db
class TestKanwilCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params shows toast (lines 27-28)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('kanwil_list'),
            {'deleted': 'true', 'name': 'TestKanwil'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET kanwil_data without order col → else branch (line 96)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('kanwil_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX DELETE success returns redirect (line 127)."""
        from diamond_web.models.kanwil import Kanwil
        obj = Kanwil.objects.create(kode_kanwil='K99', nama_kanwil='Test Kanwil')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('kanwil_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('kanwil_create'),
            {'kode_kanwil': 'K88', 'nama_kanwil': 'New Kanwil'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.kanwil import Kanwil
        obj = Kanwil.objects.create(kode_kanwil='K77', nama_kanwil='Old KW')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('kanwil_update', args=[obj.pk]),
            {'kode_kanwil': 'K77', 'nama_kanwil': 'Updated KW'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# KPP
# ============================================================

@pytest.mark.django_db
class TestKppCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params (lines 27-28)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('kpp_list'),
            {'deleted': 'true', 'name': 'TestKPP'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        """GET kpp_data without order col → else branch (line 96)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX DELETE success returns redirect (lines 142-143)."""
        from diamond_web.models.kanwil import Kanwil
        from diamond_web.models.kpp import KPP
        kanwil = Kanwil.objects.create(kode_kanwil='KWK', nama_kanwil='KW For KPP')
        obj = KPP.objects.create(kode_kpp='K99', nama_kpp='Test KPP', id_kanwil=kanwil)
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('kpp_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.kanwil import Kanwil
        kanwil = Kanwil.objects.create(kode_kanwil='KWN', nama_kanwil='KW New')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('kpp_create'),
            {'kode_kpp': 'K88', 'nama_kpp': 'New KPP', 'id_kanwil': kanwil.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.kanwil import Kanwil
        from diamond_web.models.kpp import KPP
        kanwil = Kanwil.objects.create(kode_kanwil='KWU', nama_kanwil='KW Upd')
        obj = KPP.objects.create(kode_kpp='K77', nama_kpp='Old KPP', id_kanwil=kanwil)
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('kpp_update', args=[obj.pk]),
            {'kode_kpp': 'K77', 'nama_kpp': 'Updated KPP', 'id_kanwil': kanwil.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True


# ============================================================
# StatusData
# ============================================================

@pytest.mark.django_db
class TestStatusDataCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('status_data_list'),
            {'deleted': 'true', 'name': 'TestStatus'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('status_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_redirects(self, client, p3de_admin_user):
        """Non-AJAX DELETE returns response (lines 157-158 or similar)."""
        from diamond_web.models.status_data import StatusData
        obj = StatusData.objects.create(deskripsi='ToDeleteSD')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('status_data_delete', args=[obj.pk]))
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('status_data_create'),
            {'deskripsi': 'NewStatusData99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.status_data import StatusData
        obj = StatusData.objects.create(deskripsi='OldSD')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('status_data_update', args=[obj.pk]),
            {'deskripsi': 'UpdatedSD'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# MediaBackup
# ============================================================

@pytest.mark.django_db
class TestMediaBackupCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('media_backup_list'),
            {'deleted': 'true', 'name': 'TestMedia'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('media_backup_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        from diamond_web.models.media_backup import MediaBackup
        obj = MediaBackup.objects.create(deskripsi='ToDeleteMB')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('media_backup_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'redirect' in data

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('media_backup_create'),
            {'deskripsi': 'NewMB99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.media_backup import MediaBackup
        obj = MediaBackup.objects.create(deskripsi='OldMB')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('media_backup_update', args=[obj.pk]),
            {'deskripsi': 'UpdatedMB'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_datatables_exception_path(self, client, p3de_admin_user):
        """Exception path returns 500 JSON (lines 139-140)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('media_backup_data'),
            {'draw': 'bad_draw'},  # not int → exception
        )
        assert resp.status_code == 500


# ============================================================
# KategoriWilayah
# ============================================================

@pytest.mark.django_db
class TestKategoriWilayahCRUDPOST:

    def test_list_with_deleted_toast(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(
            reverse('kategori_wilayah_list'),
            {'deleted': 'true', 'name': 'TestKW'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(
            reverse('kategori_wilayah_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, admin_user):
        """Non-AJAX DELETE returns response (lines 169-170)."""
        from diamond_web.models.kategori_wilayah import KategoriWilayah
        obj = KategoriWilayah.objects.create(deskripsi='Test KW Del')
        client.force_login(admin_user)
        resp = client.post(reverse('kategori_wilayah_delete', args=[obj.pk]))
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.post(
            reverse('kategori_wilayah_create'),
            {'deskripsi': 'New KategoriWilayah99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, admin_user):
        from diamond_web.models.kategori_wilayah import KategoriWilayah
        obj = KategoriWilayah.objects.create(deskripsi='Old KW Upd')
        client.force_login(admin_user)
        resp = client.post(
            reverse('kategori_wilayah_update', args=[obj.pk]),
            {'deskripsi': 'Updated KW'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# KlasifikasiJenisData
# ============================================================

@pytest.mark.django_db
class TestKlasifikasiJenisDataCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('klasifikasi_jenis_data_list'),
            {'deleted': 'true', 'name': 'TestKJD'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('klasifikasi_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def _create_kjd(self):
        """Create a KlasifikasiJenisData with required FK objects."""
        from diamond_web.models.klasifikasi_jenis_data import KlasifikasiJenisData
        from diamond_web.tests.conftest import JenisDataILAPFactory
        from diamond_web.models.dasar_hukum import DasarHukum
        jenis_data = JenisDataILAPFactory()
        tabel = DasarHukum.objects.create(deskripsi='TestTabel_KJD')
        return KlasifikasiJenisData.objects.create(
            id_jenis_data_ilap=jenis_data,
            id_klasifikasi_tabel=tabel,
        )

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX delete (lines 173-174)."""
        obj = self._create_kjd()
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('klasifikasi_jenis_data_delete', args=[obj.pk]))
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, p3de_admin_user):
        from diamond_web.tests.conftest import JenisDataILAPFactory
        from diamond_web.models.dasar_hukum import DasarHukum
        jenis_data = JenisDataILAPFactory()
        tabel = DasarHukum.objects.create(deskripsi='TabelForCreate')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('klasifikasi_jenis_data_create'),
            {'id_jenis_data_ilap': jenis_data.pk, 'id_klasifikasi_tabel': tabel.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.tests.conftest import JenisDataILAPFactory
        from diamond_web.models.dasar_hukum import DasarHukum
        obj = self._create_kjd()
        jenis_data2 = JenisDataILAPFactory()
        tabel2 = DasarHukum.objects.create(deskripsi='TabelForUpdate')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('klasifikasi_jenis_data_update', args=[obj.pk]),
            {'id_jenis_data_ilap': jenis_data2.pk, 'id_klasifikasi_tabel': tabel2.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# PeriodePengiriman
# ============================================================

@pytest.mark.django_db
class TestPeriodePengirimanCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_pengiriman_list'),
            {'deleted': 'true', 'name': 'TestPP'},
        )
        assert resp.status_code == 200

    def test_datatables_no_order_column(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('periode_pengiriman_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX delete (lines 172-173)."""
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        obj = PeriodePengiriman.objects.create(
            periode_penyampaian='TestPP_Del',
            periode_penerimaan='TestPP_Del',
        )
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('periode_pengiriman_delete', args=[obj.pk]))
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_pengiriman_create'),
            {'periode_penyampaian': 'TestPP_New99', 'periode_penerimaan': 'TestPP_New99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        obj = PeriodePengiriman.objects.create(
            periode_penyampaian='TestPP_Old',
            periode_penerimaan='TestPP_Old',
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('periode_pengiriman_update', args=[obj.pk]),
            {'periode_penyampaian': 'TestPP_Old', 'periode_penerimaan': 'TestPP_Updated'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# StatusPenelitian
# ============================================================

@pytest.mark.django_db
class TestStatusPenelitianCRUDPOST:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted toast (lines 26-27)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('status_penelitian_list'),
            {'deleted': 'true', 'name': 'TestSP'},
        )
        assert resp.status_code == 200

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX DELETE via SafeDeleteMixin → 200 JSON or 302 redirect (lines 119-120)."""
        from diamond_web.models.status_penelitian import StatusPenelitian
        obj = StatusPenelitian.objects.create(deskripsi='ToDeleteSP')
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('status_penelitian_delete', args=[obj.pk]))
        # SafeDeleteMixin returns JSON 200; views overriding delete() may redirect
        assert resp.status_code in (200, 302)

    def test_create_post_valid(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('status_penelitian_create'),
            {'deskripsi': 'NewSP99'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post_valid(self, client, p3de_admin_user):
        from diamond_web.models.status_penelitian import StatusPenelitian
        obj = StatusPenelitian.objects.create(deskripsi='OldSP')
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('status_penelitian_update', args=[obj.pk]),
            {'deskripsi': 'UpdatedSP'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


# ============================================================
# ILAP — missing lines 38-39, 60-78, 115, 119, 242-244, 252
# ============================================================

@pytest.mark.django_db
class TestILAPMissingBranches:

    def test_list_with_deleted_toast(self, client, p3de_admin_user):
        """GET list with deleted params shows toast (lines 38-39)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('ilap_list'),
            {'deleted': 'true', 'name': 'TestILAP'},
        )
        assert resp.status_code == 200

    def test_get_next_ilap_id_missing_param(self, client, p3de_admin_user):
        """Missing kategori_id → 400 (lines 60-61)."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('get_next_ilap_id'))
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert 'error' in data

    def test_get_next_ilap_id_first_entry(self, client, p3de_admin_user):
        """First entry for kategori → next_number=1 (lines 74-75)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('get_next_ilap_id'),
            {'kategori_id': 'ZZZ'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['next_id'] == 'ZZZ001'

    def test_get_next_ilap_id_existing_entry(self, client, p3de_admin_user):
        """Existing entries → increments last (lines 68-72)."""
        from diamond_web.models.ilap import ILAP
        from diamond_web.models.kategori_ilap import KategoriILAP
        from diamond_web.models.kategori_wilayah import KategoriWilayah
        kw, _ = KategoriWilayah.objects.get_or_create(
            deskripsi='ZZ KW',
        )
        ki, _ = KategoriILAP.objects.get_or_create(
            id_kategori='ZZ', defaults={'nama_kategori': 'ZZ Cat'}
        )
        ILAP.objects.get_or_create(
            id_ilap='XXX01',
            defaults={'nama_ilap': 'Existing ILAP', 'id_kategori': ki, 'id_kategori_wilayah': kw},
        )
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('get_next_ilap_id'),
            {'kategori_id': 'XXX'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['next_id'] == 'XXX002'

    def test_ilap_data_no_order_column(self, client, p3de_admin_user):
        """GET ilap_data without order col → else branch (line 115)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_ilap_data_exception_path(self, client, p3de_admin_user):
        """Exception path in ilap_data ordering → except branch (line 119)."""
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad'},
        )
        assert resp.status_code == 200  # exception caught in ordering block, returns 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_non_ajax_delete_success(self, client, p3de_admin_user):
        """Non-AJAX delete success returns redirect (lines 242-244)."""
        from diamond_web.models.ilap import ILAP
        from diamond_web.models.kategori_ilap import KategoriILAP
        from diamond_web.models.kategori_wilayah import KategoriWilayah
        kw, _ = KategoriWilayah.objects.get_or_create(
            deskripsi='DEL KW',
        )
        ki, _ = KategoriILAP.objects.get_or_create(
            id_kategori='DEL', defaults={'nama_kategori': 'DEL Cat'}
        )
        obj = ILAP.objects.create(
            id_ilap='DEL01', nama_ilap='ILAP To Delete',
            id_kategori=ki, id_kategori_wilayah=kw,
        )
        client.force_login(p3de_admin_user)
        resp = client.post(reverse('ilap_delete', args=[obj.pk]))
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_create_post_valid(self, client, p3de_admin_user):
        """AJAX POST creates ILAP (line 252 — create form_valid)."""
        from diamond_web.models.kategori_ilap import KategoriILAP
        from diamond_web.models.kategori_wilayah import KategoriWilayah
        kw, _ = KategoriWilayah.objects.get_or_create(
            deskripsi='CRE KW',
        )
        ki, _ = KategoriILAP.objects.get_or_create(
            id_kategori='CRE', defaults={'nama_kategori': 'CRE Cat'}
        )
        client.force_login(p3de_admin_user)
        resp = client.post(
            reverse('ilap_create'),
            {
                'id_ilap': 'CRE01',
                'nama_ilap': 'New ILAP',
                'id_kategori': ki.id_kategori,
                'id_kategori_wilayah': kw.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True
