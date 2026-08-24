"""Tests for backup_data, durasi_jatuh_tempo, and nama_tabel views."""
import json
import pytest
from datetime import date
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Group

from diamond_web.models import BackupData, DurasiJatuhTempo, JenisDataILAP, Tiket, TiketPIC
from diamond_web.views.durasi_jatuh_tempo import GENERATE_PMDE_START_YEAR
from diamond_web.tests.conftest import (
    TiketFactory, TiketPICFactory, UserFactory,
    JenisDataILAPFactory, DurasiJatuhTempoFactory, MediaBackupFactory,
    JenisPrioritasDataFactory, PeriodeJenisDataFactory,
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

    def test_generate_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code in (302, 403)

    def test_generate_requires_post(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 405

    def test_generate_preview_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_generate_preview'))
        assert resp.status_code in (302, 403)

    def test_generate_preview_summarises_without_inserting(self, client, pmde_admin_user):
        from django.utils import timezone
        """The preview reports what would be written and saves nothing."""
        self._ensure_user_pmde_group()
        prioritas = JenisDataILAPFactory()
        biasa = JenisDataILAPFactory()
        current_year = timezone.now().date().year
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=prioritas, tahun=str(current_year),
            start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31),
        )
        years = list(range(GENERATE_PMDE_START_YEAR, current_year + 1))

        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_generate_preview'))
        assert resp.status_code == 200
        payload = json.loads(resp.content)
        assert payload['success'] is True
        assert payload['tahun_awal'] == GENERATE_PMDE_START_YEAR
        assert payload['tahun_akhir'] == current_year
        assert payload['total_jenis_data'] == 2
        assert payload['total_rows'] == 2 * len(years)
        # Only the 2024 row of the prioritas Sub Jenis Data is prioritas
        assert payload['baris_prioritas'] == 1
        assert payload['baris_non_prioritas'] == 2 * len(years) - 1

        by_kode = {item['id_sub_jenis_data']: item for item in payload['items']}
        durasi_per_periode = {
            baris['periode']: baris['durasi']
            for baris in by_kode[prioritas.id_sub_jenis_data]['baris']
        }
        assert durasi_per_periode['01-01-2024 s.d. 31-12-2024'] == 45
        assert durasi_per_periode['01-01-2023 s.d. 31-12-2023'] == 85
        assert by_kode[biasa.id_sub_jenis_data]['jumlah_baris'] == len(years)
        assert by_kode[biasa.id_sub_jenis_data]['baris'][0] == {
            'periode': f'01-01-{GENERATE_PMDE_START_YEAR} s.d. 31-12-{GENERATE_PMDE_START_YEAR}',
            'durasi': 85,
            'is_prioritas': False,
        }

        # Nothing was written
        assert not DurasiJatuhTempo.objects.filter(seksi__name='user_pmde').exists()

    def test_generate_preview_matches_generate_result(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        JenisDataILAPFactory()
        JenisDataILAPFactory()
        client.force_login(pmde_admin_user)

        preview = json.loads(client.get(reverse('durasi_jatuh_tempo_pmde_generate_preview')).content)
        result = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_generate')).content)
        assert result['created'] == preview['total_rows']
        assert result['jenis_data'] == preview['total_jenis_data']

    def test_generate_preview_empty_when_nothing_to_do(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        client.force_login(pmde_admin_user)
        payload = json.loads(client.get(reverse('durasi_jatuh_tempo_pmde_generate_preview')).content)
        assert payload['total_rows'] == 0
        assert payload['items'] == []

    def test_generate_creates_one_row_per_year(self, client, pmde_admin_user):
        """Non-prioritas Sub Jenis Data get durasi 85 for every generated year."""
        self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        current_year = timezone.now().date().year
        years = list(range(GENERATE_PMDE_START_YEAR, current_year + 1))

        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200
        payload = json.loads(resp.content)
        assert payload['success'] is True
        assert payload['created'] == len(years)

        rows = DurasiJatuhTempo.objects.filter(
            id_sub_jenis_data=jenis, seksi__name='user_pmde'
        ).order_by('start_date')
        assert [r.start_date for r in rows] == [date(y, 1, 1) for y in years]
        assert [r.end_date for r in rows] == [date(y, 12, 31) for y in years]
        assert {r.durasi for r in rows} == {85}
        assert rows[0].create_by == pmde_admin_user.username[:9]

    def test_generate_uses_45_for_a_prioritas_that_never_ends(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        prioritas = JenisDataILAPFactory()
        biasa = JenisDataILAPFactory()
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=prioritas, tahun=str(GENERATE_PMDE_START_YEAR),
            start_date=date(GENERATE_PMDE_START_YEAR, 1, 1), end_date=None,
        )

        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200
        assert {
            r.durasi for r in DurasiJatuhTempo.objects.filter(id_sub_jenis_data=prioritas)
        } == {45}
        assert {
            r.durasi for r in DurasiJatuhTempo.objects.filter(id_sub_jenis_data=biasa)
        } == {85}

    def test_generate_applies_prioritas_only_to_the_years_it_covers(self, client, pmde_admin_user):
        """Prioritas is a period, so only the years it overlaps get durasi 45."""
        self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis, tahun='2023',
            start_date=date(2023, 1, 1), end_date=date(2023, 12, 31),
        )
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis, tahun='2025',
            start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        )

        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200

        durasi_per_year = {
            r.start_date.year: r.durasi
            for r in DurasiJatuhTempo.objects.filter(id_sub_jenis_data=jenis, seksi__name='user_pmde')
        }
        assert durasi_per_year[2023] == 45
        assert durasi_per_year[2025] == 45
        assert durasi_per_year[2024] == 85
        assert durasi_per_year[GENERATE_PMDE_START_YEAR] == 85

    def test_generate_fills_only_the_years_an_existing_row_leaves_open(self, client, pmde_admin_user):
        """An open-ended row from 2023 covers 2023 onwards; earlier years are added."""
        pmde_group = self._ensure_user_pmde_group()
        sudah_ada = JenisDataILAPFactory()
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sudah_ada, seksi=pmde_group, durasi=30, start_date='2023-05-01'
        )
        missing_years = list(range(GENERATE_PMDE_START_YEAR, 2023))

        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['created'] == len(missing_years)

        rows = DurasiJatuhTempo.objects.filter(
            id_sub_jenis_data=sudah_ada, seksi=pmde_group
        ).order_by('start_date')
        assert [r.start_date for r in rows] == (
            [date(y, 1, 1) for y in missing_years] + [date(2023, 5, 1)]
        )

    def test_generate_skips_a_jenis_data_whose_years_are_all_covered(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        sudah_ada = JenisDataILAPFactory()
        DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sudah_ada, seksi=pmde_group, durasi=30,
            start_date=date(GENERATE_PMDE_START_YEAR, 1, 1),
        )
        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200
        assert json.loads(resp.content)['created'] == 0
        assert DurasiJatuhTempo.objects.filter(id_sub_jenis_data=sudah_ada).count() == 1

    def test_generate_is_idempotent_and_never_overlaps(self, client, pmde_admin_user):
        """Running twice writes nothing new and leaves no overlapping ranges."""
        self._ensure_user_pmde_group()
        JenisDataILAPFactory()
        client.force_login(pmde_admin_user)

        first = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_generate')).content)
        second = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_generate')).content)
        assert first['created'] > 0
        assert second['created'] == 0

        rows = list(DurasiJatuhTempo.objects.filter(seksi__name='user_pmde').order_by('start_date'))
        assert len({(r.id_sub_jenis_data_id, r.start_date, r.end_date) for r in rows}) == len(rows)
        for earlier, later in zip(rows, rows[1:]):
            assert earlier.end_date < later.start_date

    def test_generate_reports_when_nothing_to_do(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 200
        payload = json.loads(resp.content)
        assert payload['created'] == 0
        assert 'Tidak ada Jenis Data' in payload['message']

    def test_generate_without_pmde_group_returns_error(self, client, pmde_admin_user):
        Group.objects.filter(name='user_pmde').delete()
        JenisDataILAPFactory()
        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        assert resp.status_code == 400
        assert json.loads(resp.content)['success'] is False


# ============================================================
# Durasi Jatuh Tempo PMDE - prioritas sync (step 2 of Generate Otomatis)
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPMDEPrioritasSync:
    """durasi_jatuh_tempo_pmde_prioritas_sync(_preview) endpoints."""

    def _ensure_user_pmde_group(self):
        group, _ = Group.objects.get_or_create(name='user_pmde')
        return group

    def _durasi(self, jenis, seksi, durasi, year=2024):
        return DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=seksi, durasi=durasi,
            start_date=date(year, 1, 1), end_date=date(year, 12, 31),
        )

    def _prioritas(self, jenis, year=2024):
        """Mark `jenis` prioritas for one calendar year, the way an ND does."""
        return JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=jenis, tahun=str(year),
            start_date=date(year, 1, 1), end_date=date(year, 12, 31),
        )

    def test_sync_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))
        assert resp.status_code in (302, 403)

    def test_sync_requires_post(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))
        assert resp.status_code == 405

    def test_preview_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_prioritas_sync_preview'))
        assert resp.status_code in (302, 403)

    def test_preview_summarises_without_writing(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        self._prioritas(jenis, 2024)
        row = self._durasi(jenis, pmde_group, 85, 2024)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.get(reverse('durasi_jatuh_tempo_pmde_prioritas_sync_preview')).content)
        assert payload['success'] is True
        assert payload['total_rows'] == 1
        assert payload['total_jenis_data'] == 1
        assert payload['baris_ke_prioritas'] == 1
        assert payload['baris_ke_non_prioritas'] == 0
        assert payload['items'][0]['baris'] == [{
            'periode': '01-01-2024 s.d. 31-12-2024',
            'durasi_lama': 85,
            'durasi_baru': 45,
            'is_prioritas': True,
        }]

        row.refresh_from_db()
        assert row.durasi == 85

    def test_sync_lowers_durasi_when_prioritas_added(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        rows = [self._durasi(jenis, pmde_group, 85, year) for year in (2023, 2024)]
        self._prioritas(jenis, 2023)
        self._prioritas(jenis, 2024)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['success'] is True
        assert payload['updated'] == 2
        assert payload['jenis_data'] == 1

        for row in rows:
            row.refresh_from_db()
            assert row.durasi == 45
        assert rows[0].update_by == pmde_admin_user.username[:9]

    def test_sync_only_touches_the_years_the_prioritas_covers(self, client, pmde_admin_user):
        """A prioritas for 2024 leaves the 2023 row of the same Sub Jenis Data at 85."""
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        row_2023 = self._durasi(jenis, pmde_group, 85, 2023)
        row_2024 = self._durasi(jenis, pmde_group, 85, 2024)
        self._prioritas(jenis, 2024)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['updated'] == 1

        row_2023.refresh_from_db()
        row_2024.refresh_from_db()
        assert row_2023.durasi == 85
        assert row_2024.durasi == 45

    def test_sync_raises_durasi_when_prioritas_deleted(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        prioritas = self._prioritas(jenis, 2024)
        row = self._durasi(jenis, pmde_group, 45, 2024)
        prioritas.delete()

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['updated'] == 1

        row.refresh_from_db()
        assert row.durasi == 85

    def test_sync_raises_durasi_when_the_prioritas_year_moves(self, client, pmde_admin_user):
        """Re-issuing the prioritas for another year flips both rows."""
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        row_2024 = self._durasi(jenis, pmde_group, 45, 2024)
        row_2025 = self._durasi(jenis, pmde_group, 85, 2025)
        self._prioritas(jenis, 2025)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['updated'] == 2

        row_2024.refresh_from_db()
        row_2025.refresh_from_db()
        assert row_2024.durasi == 85
        assert row_2025.durasi == 45

    def test_sync_leaves_a_hand_set_durasi_alone(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        self._prioritas(jenis, 2024)
        row = self._durasi(jenis, pmde_group, 30, 2024)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['updated'] == 0

        row.refresh_from_db()
        assert row.durasi == 30

    def test_sync_leaves_pide_rows_alone(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        pide_group, _ = Group.objects.get_or_create(name='user_pide')
        jenis = JenisDataILAPFactory()
        self._prioritas(jenis, 2024)
        row = self._durasi(jenis, pide_group, 85, 2024)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert payload['updated'] == 0

        row.refresh_from_db()
        assert row.durasi == 85

    def test_sync_keeps_the_row_so_tikets_follow_the_new_durasi(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        row = self._durasi(jenis, pmde_group, 85, 2024)
        tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis),
            id_durasi_jatuh_tempo_pmde=row,
        )
        self._prioritas(jenis, 2024)

        client.force_login(pmde_admin_user)
        client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde_id == row.pk
        assert tiket.id_durasi_jatuh_tempo_pmde.durasi == 45

    def test_sync_is_idempotent(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        self._prioritas(jenis, 2024)
        self._durasi(jenis, pmde_group, 85, 2024)

        client.force_login(pmde_admin_user)
        first = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        second = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync')).content)
        assert first['updated'] == 1
        assert second['updated'] == 0
        assert 'Tidak ada durasi' in second['message']

    def test_sync_after_generate_has_nothing_to_do(self, client, pmde_admin_user):
        """Generate already applies the rule, so the next step is a no-op."""
        self._ensure_user_pmde_group()
        prioritas = JenisDataILAPFactory()
        JenisDataILAPFactory()
        self._prioritas(prioritas, 2024)

        client.force_login(pmde_admin_user)
        client.post(reverse('durasi_jatuh_tempo_pmde_generate'))
        payload = json.loads(client.get(reverse('durasi_jatuh_tempo_pmde_prioritas_sync_preview')).content)
        assert payload['total_rows'] == 0

    def test_sync_without_pmde_group_returns_error(self, client, pmde_admin_user):
        Group.objects.filter(name='user_pmde').delete()
        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))
        assert resp.status_code == 400
        assert json.loads(resp.content)['success'] is False


# ============================================================
# Durasi Jatuh Tempo PMDE - Tiket backfill (step 3 of Generate Otomatis)
# ============================================================

@pytest.mark.django_db
class TestDurasiJatuhTempoPMDETiketBackfill:
    """durasi_jatuh_tempo_pmde_tiket_backfill(_preview) endpoints."""

    def _ensure_user_pmde_group(self):
        group, _ = Group.objects.get_or_create(name='user_pmde')
        return group

    def _tiket(self, jenis, **kwargs):
        """A tiket on `jenis` with no Durasi Jatuh Tempo PMDE yet."""
        return TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis),
            id_durasi_jatuh_tempo_pmde=None,
            **kwargs,
        )

    def test_backfill_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill'))
        assert resp.status_code in (302, 403)

    def test_backfill_requires_post(self, client, pmde_admin_user):
        client.force_login(pmde_admin_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_tiket_backfill'))
        assert resp.status_code == 405

    def test_preview_denied_non_admin(self, client, authenticated_user):
        client.force_login(authenticated_user)
        resp = client.get(reverse('durasi_jatuh_tempo_pmde_tiket_backfill_preview'))
        assert resp.status_code in (302, 403)

    def test_preview_summarises_without_writing(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        tiket = self._tiket(jenis, tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0))

        client.force_login(pmde_admin_user)
        payload = json.loads(client.get(reverse('durasi_jatuh_tempo_pmde_tiket_backfill_preview')).content)
        assert payload['success'] is True
        assert payload['total_tiket'] == 1
        assert payload['per_year'] == [{'tahun': 2019, 'jumlah': 1}]

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde is None

    def test_backfill_fills_from_tgl_transfer(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        durasi_2019 = DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=45,
            start_date=date(2020, 1, 1), end_date=date(2020, 12, 31),
        )
        tiket = self._tiket(jenis, tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0))

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        assert payload['success'] is True
        assert payload['updated'] == 1

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde_id == durasi_2019.pk

    def test_backfill_prefers_tgl_rematch_over_tgl_transfer(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        durasi_2020 = DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=45,
            start_date=date(2020, 1, 1), end_date=date(2020, 12, 31),
        )
        tiket = self._tiket(
            jenis,
            tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0),
            tgl_rematch=timezone.datetime(2020, 3, 1, 9, 0),
        )

        client.force_login(pmde_admin_user)
        client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill'))

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde_id == durasi_2020.pk

    def test_backfill_ignores_other_seksi(self, client, pmde_admin_user):
        self._ensure_user_pmde_group()
        pide_group, _ = Group.objects.get_or_create(name='user_pide')
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pide_group, durasi=30,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        tiket = self._tiket(jenis, tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0))

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        assert payload['updated'] == 0
        assert payload['unmatched'] == 1

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde is None

    def test_backfill_skips_tiket_without_base_date(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        tiket = self._tiket(jenis, tgl_transfer=None, tgl_rematch=None)

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        assert payload['updated'] == 0
        assert payload['tanpa_tanggal'] == 1

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde is None

    def test_backfill_never_overwrites_an_existing_value(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        sudah_terisi = DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=60,
            start_date=date(2018, 1, 1), end_date=date(2018, 12, 31),
        )
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=jenis),
            id_durasi_jatuh_tempo_pmde=sudah_terisi,
            tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0),
        )

        client.force_login(pmde_admin_user)
        payload = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        assert payload['updated'] == 0

        tiket.refresh_from_db()
        assert tiket.id_durasi_jatuh_tempo_pmde_id == sudah_terisi.pk

    def test_backfill_is_idempotent(self, client, pmde_admin_user):
        pmde_group = self._ensure_user_pmde_group()
        jenis = JenisDataILAPFactory()
        DurasiJatuhTempoFactory(
            id_sub_jenis_data=jenis, seksi=pmde_group, durasi=85,
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        self._tiket(jenis, tgl_transfer=timezone.datetime(2019, 6, 1, 9, 0))

        client.force_login(pmde_admin_user)
        first = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        second = json.loads(client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill')).content)
        assert first['updated'] == 1
        assert second['updated'] == 0
        assert 'Tidak ada Tiket' in second['message']
        assert Tiket.objects.filter(id_durasi_jatuh_tempo_pmde__isnull=True).count() == 0

    def test_backfill_without_pmde_group_returns_error(self, client, pmde_admin_user):
        Group.objects.filter(name='user_pmde').delete()
        client.force_login(pmde_admin_user)
        resp = client.post(reverse('durasi_jatuh_tempo_pmde_tiket_backfill'))
        assert resp.status_code == 400
        assert json.loads(resp.content)['success'] is False


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

    def test_data_endpoint_requires_admin_pide(self, client, authenticated_user):
        """nama_tabel_data requires admin or admin_pide group, matching the
        AdminPIDERequiredMixin on every other NamaTabel view."""
        client.force_login(authenticated_user)
        resp = client.get(reverse('nama_tabel_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code in (302, 403)

    def test_data_endpoint_denied_for_admin_p3de(self, client, p3de_admin_user):
        """admin_p3de cannot reach the list page, so it cannot reach its data either."""
        client.force_login(p3de_admin_user)
        resp = client.get(reverse('nama_tabel_data'), {'draw': '1', 'start': '0', 'length': '10'})
        assert resp.status_code in (302, 403)

    def test_data_endpoint_returns_json(self, client, pide_admin_user):
        client.force_login(pide_admin_user)
        resp = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'data' in data

    def test_data_endpoint_with_records(self, client, pide_admin_user):
        JenisDataILAPFactory()
        client.force_login(pide_admin_user)
        resp = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['recordsTotal'] >= 1

    def test_data_endpoint_column_search(self, client, pide_admin_user):
        jenis = JenisDataILAPFactory(nama_tabel_I='my_table')
        client.force_login(pide_admin_user)
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
