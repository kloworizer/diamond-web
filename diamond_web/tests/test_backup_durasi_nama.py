"""Tests for backup_data, durasi_jatuh_tempo, and nama_tabel views."""
import json
import pytest
from django.urls import reverse
from django.contrib.auth.models import Group

from diamond_web.models import BackupData, DurasiJatuhTempo, JenisDataILAP, TiketPIC
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory,
    JenisDataILAPFactory, DurasiJatuhTempoFactory, MediaBackupFactory,
)


# ============================================================
# BackupData Views
# ============================================================

@pytest.mark.django_db
class TestBackupDataListView:
    def test_requires_login(self, client):
        resp = client.get(reverse('backup_data_list'))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('backup_data_list'))
        assert resp.status_code in (302, 403)

    def test_p3de_user_can_access(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_list'))
        assert resp.status_code == 200

    def test_admin_can_access(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_list'))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestBackupDataData:
    """backup_data_data – server-side DataTables endpoint."""

    def test_requires_login(self, client):
        resp = client.get(reverse('backup_data_data'))
        assert resp.status_code in (302, 403)

    def test_returns_json(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data
        assert 'draw' in data

    def test_admin_sees_all_records(self, client, admin_user):
        tiket = TiketFactory()
        media = MediaBackupFactory()
        BackupData.objects.create(
            id_tiket=tiket,
            id_user=admin_user,
            id_media_backup=media,
            lokasi_backup='/mnt/backup',
        )
        client.force_login(admin_user)
        resp = client.get(reverse('backup_data_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1

    def test_p3de_user_filtered_by_pic(self, client, authenticated_user):
        """Non-admin user only sees backups for tikets where they are active P3DE PIC."""
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        BackupData.objects.create(
            id_tiket=tiket,
            id_user=authenticated_user,
            id_media_backup=media,
            lokasi_backup='/mnt/backup/user',
        )
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1

    def test_column_search(self, client, admin_user):
        """Column search filters results."""
        client.force_login(admin_user)
        resp = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': 'nonexistent_tiket'},
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestBackupDataCreateView:
    def test_requires_login(self, client):
        resp = client.get(reverse('backup_data_create'))
        assert resp.status_code in (302, 403)

    def test_get_renders_form(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_create'))
        assert resp.status_code == 200

    def test_post_creates_backup(self, client, authenticated_user):
        """Valid POST creates a BackupData record and marks tiket.backup=True."""
        tiket = TiketFactory(status_tiket=1, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_create'),
            {
                'id_tiket': tiket.pk,
                'lokasi_backup': '/mnt/backup/test',
                'nama_file': 'backup.zip',
                'id_media_backup': media.pk,
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.backup is True

    def test_ajax_post_creates_backup(self, client, authenticated_user):
        """AJAX POST returns JSON success."""
        tiket = TiketFactory(status_tiket=1, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_create'),
            {
                'id_tiket': tiket.pk,
                'lokasi_backup': '/mnt/ajax/test',
                'nama_file': 'ajax_backup.zip',
                'id_media_backup': media.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


@pytest.mark.django_db
class TestBackupDataFromTiketCreateView:
    def test_requires_login(self, client):
        tiket = TiketFactory()
        resp = client.get(reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': tiket.pk}))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        tiket = TiketFactory()
        user = UserFactory()
        client.force_login(user)
        resp = client.get(reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': tiket.pk}))
        assert resp.status_code in (302, 403)

    def test_get_renders_form(self, client, authenticated_user):
        tiket = TiketFactory()
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': tiket.pk})
        )
        assert resp.status_code == 200

    def test_post_creates_backup(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': tiket.pk}),
            {
                'lokasi_backup': '/mnt/backup/from_tiket',
                'nama_file': 'from_tiket.zip',
                'id_media_backup': media.pk,
            },
            follow=True,
        )
        assert resp.status_code == 200
        tiket.refresh_from_db()
        assert tiket.backup is True

    def test_ajax_post_creates_backup(self, client, authenticated_user):
        tiket = TiketFactory(status_tiket=1, backup=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': tiket.pk}),
            {
                'lokasi_backup': '/mnt/backup/ajax',
                'nama_file': 'ajax.zip',
                'id_media_backup': media.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


@pytest.mark.django_db
class TestBackupDataUpdateView:
    def _make_backup(self, user):
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        backup = BackupData.objects.create(
            id_tiket=tiket,
            id_user=user,
            id_media_backup=media,
            lokasi_backup='/original',
        )
        return backup, media

    def test_requires_login(self, client, db):
        backup, _ = self._make_backup(UserFactory())
        resp = client.get(reverse('backup_data_update', args=[backup.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        user = UserFactory()
        backup, _ = self._make_backup(user)
        user2 = UserFactory()  # no group
        client.force_login(user2)
        resp = client.get(reverse('backup_data_update', args=[backup.pk]))
        assert resp.status_code in (302, 403)

    def test_get_renders_form(self, client, authenticated_user):
        backup, _ = self._make_backup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_update', args=[backup.pk]))
        assert resp.status_code == 200

    def test_post_updates_backup(self, client, authenticated_user):
        backup, media = self._make_backup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_update', args=[backup.pk]),
            {
                'lokasi_backup': '/updated/path',
                'nama_file': 'updated.zip',
                'id_media_backup': media.pk,
            },
            follow=True,
        )
        assert resp.status_code == 200
        backup.refresh_from_db()
        assert backup.lokasi_backup == '/updated/path'

    def test_ajax_post_updates_backup(self, client, authenticated_user):
        backup, media = self._make_backup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_update', args=[backup.pk]),
            {
                'lokasi_backup': '/ajax/updated',
                'nama_file': 'ajax_updated.zip',
                'id_media_backup': media.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True


@pytest.mark.django_db
class TestBackupDataDeleteView:
    def _make_backup(self, user):
        tiket = TiketFactory(status_tiket=1)
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.P3DE, active=True)
        media = MediaBackupFactory()
        backup = BackupData.objects.create(
            id_tiket=tiket,
            id_user=user,
            id_media_backup=media,
            lokasi_backup='/to_delete',
        )
        return backup

    def test_requires_login(self, client, db):
        backup = self._make_backup(UserFactory())
        resp = client.post(reverse('backup_data_delete', args=[backup.pk]))
        assert resp.status_code in (302, 403)

    def test_denied_without_p3de_group(self, client, db):
        backup = self._make_backup(UserFactory())
        user = UserFactory()  # no group
        client.force_login(user)
        resp = client.post(reverse('backup_data_delete', args=[backup.pk]))
        assert resp.status_code in (302, 403)

    def test_get_renders_confirmation(self, client, authenticated_user):
        backup = self._make_backup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('backup_data_delete', args=[backup.pk]))
        assert resp.status_code == 200

    def test_ajax_get_returns_html_fragment(self, client, authenticated_user):
        backup = self._make_backup(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(
            reverse('backup_data_delete', args=[backup.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_post_deletes_backup(self, client, authenticated_user):
        backup = self._make_backup(authenticated_user)
        pk = backup.pk
        client.force_login(authenticated_user)
        resp = client.post(reverse('backup_data_delete', args=[pk]))
        assert resp.status_code == 200
        assert not BackupData.objects.filter(pk=pk).exists()

    def test_ajax_post_deletes_backup(self, client, authenticated_user):
        backup = self._make_backup(authenticated_user)
        pk = backup.pk
        client.force_login(authenticated_user)
        resp = client.post(
            reverse('backup_data_delete', args=[pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert not BackupData.objects.filter(pk=pk).exists()


# ============================================================
# DurasiJatuhTempo PIDE Views
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPIDEViews:
    """DurasiJatuhTempoPIDEListView, CreateView, UpdateView, DeleteView + data endpoint."""

    def _ensure_user_pide_group(self):
        group, _ = Group.objects.get_or_create(name='user_pide')
        return group

    def test_list_requires_login(self, client):
        resp = client.get(reverse('durasi_jatuh_tempo_pide_list'))
        assert resp.status_code in (302, 403)

    def test_list_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_list'))
        assert resp.status_code in (302, 403)

    def test_list_accessible_by_pide_admin(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_list'))
        assert resp.status_code == 200

    def test_list_delete_message_on_redirect(self, client, pide_admin_user):
        """Query params deleted+name trigger a success message."""
        client.force_login(pide_admin_user)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_list'),
            {'deleted': '1', 'name': 'Test+Durasi'},
        )
        assert resp.status_code == 200

    def test_data_endpoint_returns_json(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pide_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_create_get(self, client, pide_admin_user):
        self._ensure_user_pide_group()
        client.force_login(pide_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_create'))
        assert resp.status_code == 200

    def test_create_post(self, client, pide_admin_user):
        self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 30,
                'start_date': '2024-01-01',
                'end_date': '2024-12-31',
            },
            follow=True,
        )
        assert resp.status_code == 200
        assert DurasiJatuhTempo.objects.filter(id_sub_jenis_data=jenis).exists()

    def test_create_post_ajax(self, client, pide_admin_user):
        self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 45,
                'start_date': '2025-01-01',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_create_post_overlapping_dates_error(self, client, pide_admin_user):
        """Overlapping date range for same jenis data returns form error."""
        pide_group = self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis,
            seksi=pide_group,
            durasi=30,
            start_date='2024-01-01',
            end_date='2024-12-31',
        )
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_create'),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 15,
                'start_date': '2024-06-01',
                'end_date': '2024-09-30',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is False

    def test_update_get(self, client, pide_admin_user):
        pide_group = self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis,
            seksi=pide_group,
            durasi=30,
            start_date='2024-01-01',
        )
        client.force_login(pide_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_update', args=[durasi.pk]))
        assert resp.status_code == 200

    def test_update_post(self, client, pide_admin_user):
        pide_group = self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis,
            seksi=pide_group,
            durasi=30,
            start_date='2024-01-01',
        )
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_update', args=[durasi.pk]),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 60,
                'start_date': '2024-01-01',
            },
            follow=True,
        )
        assert resp.status_code == 200
        durasi.refresh_from_db()
        assert durasi.durasi == 60

    def test_delete_get_confirmation(self, client, pide_admin_user):
        pide_group = self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis, seksi=pide_group, durasi=30, start_date='2024-01-01'
        )
        client.force_login(pide_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pide_delete', args=[durasi.pk]))
        assert resp.status_code == 200

    def test_delete_post(self, client, pide_admin_user):
        pide_group = self._ensure_user_pide_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis, seksi=pide_group, durasi=30, start_date='2024-01-01'
        )
        pk = durasi.pk
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pide_delete', args=[pk]),
            follow=True,
        )
        assert resp.status_code == 200
        assert not DurasiJatuhTempo.objects.filter(pk=pk).exists()


# ============================================================
# DurasiJatuhTempo PMDE Views
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPMDEViews:
    """DurasiJatuhTempoPMDEListView, CreateView, UpdateView, DeleteView + data endpoint."""

    def _ensure_user_pmde_group(self):
        group, _ = Group.objects.get_or_create(name='user_pmde')
        return group

    def test_list_requires_login(self, client):
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_list'))
        assert resp.status_code in (302, 403)

    def test_list_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_list'))
        assert resp.status_code in (302, 403)

    def test_list_accessible_by_pmde_admin(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_list'))
        assert resp.status_code == 200

    def test_data_endpoint_returns_json(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(
            reverse('durasi_jatuh_tempo_pmde_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_create_get(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_create'))
        assert resp.status_code == 200

    def test_create_post(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_create'),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 25,
                'start_date': '2024-03-01',
            },
            follow=True,
        )
        assert resp.status_code == 200
        assert DurasiJatuhTempo.objects.filter(id_sub_jenis_data=jenis).exists()

    def test_create_post_ajax(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_create'),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 20,
                'start_date': '2025-03-01',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_post(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=20, start_date='2024-03-01'
        )
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_update', args=[durasi.pk]),
            {
                'id_sub_jenis_data': jenis.pk,
                'durasi': 45,
                'start_date': '2024-03-01',
            },
            follow=True,
        )
        assert resp.status_code == 200
        durasi.refresh_from_db()
        assert durasi.durasi == 45

    def test_delete_post(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        durasi = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=20, start_date='2024-03-01'
        )
        pk = durasi.pk
        client.force_login(pmde_admin_user)
        resp = client.post(
            reverse('durasi_jatuh_tempo_pmde_delete', args=[pk]),
            follow=True,
        )
        assert resp.status_code == 200
        assert not DurasiJatuhTempo.objects.filter(pk=pk).exists()


# ============================================================
# NamaTabel Views
# ============================================================

@pytest.mark.django_db
class TestNamaTabelViews:
    """NamaTabelListView, CreateView, UpdateView, DeleteView, data endpoint."""

    def test_list_requires_login(self, client):
        resp = client.get(reverse('nama_tabel_list'))
        assert resp.status_code in (302, 403)

    def test_list_denied_p3de_user(self, client, authenticated_user):
        """user_p3de cannot access the NamaTabel admin area."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('nama_tabel_list'))
        assert resp.status_code in (302, 403)

    def test_list_accessible_by_pide_admin(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('nama_tabel_list'))
        assert resp.status_code == 200

    def test_list_accessible_by_admin(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('nama_tabel_list'))
        assert resp.status_code == 200

    def test_data_endpoint_requires_admin_p3de(self, client, authenticated_user):
        """nama_tabel_data requires admin or admin_p3de group."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('nama_tabel_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code in (302, 403)

    def test_data_endpoint_returns_json(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_data_endpoint_with_records(self, client, p3de_admin_user):
        JenisDataILAPFactory()
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1

    def test_data_endpoint_column_search(self, client, p3de_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='my_table')
        client.force_login(p3de_admin_user)
        resp = client.get(
            reverse('nama_tabel_data'),
            {
                'draw': '1',
                'start': '0',
                'length': '10',
                'columns_search[]': ['', '', '', 'my_table', ''],
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsFiltered'] >= 1

    def test_create_get(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(reverse('nama_tabel_create'))
        assert resp.status_code == 200

    def test_create_post(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='', nama_tabel_U='')
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('nama_tabel_create'),
            {
                'sub_jenis': jenis.pk,
                'nama_tabel_I': 'new_table_I',
                'nama_tabel_U': 'new_table_U',
            },
            follow=True,
        )
        assert resp.status_code == 200
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == 'new_table_I'

    def test_create_post_ajax(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='', nama_tabel_U='')
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('nama_tabel_create'),
            {
                'sub_jenis': jenis.pk,
                'nama_tabel_I': 'ajax_table_I',
                'nama_tabel_U': 'ajax_table_U',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data.get('success') is True

    def test_update_get(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.get(reverse('nama_tabel_update', args=[jenis.pk]))
        assert resp.status_code == 200

    def test_update_post(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='old_I', nama_tabel_U='old_U')
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('nama_tabel_update', args=[jenis.pk]),
            {
                'nama_tabel_I': 'updated_I',
                'nama_tabel_U': 'updated_U',
            },
            follow=True,
        )
        assert resp.status_code == 200
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == 'updated_I'

    def test_delete_get_renders_confirmation(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.get(reverse('nama_tabel_delete', args=[jenis.pk]))
        assert resp.status_code == 200

    def test_delete_ajax_get_returns_html(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.get(
            reverse('nama_tabel_delete', args=[jenis.pk]),
            {'ajax': '1'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'html' in data

    def test_delete_post_clears_fields(self, client, pide_admin_user):
        """Delete clears nama_tabel_I/U fields instead of deleting the row."""
        jenis = JenisDataILAPFactory(nama_tabel_I='to_clear_I', nama_tabel_U='to_clear_U')
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('nama_tabel_delete', args=[jenis.pk]),
        )
        assert resp.status_code == 200
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == ''
        assert jenis.nama_tabel_U == ''
        # Row still exists
        assert JenisDataILAP.objects.filter(pk=jenis.pk).exists()

    def test_delete_ajax_post_returns_json(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='ajax_I')
        client.force_login(pide_admin_user)
        resp = client.post(
            reverse('nama_tabel_delete', args=[jenis.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
