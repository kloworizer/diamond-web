from django.db import models
from .tanda_terima_data import TandaTerimaData
from .tiket import Tiket


class DetilTandaTerima(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_tanda_terima = models.ForeignKey(
        TandaTerimaData,
        on_delete=models.CASCADE,
        db_column="id_tanda_terima",
        verbose_name="Tanda Terima Data",
        related_name="detil_items"
    )
    id_tiket = models.ForeignKey(
        Tiket,
        on_delete=models.CASCADE,
        db_column="id_tiket",
        verbose_name="Tiket"
    )

    class Meta:
        verbose_name = "Detil Tanda Terima"
        verbose_name_plural = "Detil Tanda Terima"
        db_table = "detil_tanda_terima"
        ordering = ["id"]
        unique_together = [['id_tanda_terima', 'id_tiket']]

    def __str__(self):
        return f"{self.id_tanda_terima} - {self.id_tiket}"
