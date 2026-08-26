from django.db import models
from django.db.models import Q
from .jenis_data_ilap import JenisDataILAP
from .audit import AuditTrailModel


class NamaTabelJenisData(AuditTrailModel):
    """The bank data tables one sub jenis data lands in.

    A sub jenis data usually feeds a single table, but not always: a few are
    split across several, either by stage (`..._TAHAP2`, `..._TAHAP3`) or by
    source within one arrangement. That used to be recorded by duplicating the
    whole `JenisDataILAP` row, which left `id_sub_jenis_data` non-unique and
    every lookup by it picking whichever row came first. The table names live
    here instead, so the parent stays one row per sub jenis data.

    `JenisDataILAP.nama_tabel_I` and `nama_tabel_U` remain as a denormalised
    copy of the `utama` row. The reports, exports and detail pages that show a
    single table name read those columns; traversing this relation instead
    would fan their queries out to one row per table name, which is a silent
    wrong count rather than an error.
    """

    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_jenis_data_ilap = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.CASCADE,
        db_column="id_jenis_data_ilap",
        related_name="nama_tabel_set",
        verbose_name="Jenis Data ILAP"
    )
    nama_tabel_I = models.CharField(max_length=255, verbose_name="Nama Tabel I")
    nama_tabel_U = models.CharField(max_length=255, blank=True, verbose_name="Nama Tabel U")
    # The one mirrored into JenisDataILAP.nama_tabel_I/_U, and so the one every
    # single-value display shows. Exactly one per jenis data, enforced below.
    utama = models.BooleanField(default=False, verbose_name="Utama")
    aktif = models.BooleanField(default=True, verbose_name="Aktif")

    class Meta:
        verbose_name = "Nama Tabel Jenis Data"
        verbose_name_plural = "Nama Tabel Jenis Data"
        db_table = "nama_tabel_jenis_data"
        ordering = ["-utama", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["id_jenis_data_ilap", "nama_tabel_I"],
                name="ntjd_unik_per_jenis_data",
            ),
            models.UniqueConstraint(
                fields=["id_jenis_data_ilap"],
                condition=Q(utama=True),
                name="ntjd_satu_utama",
            ),
        ]
        indexes = [
            # The navbar table-name search and the nama tabel detail page both
            # start from the name and look for the jenis data feeding it.
            models.Index(fields=["nama_tabel_I"], name="ntjd_tabel_i_idx"),
            models.Index(fields=["id_jenis_data_ilap", "aktif"], name="ntjd_jdi_aktif_idx"),
        ]

    def __str__(self):
        return self.nama_tabel_I
