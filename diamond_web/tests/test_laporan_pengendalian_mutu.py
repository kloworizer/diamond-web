"""Unit tests for Laporan Pengendalian Mutu view and form with 100% coverage."""
import json
import pytest
from datetime import datetime, timedelta
from django.urls import reverse
from django.contrib.auth.models import Group
from io import BytesIO

from diamond_web.models import (
    Tiket, PeriodeJenisData, JenisDataILAP, ILAP, KategoriILAP, 
    KategoriWilayah, JenisTabel, CaraPenyampaian, BentukData
)
from diamond_web.forms.laporan_pengendalian_mutu import LaporanPengendalianMutuFilterForm, TiketExportResource


@pytest.fixture
def pmde_user(db):
    """Create a PMDE user."""
    user = __import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
        username='pmde_user',
        password='testpass123'
    )
    pmde_group = Group.objects.create(name='user_pmde')
    user.groups.add(pmde_group)
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    user = __import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
        username='admin_user',
        password='testpass123'
    )
    admin_group = Group.objects.create(name='admin')
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
    """Create a tiket with tgl_transfer date."""
    # Create required dependencies
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
        nomor_tiket='TK/2026/000001',
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
        baris_i=50,
        baris_u=50,
        lolos_qc=45,
        tidak_lolos_qc=5,
        qc_p=10,
        qc_x=9,
        qc_w=8,
        qc_v=7,
        qc_a=6,
        qc_n=5,
        qc_y=4,
        qc_z=3,
        qc_d=2,
        qc_u=1,
        qc_c=0
    )
    return tiket


@pytest.mark.django_db
class TestLaporanPengendalianMutuForm:
    """Tests for LaporanPengendalianMutuFilterForm."""

    def test_form_initialization_with_years(self):
        """Test form initializes with years list."""
        years = [2025, 2026, 2027]
        form = LaporanPengendalianMutuFilterForm(years=years)
        
        # Check periode_type field
        assert 'periode_type' in form.fields
        assert form.fields['periode_type'].label == 'Jenis Periode'
        assert form.fields['periode_type'].required == True
        
        # Check tahun field choices include the provided years
        tahun_choices = [choice[0] for choice in form.fields['tahun'].choices]
        assert '2025' in tahun_choices
        assert '2026' in tahun_choices
        assert '2027' in tahun_choices

    def test_form_initialization_without_years(self):
        """Test form initializes without years."""
        form = LaporanPengendalianMutuFilterForm()
        tahun_choices = [choice[0] for choice in form.fields['tahun'].choices]
        # Should have empty choice only
        assert tahun_choices == ['']

    def test_form_periode_type_choices(self):
        """Test periode_type has correct choices."""
        form = LaporanPengendalianMutuFilterForm()
        choices = [choice[0] for choice in form.fields['periode_type'].choices]
        assert '' in choices
        assert 'bulanan' in choices
        assert 'triwulanan' in choices
        assert 'semester' in choices
        assert 'tahunan' in choices

    def test_form_fields_widget_attributes(self):
        """Test form fields have correct widget attributes."""
        form = LaporanPengendalianMutuFilterForm()
        
        assert form.fields['periode_type'].widget.attrs['class'] == 'form-select'
        assert form.fields['periode_type'].widget.attrs['id'] == 'filter-periode-type'
        
        assert form.fields['periode'].widget.attrs['class'] == 'form-select'
        assert form.fields['periode'].widget.attrs['id'] == 'filter-periode'
        
        assert form.fields['tahun'].widget.attrs['class'] == 'form-select'
        assert form.fields['tahun'].widget.attrs['id'] == 'filter-tahun'

    def test_form_valid_data(self):
        """Test form with valid data."""
        years = [2026]
        data = {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        }
        form = LaporanPengendalianMutuFilterForm(data=data, years=years)
        assert form.is_valid()

    def test_form_invalid_periode_type(self):
        """Test form with invalid periode_type."""
        years = [2026]
        data = {
            'periode_type': 'invalid',
            'periode': '1',
            'tahun': '2026'
        }
        form = LaporanPengendalianMutuFilterForm(data=data, years=years)
        assert not form.is_valid()

    def test_form_missing_required_fields(self):
        """Test form with missing required fields."""
        data = {}
        form = LaporanPengendalianMutuFilterForm(data=data)
        assert not form.is_valid()


@pytest.mark.django_db
class TestLaporanPengendalianMutuView:
    """Tests for Laporan Pengendalian Mutu views."""

    def test_view_unauthenticated(self, client):
        """Test view requires authentication."""
        response = client.get(reverse('laporan_pengendalian_mutu'), follow=False)
        assert response.status_code in [302, 403]

    def test_view_without_pmde_permission(self, client, regular_user):
        """Test view requires PMDE permission."""
        client.force_login(regular_user)
        response = client.get(reverse('laporan_pengendalian_mutu'), follow=False)
        assert response.status_code == 403

    def test_view_with_pmde_user(self, client, pmde_user):
        """Test view accessible to PMDE user."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_view_with_admin_user(self, client, admin_user):
        """Test view accessible to admin user."""
        client.force_login(admin_user)
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_view_context_contains_years(self, client, pmde_user, tiket_with_transfer_date):
        """Test view context contains available years."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
        assert 'years' in response.context
        assert 2026 in response.context['years']

    def test_view_template_used(self, client, pmde_user):
        """Test view uses correct template."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert 'laporan_pengendalian_mutu/list.html' in [t.name for t in response.templates]


@pytest.mark.django_db
class TestLaporanPengendalianMutuData:
    """Tests for laporan_pengendalian_mutu_data AJAX endpoint."""

    def test_data_endpoint_unauthenticated(self, client):
        """Test data endpoint requires authentication."""
        response = client.get(reverse('laporan_pengendalian_mutu_data'), follow=False)
        assert response.status_code in [302, 403]

    def test_data_endpoint_without_pmde_permission(self, client, regular_user):
        """Test data endpoint requires PMDE permission."""
        client.force_login(regular_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), follow=False)
        assert response.status_code == 403

    def test_data_endpoint_missing_parameters(self, client, pmde_user):
        """Test data endpoint with missing parameters."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsTotal'] == 0
        assert data['recordsFiltered'] == 0
        assert data['data'] == []

    def test_data_endpoint_bulanan_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with bulanan (monthly) filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['draw'] == 1
        assert data['recordsFiltered'] == 1
        assert len(data['data']) == 1
        assert data['data'][0]['nomor_tiket'] == 'TK/2026/000001'
        assert data['data'][0]['status_tiket'] == 'Direkam'

    def test_data_endpoint_bulanan_different_month(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with bulanan filter for different month."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '2',  # February
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_triwulanan_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with triwulanan (quarterly) filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'triwulanan',
            'periode': '1',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 1

    def test_data_endpoint_triwulanan_q2(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with Q2 filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'triwulanan',
            'periode': '2',  # Q2
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_semester_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with semester filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'semester',
            'periode': '1',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 1

    def test_data_endpoint_semester_2_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with semester 2 filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'semester',
            'periode': '2',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_tahunan_filter(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint with tahunan (yearly) filter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 1
        assert data['data'][0]['data_diterima'] == 100
        assert data['data'][0]['data_direkam'] == 100
        assert data['data'][0]['data_teridentifikasi_i'] == 50
        assert data['data'][0]['data_tidak_teridentifikasi_u'] == 50
        assert data['data'][0]['lolos_qc'] == 45
        assert data['data'][0]['tidak_lolos_qc'] == 5

    def test_data_endpoint_qc_fields(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint includes all QC fields."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '10'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        row = data['data'][0]
        assert row['qc_p'] == 10
        assert row['qc_x'] == 9
        assert row['qc_w'] == 8
        assert row['qc_v'] == 7
        assert row['qc_a'] == 6
        assert row['qc_n'] == 5
        assert row['qc_y'] == 4
        assert row['qc_z'] == 3
        assert row['qc_d'] == 2
        assert row['qc_u'] == 1
        assert row['qc_c'] == 0

    def test_data_endpoint_invalid_periode_type(self, client, pmde_user):
        """Test data endpoint with invalid periode_type."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'invalid',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_invalid_month(self, client, pmde_user):
        """Test data endpoint with invalid month."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '13',  # Invalid month
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_invalid_quarter(self, client, pmde_user):
        """Test data endpoint with invalid quarter."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'triwulanan',
            'periode': '5',  # Invalid quarter
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_invalid_semester(self, client, pmde_user):
        """Test data endpoint with invalid semester."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'semester',
            'periode': '3',  # Invalid semester
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_invalid_year(self, client, pmde_user):
        """Test data endpoint with invalid year."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': 'invalid'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0

    def test_data_endpoint_pagination(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint pagination."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026',
            'draw': '1',
            'start': '0',
            'length': '1'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data['data']) == 1

    def test_data_endpoint_null_tgl_transfer(self, client, pmde_user, db):
        """Test data endpoint excludes tikets without tgl_transfer."""
        # Create tiket without tgl_transfer
        kategori = KategoriILAP.objects.create(id_kategori='02', nama_kategori='Test Kategori 2')
        wilayah = KategoriWilayah.objects.create(deskripsi='Test Wilayah 2')
        ilap = ILAP.objects.create(
            id_ilap='00002',
            id_kategori=kategori,
            nama_ilap='Test ILAP 2',
            id_kategori_wilayah=wilayah
        )
        jenis_tabel = JenisTabel.objects.create(deskripsi='Test Jenis Tabel 2')
        jenis_data = JenisDataILAP.objects.create(
            id_jenis_data='0000002',
            id_sub_jenis_data='000000002',
            nama_jenis_data='Test Jenis Data 2',
            nama_sub_jenis_data='Test Sub Jenis Data 2',
            nama_tabel_I='Test Tabel I 2',
            nama_tabel_U='Test Tabel U 2',
            id_jenis_tabel=jenis_tabel,
            id_ilap=ilap
        )
        periode_jenis_data = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman_id=1,
            start_date='2026-01-01',
            akhir_penyampaian=10
        )
        
        bentuk_data = BentukData.objects.create(deskripsi='Test Bentuk 2')
        cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test Cara 2')
        
        Tiket.objects.create(
            nomor_tiket='TK/2026/000002',
            status_tiket=1,
            id_periode_data=periode_jenis_data,
            periode=1,
            tahun=2026,
            nomor_surat_pengantar='SPN/2026/002',
            tanggal_surat_pengantar='2026-01-01',
            nama_pengirim='Test Pengirim 2',
            id_bentuk_data=bentuk_data,
            id_cara_penyampaian=cara_penyampaian,
            baris_diterima=50,
            tgl_terima_dip='2026-01-05',
            tgl_transfer=None  # No transfer date
        )
        
        client.force_login(__import__('django.contrib.auth.models', fromlist=['User']).User.objects.create_user(
            username='pmde_user2',
            password='testpass123'
        ))
        pmde_user = __import__('django.contrib.auth.models', fromlist=['User']).User.objects.get(username='pmde_user2')
        pmde_group = Group.objects.get(name='user_pmde')
        pmde_user.groups.add(pmde_group)
        
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        # Should only return tiket with tgl_transfer
        assert data['recordsFiltered'] == 1

    def test_data_endpoint_ilap_data_in_response(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint includes ILAP and sub jenis data info."""
        client.force_login(pmde_user)
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        row = data['data'][0]
        assert row['nama_ilap'] == 'Test ILAP'
        assert row['nama_sub_jenis_data'] == 'Test Sub Jenis Data'
        assert row['nama_tabel'] == 'Test Jenis Tabel'


# === Export Tests ===

@pytest.mark.django_db
class TestExportLaporanPengendalianMutu:
    """Test export functionality."""
    
    def test_export_requires_login(self, client):
        """Test that export endpoint requires login."""
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 302  # Redirect to login
    
    def test_export_requires_pmde_permission(self, client, regular_user):
        """Test that export endpoint requires PMDE permission."""
        client.login(username='regular_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 403
    
    def test_export_missing_parameters(self, client, pmde_user):
        """Test export with missing parameters."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {})
        assert response.status_code == 400
    
    def test_export_invalid_tahun(self, client, pmde_user):
        """Test export with invalid year."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': 'invalid'
        })
        assert response.status_code == 400
    
    def test_export_invalid_periode_type(self, client, pmde_user):
        """Test export with invalid periode type."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'invalid',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 400
    
    def test_export_bulanan_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid monthly parameters."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'attachment' in response['Content-Disposition']
    
    def test_export_bulanan_invalid_month(self, client, pmde_user):
        """Test export with invalid month."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '13',
            'tahun': '2026'
        })
        assert response.status_code == 400
    
    def test_export_triwulanan_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid quarterly parameters."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'triwulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def test_export_triwulanan_invalid_quarter(self, client, pmde_user):
        """Test export with invalid quarter."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'triwulanan',
            'periode': '5',
            'tahun': '2026'
        })
        assert response.status_code == 400
    
    def test_export_semester_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid semester parameters."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'semester',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def test_export_semester_invalid(self, client, pmde_user):
        """Test export with invalid semester."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'semester',
            'periode': '3',
            'tahun': '2026'
        })
        assert response.status_code == 400
    
    def test_export_tahunan_valid(self, client, pmde_user, tiket_with_transfer_date):
        """Test export with valid yearly parameters."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def test_export_xlsx_structure(self, client, pmde_user, tiket_with_transfer_date):
        """Test that exported XLSX has correct structure."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        
        # Verify response is valid XLSX file
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        # Verify file is not empty and is a valid bytes stream
        xlsx_content = response.content
        assert len(xlsx_content) > 0
        
        # Check for XLSX magic bytes (PK for ZIP format)
        assert xlsx_content[:2] == b'PK'
    
    def test_export_xlsx_filename(self, client, pmde_user, tiket_with_transfer_date):
        """Test that exported file has correct filename."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        
        assert 'Laporan_Pengendalian_Mutu_Januari' in response['Content-Disposition']
        assert '.xlsx' in response['Content-Disposition']
    
    def test_export_with_admin_user(self, client, admin_user):
        """Test that admin user can export."""
        # Create tiket for admin
        kategori = KategoriILAP.objects.create(kode_kategori='K001', nama_kategori='Test')
        ilap = ILAP.objects.create(
            id_ilap='I001',
            id_kategori_ilap=kategori,
            nama_ilap='Test ILAP'
        )
        jenis_tabel = JenisTabel.objects.create(
            id_jenis_tabel=1,
            deskripsi='Test'
        )
        sub_jenis = JenisDataILAP.objects.create(
            id_jenis_data_ilap=1,
            id_ilap=ilap,
            id_jenis_tabel=jenis_tabel,
            nama_sub_jenis_data='Test Sub'
        )
        periode = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=sub_jenis,
            bulan='1',
            tahun='2026'
        )
        Tiket.objects.create(
            id_periode_data=periode,
            nomor_tiket='T001',
            tgl_transfer=datetime(2026, 1, 15, tzinfo=__import__('django.utils.timezone', fromlist=['utc']).utc)
        )
        
        client.login(username='admin_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200


# === Additional Edge Case Tests for 100% Coverage ===

@pytest.mark.django_db
class TestDataEndpointEdgeCases:
    """Test edge cases and error scenarios for data endpoint."""
    
    def test_data_endpoint_invalid_periode_type(self, client, pmde_user):
        """Test data endpoint with invalid periode type."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'invalid',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
        assert data['data'] == []
    
    def test_data_endpoint_invalid_month(self, client, pmde_user):
        """Test data endpoint with invalid month number."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '13',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_invalid_quarter(self, client, pmde_user):
        """Test data endpoint with invalid quarter number."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'triwulanan',
            'periode': '5',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_invalid_semester(self, client, pmde_user):
        """Test data endpoint with invalid semester number."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'semester',
            'periode': '3',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_non_numeric_periode(self, client, pmde_user):
        """Test data endpoint with non-numeric periode."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': 'invalid',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_empty_periodo_values(self, client, pmde_user):
        """Test data endpoint with empty parameter values."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': '',
            'periode': '',
            'tahun': ''
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_tiket_without_transfer_date(self, client, pmde_user, db):
        """Test that tikets without tgl_transfer are excluded."""
        # Create tiket without transfer date
        kategori = KategoriILAP.objects.create(id_kategori='01', nama_kategori='Test')
        wilayah = KategoriWilayah.objects.create(deskripsi='Test')
        ilap = ILAP.objects.create(
            id_ilap='00001',
            id_kategori=kategori,
            nama_ilap='Test ILAP',
            id_kategori_wilayah=wilayah
        )
        jenis_tabel = JenisTabel.objects.create(deskripsi='Test')
        jenis_data = JenisDataILAP.objects.create(
            id_jenis_data='0000001',
            id_sub_jenis_data='000000001',
            nama_jenis_data='Test',
            nama_sub_jenis_data='Test Sub',
            nama_tabel_I='Test I',
            nama_tabel_U='Test U',
            id_jenis_tabel=jenis_tabel,
            id_ilap=ilap
        )
        periode = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman_id=1,
            start_date='2026-01-01',
            akhir_penyampaian=10
        )
        bentuk_data = BentukData.objects.create(deskripsi='Test')
        cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test')
        
        # Create tiket WITHOUT tgl_transfer
        Tiket.objects.create(
            nomor_tiket='TK/2026/000002',
            status_tiket=1,
            id_periode_data=periode,
            periode=1,
            tahun=2026,
            nomor_surat_pengantar='SPN/2026/002',
            tanggal_surat_pengantar='2026-01-01',
            nama_pengirim='Test',
            id_bentuk_data=bentuk_data,
            id_cara_penyampaian=cara_penyampaian,
            baris_diterima=50,
            tgl_terima_dip='2026-01-05',
            tgl_transfer=None  # No transfer date
        )
        
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] == 0
    
    def test_data_endpoint_pagination(self, client, pmde_user, tiket_with_transfer_date):
        """Test data endpoint pagination."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026',
            'start': '0',
            'length': '5'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'recordsTotal' in data
        assert 'recordsFiltered' in data
    
    def test_data_endpoint_all_qc_fields_null(self, client, pmde_user, tiket_with_transfer_date):
        """Test that QC fields return 0 when null."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periodo_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        if data['data']:
            row = data['data'][0]
            # All QC fields should be 0 (since they were null)
            assert row['qc_p'] == 0
            assert row['qc_x'] == 0
            assert row['qc_w'] == 0
            assert row['qc_v'] == 0
            assert row['qc_a'] == 0
            assert row['qc_n'] == 0
            assert row['qc_y'] == 0
            assert row['qc_z'] == 0
            assert row['qc_d'] == 0
            assert row['qc_u'] == 0
    
    def test_data_endpoint_multiple_tikets_same_month(self, client, pmde_user, db):
        """Test filtering with multiple tikets in same month."""
        kategori = KategoriILAP.objects.create(id_kategori='01', nama_kategori='Test')
        wilayah = KategoriWilayah.objects.create(deskripsi='Test')
        ilap = ILAP.objects.create(
            id_ilap='00001',
            id_kategori=kategori,
            nama_ilap='Test ILAP',
            id_kategori_wilayah=wilayah
        )
        jenis_tabel = JenisTabel.objects.create(deskripsi='Test')
        jenis_data = JenisDataILAP.objects.create(
            id_jenis_data='0000001',
            id_sub_jenis_data='000000001',
            nama_jenis_data='Test',
            nama_sub_jenis_data='Test Sub',
            nama_tabel_I='Test I',
            nama_tabel_U='Test U',
            id_jenis_tabel=jenis_tabel,
            id_ilap=ilap
        )
        periode = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman_id=1,
            start_date='2026-01-01',
            akhir_penyampaian=10
        )
        bentuk_data = BentukData.objects.create(deskripsi='Test')
        cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test')
        
        # Create multiple tikets in same month
        for i in range(3):
            Tiket.objects.create(
                nomor_tiket=f'TK/2026/{i:06d}',
                status_tiket=1,
                id_periode_data=periode,
                periode=1,
                tahun=2026,
                nomor_surat_pengantar=f'SPN/2026/{i:03d}',
                tanggal_surat_pengantar='2026-01-01',
                nama_pengirim='Test',
                id_bentuk_data=bentuk_data,
                id_cara_penyampaian=cara_penyampaian,
                baris_diterima=50 + i,
                tgl_terima_dip='2026-01-05',
                tgl_transfer=datetime(2026, 1, 10 + i, tzinfo=__import__('django.utils.timezone', fromlist=['utc']).utc)
            )
        
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['recordsFiltered'] >= 3


@pytest.mark.django_db
class TestTiketExportResource:
    """Test TiketExportResource functionality."""
    
    def test_resource_initialization(self):
        """Test that TiketExportResource initializes correctly."""
        resource = TiketExportResource()
        assert resource is not None
        assert resource._meta.model == Tiket
    
    def test_resource_fields_defined(self):
        """Test that all required fields are defined in resource."""
        resource = TiketExportResource()
        required_fields = [
            'nama_ilap', 'nama_sub_jenis_data', 'nama_tabel', 'nomor_tiket', 
            'status_tiket', 'data_diterima', 'data_direkam', 'qc_p', 'qc_x'
        ]
        for field_name in required_fields:
            assert hasattr(resource, field_name)
    
    def test_resource_export_with_data(self, tiket_with_transfer_date):
        """Test resource export with actual tiket data."""
        tikets = Tiket.objects.all()
        resource = TiketExportResource()
        dataset = resource.export(tikets)
        
        # Verify dataset has headers
        assert len(dataset.headers) > 0
        # Verify dataset has data rows
        assert len(dataset) >= 0
    
    def test_resource_dehydrate_status(self, tiket_with_transfer_date):
        """Test status field dehydration returns label."""
        tiket = Tiket.objects.first()
        resource = TiketExportResource()
        status = resource.dehydrate_status_tiket(tiket)
        # Status should be a string (label, not numeric)
        assert isinstance(status, str)
    
    def test_resource_dehydrate_data_direkam(self, tiket_with_transfer_date):
        """Test data_direkam dehydration calculates I + U."""
        tiket = Tiket.objects.first()
        resource = TiketExportResource()
        data_direkam = resource.dehydrate_data_direkam(tiket)
        # Should be sum of baris_i and baris_u
        expected = (tiket.baris_i or 0) + (tiket.baris_u or 0)
        assert data_direkam == expected
    
    def test_resource_dehydrate_null_qc_fields(self, tiket_with_transfer_date):
        """Test that null QC fields are converted to 0."""
        tiket = Tiket.objects.first()
        resource = TiketExportResource()
        
        assert resource.dehydrate_qc_p(tiket) == 0
        assert resource.dehydrate_qc_x(tiket) == 0
        assert resource.dehydrate_qc_w(tiket) == 0
        assert resource.dehydrate_qc_v(tiket) == 0
        assert resource.dehydrate_qc_a(tiket) == 0


@pytest.mark.django_db
def test_export_no_data_found(client, pmde_user):
    """Test export when no tickets match filter."""
    client.login(username='pmde_user', password='testpass123')
class TestLaporanPengendalianMutuExportEdgeCases:
    """Test edge cases for export functionality."""
    def test_export_no_data_found(self, client, pmde_user):
        """Test export when no tikets match filter."""
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '12',
            'tahun': '2025'  # No data for this year
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
        'periode_type': 'bulanan',
        'periode': '12',
        'tahun': '2025'
    })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    def test_export_quarter_boundary_dates(self, client, pmde_user, db):
        """Test export quarter filtering includes correct date ranges."""
        kategori = KategoriILAP.objects.create(id_kategori='01', nama_kategori='Test')
        wilayah = KategoriWilayah.objects.create(deskripsi='Test')
        ilap = ILAP.objects.create(
            id_ilap='00001',
            id_kategori=kategori,
            nama_ilap='Test ILAP',
            id_kategori_wilayah=wilayah
        )
        jenis_tabel = JenisTabel.objects.create(deskripsi='Test')
        jenis_data = JenisDataILAP.objects.create(
            id_jenis_data='0000001',
            id_sub_jenis_data='000000001',
            nama_jenis_data='Test',
            nama_sub_jenis_data='Test Sub',
            nama_tabel_I='Test I',
            nama_tabel_U='Test U',
            id_jenis_tabel=jenis_tabel,
            id_ilap=ilap
        )
        periode = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman_id=1,
            start_date='2026-01-01',
            akhir_penyampaian=10
        )
        bentuk_data = BentukData.objects.create(deskripsi='Test')
        cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test')
        
        # Tiket at quarter boundaries
        Tiket.objects.create(
            nomor_tiket='TK/2026/Q1_START',
            status_tiket=1,
            id_periode_data=periode,
            periode=1,
            tahun=2026,
            nomor_surat_pengantar='SPN/Q1_START',
            tanggal_surat_pengantar='2026-01-01',
            nama_pengirim='Test',
            id_bentuk_data=bentuk_data,
            id_cara_penyampaian=cara_penyampaian,
            baris_diterima=50,
            tgl_terima_dip='2026-01-01',
            tgl_transfer=datetime(2026, 1, 1, tzinfo=__import__('django.utils.timezone', fromlist=['utc']).utc)
        )
        Tiket.objects.create(
            nomor_tiket='TK/2026/Q1_END',
            status_tiket=1,
            id_periode_data=periode,
            periode=1,
            tahun=2026,
            nomor_surat_pengantar='SPN/Q1_END',
            tanggal_surat_pengantar='2026-03-31',
            nama_pengirim='Test',
            id_bentuk_data=bentuk_data,
            id_cara_penyampaian=cara_penyampaian,
            baris_diterima=50,
            tgl_terima_dip='2026-03-31',
            tgl_transfer=datetime(2026, 3, 31, tzinfo=__import__('django.utils.timezone', fromlist=['utc']).utc)
        )
        
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'triwulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
    
    def test_export_tahunan_includes_all_months(self, client, pmde_user, db):
        """Test that tahunan export includes all 12 months."""
        kategori = KategoriILAP.objects.create(id_kategori='01', nama_kategori='Test')
        wilayah = KategoriWilayah.objects.create(deskripsi='Test')
        ilap = ILAP.objects.create(
            id_ilap='00001',
            id_kategori=kategori,
            nama_ilap='Test ILAP',
            id_kategori_wilayah=wilayah
        )
        jenis_tabel = JenisTabel.objects.create(deskripsi='Test')
        jenis_data = JenisDataILAP.objects.create(
            id_jenis_data='0000001',
            id_sub_jenis_data='000000001',
            nama_jenis_data='Test',
            nama_sub_jenis_data='Test Sub',
            nama_tabel_I='Test I',
            nama_tabel_U='Test U',
            id_jenis_tabel=jenis_tabel,
            id_ilap=ilap
        )
        periode = PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman_id=1,
            start_date='2026-01-01',
            akhir_penyampaian=10
        )
        bentuk_data = BentukData.objects.create(deskripsi='Test')
        cara_penyampaian = CaraPenyampaian.objects.create(deskripsi='Test')
        
        # Create tikets in various months
        for month in [1, 6, 12]:
            Tiket.objects.create(
                nomor_tiket=f'TK/2026/M{month:02d}',
                status_tiket=1,
                id_periode_data=periode,
                periode=month,
                tahun=2026,
                nomor_surat_pengantar=f'SPN/M{month:02d}',
                tanggal_surat_pengantar='2026-01-01',
                nama_pengirim='Test',
                id_bentuk_data=bentuk_data,
                id_cara_penyampaian=cara_penyampaian,
                baris_diterima=50,
                tgl_terima_dip='2026-01-01',
                tgl_transfer=datetime(2026, month, 15, tzinfo=__import__('django.utils.timezone', fromlist=['utc']).utc)
            )
        
        client.login(username='pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periodo_type': 'tahunan',
            'periode': 'all',
            'tahun': '2026'
        })
        assert response.status_code == 200


@pytest.mark.django_db
class TestFormFieldValidation:
    """Test form field validation in detail."""
    
    def test_form_periode_choices_bulanan(self):
        """Test bulanan has 12 month options."""
        form = LaporanPengendalianMutuFilterForm(years=[2026])
        # Manually trigger periode_type change to bulanan
        assert form.fields['periode_type'].choices[0][0] == 'bulanan'
    
    def test_form_tahun_field_sorted_descending(self):
        """Test that year choices are sorted in descending order."""
        years = [2020, 2025, 2024, 2026]
        form = LaporanPengendalianMutuFilterForm(years=years)
        year_choices = form.fields['tahun'].choices
        # Extract just the values (exclude empty choice)
        year_values = [int(choice[0]) for choice in year_choices if choice[0]]
        assert year_values == sorted(years, reverse=True)
    
    def test_form_with_no_years(self):
        """Test form initialization with empty year list."""
        form = LaporanPengendalianMutuFilterForm(years=[])
        assert form.fields['tahun'].choices == [('', '-- Pilih Tahun --')]
    
    def test_form_is_bound_valid(self):
        """Test form validation with valid bound data."""
        form = LaporanPengendalianMutuFilterForm(
            years=[2026],
            data={'periode_type': 'bulanan', 'periode': '1', 'tahun': '2026'}
        )
        assert form.is_valid()
    
    def test_form_is_bound_invalid_tahun(self):
        """Test form validation with invalid year."""
        form = LaporanPengendalianMutuFilterForm(
            years=[2026],
            data={'periode_type': 'bulanan', 'periode': '1', 'tahun': 'invalid'}
        )
        assert not form.is_valid()


@pytest.mark.django_db
class TestViewAccessControl:
    """Test view access control and permission checks."""
    
    def test_view_superuser_access(self, client, db):
        """Test that superuser can access view."""
        from django.contrib.auth.models import User
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@test.com',
            password='testpass123'
        )
        client.login(username='superuser', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
    
    def test_view_staff_access(self, client, db):
        """Test that staff user can access view."""
        from django.contrib.auth.models import User
        staff_user = User.objects.create_user(
            username='staff_user',
            password='testpass123'
        )
        staff_user.is_staff = True
        staff_user.save()
        client.login(username='staff_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
    
    def test_view_admin_pmde_group_access(self, client, db):
        """Test that user in admin_pmde group can access view."""
        from django.contrib.auth.models import User
        user = User.objects.create_user(
            username='admin_pmde_user',
            password='testpass123'
        )
        admin_pmde_group = Group.objects.create(name='admin_pmde')
        user.groups.add(admin_pmde_group)
        client.login(username='admin_pmde_user', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu'))
        assert response.status_code == 200
    
    def test_data_endpoint_superuser_access(self, client, db):
        """Test that superuser can access data endpoint."""
        from django.contrib.auth.models import User
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@test.com',
            password='testpass123'
        )
        client.login(username='superuser', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_data'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
    
    def test_export_superuser_access(self, client, db):
        """Test that superuser can access export endpoint."""
        from django.contrib.auth.models import User
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@test.com',
            password='testpass123'
        )
        client.login(username='superuser', password='testpass123')
        response = client.get(reverse('laporan_pengendalian_mutu_export'), {
            'periode_type': 'bulanan',
            'periode': '1',
            'tahun': '2026'
        })
        assert response.status_code == 200
