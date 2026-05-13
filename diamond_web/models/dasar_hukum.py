from django.db import models
from .audit import AuditTrailModel

class DasarHukum(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=50, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Dasar Hukum"
        verbose_name_plural = "Dasar Hukum"
        db_table = "dasar_hukum"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
