from django.db import models
from .jenis_data_ilap import JenisDataILAP
from .dasar_hukum import DasarHukum
from .audit import AuditTrailModel

class KlasifikasiJenisData(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_sub_jenis_data = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.PROTECT,
        db_column="id_sub_jenis_data",
        verbose_name="Sub Jenis Data ILAP"
    )
    id_klasifikasi_tabel = models.ForeignKey(
        DasarHukum,
        on_delete=models.PROTECT,
        db_column="id_klasifikasi_tabel",
        verbose_name="Dasar Hukum"
    )

    class Meta:
        verbose_name = "Klasifikasi Jenis Data"
        verbose_name_plural = "Klasifikasi Jenis Data"
        db_table = "klasifikasi_jenis_data"
        ordering = ["id"]
        unique_together = [['id_sub_jenis_data', 'id_klasifikasi_tabel']]
        indexes = [
            models.Index(fields=["id_sub_jenis_data"], name="kjd_subjenis_idx"),
            models.Index(fields=["id_klasifikasi_tabel"], name="kjd_klasif_idx"),
        ]

    def __str__(self):
        return f"{self.id_sub_jenis_data} - {self.id_klasifikasi_tabel}"
