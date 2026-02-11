from django.db import models
from django.contrib.auth.models import User
from .tiket import Tiket


class TiketPIC(models.Model):
    class Role(models.IntegerChoices):
        P3DE = 1, "P3DE"
        PIDE = 2, "PIDE"
        PMDE = 3, "PMDE"
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
    role = models.IntegerField(null=True, blank=True, verbose_name="Role", choices=Role.choices)
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Tiket PIC"
        verbose_name_plural = "Tiket PICs"
        db_table = "tiket_pic"
        ordering = ["id"]

    def __str__(self):
        return f"Tiket {self.id_tiket} - PIC {self.id_user} (Role {self.role})"
