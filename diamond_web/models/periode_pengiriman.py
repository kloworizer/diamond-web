from django.db import models

class PeriodePengiriman(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=50, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Periode Pengiriman"
        verbose_name_plural = "Periode Pengiriman"
        db_table = "periode_pengiriman"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
