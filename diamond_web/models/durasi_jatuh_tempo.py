from django.db import models
from django.contrib.auth.models import Group
from .jenis_data_ilap import JenisDataILAP

class DurasiJatuhTempo(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_sub_jenis_data = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.PROTECT,
        db_column="id_sub_jenis_data",
        verbose_name="Sub Jenis Data ILAP"
    )
    seksi = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        db_column="seksi",
        verbose_name="Seksi"
    )
    durasi = models.IntegerField(verbose_name="Durasi")
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(null=True, blank=True, default=None, verbose_name="End Date")

    class Meta:
        verbose_name = "Durasi Jatuh Tempo"
        verbose_name_plural = "Durasi Jatuh Tempo"
        db_table = "durasi_jatuh_tempo"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id_sub_jenis_data} - {self.seksi}"

