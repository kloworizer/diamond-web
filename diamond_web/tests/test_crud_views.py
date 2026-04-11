"""Unit tests for CRUD views (KategoriILAP, ILAP, JenisDataILAP, etc.)."""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from urllib.parse import quote_plus
from diamond_web.models import (
    KategoriILAP, ILAP, JenisDataILAP, JenisTabel, KategoriWilayah, Kanwil, KPP,
    StatusData, DasarHukum, StatusPenelitian, BentukData, CaraPenyampaian,
    MediaBackup, KlasifikasiJenisData, PeriodePengiriman, PeriodeJenisData,
    JenisPrioritasData, PIC
)


@pytest.mark.django_db
class TestKategoriILAPViews:
    """Tests for KategoriILAP CRUD views."""

    def test_list_view_unauthenticated(self, client):
        """Test list view requires authentication."""
        response = client.get(reverse('kategori_ilap_list'), follow=False)
        assert response.status_code in [302, 403]

    def test_list_view_non_admin(self, client, authenticated_user):
        """Test list view requires admin privileges."""
        client.force_login(authenticated_user)
        response = client.get(reverse('kategori_ilap_list'), follow=False)
        assert response.status_code == 403

    def test_list_view_admin(self, client, p3de_admin_user):
        """Test list view accessible to admin."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_list'))
        assert response.status_code == 200

    def test_list_view_with_delete_message(self, client, p3de_admin_user):
        """Test list view displays delete success message."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_list'), {'deleted': '1', 'name': 'Test'})
        assert response.status_code == 200
        messages = list(response.context['messages'])
        assert len(messages) > 0
        assert 'berhasil dihapus' in str(messages[0])

    def test_list_view_with_encoded_name(self, client, p3de_admin_user):
        """Test list view decodes URL-encoded category name."""
        client.force_login(p3de_admin_user)
        encoded_name = quote_plus('Test Category Name')
        response = client.get(reverse('kategori_ilap_list'), {'deleted': '1', 'name': encoded_name})
        assert response.status_code == 200
        messages = list(response.context['messages'])
        assert any('Test Category Name' in str(msg) for msg in messages)

    def test_create_view_get(self, client, p3de_admin_user):
        """Test create view GET returns form."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_create'))
        assert response.status_code == 200
        assert 'form' in response.context

    def test_create_view_post_valid(self, client, p3de_admin_user, db):
        """Test create view POST with valid data."""
        client.force_login(p3de_admin_user)
        data = {'id_kategori': '01', 'nama_kategori': 'Test Kategori'}
        response = client.post(reverse('kategori_ilap_create'), data, follow=True)
        assert response.status_code == 200
        assert KategoriILAP.objects.filter(nama_kategori='Test Kategori').exists()

    def test_create_view_post_invalid(self, client, p3de_admin_user):
        """Test create view POST with invalid data."""
        client.force_login(p3de_admin_user)
        data = {'id_kategori': '', 'nama_kategori': ''}  # Required fields
        response = client.post(reverse('kategori_ilap_create'), data)
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors

    def test_create_view_ajax_valid(self, client, p3de_admin_user, db):
        """Test create view AJAX POST with valid data."""
        client.force_login(p3de_admin_user)
        data = {'id_kategori': '02', 'nama_kategori': 'Test Kategori AJAX'}
        response = client.post(
            reverse('kategori_ilap_create'),
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert response.status_code == 200
        result = json.loads(response.content)
        assert result['success'] is True
        assert KategoriILAP.objects.filter(nama_kategori='Test Kategori AJAX').exists()

    def test_update_view_get(self, client, p3de_admin_user, kategori_ilap):
        """Test update view GET returns form with existing data."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_update', args=[kategori_ilap.pk]))
        assert response.status_code == 200
        assert response.context['form'].instance == kategori_ilap

    def test_update_view_post_valid(self, client, p3de_admin_user, kategori_ilap):
        """Test update view POST with valid data."""
        client.force_login(p3de_admin_user)
        data = {'id_kategori': kategori_ilap.id_kategori, 'nama_kategori': 'Updated Kategori'}
        response = client.post(
            reverse('kategori_ilap_update', kwargs={'pk': kategori_ilap.pk}),
            data,
            follow=True
        )
        assert response.status_code == 200
        kategori_ilap.refresh_from_db()
        assert kategori_ilap.nama_kategori == 'Updated Kategori'

    def test_update_view_nonexistent(self, client, p3de_admin_user):
        """Test update view with non-existent object."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_update', args=[99999]), follow=False)
        assert response.status_code == 404

    def test_delete_view_get_confirmation(self, client, p3de_admin_user, kategori_ilap):
        """Test delete view GET returns confirmation."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kategori_ilap_delete', args=[kategori_ilap.pk]))
        assert response.status_code == 200
        assert kategori_ilap.nama_kategori in response.content.decode()

    def test_delete_view_get_ajax_confirmation(self, client, p3de_admin_user, kategori_ilap):
        """Test delete view GET AJAX returns confirmation HTML."""
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kategori_ilap_delete', args=[kategori_ilap.pk]),
            {'ajax': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert response.status_code == 200
        result = json.loads(response.content)
        assert 'html' in result

    def test_delete_view_post(self, client, p3de_admin_user, kategori_ilap):
        """Test delete view POST deletes object."""
        client.force_login(p3de_admin_user)
        pk = kategori_ilap.pk
        response = client.post(
            reverse('kategori_ilap_delete', args=[pk]),
            follow=True
        )
        assert response.status_code == 200
        assert not KategoriILAP.objects.filter(pk=pk).exists()

    def test_delete_view_nonexistent(self, client, p3de_admin_user):
        """Test delete view with non-existent object."""
        client.force_login(p3de_admin_user)
        response = client.post(
            reverse('kategori_ilap_delete', args=[99999]),
            follow=False
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestILAPViews:
    """Tests for ILAP CRUD views."""

    def test_ilap_list_view(self, client, p3de_admin_user):
        """Test ILAP list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('ilap_list'))
        assert response.status_code == 200

    def test_ilap_create_view(self, client, p3de_admin_user, kategori_ilap):
        """Test ILAP create view."""
        client.force_login(p3de_admin_user)
        from diamond_web.tests.conftest import KategoriWilayahFactory, KPPFactory
        wilayah = KategoriWilayahFactory()
        kpp = KPPFactory()
        data = {'id_ilap': 'ILAP0', 'id_kategori': kategori_ilap.pk, 'nama_ilap': 'Test ILAP', 'id_kategori_wilayah': wilayah.pk, 'id_kpp': kpp.pk}
        response = client.post(reverse('ilap_create'), data, follow=True)
        assert response.status_code == 200
        assert ILAP.objects.filter(nama_ilap='Test ILAP').exists()

    def test_ilap_update_view(self, client, p3de_admin_user, ilap):
        """Test ILAP update view."""
        import uuid
        client.force_login(p3de_admin_user)
        new_name = f'Updated ILAP {uuid.uuid4().hex[:8]}'
        # Only send fields that are actually editable in the form
        data = {'nama_ilap': new_name, 'id_kategori_wilayah': ilap.id_kategori_wilayah.pk}
        response = client.post(
            reverse('ilap_update', args=[ilap.pk]),
            data,
            follow=True
        )
        assert response.status_code == 200
        ilap.refresh_from_db()
        assert ilap.nama_ilap == new_name

    def test_ilap_delete_view(self, client, p3de_admin_user, ilap):
        """Test ILAP delete view."""
        client.force_login(p3de_admin_user)
        pk = ilap.pk
        response = client.post(reverse('ilap_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not ILAP.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestJenisDataILAPViews:
    """Tests for JenisDataILAP CRUD views."""

    def test_jenis_data_ilap_list_view(self, client, p3de_admin_user):
        """Test JenisDataILAP list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('jenis_data_ilap_list'))
        assert response.status_code == 200

    def test_jenis_data_ilap_create_view(self, client, p3de_admin_user, ilap):
        """Test JenisDataILAP create view."""
        client.force_login(p3de_admin_user)
        from diamond_web.tests.conftest import JenisTabelFactory, StatusDataFactory
        tabel = JenisTabelFactory()
        status = StatusDataFactory()
        data = {'id_ilap': ilap.pk, 'id_jenis_data': '0000001', 'id_sub_jenis_data': '000000001', 'nama_jenis_data': 'Test Jenis Data', 'nama_sub_jenis_data': 'Test Sub', 'nama_tabel_I': 'Table I', 'nama_tabel_U': 'Table U', 'id_jenis_tabel': tabel.pk, 'id_status_data': status.pk}
        response = client.post(reverse('jenis_data_ilap_create'), data, follow=True)
        assert response.status_code == 200
        assert JenisDataILAP.objects.filter(nama_jenis_data='Test Jenis Data').exists()

    def test_jenis_data_ilap_update_view(self, client, p3de_admin_user, jenis_data_ilap):
        """Test JenisDataILAP update view."""
        client.force_login(p3de_admin_user)
        data = {'id_ilap': jenis_data_ilap.id_ilap.pk, 'id_jenis_data': jenis_data_ilap.id_jenis_data, 'id_sub_jenis_data': jenis_data_ilap.id_sub_jenis_data, 'nama_jenis_data': 'Updated Jenis Data', 'nama_sub_jenis_data': jenis_data_ilap.nama_sub_jenis_data, 'nama_tabel_I': jenis_data_ilap.nama_tabel_I, 'nama_tabel_U': jenis_data_ilap.nama_tabel_U, 'id_jenis_tabel': jenis_data_ilap.id_jenis_tabel.pk, 'id_status_data': jenis_data_ilap.id_status_data.pk if jenis_data_ilap.id_status_data else ''}
        response = client.post(
            reverse('jenis_data_ilap_update', args=[jenis_data_ilap.pk]),
            data,
            follow=True
        )
        assert response.status_code == 200
        jenis_data_ilap.refresh_from_db()
        assert jenis_data_ilap.nama_jenis_data == 'Updated Jenis Data'

    def test_jenis_data_ilap_delete_view(self, client, p3de_admin_user, jenis_data_ilap):
        """Test JenisDataILAP delete view."""
        client.force_login(p3de_admin_user)
        pk = jenis_data_ilap.pk
        response = client.post(reverse('jenis_data_ilap_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not JenisDataILAP.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestKanwilViews:
    """Tests for Kanwil CRUD views."""

    def test_kanwil_list_view(self, client, p3de_admin_user):
        """Test Kanwil list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kanwil_list'))
        assert response.status_code == 200

    def test_kanwil_create_view(self, client, p3de_admin_user, db):
        """Test Kanwil create view."""
        client.force_login(p3de_admin_user)
        data = {'kode_kanwil': 'KWI', 'nama_kanwil': 'Test Kanwil'}
        response = client.post(reverse('kanwil_create'), data, follow=True)
        assert response.status_code == 200
        assert Kanwil.objects.filter(nama_kanwil='Test Kanwil').exists()

    def test_kanwil_update_view(self, client, p3de_admin_user, kanwil):
        """Test Kanwil update view."""
        client.force_login(p3de_admin_user)
        # Update with same kode since it's unique
        data = {'kode_kanwil': kanwil.kode_kanwil, 'nama_kanwil': 'Updated Kanwil'}
        response = client.post(
            reverse('kanwil_update', args=[kanwil.pk]),
            data,
            follow=True
        )
        assert response.status_code == 200
        kanwil.refresh_from_db()
        assert kanwil.nama_kanwil == 'Updated Kanwil'

    def test_kanwil_delete_view(self, client, p3de_admin_user, kanwil):
        """Test Kanwil delete view."""
        client.force_login(p3de_admin_user)
        pk = kanwil.pk
        response = client.post(reverse('kanwil_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not Kanwil.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestKPPViews:
    """Tests for KPP CRUD views."""

    def test_kpp_list_view(self, client, p3de_admin_user):
        """Test KPP list view."""
        client.force_login(p3de_admin_user)
        response = client.get(reverse('kpp_list'))
        assert response.status_code == 200

    def test_kpp_create_view(self, client, p3de_admin_user, kanwil):
        """Test KPP create view."""
        client.force_login(p3de_admin_user)
        data = {'kode_kpp': 'KPP', 'nama_kpp': 'Test KPP', 'id_kanwil': kanwil.pk}
        response = client.post(reverse('kpp_create'), data, follow=True)
        assert response.status_code == 200
        assert KPP.objects.filter(nama_kpp='Test KPP').exists()

    def test_kpp_update_view(self, client, p3de_admin_user, kpp):
        """Test KPP update view."""
        client.force_login(p3de_admin_user)
        data = {'kode_kpp': kpp.kode_kpp, 'nama_kpp': 'Updated KPP', 'id_kanwil': kpp.id_kanwil.pk}
        response = client.post(
            reverse('kpp_update', args=[kpp.pk]),
            data,
            follow=True
        )
        assert response.status_code == 200
        kpp.refresh_from_db()
        assert kpp.nama_kpp == 'Updated KPP'

    def test_kpp_delete_view(self, client, p3de_admin_user, kpp):
        """Test KPP delete view."""
        client.force_login(p3de_admin_user)
        pk = kpp.pk
        response = client.post(reverse('kpp_delete', args=[pk]), follow=True)
        assert response.status_code == 200
        assert not KPP.objects.filter(pk=pk).exists()
