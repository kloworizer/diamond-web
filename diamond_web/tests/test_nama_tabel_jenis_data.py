"""The table names now live in their own rows, and the jenis data caches one.

What these guard is the seam between the two: `JenisDataILAP.nama_tabel_I` and
`nama_tabel_U` are read by every report filter, export column and detail page,
but they are no longer where the value is written. If the mirroring breaks, the
whole application keeps working and quietly shows a stale table name — so the
mirror is asserted directly rather than through any view.
"""
import pytest
from django.db import IntegrityError, transaction

from diamond_web.models.jenis_data_ilap import JenisDataILAP
from diamond_web.models.nama_tabel_jenis_data import NamaTabelJenisData

from .conftest import JenisDataILAPFactory


@pytest.mark.django_db
class TestCacheKolomIkutBarisUtama:
    """The jenis data's two columns follow its utama row, in both directions."""

    def test_membuat_baris_utama_mengisi_cache(self):
        jenis = JenisDataILAPFactory(nama_tabel_I='', nama_tabel_U='')
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='KPDE_A', nama_tabel_U='KPDE_A_U', utama=True
        )
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == 'KPDE_A'
        assert jenis.nama_tabel_U == 'KPDE_A_U'

    def test_mengubah_baris_utama_memperbarui_cache(self):
        jenis = JenisDataILAPFactory()
        utama = NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='LAMA', nama_tabel_U='LAMA_U', utama=True
        )
        utama.nama_tabel_I = 'BARU'
        utama.nama_tabel_U = 'BARU_U'
        utama.save(update_fields=['nama_tabel_I', 'nama_tabel_U'])
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == 'BARU'
        assert jenis.nama_tabel_U == 'BARU_U'

    def test_menghapus_baris_utama_mengosongkan_cache(self):
        jenis = JenisDataILAPFactory()
        utama = NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='KPDE_B', nama_tabel_U='KPDE_B_U', utama=True
        )
        utama.delete()
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == ''
        assert jenis.nama_tabel_U == ''

    def test_baris_sekunder_tidak_menyentuh_cache(self):
        """A second table name is recorded without changing what pages display."""
        jenis = JenisDataILAPFactory()
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='UTAMA', nama_tabel_U='UTAMA_U', utama=True
        )
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='TAHAP2', nama_tabel_U='TAHAP2_U', utama=False
        )
        jenis.refresh_from_db()
        assert jenis.nama_tabel_I == 'UTAMA'
        assert jenis.nama_tabel_set.count() == 2


@pytest.mark.django_db
class TestInvarianDatabase:
    """The constraints migration 0015 exists to establish."""

    def test_id_sub_jenis_data_wajib_unik(self):
        """The point of the whole change: one row per sub jenis data."""
        jenis = JenisDataILAPFactory(id_sub_jenis_data='XX1234567')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                JenisDataILAPFactory(id_sub_jenis_data='XX1234567')
        assert JenisDataILAP.objects.filter(id_sub_jenis_data='XX1234567').count() == 1
        assert jenis.pk is not None

    def test_hanya_satu_baris_utama_per_jenis_data(self):
        jenis = JenisDataILAPFactory()
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='SATU', utama=True
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                NamaTabelJenisData.objects.create(
                    id_jenis_data_ilap=jenis, nama_tabel_I='DUA', utama=True
                )

    def test_nama_tabel_tidak_boleh_kembar_dalam_satu_jenis_data(self):
        jenis = JenisDataILAPFactory()
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='KEMBAR', utama=True
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                NamaTabelJenisData.objects.create(
                    id_jenis_data_ilap=jenis, nama_tabel_I='KEMBAR', utama=False
                )

    def test_nama_sama_boleh_dipakai_jenis_data_berbeda(self):
        """One bank data table is routinely fed by many sub jenis data."""
        satu = JenisDataILAPFactory()
        dua = JenisDataILAPFactory()
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=satu, nama_tabel_I='KPDE_BERSAMA', utama=True
        )
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=dua, nama_tabel_I='KPDE_BERSAMA', utama=True
        )
        assert NamaTabelJenisData.objects.filter(nama_tabel_I='KPDE_BERSAMA').count() == 2

    def test_menghapus_jenis_data_ikut_menghapus_nama_tabelnya(self):
        jenis = JenisDataILAPFactory()
        NamaTabelJenisData.objects.create(
            id_jenis_data_ilap=jenis, nama_tabel_I='IKUT_TERHAPUS', utama=True
        )
        jenis.delete()
        assert not NamaTabelJenisData.objects.filter(nama_tabel_I='IKUT_TERHAPUS').exists()
