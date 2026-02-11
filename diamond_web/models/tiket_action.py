from django.db import models
from django.contrib.auth.models import User
from .tiket import Tiket


class TiketAction(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_tiket = models.ForeignKey(
        Tiket,
        on_delete=models.PROTECT,
        db_column="id_tiket",
        verbose_name="Tiket"
    )
    id_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="id_user",
        verbose_name="User"
    )
    timestamp = models.DateTimeField(null=True, blank=True, verbose_name="Timestamp")
    action = models.IntegerField(null=True, blank=True, verbose_name="Action")
    catatan = models.CharField(max_length=255, null=True, blank=True, verbose_name="Catatan")

    class Meta:
        verbose_name = "Tiket Action"
        verbose_name_plural = "Tiket Actions"
        db_table = "tiket_action"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Action {self.action} by {self.id_user} on {self.timestamp}"
