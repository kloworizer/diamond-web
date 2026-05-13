from django.db import models
from .audit import AuditTrailModel

class KategoriILAP(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_kategori = models.CharField(max_length=2, unique=True, verbose_name="ID Kategori")
    nama_kategori = models.CharField(max_length=50, unique=True, verbose_name="Nama Kategori")

    class Meta:
        verbose_name = "Kategori ILAP"
        verbose_name_plural = "Kategori ILAP"
        db_table = "kategori_ilap"
        ordering = ["id_kategori"]

    def __str__(self):
        return self.nama_kategori
