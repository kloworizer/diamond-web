from django.db import models
from .audit import AuditTrailModel

class BentukData(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=25, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Bentuk Data"
        verbose_name_plural = "Bentuk Data"
        db_table = "bentuk_data"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
