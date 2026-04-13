"""Unit tests for Laporan Pengendalian Mutu view and form with 100% coverage."""
import json
import pytest
from datetime import datetime, timedelta
from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models import (
    Tiket, PeriodeJenisData, JenisDataILAP, ILAP, KategoriILAP, 
    KategoriWilayah, JenisTabel, CaraPenyampaian, BentukData
)
from diamond_web.forms.laporan_pengendalian_mutu import LaporanPengendalianMutuFilterForm


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
