from django.db import models
from django.conf import settings
from .tiket import Tiket


class KirimPideTemp(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_temp = models.IntegerField(verbose_name="ID Temp")
    id_tiket = models.ForeignKey(
        Tiket,
        on_delete=models.PROTECT,
        db_column="id_tiket",
        verbose_name="Tiket",
    )
    id_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_user",
        verbose_name="User",
    )

    class Meta:
        verbose_name = "Kirim PIDE Temp"
        verbose_name_plural = "Kirim PIDE Temp"
        db_table = "kirim_pide_temp"
        ordering = ["id"]

    def __str__(self):
        return f"KirimPIDE Temp #{self.id_temp}"
