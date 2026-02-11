from django.db import models
from django.conf import settings
from .tiket import Tiket

class BackupData(models.Model):
    """Model untuk menyimpan riwayat backup data per tiket."""
    
    id_tiket = models.ForeignKey(
        Tiket, 
        on_delete=models.PROTECT, 
        verbose_name="No Tiket",
        related_name="backups"
    )
    lokasi_backup = models.CharField(max_length=255, verbose_name="Lokasi Backup")
    
    # Audit trail
    id_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Dilakukan Oleh")

    class Meta:
        db_table = 'backup_data'
        ordering = ['id']

    def __str__(self):
        return f"Backup {self.id_tiket.nomor_tiket} - {self.created_at.strftime('%Y-%m-%d')}"