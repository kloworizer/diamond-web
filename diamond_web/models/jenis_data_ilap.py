from django.db import models

class JenisDataILAP(models.Model):
    id_jenis_data = models.CharField(max_length=7, primary_key=True, verbose_name="ID Jenis Data")
    nama_jenis_data = models.CharField(max_length=2000, verbose_name="Nama Jenis Data")

    class Meta:
        verbose_name = "Jenis Data ILAP"
        verbose_name_plural = "Jenis Data ILAP"
        db_table = "jenis_data_ilap"
        ordering = ["id_jenis_data"]

    def __str__(self):
        return f"{self.id_jenis_data} - {self.nama_jenis_data}"