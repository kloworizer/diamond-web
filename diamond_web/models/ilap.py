from django.db import models
from .kategori_ilap import KategoriILAP

class ILAP(models.Model):
    id_ilap = models.CharField(max_length=5, primary_key=True, verbose_name="ID ILAP")
    id_kategori = models.ForeignKey(
        KategoriILAP,
        on_delete=models.CASCADE,
        db_column="id_kategori",
        verbose_name="ID Kategori"
    )
    nama_ilap = models.CharField(max_length=150, verbose_name="Nama ILAP")

    class Meta:
        verbose_name = "ILAP"
        verbose_name_plural = "ILAP"
        db_table = "ilap"
        ordering = ["id_ilap"]

    def __str__(self):
        return f"{self.id_ilap} - {self.nama_ilap}"