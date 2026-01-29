from django.db import models
from .jenis_data_ilap import JenisDataILAP
from .klasifikasi_tabel import KlasifikasiTabel

class KlasifikasiJenisData(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_jenis_data_ilap = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.CASCADE,
        db_column="id_jenis_data_ilap",
        verbose_name="Jenis Data ILAP"
    )
    id_klasifikasi_tabel = models.ForeignKey(
        KlasifikasiTabel,
        on_delete=models.CASCADE,
        db_column="id_klasifikasi_tabel",
        verbose_name="Klasifikasi Tabel"
    )

    class Meta:
        verbose_name = "Klasifikasi Jenis Data"
        verbose_name_plural = "Klasifikasi Jenis Data"
        db_table = "klasifikasi_jenis_data"
        ordering = ["id"]
        unique_together = [['id_jenis_data_ilap', 'id_klasifikasi_tabel']]

    def __str__(self):
        return f"{self.id_jenis_data_ilap} - {self.id_klasifikasi_tabel}"
