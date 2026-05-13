from django.db import models
from .audit import AuditTrailModel

class MediaBackup(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    deskripsi = models.CharField(max_length=25, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Media Backup"
        verbose_name_plural = "Media Backup"
        db_table = "media_backup"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
