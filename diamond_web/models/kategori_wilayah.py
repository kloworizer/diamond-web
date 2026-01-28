from django.db import models

class KategoriWilayah(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=50, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Kategori Wilayah"
        verbose_name_plural = "Kategori Wilayah"
        db_table = "kategori_wilayah"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
