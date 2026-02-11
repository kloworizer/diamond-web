from django.db import models
from .jenis_data_ilap import JenisDataILAP
from .periode_pengiriman import PeriodePengiriman

class PeriodeJenisData(models.Model):
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

    class Meta:
        verbose_name = "Periode Jenis Data"
        verbose_name_plural = "Periode Jenis Data"
        db_table = "periode_jenis_data"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id_sub_jenis_data_ilap} - {self.id_periode_pengiriman}"
