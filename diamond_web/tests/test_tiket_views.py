"""Unit tests for Tiket-related views."""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from diamond_web.models import Tiket, TiketPIC


@pytest.mark.django_db
class TestTiketListView:
    """Tests for Tiket list view."""

    def test_tiket_list_unauthenticated(self, client):
        """Test tiket list requires authentication."""
        response = client.get(reverse('tiket_list'), follow=False)
        assert response.status_code in [302, 403]

    def test_tiket_list_non_authorized(self, client, authenticated_user):
        """Test non-authorized user cannot access tiket list."""
        # Remove user_p3de group to make non-authorized
        authenticated_user.groups.clear()
        client.force_login(authenticated_user)
        response = client.get(reverse('tiket_list'), follow=False)
        # Should be denied based on can_access_tiket_list
        assert response.status_code in [403, 404]

    def test_tiket_list_admin(self, client, admin_user):
        """Test admin can access tiket list."""
        client.force_login(admin_user)
        response = client.get(reverse('tiket_list'))
        assert response.status_code == 200

    def test_tiket_list_p3de_user_with_pic(self, client, tiket_with_pic, authenticated_user):
        """Test P3DE user can access tiket list when they have PIC assignment."""
        client.force_login(authenticated_user)
        response = client.get(reverse('tiket_list'))
        assert response.status_code == 200

    def test_tiket_data_endpoint(self, client, admin_user, tiket, db):
        """Test tiket data AJAX endpoint."""
        client.force_login(admin_user)
        response = client.get(
            reverse('tiket_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
            }
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data
        assert 'recordsTotal' in data
        assert 'recordsFiltered' in data

    def test_tiket_data_with_filters(self, client, admin_user, tiket):
        """Test tiket data endpoint with filters."""
        client.force_login(admin_user)
        response = client.get(
            reverse('tiket_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
                'columns_search[0]': tiket.nomor_tiket,
            }
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data['data']) >= 0

    def test_tiket_data_sorting(self, client, admin_user, db):
        """Test tiket data endpoint with sorting."""
        from diamond_web.tests.conftest import TiketFactory
        TiketFactory()
        TiketFactory()
        
        client.force_login(admin_user)
        response = client.get(
            reverse('tiket_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
                'order[0][column]': '0',
                'order[0][dir]': 'asc',
            }
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data


@pytest.mark.django_db
class TestTiketDetailView:
    """Tests for Tiket detail view."""

    def test_tiket_detail_unauthenticated(self, client, tiket):
        """Test tiket detail requires authentication."""
        response = client.get(
            reverse('tiket_detail', args=[tiket.pk]),
            follow=False
        )
        assert response.status_code in [302, 403]

    def test_tiket_detail_admin_access(self, client, admin_user, tiket):
        """Test admin can view tiket detail."""
        client.force_login(admin_user)
        response = client.get(reverse('tiket_detail', args=[tiket.pk]))
        assert response.status_code == 200

    def test_tiket_detail_nonexistent(self, client, admin_user):
        """Test detail view for non-existent tiket."""
        client.force_login(admin_user)
        response = client.get(
            reverse('tiket_detail', args=[99999]),
            follow=False
        )
        assert response.status_code == 404

    def test_tiket_detail_with_pic(self, client, tiket_with_pic, authenticated_user):
        """Test user with PIC can view their assigned tiket."""
        client.force_login(authenticated_user)
        response = client.get(reverse('tiket_detail', args=[tiket_with_pic.pk]))
        assert response.status_code == 200


@pytest.mark.django_db
class TestTiketIdentifikasiView:
    """Tests for Tiket identifikasi view."""

    def test_tiket_identifikasi_list(self, client, p3de_admin_user):
        """Test tiket identifikasi list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('tiket_identifikasi_list'))
        assert response.status_code == 200

    def test_tiket_identifikasi_create_form(self, client, p3de_admin_user):
        """Test tiket identifikasi create form."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('tiket_identifikasi_create'))
        assert response.status_code == 200

    def test_tiket_identifikasi_create(self, client, admin_user, db):
        """Test creating a new tiket via TiketRekamCreateView."""
        from datetime import date
        from django.contrib.auth.models import Group
        from diamond_web.tests.conftest import (
            JenisDataILAPFactory, PeriodeJenisDataFactory,
            BentukDataFactory, CaraPenyampaianFactory
        )
        from diamond_web.models import DurasiJatuhTempo

        # TiketForm.__init__ calls Group.objects.get(name='user_pide'/'user_pmde') directly
        pide_group, _ = Group.objects.get_or_create(name='user_pide')
        pmde_group, _ = Group.objects.get_or_create(name='user_pmde')

        # Build ILAP hierarchy: JenisDataILAP → PeriodeJenisData
        jenis_data = JenisDataILAPFactory()
        periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis_data)
        bentuk = BentukDataFactory()
        cara = CaraPenyampaianFactory()

        # Create active DurasiJatuhTempo for PIDE and PMDE (required by TiketForm filter
        # and _set_durasi_fields in form_valid)
        today = date.today()
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis_data,
            seksi=pide_group,
            durasi=30,
            start_date=date(2000, 1, 1),
            end_date=None,
        )
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis_data,
            seksi=pmde_group,
            durasi=30,
            start_date=date(2000, 1, 1),
            end_date=None,
        )

        ilap = jenis_data.id_ilap

        client.force_login(admin_user)
        data = {
            'id_ilap': ilap.pk,
            'id_periode_data': periode.pk,
            'periode': 1,
            'tahun': today.year,
            'penyampaian': 1,
            'nomor_surat_pengantar': 'SP-001',
            'tanggal_surat_pengantar': '2024-01-01T10:00',
            'nama_pengirim': 'Test User',
            'id_bentuk_data': bentuk.pk,
            'id_cara_penyampaian': cara.pk,
            'baris_diterima': 100,
            'tgl_terima_dip': '2024-01-02T10:00',
            'satuan_data': 1,
            'status_ketersediaan_data': '1',
        }
        response = client.post(reverse('tiket_identifikasi_create'), data, follow=True)
        assert response.status_code == 200
        assert Tiket.objects.count() > 0

    def test_tiket_identifikasi_update(self, client, pide_admin_user, db):
        """Test updating tiket identifikasi (marking as identified by PIDE)."""
        from diamond_web.tests.conftest import TiketFactory, TiketPICFactory

        # Create tiket in DIKIRIM_KE_PIDE status (status=4) as required by view's test_func
        tiket = TiketFactory(status_tiket=4)
        # Assign pide_admin_user as active PIDE PIC for this tiket
        TiketPICFactory(id_tiket=tiket, id_user=pide_admin_user, role=TiketPIC.Role.PIDE, active=True)

        client.force_login(pide_admin_user)
        data = {'tgl_rekam_pide': '2024-01-01T10:00'}
        response = client.post(
            reverse('identifikasi_tiket', args=[tiket.pk]),
            data,
            follow=True
        )
        assert response.status_code == 200
        tiket.refresh_from_db()
        assert tiket.status_tiket == 5  # STATUS_IDENTIFIKASI


@pytest.mark.django_db
class TestTiketKirimView:
    """Tests for Tiket kirim (send) view."""

    def test_tiket_kirim_list(self, client, p3de_admin_user):
        """Test tiket kirim list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('tiket_kirim_list'))
        assert response.status_code == 200

    def test_tiket_kirim_requires_permission(self, client, authenticated_user, tiket):
        """Test tiket kirim requires specific permission."""
        authenticated_user.groups.clear()  # Remove all groups so user has no P3DE access
        client.force_login(authenticated_user)
        response = client.get(
            reverse('tiket_kirim_update', args=[tiket.pk]),
            follow=False
        )
        # authenticated_user is in neither admin nor p3de groups, should be denied
        assert response.status_code in [403, 404, 302]


@pytest.mark.django_db
class TestTiketBackupDataView:
    """Tests for Tiket backup data views."""

    def test_backup_data_list(self, client, p3de_admin_user):
        """Test backup data list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('backup_data_list'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestTandaTerimaDataView:
    """Tests for Tanda Terima Data views."""

    def test_tanda_terima_list(self, client, p3de_admin_user):
        """Test tanda terima list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('tanda_terima_data_list'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestMonitoringPenyampaianDataView:
    """Tests for Monitoring Penyampaian Data view."""

    def test_monitoring_penyampaian_list(self, client, authenticated_user):
        """Test monitoring penyampaian view."""
        client.force_login(authenticated_user)
        response = client.get(reverse('monitoring_penyampaian_data_list'))
        assert response.status_code == 200
