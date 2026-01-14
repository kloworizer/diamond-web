from django.db import models

class KategoriILAP(models.Model):
    id_kategori = models.CharField(max_length=2, primary_key=True, verbose_name="ID Kategori")
    nama_kategori = models.CharField(max_length=50, verbose_name="Nama Kategori")

    class Meta:
        verbose_name = "Kategori ILAP"
        verbose_name_plural = "Kategori ILAP"
        db_table = "kategori_ilap"

    def __str__(self):
        return f"{self.id_kategori} - {self.nama_kategori}"
