from django.db import models

class KlasifikasiTabel(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=50, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Klasifikasi Tabel"
        verbose_name_plural = "Klasifikasi Tabel"
        db_table = "klasifikasi_tabel"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
