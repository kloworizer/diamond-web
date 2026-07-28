from django.db import models
from .ilap import ILAP
from .kpp import KPP
from .kanwil import Kanwil


class ILAPKPP(models.Model):
    """Wilayah mapping for an ILAP.

    A regional ILAP is not always attached to a KPP. ILAP with kategori
    ``PD`` (Pemerintah Daerah Kabupaten/Kota) map to a KPP, while ILAP with
    kategori ``PV`` (Pemerintah Daerah Provinsi) have no KPP counterpart and
    map straight to a Kanwil. The ``kpp`` flag tells which side of the
    relation is filled: ``True`` → ``id_kpp``, ``False`` → ``id_kanwil``.
    """

    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        db_column="id_ilap",
        verbose_name="ILAP",
        related_name="ilap_kpp_relations"
    )
    kpp = models.BooleanField(
        default=True,
        verbose_name="Relasi ke KPP",
        help_text="True: ILAP dipetakan ke KPP. False: ILAP dipetakan langsung ke Kanwil."
    )
    id_kpp = models.ForeignKey(
        KPP,
        on_delete=models.PROTECT,
        db_column="id_kpp",
        verbose_name="KPP",
        null=True,
        blank=True
    )
    id_kanwil = models.ForeignKey(
        Kanwil,
        on_delete=models.PROTECT,
        db_column="id_kanwil",
        verbose_name="Kanwil",
        null=True,
        blank=True,
        related_name="ilap_kanwil_relations"
    )

    class Meta:
        verbose_name = "ILAP KPP"
        verbose_name_plural = "ILAP KPP"
        db_table = "ilap_kpp"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["id_ilap"], name="ilk_id_ilap_idx"),
            models.Index(fields=["id_kpp"], name="ilk_id_kpp_idx"),
            models.Index(fields=["id_kanwil"], name="ilk_id_kanwil_idx"),
        ]

    @property
    def kanwil(self):
        """Return the Kanwil this row points to, directly or through its KPP."""
        if self.kpp:
            return self.id_kpp.id_kanwil if self.id_kpp else None
        return self.id_kanwil

    def __str__(self):
        if self.kpp:
            return f"ILAP {self.id_ilap_id} - KPP {self.id_kpp_id}"
        return f"ILAP {self.id_ilap_id} - Kanwil {self.id_kanwil_id}"
