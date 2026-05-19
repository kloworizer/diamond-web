"""Unit tests for Laporan Kelengkapan Data view and export."""
import json
import pytest
from datetime import datetime, timedelta
from django.urls import reverse
from django.contrib.auth.models import Group
from io import BytesIO
from openpyxl import load_workbook

from diamond_web.models import (
    Tiket, PeriodeJenisData, JenisDataILAP, ILAP, KategoriILAP, 
    KategoriWilayah, JenisTabel
)


@pytest.fixture
def pmde_user(db):
    """Create a PMDE user."""
    user = __import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
        username='pmde_user',
        password='testpass123'
    )
    pmde_group, _ = Group.objects.get_or_create(name='user_pmde')
    user.groups.add(pmde_group)
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    user = __import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
        username='admin_user',
        password='testpass123'
    )
    admin_group, _ = Group.objects.get_or_create(name='admin')
    user.groups.add(admin_group)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    return user


@pytest.fixture
def regular_user(db):
    """Create a regular user without PMDE permissions."""
    return __import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
        username='regular_user',
        password='testpass123'
    )


@pytest.fixture
def tiket_with_transfer_date(db):
    """Create a tiket with tgl_transfer date for kelengkapan testing."""
    kategori = KategoriILAP.objects.create(id_kategori='01', nama_kategori='Test Kategori')
    wilayah = KategoriWilayah.objects.create(deskripsi='Test Wilayah')
    ilap = ILAP.objects.create(
        id_ilap='00001',
        id_kategori=kategori,
        nama_ilap='Test ILAP',
        id_kategori_wilayah=wilayah
    )
    jenis_tabel = JenisTabel.objects.create(deskripsi='Test Jenis Tabel')
    jenis_data = JenisDataILAP.objects.create(
        id_jenis_data='0000001',
        id_sub_jenis_data='000000001',
        nama_jenis_data='Test Jenis Data',
        nama_sub_jenis_data='Test Sub Jenis Data',
        nama_tabel_I='Test Tabel I',
        nama_tabel_U='Test Tabel U',
        id_jenis_tabel=jenis_tabel,
        id_ilap=ilap
    )
    periode_jenis_data = PeriodeJenisData.objects.create(
        id_sub_jenis_data_ilap=jenis_data,
        id_periode_pengiriman_id=1,
        start_date='2026-01-01',
        akhir_penyampaian=10
    )
    
    bentuk_data = BentukData.objects.create(deskripsi='Test Bentuk')
    cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test Cara')
    
    tiket = Tiket.objects.create(
        nomor_tiket='TK/KEL/2026/001',
        status_tiket=1,
        id_periode_data=periode_jenis_data,
        periode=1,
        tahun=2026,
        nomor_surat_pengantar='SPN/2026/001',
        tanggal_surat_pengantar='2026-01-01',
        nama_pengirim='Test Pengirim',
        id_bentuk_data=bentuk_data,
        id_cara_penyampaian=cara_penyampaian,
        baris_diterima=100,
        tgl_terima_dip='2026-01-05',
        tgl_transfer=datetime(2026, 1, 15, 10, 0, 0),
        qc_c=10
    )
    return tiket


@pytest.mark.django_db
class TestLaporanKelengkapanDataForm:
    """Tests for LaporanKelengkapanDataFilterForm."""

    def test_form_initialization_with_years(self):
        """Test form initializes with years list."""
        years = [2025, 2026]
        form = LaporanKelengkapanDataFilterForm(years=years)
        assert 'periode_type' in form.fields
        tahun_choices = [choice[0] for choice in form.fields['tahun'].choices]
        assert '2025' in tahun_choices
        assert '2026' in tahun_choices

    def test_form_valid_data(self):
        """Test form with valid data."""
        years = [2026]
        data = {'periode_type': 'bulanan', 'periode': '1', 'tahun': '2026'}
        form = LaporanKelengkapanDataFilterForm(data=data, years=years)
        assert form.is_valid()

    def test_form_invalid_periode_type(self):
        """Test form with invalid periode_type."""
        data = {'periode_type': 'invalid', 'periode': '1', 'tahun': '2026'}
        form = LaporanKelengkapanDataFilterForm(data=data)
        assert not form.is_valid()


@pytest.mark.django_db
class TestLaporanKelengkapanDataView:
    """Tests for Laporan Kelengkapan Data views."""

    def test_view_unauthenticated(self, client):
        """Test view requires authentication."""
        response = client.get(reverse('laporan_kelengkapan_data'), follow=False)
        assert response.status_code in [302, 403]

    def test_view_with_pmde_user(self, client, pmde_user):
        """Test view accessible to PMDE user."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_kelengkapan_data'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_view_with_admin_user(self, client, admin_user):
        """Test view accessible to admin user."""
        client.force_login(admin_user)
        response = client.get(reverse('laporan_kelengkapan_data'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestLaporanKelengkapanDataData:
    """Tests for laporan_kelengkapan_data_data AJAX endpoint."""

    def test_data_endpoint_bulanan_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with bulanan (monthly) filter."""
        client.force_login(pmde_user)
        response = client.post(reverse('laporan_kelengkapan_data_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 1
        assert data['data'][0]['nomor_tiket'] == 'TK/KEL/2026/001'
        assert data['data'][0]['qc_c'] == 10

    def test_data_endpoint_triwulanan_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with triwulanan filter."""
        client.force_login(pmde_user)
        response = client.post(reverse('laporan_kelengkapan_data_data'), {
            'periode_type': 'triwulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 1


@pytest.mark.django_db
class TestExportLaporanKelengkapanData:
    """Test export functionality for Laporan Kelengkapan Data."""

    def test_export_bulanan_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid monthly parameters."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_kelengkapan_data_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'attachment' in response['Content-Disposition']
        assert 'Januari' in response['Content-Disposition']

    def test_export_tahunan_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid yearly parameters."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_kelengkapan_data_export'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert 'Tahun_2026' in response['Content-Disposition']


@pytest.mark.django_db
class TestKelengkapanDataEndpointEdgeCases:
    """Test edge cases and error scenarios for Kelengkapan Data endpoint."""

    def test_data_endpoint_invalid_periode_type(self, client, pmde_user):
        client.force_login(pmde_user)
        response = client.post(reverse('laporan_kelengkapan_data_data'), {
            'periode_type': 'invalid',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_missing_params(self, client, pmde_user):
        client.force_login(pmde_user)
        response = client.post(reverse('laporan_kelengkapan_data_data'), {})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'error' in data


@pytest.mark.django_db
class TestKelengkapanTiketExportResource:
    """Test TiketExportResource functionality for Laporan Kelengkapan Data."""

    def test_resource_initialization(self):
        resource = TiketExportResource()
        assert resource is not None
        assert resource._meta.model == Tiket

    def test_resource_dehydrate_qc_c(self, tiket_with_transfer_date):
        resource = TiketExportResource()
        assert resource.dehydrate_qc_c(tiket_with_transfer_date) == 10
        
        tiket_with_transfer_date.qc_c = None
        assert resource.dehydrate_qc_c(tiket_with_transfer_date) == 0

    def test_resource_dehydrate_data_diterima(self, tiket_with_transfer_date):
        resource = TiketExportResource()
        assert resource.dehydrate_data_diterima(tiket_with_transfer_date) == 100


@pytest.mark.django_db
class TestLaporanKelengkapanDataExportEdgeCases:
    """Test edge cases for export functionality."""

    def test_export_no_data_found(self, client, pmde_user):
        """Test export when no tikets match filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_kelengkapan_data_export'), {
            'periode_type': 'bulanan',
            'periode': '12',
            'tahun': '2025'  # No data for this year
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    def test_export_invalid_month(self, client, pmde_user):
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_kelengkapan_data_export'), {
            'periode_type': 'bulanan',
            'periode': '13',
            'tahun': '2026'
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestFormFieldValidation:
    """Test form field validation details."""

    def test_form_tahun_field_choices(self):
        years = [2020, 2021]
        form = LaporanKelengkapanDataFilterForm(years=years)
        year_choices = [c[0] for c in form.fields['tahun'].choices if c[0]]
        assert '2020' in year_choices
        assert '2021' in year_choices


@pytest.mark.django_db
class TestViewAccessControl:
    """Test view access control and permission checks."""

    def test_view_regular_user_access_denied(self, client, regular_user):
        client.force_login(regular_user)
        response = client.get(reverse('laporan_kelengkapan_data'))
        assert response.status_code == 403

    def test_data_endpoint_pmde_access_granted(self, client, pmde_user):
        client.force_login(pmde_user)
        response = client.post(reverse('laporan_kelengkapan_data_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
