from django.db import models
from .audit import AuditTrailModel

class DasarHukum(AuditTrailModel):
    KATEGORI_CHOICES = [
        ('DAPEN', 'DAPEN'),
        ('EOI', 'EOI'),
        ('KMK', 'KMK'),
        ('KSWP', 'KSWP'),
        ('MOU', 'MOU'),
        ('PKD', 'PKD'),
        ('PKS', 'PKS'),
        ('PMK', 'PMK'),
    ]
    
    id = models.AutoField(primary_key=True, verbose_name="ID")
    kategori = models.CharField(
        max_length=10,
        choices=KATEGORI_CHOICES,
        verbose_name="Kategori"
    )
    deskripsi = models.CharField(max_length=50, unique=True, verbose_name="Deskripsi")

    class Meta:
        verbose_name = "Dasar Hukum"
        verbose_name_plural = "Dasar Hukum"
        db_table = "dasar_hukum"
        ordering = ["id"]

    def __str__(self):
        return self.deskripsi
