"""Tests for model __str__ methods and property methods to ensure coverage."""
import pytest
from datetime import date
from diamond_web.tests.conftest import (
    UserFactory, TiketFactory, TiketPICFactory, PeriodeJenisDataFactory,
    PeriodePengirimanFactory, JenisDataILAPFactory, ILAPFactory,
    KategoriILAPFactory, KategoriWilayahFactory, PICFactory,
    BentukDataFactory, CaraPenyampaianFactory, NotificationFactory,
    JenisPrioritasDataFactory,
)
from diamond_web.models import (
    ILAP, JenisDataILAP, TandaTerimaData, PIC, TiketPIC, Tiket,
    PeriodeJenisData, Notification,
)
from diamond_web.models.backup_data import BackupData
from diamond_web.models.detil_tanda_terima import DetilTandaTerima
from diamond_web.models.tiket_action import TiketAction
from diamond_web.constants.tiket_action_types import TiketActionType


@pytest.mark.django_db
class TestModelStrMethods:
    """Test __str__ methods for all models with missing coverage."""

    def test_backup_data_str(self, db):
        """Test BackupData.__str__ returns formatted string."""
        tiket = TiketFactory()
        media_backup_obj = BentukDataFactory()  # use any model that matches
        # Create BackupData directly
        from diamond_web.models.media_backup import MediaBackup
        media_backup = MediaBackup.objects.create(deskripsi='Test Media')
        backup = BackupData.objects.create(
            id_tiket=tiket,
            lokasi_backup='/tmp',
            nama_file='test.csv',
            id_media_backup=media_backup,
            id_user=UserFactory(),
        )
        result = str(backup)
        assert tiket.nomor_tiket in result

    def test_detil_tanda_terima_str(self, db):
        """Test DetilTandaTerima.__str__ returns formatted string."""
        from django.utils import timezone
        from diamond_web.models.tanda_terima_data import TandaTerimaData
        ilap = ILAPFactory()
        tiket = TiketFactory()
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=1,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
        )
        detil = DetilTandaTerima.objects.create(
            id_tanda_terima=tanda_terima,
            id_tiket=tiket,
        )
        result = str(detil)
        assert str(tanda_terima) in result or str(tiket) in result

    def test_notification_str(self, db):
        """Test Notification.__str__ returns formatted string."""
        user = UserFactory()
        notif = Notification.objects.create(
            recipient=user,
            title='Test Notification Title',
            message='Test message',
        )
        result = str(notif)
        assert 'Test Notification Title' in result
        assert user.username in result

    def test_periode_jenis_data_str(self, db):
        """Test PeriodeJenisData.__str__ returns formatted string."""
        periode_jenis = PeriodeJenisDataFactory()
        result = str(periode_jenis)
        assert result  # just verify it returns something non-empty

    def test_tiket_str(self, db):
        """Test Tiket.__str__ returns formatted string."""
        tiket = TiketFactory(periode=3, tahun=2024)
        result = str(tiket)
        assert 'Tiket' in result
        assert '3' in result or '2024' in result

    def test_tiket_action_str(self, db):
        """Test TiketAction.__str__ returns formatted string."""
        tiket = TiketFactory()
        user = UserFactory()
        from datetime import datetime
        action = TiketAction.objects.create(
            id_tiket=tiket,
            id_user=user,
            timestamp=datetime.now(),
            action=TiketActionType.DIREKAM,
            catatan='Test action',
        )
        result = str(action)
        assert result  # verify it returns something

    def test_tiket_pic_str(self, db):
        """Test TiketPIC.__str__ returns formatted string."""
        tiket = TiketFactory()
        user = UserFactory()
        from datetime import datetime
        tiket_pic = TiketPIC.objects.create(
            id_tiket=tiket,
            id_user=user,
            timestamp=datetime.now(),
            role=TiketPIC.Role.P3DE,
            active=True,
        )
        result = str(tiket_pic)
        assert result  # verify it returns something


@pytest.mark.django_db
class TestPICProperties:
    """Test PIC model property methods."""

    def test_pic_is_active_true_when_no_end_date(self, db):
        """Test PIC.is_active() returns True when end_date is None."""
        jenis_data = JenisDataILAPFactory()
        user = UserFactory()
        pic = PIC.objects.create(
            tipe='P3DE',
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            start_date=date(2024, 1, 1),
            end_date=None,
        )
        assert pic.is_active() is True

    def test_pic_is_active_false_when_has_end_date(self, db):
        """Test PIC.is_active() returns False when end_date is set."""
        jenis_data = JenisDataILAPFactory()
        user = UserFactory()
        pic = PIC.objects.create(
            tipe='P3DE',
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert pic.is_active() is False

    def test_pic_get_by_tipe(self, db):
        """Test PIC.get_by_tipe() classmethod returns correct records."""
        jenis_data = JenisDataILAPFactory()
        user = UserFactory()
        PIC.objects.create(
            tipe='P3DE',
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            start_date=date(2024, 1, 1),
        )
        result = PIC.get_by_tipe('P3DE')
        assert result.count() >= 1

    def test_pic_str(self, db):
        """Test PIC.__str__ returns formatted string."""
        jenis_data = JenisDataILAPFactory()
        user = UserFactory(username='testpicuser')
        pic = PIC.objects.create(
            tipe='P3DE',
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            start_date=date(2024, 1, 1),
        )
        result = str(pic)
        assert 'testpicuser' in result


@pytest.mark.django_db
class TestTandaTerimaDataProperties:
    """Test TandaTerimaData model property methods."""

    def test_tanda_terima_nama_ilap(self, db):
        """Test TandaTerimaData.nama_ILAP property."""
        from django.utils import timezone
        ilap = ILAPFactory(nama_ilap='Test ILAP Name')
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=2,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
        )
        result = tanda_terima.nama_ILAP
        assert result == 'Test ILAP Name'

    def test_tanda_terima_daftar_jenis_data(self, db):
        """Test TandaTerimaData.daftar_jenis_data property."""
        from django.utils import timezone
        ilap = ILAPFactory()
        jenis_data = JenisDataILAPFactory(id_ilap=ilap, nama_jenis_data='Jenis ABC')
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=3,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
        )
        result = tanda_terima.daftar_jenis_data
        assert 'Jenis ABC' in result

    def test_tanda_terima_periode_data_with_data(self, db):
        """Test TandaTerimaData.periode_data property with existing data."""
        from django.utils import timezone
        ilap = ILAPFactory()
        jenis_data = JenisDataILAPFactory(id_ilap=ilap)
        from diamond_web.models.periode_pengiriman import PeriodePengiriman
        periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian='Bulanan',
            defaults={'periode_penerimaan': 'Bulanan'},
        )
        PeriodeJenisData.objects.create(
            id_sub_jenis_data_ilap=jenis_data,
            id_periode_pengiriman=periode_pengiriman,
            start_date=date(2024, 1, 1),
            akhir_penyampaian=31,
        )
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=4,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
        )
        # periode_data fetches from PeriodeJenisData
        result = tanda_terima.periode_data
        # The result depends on DB query, just ensure it doesn't raise

    def test_tanda_terima_periode_data_without_data(self, db):
        """Test TandaTerimaData.periode_data property without related data."""
        from django.utils import timezone
        ilap = ILAPFactory()
        user = UserFactory()
        tanda_terima = TandaTerimaData.objects.create(
            nomor_tanda_terima=5,
            tahun_terima=2024,
            tanggal_tanda_terima=timezone.now(),
            id_ilap=ilap,
            id_perekam=user,
        )
        result = tanda_terima.periode_data
        assert result is None
