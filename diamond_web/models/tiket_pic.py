from django.db import models
from django.db.models import Q
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
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    role = models.IntegerField(verbose_name="Role", choices=Role.choices)
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Tiket PIC"
        verbose_name_plural = "Tiket PICs"
        db_table = "tiket_pic"
        ordering = ["id"]
        indexes = [
            # Every PIC-scoping query in the app reads (id_user, role, active)
            # together; the plain id_user FK index leaves role and active to be
            # re-checked per fetched row. Partial, because no caller wants the
            # inactive assignments — which keeps the index a fraction of the
            # table and cache-resident.
            models.Index(
                fields=["id_user", "role"],
                condition=Q(active=True),
                name="tpic_user_role_act_idx",
            ),
            # The mirror direction: "who is the PIC of this tiket", and the
            # ~Exists(TiketPIC...) 'tanpa PIC' admin counts.
            models.Index(
                fields=["id_tiket", "role"],
                condition=Q(active=True),
                name="tpic_tiket_role_act_idx",
            ),
        ]

    def __str__(self):
        return f"Tiket {self.id_tiket} - PIC {self.id_user} (Role {self.role})"
