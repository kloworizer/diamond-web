from django.db import models
from .ilap import ILAP
from .kpp import KPP


class ILAPKanwilKPP(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        verbose_name="ILAP",
        related_name="kanwil_kpp"
    )
    id_kpp = models.ForeignKey(
        KPP,
        on_delete=models.PROTECT,
        verbose_name="KPP",
        related_name="ilap_kanwil"
    )

    class Meta:
        verbose_name = "ILAP Kanwil KPP"
        verbose_name_plural = "ILAP Kanwil KPP"
        db_table = "ilap_kanwil_kpp"
        ordering = ["id"]
        unique_together = [['id_ilap', 'id_kpp']]

    def __str__(self):
        return f"{self.id_ilap} - {self.id_kpp}"
