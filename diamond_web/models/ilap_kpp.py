from django.db import models
from .ilap import ILAP
from .kpp import KPP


class ILAPKPP(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        db_column="id_ilap",
        verbose_name="ILAP",
        related_name="ilap_kpp_relations"
    )
    id_kpp = models.ForeignKey(
        KPP,
        on_delete=models.PROTECT,
        db_column="id_kpp",
        verbose_name="KPP"
    )

    class Meta:
        verbose_name = "ILAP KPP"
        verbose_name_plural = "ILAP KPP"
        db_table = "ilap_kpp"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["id_ilap"], name="ilk_id_ilap_idx"),
            models.Index(fields=["id_kpp"], name="ilk_id_kpp_idx"),
        ]

    def __str__(self):
        return f"ILAP {self.id_ilap_id} - KPP {self.id_kpp_id}"
