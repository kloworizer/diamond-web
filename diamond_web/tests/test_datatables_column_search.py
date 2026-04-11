"""Tests for DataTables column search and ordering for all endpoints.

Covers the missing column-specific filtering and ordering desc paths
in all DataTables endpoints.
"""
import json
import pytest
from django.urls import reverse
from diamond_web.tests.conftest import (
    BentukDataFactory, CaraPenyampaianFactory, DasarHukumFactory,
    JenisTabelFactory, KanwilFactory, KPPFactory, StatusDataFactory,
    MediaBackupFactory, KategoriWilayahFactory, KlasifikasiJenisDataFactory,
    PeriodePengirimanFactory, StatusPenelitianFactory, ILAPFactory,
    JenisDataILAPFactory, JenisPrioritasDataFactory, PeriodeJenisDataFactory,
    DurasiJatuhTempoFactory,
)


@pytest.mark.django_db
class TestBentukDataDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('bentuk_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('bentuk_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_ordering_desc(self, client, p3de_admin_user, db):
        BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('bentuk_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_ordering_invalid_column(self, client, p3de_admin_user, db):
        BentukDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('bentuk_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'abc', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200

    def test_exception_returns_500(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        # Trigger exception by sending invalid draw value
        response = client.get(
            reverse('bentuk_data_data'),
            {'draw': 'not_a_number', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 500


@pytest.mark.django_db
class TestCaraPenyampaianDataTableColumnSearch:
    """Full coverage for cara_penyampaian_data endpoint (previously 0% coverage)."""

    def test_basic_fetch(self, client, p3de_admin_user, db):
        CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'data' in data

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '1', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_ordering_with_exception(self, client, p3de_admin_user, db):
        CaraPenyampaianFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200

    def test_exception_returns_500(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('cara_penyampaian_data'),
            {'draw': 'nan', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 500


@pytest.mark.django_db
class TestDasarHukumDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('dasar_hukum_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('dasar_hukum_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        DasarHukumFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('dasar_hukum_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('dasar_hukum_data'),
            {'draw': 'bad', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 500


@pytest.mark.django_db
class TestJenisTabelDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('jenis_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('jenis_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        JenisTabelFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('jenis_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('jenis_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestKanwilDataTableColumnSearch:

    def test_column_search_by_kode(self, client, p3de_admin_user, kanwil):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kanwil_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [kanwil.kode_kanwil[:2], '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama(self, client, p3de_admin_user, kanwil):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kanwil_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', kanwil.nama_kanwil[:3], '']}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, kanwil):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kanwil_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kanwil_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestKPPDataTableColumnSearch:

    def test_column_search_by_kode(self, client, p3de_admin_user, kpp):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [kpp.kode_kpp[:2], '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama(self, client, p3de_admin_user, kpp):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', kpp.nama_kpp[:3], '']}
        )
        assert response.status_code == 200

    def test_column_search_by_kanwil(self, client, p3de_admin_user, kpp):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', '', kpp.id_kanwil.nama_kanwil[:3]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, kpp):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kpp_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestStatusDataDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        StatusDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('status_data_data'),
            {'draw': 'bad', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 500


@pytest.mark.django_db
class TestMediaBackupDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('media_backup_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('media_backup_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        MediaBackupFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('media_backup_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('media_backup_data'),
            {'draw': 'bad', 'start': '0', 'length': '10'}
        )
        assert response.status_code == 500


@pytest.mark.django_db
class TestKategoriWilayahDataTableColumnSearch:

    def test_column_search_by_id(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kategori_wilayah_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.pk), '']}
        )
        assert response.status_code == 200

    def test_column_search_by_deskripsi(self, client, p3de_admin_user, db):
        obj = KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kategori_wilayah_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.deskripsi[:4]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        KategoriWilayahFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kategori_wilayah_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('kategori_wilayah_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestKlasifikasiJenisDataTableColumnSearch:

    def test_column_search_by_jenis_data(self, client, p3de_admin_user, db):
        obj = KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('klasifikasi_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [str(obj.id_jenis_data_ilap.id_sub_jenis_data)[:3], '', '']}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('klasifikasi_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('klasifikasi_jenis_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestPeriodePengirimanDataTableColumnSearch:

    def test_column_search_by_penyampaian(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('periode_pengiriman_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': [obj.periode_penyampaian[:3], '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_penerimaan(self, client, p3de_admin_user, db):
        obj = PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('periode_pengiriman_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'columns_search[]': ['', obj.periode_penerimaan[:3], '']}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, db):
        PeriodePengirimanFactory()
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('periode_pengiriman_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_exception_path(self, client, p3de_admin_user):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('periode_pengiriman_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestILAPDataTableColumnSearch:

    def test_column_search_by_kategori_wilayah(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': [ilap.id_kategori_wilayah.deskripsi[:3], '', '', '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_id_ilap(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', ilap.id_ilap[:3], '', '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama_ilap(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '', '', ilap.nama_ilap[:3], '']}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '1', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_ordering_exception(self, client, p3de_admin_user, ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('ilap_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestNamaTabelDataTableColumnSearch:
    """Tests for nama_tabel_data column search (missing lines 159, 161, 163, 167, 176-183)."""

    def test_column_search_by_id_sub_jenis(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': [jenis_data_ilap.id_sub_jenis_data[:3], '', '', '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama_jenis(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', jenis_data_ilap.nama_jenis_data[:3], '', '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama_sub_jenis(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '', jenis_data_ilap.nama_sub_jenis_data[:3], '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama_tabel_u(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '', '', '', jenis_data_ilap.nama_tabel_U[:3]]}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200

    def test_ordering_exception(self, client, p3de_admin_user, jenis_data_ilap):
        client.force_login(p3de_admin_user)
        response = client.get(
            reverse('nama_tabel_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': 'bad', 'order[0][dir]': 'asc'}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestBackupDataDataTableColumnSearch:
    """Tests for backup_data DataTables column search (missing lines 388-409)."""

    def test_column_search_by_lokasi(self, client, authenticated_user, tiket):
        from diamond_web.models.backup_data import BackupData
        from diamond_web.models.media_backup import MediaBackup
        from diamond_web.tests.conftest import UserFactory
        media = MediaBackup.objects.create(deskripsi='CD')
        BackupData.objects.create(
            id_tiket=tiket, lokasi_backup='/test', nama_file='file.csv',
            id_media_backup=media, id_user=UserFactory()
        )
        client.force_login(authenticated_user)
        response = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '/test', '', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_nama_file(self, client, authenticated_user, tiket):
        from diamond_web.models.backup_data import BackupData
        from diamond_web.models.media_backup import MediaBackup
        from diamond_web.tests.conftest import UserFactory
        media = MediaBackup.objects.create(deskripsi='USB')
        BackupData.objects.create(
            id_tiket=tiket, lokasi_backup='/test2', nama_file='data.csv',
            id_media_backup=media, id_user=UserFactory()
        )
        client.force_login(authenticated_user)
        response = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '', 'data', '']}
        )
        assert response.status_code == 200

    def test_column_search_by_media(self, client, authenticated_user, tiket):
        from diamond_web.models.backup_data import BackupData
        from diamond_web.models.media_backup import MediaBackup
        from diamond_web.tests.conftest import UserFactory
        media = MediaBackup.objects.create(deskripsi='HDD-MEDIA')
        BackupData.objects.create(
            id_tiket=tiket, lokasi_backup='/test3', nama_file='f3.csv',
            id_media_backup=media, id_user=UserFactory()
        )
        client.force_login(authenticated_user)
        response = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10',
             'columns_search[]': ['', '', '', 'HDD']}
        )
        assert response.status_code == 200

    def test_ordering_desc(self, client, authenticated_user):
        client.force_login(authenticated_user)
        response = client.get(
            reverse('backup_data_data'),
            {'draw': '1', 'start': '0', 'length': '10', 'order[0][column]': '0', 'order[0][dir]': 'desc'}
        )
        assert response.status_code == 200
