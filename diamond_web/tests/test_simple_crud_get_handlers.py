"""Tests for GET handlers in all simple CRUD views to achieve full coverage.

Covers:
- ListView with ?deleted=1&name=... toast message
- CreateView GET (returns form, calls get_context_data)
- CreateView GET with ?ajax=1 (returns JSON html)
- UpdateView GET (returns form with instance)
- UpdateView GET with ?ajax=1
- DeleteView GET with ?ajax=1 (returns JSON html)
- DeleteView GET without ajax (renders template)
- DeleteView POST without XMLHttpRequest header (non-AJAX delete)
"""
import json
import pytest
from django.urls import reverse
from urllib.parse import quote_plus
from diamond_web.tests.conftest import (
    BentukDataFactory, CaraPenyampaianFactory, DasarHukumFactory,
    JenisTabelFactory, KanwilFactory, KPPFactory, StatusDataFactory,
    MediaBackupFactory, KategoriWilayahFactory, KlasifikasiJenisDataFactory,
    PeriodePengirimanFactory, StatusPenelitianFactory, JenisDataILAPFactory,
)


# ─── BENTUK DATA ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestBentukDataGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Test Bentuk Data')
        response = client.get(reverse('bentuk_data_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('bentuk_data_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        # POST without XMLHttpRequest header → non-AJAX delete
        response = client.post(reverse('bentuk_data_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── CARA PENYAMPAIAN ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCaraPenyampaianGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Test Cara')
        response = client.get(reverse('cara_penyampaian_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('cara_penyampaian_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('cara_penyampaian_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── DASAR HUKUM ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDasarHukumGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Test Dasar Hukum')
        response = client.get(reverse('dasar_hukum_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('dasar_hukum_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('dasar_hukum_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── JENIS TABEL ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestJenisTabelGetHandlers:

    def test_list_accessible(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_list'))
        assert response.status_code == 200

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_tabel_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('jenis_tabel_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── KANWIL ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestKanwilGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Kanwil Test')
        response = client.get(reverse('kanwil_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = KanwilFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = KanwilFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = KanwilFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = KanwilFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = KanwilFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('kanwil_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── KPP ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestKPPGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('KPP Test')
        response = client.get(reverse('kpp_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = KPPFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = KPPFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = KPPFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = KPPFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = KPPFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('kpp_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── STATUS DATA ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestStatusDataGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Status Test')
        response = client.get(reverse('status_data_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_data_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('status_data_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── MEDIA BACKUP ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMediaBackupGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Media Test')
        response = client.get(reverse('media_backup_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('media_backup_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('media_backup_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── KATEGORI WILAYAH ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestKategoriWilayahGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Wilayah Test')
        response = client.get(reverse('kategori_wilayah_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_wilayah_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('kategori_wilayah_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── KLASIFIKASI JENIS DATA ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestKlasifikasiJenisDataGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Klasifikasi Test')
        response = client.get(reverse('klasifikasi_jenis_data_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('klasifikasi_jenis_data_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('klasifikasi_jenis_data_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── PERIODE PENGIRIMAN ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPeriodePengirimanGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Periode Test')
        response = client.get(reverse('periode_pengiriman_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_update', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_ajax(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_delete', args=[obj.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('periode_pengiriman_delete', args=[obj.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('periode_pengiriman_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True


# ─── STATUS PENELITIAN ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestStatusPenelitianGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Status Penelitian Test')
        response = client.get(reverse('status_penelitian_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_penelitian_create'))
        assert response.status_code == 200

    def test_update_get(self, client, p3de_admin_user, db):
        obj = StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(reverse('status_penelitian_update', args=[obj.pk]))
        assert response.status_code == 200

    def test_data_with_search(self, client, p3de_admin_user, db):
        obj = StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_penelitian_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'search[value]': obj.deskripsi[:3],
            }
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_data_column_filter_id(self, client, p3de_admin_user, db):
        obj = StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_penelitian_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': [str(obj.pk), ''],
            }
        )
        assert response.status_code == 200

    def test_data_column_filter_deskripsi(self, client, p3de_admin_user, db):
        obj = StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_penelitian_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'columns_search[]': ['', obj.deskripsi[:3]],
            }
        )
        assert response.status_code == 200

    def test_data_ordering_desc(self, client, p3de_admin_user, db):
        StatusPenelitianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_penelitian_data'),
            {
                'draw': '1', 'start': '0', 'length': '10',
                'order[0][column]': '0',
                'order[0][dir]': 'desc',
            }
        )
        assert response.status_code == 200


# ─── ILAP VIEWS (LIST TOAST + GET HANDLERS) ─────────────────────────────────

@pytest.mark.django_db
class TestILAPGetHandlers:

    def test_list_with_delete_toast(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        name = quote_plus('Test ILAP')
        response = client.get(reverse('ilap_list'), {'deleted': '1', 'name': name})
        assert response.status_code == 200
        msgs = [str(m) for m in response.context['messages']]
        assert any('berhasil dihapus' in m for m in msgs)

    def test_create_get(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_create'))
        assert response.status_code == 200

    def test_create_get_ajax(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_create'), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_update_get(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_update', args=[ilap.pk]))
        assert response.status_code == 200

    def test_update_get_ajax(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_update', args=[ilap.pk]), {'ajax': '1'})
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'html' in data

    def test_delete_get_non_ajax(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_delete', args=[ilap.pk]))
        assert response.status_code == 200

    def test_delete_post_non_ajax(self, client, p3de_admin_user, db):
        from diamond_web.tests.conftest import ILAPFactory
        obj = ILAPFactory()
        pk = obj.pk
        client.force_login(p3de_admin_user)
        response = client.post(reverse('ilap_delete', args=[pk]))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data.get('success') is True
