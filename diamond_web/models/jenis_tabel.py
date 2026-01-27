from django.db import models

class JenisTabel(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=50, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Jenis Tabel"
        verbose_name_plural = "Jenis Tabel"
        db_table = "jenis_tabel"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id} - {self.deskripsi}"
