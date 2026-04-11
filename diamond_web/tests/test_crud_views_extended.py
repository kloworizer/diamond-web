"""Unit tests for additional CRUD views."""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from diamond_web.models import (
    JenisTabel, StatusData, DasarHukum, StatusPenelitian, BentukData,
    CaraPenyampaian, MediaBackup, KlasifikasiJenisData, PeriodePengiriman,
    KategoriWilayah, PeriodeJenisData, JenisPrioritasData, PIC,
    DurasiJatuhTempo
)


@pytest.mark.django_db
class TestJenisTabelViews:
    """Tests for JenisTabel CRUD views."""

    def test_jenis_tabel_list(self, client, p3de_admin_user):
        """Test JenisTabel list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_list'))
        assert response.status_code == 200

    def test_jenis_tabel_create(self, client, p3de_admin_user):
        """Test JenisTabel create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Jenis Tabel'}
        response = client.post(reverse('jenis_tabel_create'), data, follow=True)
        assert response.status_code == 200
        assert JenisTabel.objects.filter(deskripsi='Test Jenis Tabel').exists()

    def test_jenis_tabel_update(self, client, p3de_admin_user, db):
        """Test JenisTabel update view."""
        from diamond_web.tests.conftest import JenisTabelFactory
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Jenis Tabel'}
        response = client.post(reverse('jenis_tabel_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Jenis Tabel'

    def test_jenis_tabel_delete(self, client, p3de_admin_user, db):
        """Test JenisTabel delete view."""
        from diamond_web.tests.conftest import JenisTabelFactory
        obj = JenisTabelFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('jenis_tabel_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not JenisTabel.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestStatusDataViews:
    """Tests for StatusData CRUD views."""

    def test_status_data_list(self, client, p3de_admin_user):
        """Test StatusData list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_list'))
        assert response.status_code == 200

    def test_status_data_create(self, client, p3de_admin_user):
        """Test StatusData create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Status Data'}
        response = client.post(reverse('status_data_create'), data, follow=True)
        assert response.status_code == 200
        assert StatusData.objects.filter(deskripsi='Test Status Data').exists()

    def test_status_data_update(self, client, p3de_admin_user, db):
        """Test StatusData update view."""
        from diamond_web.tests.conftest import StatusDataFactory
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Status Data'}
        response = client.post(reverse('status_data_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Status Data'

    def test_status_data_delete(self, client, p3de_admin_user, db):
        """Test StatusData delete view."""
        from diamond_web.tests.conftest import StatusDataFactory
        obj = StatusDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('status_data_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not StatusData.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestDasarHukumViews:
    """Tests for DasarHukum CRUD views."""

    def test_dasar_hukum_list(self, client, p3de_admin_user):
        """Test DasarHukum list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_list'))
        assert response.status_code == 200

    def test_dasar_hukum_create(self, client, p3de_admin_user):
        """Test DasarHukum create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Dasar Hukum'}
        response = client.post(reverse('dasar_hukum_create'), data, follow=True)
        assert response.status_code == 200
        assert DasarHukum.objects.filter(deskripsi='Test Dasar Hukum').exists()

    def test_dasar_hukum_update(self, client, p3de_admin_user, db):
        """Test DasarHukum update view."""
        from diamond_web.tests.conftest import DasarHukumFactory
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Dasar Hukum'}
        response = client.post(reverse('dasar_hukum_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Dasar Hukum'

    def test_dasar_hukum_delete(self, client, p3de_admin_user, db):
        """Test DasarHukum delete view."""
        from diamond_web.tests.conftest import DasarHukumFactory
        obj = DasarHukumFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('dasar_hukum_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not DasarHukum.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestStatusPenelitianViews:
    """Tests for StatusPenelitian CRUD views."""

    def test_status_penelitian_list(self, client, p3de_admin_user):
        """Test StatusPenelitian list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_penelitian_list'))
        assert response.status_code == 200

    def test_status_penelitian_create(self, client, p3de_admin_user):
        """Test StatusPenelitian create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Status Penelitian'}
        response = client.post(reverse('status_penelitian_create'), data, follow=True)
        assert response.status_code == 200
        assert StatusPenelitian.objects.filter(deskripsi='Test Status Penelitian').exists()

    def test_status_penelitian_update(self, client, p3de_admin_user, db):
        """Test StatusPenelitian update view."""
        from diamond_web.tests.conftest import StatusPenelitianFactory
        obj = StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Status Penelitian'}
        response = client.post(reverse('status_penelitian_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Status Penelitian'

    def test_status_penelitian_delete(self, client, p3de_admin_user, db):
        """Test StatusPenelitian delete view."""
        from diamond_web.tests.conftest import StatusPenelitianFactory
        obj = StatusPenelitianFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('status_penelitian_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not StatusPenelitian.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestBentukDataViews:
    """Tests for BentukData CRUD views."""

    def test_bentuk_data_list(self, client, p3de_admin_user):
        """Test BentukData list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_list'))
        assert response.status_code == 200

    def test_bentuk_data_create(self, client, p3de_admin_user):
        """Test BentukData create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Bentuk Data'}
        response = client.post(reverse('bentuk_data_create'), data, follow=True)
        assert response.status_code == 200
        assert BentukData.objects.filter(deskripsi='Test Bentuk Data').exists()

    def test_bentuk_data_update(self, client, p3de_admin_user, db):
        """Test BentukData update view."""
        from diamond_web.tests.conftest import BentukDataFactory
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Bentuk Data'}
        response = client.post(reverse('bentuk_data_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Bentuk Data'

    def test_bentuk_data_delete(self, client, p3de_admin_user, db):
        """Test BentukData delete view."""
        from diamond_web.tests.conftest import BentukDataFactory
        obj = BentukDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('bentuk_data_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not BentukData.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestCaraPenyampaianViews:
    """Tests for CaraPenyampaian CRUD views."""

    def test_cara_penyampaian_list(self, client, p3de_admin_user):
        """Test CaraPenyampaian list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_list'))
        assert response.status_code == 200

    def test_cara_penyampaian_create(self, client, p3de_admin_user):
        """Test CaraPenyampaian create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Cara Penyampaian'}
        response = client.post(reverse('cara_penyampaian_create'), data, follow=True)
        assert response.status_code == 200
        assert CaraPenyampaian.objects.filter(deskripsi='Test Cara Penyampaian').exists()

    def test_cara_penyampaian_update(self, client, p3de_admin_user, db):
        """Test CaraPenyampaian update view."""
        from diamond_web.tests.conftest import CaraPenyampaianFactory
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Cara Penyampaian'}
        response = client.post(reverse('cara_penyampaian_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Cara Penyampaian'

    def test_cara_penyampaian_delete(self, client, p3de_admin_user, db):
        """Test CaraPenyampaian delete view."""
        from diamond_web.tests.conftest import CaraPenyampaianFactory
        obj = CaraPenyampaianFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('cara_penyampaian_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not CaraPenyampaian.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestMediaBackupViews:
    """Tests for MediaBackup CRUD views."""

    def test_media_backup_list(self, client, p3de_admin_user):
        """Test MediaBackup list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_list'))
        assert response.status_code == 200

    def test_media_backup_create(self, client, p3de_admin_user):
        """Test MediaBackup create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Media Backup'}
        response = client.post(reverse('media_backup_create'), data, follow=True)
        assert response.status_code == 200
        assert MediaBackup.objects.filter(deskripsi='Test Media Backup').exists()

    def test_media_backup_update(self, client, p3de_admin_user, db):
        """Test MediaBackup update view."""
        from diamond_web.tests.conftest import MediaBackupFactory
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Media Backup'}
        response = client.post(reverse('media_backup_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Media Backup'

    def test_media_backup_delete(self, client, p3de_admin_user, db):
        """Test MediaBackup delete view."""
        from diamond_web.tests.conftest import MediaBackupFactory
        obj = MediaBackupFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('media_backup_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not MediaBackup.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestKategoriWilayahViews:
    """Tests for KategoriWilayah CRUD views."""

    def test_kategori_wilayah_list(self, client, p3de_admin_user):
        """Test KategoriWilayah list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_list'))
        assert response.status_code == 200

    def test_kategori_wilayah_create(self, client, p3de_admin_user):
        """Test KategoriWilayah create view."""
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Test Kategori Wilayah'}
        response = client.post(reverse('kategori_wilayah_create'), data, follow=True)
        assert response.status_code == 200
        assert KategoriWilayah.objects.filter(deskripsi='Test Kategori Wilayah').exists()

    def test_kategori_wilayah_update(self, client, p3de_admin_user, db):
        """Test KategoriWilayah update view."""
        from diamond_web.tests.conftest import KategoriWilayahFactory
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        data = {'deskripsi': 'Updated Kategori Wilayah'}
        response = client.post(reverse('kategori_wilayah_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.deskripsi == 'Updated Kategori Wilayah'

    def test_kategori_wilayah_delete(self, client, p3de_admin_user, db):
        """Test KategoriWilayah delete view."""
        from diamond_web.tests.conftest import KategoriWilayahFactory
        obj = KategoriWilayahFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('kategori_wilayah_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not KategoriWilayah.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestKlasifikasiJenisDataViews:
    """Tests for KlasifikasiJenisData CRUD views."""

    def test_klasifikasi_jenis_data_list(self, client, p3de_admin_user):
        """Test KlasifikasiJenisData list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_list'))
        assert response.status_code == 200

    def test_klasifikasi_jenis_data_create(self, client, p3de_admin_user):
        """Test KlasifikasiJenisData create view."""
        from diamond_web.tests.conftest import JenisDataILAPFactory, DasarHukumFactory
        jenis_data = JenisDataILAPFactory()
        dasar_hukum = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        data = {'id_jenis_data_ilap': jenis_data.pk, 'id_klasifikasi_tabel': dasar_hukum.pk}
        response = client.post(reverse('klasifikasi_jenis_data_create'), data, follow=True)
        assert response.status_code == 200
        assert KlasifikasiJenisData.objects.filter(id_jenis_data_ilap=jenis_data).exists()

    def test_klasifikasi_jenis_data_update(self, client, p3de_admin_user, db):
        """Test KlasifikasiJenisData update view."""
        from diamond_web.tests.conftest import KlasifikasiJenisDataFactory, JenisDataILAPFactory, DasarHukumFactory
        obj = KlasifikasiJenisDataFactory()
        new_jenis_data = JenisDataILAPFactory()
        new_dasar_hukum = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        data = {'id_jenis_data_ilap': new_jenis_data.pk, 'id_klasifikasi_tabel': new_dasar_hukum.pk}
        response = client.post(reverse('klasifikasi_jenis_data_update', args=[obj.pk]), data, follow=True)
        assert response.status_code == 200
        obj.refresh_from_db()
        assert obj.id_jenis_data_ilap == new_jenis_data

    def test_klasifikasi_jenis_data_delete(self, client, p3de_admin_user, db):
        """Test KlasifikasiJenisData delete view."""
        from diamond_web.tests.conftest import KlasifikasiJenisDataFactory
        obj = KlasifikasiJenisDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('klasifikasi_jenis_data_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not KlasifikasiJenisData.objects.filter(pk=pk).exists()
