from django.db import models
from django.contrib.auth.models import User
from .jenis_data_ilap import JenisDataILAP

class PIC(models.Model):
    """
    Unified Person In Charge model for all PIC types (P3DE, PIDE, PMDE).
    Consolidates the previously separate PICP3DE, PICPIDE, and PICPMDE models.
    """
    
    class TipePIC(models.TextChoices):
        P3DE = 'P3DE', 'PIC P3DE'
        PIDE = 'PIDE', 'PIC PIDE'
        PMDE = 'PMDE', 'PIC PMDE'
    
    id = models.AutoField(primary_key=True, verbose_name="ID")
    tipe = models.CharField(
        max_length=10,
        choices=TipePIC.choices,
        verbose_name="Tipe PIC",
        db_index=True
    )
    id_sub_jenis_data_ilap = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.CASCADE,
        db_column="id_sub_jenis_data_ilap",
        verbose_name="Sub Jenis Data ILAP"
    )
    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="id_user",
        verbose_name="User"
    )
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(null=True, blank=True, default=None, verbose_name="End Date")

    class Meta:
        verbose_name = "PIC"
        verbose_name_plural = "PIC"
        db_table = "pic"
        ordering = ["tipe", "id"]
        indexes = [
            models.Index(fields=['tipe', 'id_sub_jenis_data_ilap']),
        ]

    def __str__(self):
        return f"{self.get_tipe_display()} - {self.id_sub_jenis_data_ilap} - {self.id_user.username}"
    
    @classmethod
    def get_by_tipe(cls, tipe):
        """Helper method to filter PICs by type"""
        return cls.objects.filter(tipe=tipe)
