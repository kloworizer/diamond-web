from django.db import models
from django.contrib.auth.models import User
from .ilap import ILAP
from .kanwil import Kanwil


class TandaTerimaData(models.Model):
    """A receipt covering one or more tikets.

    A tanda terima is scoped either per Kanwil (regional ILAP — kategori PV
    and PD) or per ILAP (nasional/internasional ILAP). Exactly one of
    ``id_kanwil`` / ``id_ilap`` is filled. ``nomor_nd_pengantar`` optionally
    narrows the scope further to a single ND Pengantar.
    """

    id = models.AutoField(primary_key=True, verbose_name="ID")
    nomor_tanda_terima = models.IntegerField(verbose_name="Nomor Tanda Terima")
    tahun_terima = models.IntegerField(verbose_name="Tahun Terima")
    tanggal_tanda_terima = models.DateTimeField(verbose_name="Tanggal Tanda Terima")
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        db_column="id_ilap",
        verbose_name="ILAP",
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
        related_name="tanda_terima_data"
    )
    nomor_nd_pengantar = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Nomor ND Pengantar"
    )
    id_perekam = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="id_perekam",
        verbose_name="Perekam"
    )
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Tanda Terima Data"
        verbose_name_plural = "Tanda Terima Data"
        db_table = "tanda_terima_data"
        ordering = ["-tanggal_tanda_terima"]
        unique_together = ('nomor_tanda_terima', 'tahun_terima')

    def __str__(self):
        return self.nomor_tanda_terima_format

    @property
    def nomor_tanda_terima_format(self):
        """Returns formatted nomor tanda terima as 5 digit sequence.TTD/PJ.1031/year"""
        from ..utils.tanda_terima_nomor import format_nomor_tanda_terima

        return format_nomor_tanda_terima(self.nomor_tanda_terima, self.tahun_terima)

    @property
    def is_regional(self):
        """True when this tanda terima is scoped to a Kanwil."""
        return self.id_kanwil_id is not None

    @property
    def nama_ILAP(self):
        return self.id_ilap.nama_ilap if self.id_ilap else None

    @property
    def nama_sumber(self):
        """Label of whatever this tanda terima is scoped to (Kanwil or ILAP)."""
        if self.id_kanwil:
            return self.id_kanwil.nama_kanwil
        if self.id_ilap:
            return self.id_ilap.nama_ilap
        return '-'

    @property
    def daftar_jenis_data(self):
        if not self.id_ilap:
            # Kanwil-scoped: jenis data comes from the tikets themselves
            return ", ".join(
                sorted({
                    detil.id_tiket.id_periode_data.id_sub_jenis_data_ilap.nama_jenis_data
                    for detil in self.detil_items.select_related(
                        'id_tiket__id_periode_data__id_sub_jenis_data_ilap'
                    )
                    if detil.id_tiket.id_periode_data
                })
            )
        return ", ".join(
            [j.nama_jenis_data for j in self.id_ilap.jenisdatailap_set.all()]
        )

    @property
    def periode_data(self):
        if not self.id_ilap:
            return None
        data = self.id_ilap.jenisdatailap_set.first()
        if data is None:
            return None
        periode = data.periodejenisdata_set.first()
        return periode.id_periode_pengiriman.periode_penerimaan if periode else None
