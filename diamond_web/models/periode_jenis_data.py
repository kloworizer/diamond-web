from django.db import models
from .jenis_data_ilap import JenisDataILAP
from .periode_pengiriman import PeriodePengiriman
from .audit import AuditTrailModel

class PeriodeJenisData(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_sub_jenis_data_ilap = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.PROTECT,
        db_column="id_sub_jenis_data_ilap",
        verbose_name="Sub Jenis Data ILAP"
    )
    id_periode_pengiriman = models.ForeignKey(
        PeriodePengiriman,
        on_delete=models.PROTECT,
        db_column="id_periode_pengiriman",
        verbose_name="Periode Pengiriman"
    )
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(null=True, blank=True, default=None, verbose_name="End Date")
    akhir_penyampaian = models.IntegerField(verbose_name="Akhir Penyampaian")

    class Meta:
        verbose_name = "Periode Jenis Data"
        verbose_name_plural = "Periode Jenis Data"
        db_table = "periode_jenis_data"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["id_sub_jenis_data_ilap"], name="pjd_subjenis_idx"),
            models.Index(fields=["id_periode_pengiriman"], name="pjd_periode_idx"),
            models.Index(fields=["start_date"], name="pjd_start_idx"),
            models.Index(fields=["end_date"], name="pjd_end_idx"),
            models.Index(fields=["id_sub_jenis_data_ilap", "id_periode_pengiriman"], name="pjd_sub_per_idx"),
            models.Index(fields=["id_sub_jenis_data_ilap", "start_date"], name="pjd_sub_start_idx"),
        ]

    def __str__(self):
        label = (
            f"{self.id_sub_jenis_data_ilap.id_sub_jenis_data} - "
            f"{self.id_sub_jenis_data_ilap.nama_sub_jenis_data} - "
            f"{self.id_sub_jenis_data_ilap.nama_tabel_I} - "
            f"{self.id_periode_pengiriman.periode_penerimaan}"
        )
        if self.end_date:
            label += f" ({self.end_date.isoformat()})"
        return label
