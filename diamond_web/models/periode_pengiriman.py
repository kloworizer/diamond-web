from django.db import models

class PeriodePengiriman(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    periode_penyampaian = models.CharField(max_length=50, unique=True, verbose_name="Periode Penyampaian")
    periode_penerimaan = models.CharField(max_length=50, verbose_name="Periode Penerimaan")

    class Meta:
        verbose_name = "Periode Pengiriman"
        verbose_name_plural = "Periode Pengiriman"
        db_table = "periode_pengiriman"
        ordering = ["id"]

    def __str__(self):
        return self.periode_penyampaian
