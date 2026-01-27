from django.db import models
from .kategori_ilap import KategoriILAP
from .ilap import ILAP
from .jenis_tabel import JenisTabel
from .klasifikasi_tabel import KlasifikasiTabel

class JenisDataILAP(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_kategori_ilap = models.ForeignKey(
        KategoriILAP,
        on_delete=models.CASCADE,
        db_column="id_kategori_ilap",
        verbose_name="Kategori ILAP"
    )
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.CASCADE,
        db_column="id_ilap",
        verbose_name="ILAP"
    )
    id_jenis_data = models.CharField(max_length=7, verbose_name="ID Jenis Data")
    id_sub_jenis_data = models.CharField(max_length=9, verbose_name="ID Sub Jenis Data")
    nama_jenis_data = models.CharField(max_length=255, verbose_name="Nama Jenis Data")
    nama_sub_jenis_data = models.CharField(max_length=255, verbose_name="Nama Sub Jenis Data")
    nama_tabel_I = models.CharField(max_length=255, verbose_name="Nama Tabel I")
    nama_tabel_U = models.CharField(max_length=255, verbose_name="Nama Tabel U")
    id_jenis_tabel = models.ForeignKey(
        JenisTabel,
        on_delete=models.CASCADE,
        db_column="id_jenis_tabel",
        verbose_name="Jenis Tabel"
    )
    id_klasifikasi_tabel = models.ForeignKey(
        KlasifikasiTabel,
        on_delete=models.CASCADE,
        db_column="id_klasifikasi_tabel",
        verbose_name="Klasifikasi Tabel"
    )

    class Meta:
        verbose_name = "Jenis Data ILAP"
        verbose_name_plural = "Jenis Data ILAP"
        db_table = "jenis_data_ilap"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id_jenis_data} - {self.nama_jenis_data}"