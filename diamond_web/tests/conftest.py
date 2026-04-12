"""Pytest configuration and shared fixtures for Django tests."""
import os
import sys
import django
from pathlib import Path
import pytest
from django.contrib.auth.models import User, Group
from faker import Faker
import factory
from factory.django import DjangoModelFactory

# Setup Django settings — always use test settings for the test suite,
# overriding any OS-level DJANGO_SETTINGS_MODULE that may point to config.settings.
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
django.setup()

from diamond_web.models import (
    KategoriILAP, ILAP, JenisDataILAP, JenisTabel, KategoriWilayah, Kanwil, KPP,
    StatusData, DasarHukum, StatusPenelitian, BentukData, CaraPenyampaian,
    MediaBackup, KlasifikasiJenisData, PeriodePengiriman, PeriodeJenisData,
    JenisPrioritasData, PIC, TandaTerimaData, Tiket,
    DurasiJatuhTempo, Notification, TiketPIC
)

# Import DocxTemplate directly if available
try:
    from diamond_web.models.docx_template import DocxTemplate
except (ImportError, ModuleNotFoundError):
    DocxTemplate = None

fake = Faker('id_ID')


class UserFactory(DjangoModelFactory):
    """Factory for creating test users."""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user_{n}')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    first_name = factory.LazyFunction(fake.first_name)
    last_name = factory.LazyFunction(fake.last_name)


class GroupFactory(DjangoModelFactory):
    """Factory for creating test groups."""
    class Meta:
        model = Group

    name = factory.Sequence(lambda n: f'group_{n}')


class KategoriILAPFactory(DjangoModelFactory):
    """Factory for KategoriILAP model."""
    class Meta:
        model = KategoriILAP

    id_kategori = factory.Sequence(lambda n: f'{n % 100:02d}')
    nama_kategori = factory.Sequence(lambda n: f'Kategori_{n:04d}')


class JenisTabelFactory(DjangoModelFactory):
    """Factory for JenisTabel model."""
    class Meta:
        model = JenisTabel

    deskripsi = factory.Sequence(lambda n: f'JenisTabel_{n:04d}')


class KategoriWilayahFactory(DjangoModelFactory):
    """Factory for KategoriWilayah model."""
    class Meta:
        model = KategoriWilayah

    deskripsi = factory.Sequence(lambda n: f'Wilayah_{n:04d}')


class StatusDataFactory(DjangoModelFactory):
    """Factory for StatusData model."""
    class Meta:
        model = StatusData

    deskripsi = factory.Sequence(lambda n: f'Status_{n:04d}')


class ILAPFactory(DjangoModelFactory):
    """Factory for ILAP model."""
    class Meta:
        model = ILAP

    id_ilap = factory.Sequence(lambda n: f'{n:05d}')  # max_length=5, so use numeric format
    id_kategori = factory.SubFactory(KategoriILAPFactory)
    nama_ilap = factory.Sequence(lambda n: f'ILAP_{n:05d}')
    id_kategori_wilayah = factory.SubFactory(KategoriWilayahFactory)


class JenisDataILAPFactory(DjangoModelFactory):
    """Factory for JenisDataILAP model."""
    class Meta:
        model = JenisDataILAP

    id_ilap = factory.SubFactory(ILAPFactory)
    id_jenis_data = factory.Sequence(lambda n: f'{n:07d}')
    id_sub_jenis_data = factory.Sequence(lambda n: f'{n:09d}')
    nama_jenis_data = factory.LazyFunction(lambda: fake.word().title())
    nama_sub_jenis_data = factory.LazyFunction(lambda: fake.word().title())
    nama_tabel_I = factory.LazyFunction(lambda: fake.word().title())
    nama_tabel_U = factory.LazyFunction(lambda: fake.word().title())
    id_jenis_tabel = factory.SubFactory(JenisTabelFactory)
    id_status_data = factory.SubFactory(StatusDataFactory)


class KanwilFactory(DjangoModelFactory):
    """Factory for Kanwil model."""
    class Meta:
        model = Kanwil

    kode_kanwil = factory.LazyFunction(lambda: ''.join(fake.random_letters(length=3)).upper())
    nama_kanwil = factory.LazyFunction(lambda: fake.word().title())


class KPPFactory(DjangoModelFactory):
    """Factory for KPP model."""
    class Meta:
        model = KPP

    kode_kpp = factory.LazyFunction(lambda: ''.join(fake.random_letters(length=3)).upper())
    nama_kpp = factory.LazyFunction(lambda: fake.word().title())
    id_kanwil = factory.SubFactory(KanwilFactory)


class DasarHukumFactory(DjangoModelFactory):
    """Factory for DasarHukum model."""
    class Meta:
        model = DasarHukum

    deskripsi = factory.LazyFunction(lambda: fake.sentence())


class StatusPenelitianFactory(DjangoModelFactory):
    """Factory for StatusPenelitian model."""
    class Meta:
        model = StatusPenelitian

    deskripsi = factory.LazyFunction(lambda: fake.word().title())


class BentukDataFactory(DjangoModelFactory):
    """Factory for BentukData model."""
    class Meta:
        model = BentukData

    deskripsi = factory.Sequence(lambda n: f'BentukData_{n:04d}')


class CaraPenyampaianFactory(DjangoModelFactory):
    """Factory for CaraPenyampaian model."""
    class Meta:
        model = CaraPenyampaian

    deskripsi = factory.Sequence(lambda n: f'CaraPenyampaian_{n:04d}')


class MediaBackupFactory(DjangoModelFactory):
    """Factory for MediaBackup model."""
    class Meta:
        model = MediaBackup

    deskripsi = factory.Sequence(lambda n: f'MediaBackup_{n:04d}')


class KlasifikasiJenisDataFactory(DjangoModelFactory):
    """Factory for KlasifikasiJenisData model."""
    class Meta:
        model = KlasifikasiJenisData

    id_jenis_data_ilap = factory.SubFactory(JenisDataILAPFactory)
    id_klasifikasi_tabel = factory.SubFactory(DasarHukumFactory)


class PeriodePengirimanFactory(DjangoModelFactory):
    """Factory for PeriodePengiriman model."""
    class Meta:
        model = PeriodePengiriman

    periode_penyampaian = factory.LazyFunction(lambda: fake.word().title())
    periode_penerimaan = factory.LazyFunction(lambda: fake.word().title())


class PeriodeJenisDataFactory(DjangoModelFactory):
    """Factory for PeriodeJenisData model."""
    class Meta:
        model = PeriodeJenisData

    id_sub_jenis_data_ilap = factory.SubFactory(JenisDataILAPFactory)
    id_periode_pengiriman = factory.SubFactory(PeriodePengirimanFactory)
    start_date = factory.LazyFunction(lambda: fake.date_object())
    end_date = factory.LazyFunction(lambda: fake.date_object())
    akhir_penyampaian = factory.LazyFunction(lambda: fake.random_int(min=1, max=31))


class JenisPrioritasDataFactory(DjangoModelFactory):
    """Factory for JenisPrioritasData model."""
    class Meta:
        model = JenisPrioritasData

    id_sub_jenis_data_ilap = factory.SubFactory(JenisDataILAPFactory)
    no_nd = factory.Sequence(lambda n: f'ND{n:06d}')
    tahun = factory.LazyFunction(lambda: str(fake.random_int(min=2020, max=2025)))
    start_date = factory.LazyFunction(fake.date_object)
    end_date = factory.LazyFunction(fake.date_object)


class PICFactory(DjangoModelFactory):
    """Factory for PIC model."""
    class Meta:
        model = PIC

    tipe = 'P3DE'
    id_sub_jenis_data_ilap = factory.SubFactory(JenisDataILAPFactory)
    id_user = factory.SubFactory(UserFactory)
    start_date = factory.LazyFunction(lambda: fake.date_object())
    end_date = factory.LazyFunction(lambda: fake.date_object())


class DurasiJatuhTempoFactory(DjangoModelFactory):
    """Factory for DurasiJatuhTempo model."""
    class Meta:
        model = DurasiJatuhTempo

    id_sub_jenis_data = factory.SubFactory(JenisDataILAPFactory)
    seksi = factory.LazyAttribute(lambda o: Group.objects.first() or GroupFactory())
    durasi = factory.LazyFunction(lambda: fake.random_int(min=1, max=100))
    start_date = factory.LazyFunction(fake.date_object)
    end_date = factory.LazyFunction(fake.date_object)


class TandaTerimaDataFactory(DjangoModelFactory):
    """Factory for TandaTerimaData model."""
    class Meta:
        model = TandaTerimaData

    nomor_tanda_terima = factory.LazyFunction(lambda: fake.uuid4()[:8])


class DocxTemplateFactory(DjangoModelFactory):
    """Factory for DocxTemplate model."""
    class Meta:
        model = DocxTemplate if DocxTemplate else type('DocxTemplate', (), {})

    nama_template = factory.LazyFunction(lambda: fake.word().title())
    jenis_dokumen = 'tanda_terima_nasional_internasional'
    deskripsi = factory.LazyFunction(lambda: fake.text())
    file_template = factory.django.FileField(filename='test.docx', data=b'PK fake docx content')


class TiketFactory(DjangoModelFactory):
    """Factory for Tiket model."""
    class Meta:
        model = Tiket

    nomor_tiket = factory.LazyFunction(lambda: fake.uuid4()[:17])
    status_tiket = 1
    id_periode_data = factory.SubFactory(PeriodeJenisDataFactory)
    id_jenis_prioritas_data = factory.SubFactory(JenisPrioritasDataFactory)
    periode = factory.LazyFunction(lambda: fake.random_int(min=1, max=12))
    tahun = factory.LazyFunction(lambda: fake.random_int(min=2020, max=2025))
    nomor_surat_pengantar = factory.LazyFunction(lambda: fake.uuid4()[:50])
    tanggal_surat_pengantar = factory.LazyFunction(fake.date_time)
    nama_pengirim = factory.LazyFunction(fake.name)
    id_bentuk_data = factory.SubFactory(BentukDataFactory)
    id_cara_penyampaian = factory.SubFactory(CaraPenyampaianFactory)
    baris_diterima = factory.LazyFunction(lambda: fake.random_int(min=1, max=1000))
    tgl_terima_dip = factory.LazyFunction(fake.date_time)


class NotificationFactory(DjangoModelFactory):
    """Factory for Notification model."""
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    message = factory.LazyFunction(lambda: fake.sentence())
    is_read = False


class TiketPICFactory(DjangoModelFactory):
    """Factory for TiketPIC model."""
    class Meta:
        model = TiketPIC

    id_tiket = factory.SubFactory(TiketFactory)
    id_user = factory.SubFactory(UserFactory)
    timestamp = factory.LazyFunction(lambda: fake.date_time())
    role = TiketPIC.Role.P3DE
    active = True


# Fixtures

@pytest.fixture(autouse=True)
def reset_sequences():
    """Reset factory sequences before each test."""
    factory.Factory.reset_sequence(UserFactory)
    factory.Factory.reset_sequence(GroupFactory)


@pytest.fixture
def user():
    """Create a test user."""
    return UserFactory()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    user = UserFactory(is_staff=True, is_superuser=True)
    group, _ = Group.objects.get_or_create(name='admin')
    user.groups.add(group)
    return user


@pytest.fixture
def authenticated_user(db):
    """Create an authenticated user with user_p3de group."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_p3de')
    user.groups.add(group)
    return user


@pytest.fixture
def p3de_admin_user(db):
    """Create a P3DE admin user."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='admin_p3de')
    user.groups.add(group)
    return user


@pytest.fixture
def pide_user(db):
    """Create a PIDE user."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_pide')
    user.groups.add(group)
    return user


@pytest.fixture
def pmde_user(db):
    """Create a PMDE user."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='user_pmde')
    user.groups.add(group)
    return user


@pytest.fixture
def pide_admin_user(db):
    """Create a PIDE admin user."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='admin_pide')
    user.groups.add(group)
    return user


@pytest.fixture
def pmde_admin_user(db):
    """Create a PMDE admin user."""
    user = UserFactory()
    group, _ = Group.objects.get_or_create(name='admin_pmde')
    user.groups.add(group)
    return user


@pytest.fixture
def kategori_ilap(db):
    """Create a test KategoriILAP."""
    return KategoriILAPFactory()


@pytest.fixture
def ilap(db, kategori_ilap):
    """Create a test ILAP."""
    return ILAPFactory(id_kategori=kategori_ilap)


@pytest.fixture
def jenis_data_ilap(db, ilap):
    """Create a test JenisDataILAP."""
    return JenisDataILAPFactory(id_ilap=ilap)


@pytest.fixture
def kanwil(db):
    """Create a test Kanwil."""
    return KanwilFactory()


@pytest.fixture
def kpp(db, kanwil):
    """Create a test KPP."""
    return KPPFactory(id_kanwil=kanwil)


@pytest.fixture
def pic(db, authenticated_user):
    """Create a test PIC."""
    jenis_data = JenisDataILAPFactory()
    return PICFactory(id_sub_jenis_data_ilap=jenis_data, id_user=authenticated_user, tipe='P3DE')


@pytest.fixture
def tiket(db):
    """Create a test Tiket."""
    return TiketFactory()


@pytest.fixture
def tiket_with_pic(db, tiket, authenticated_user):
    """Create a test Tiket with PIC assignment."""
    TiketPICFactory(id_tiket=tiket, id_user=authenticated_user)
    return tiket


@pytest.fixture
def notification(db, authenticated_user):
    """Create a test Notification."""
    return NotificationFactory(recipient=authenticated_user)


@pytest.fixture
def client():
    """Return a Django test client."""
    from django.test import Client
    return Client()
