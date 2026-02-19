from django.db import models
from django.contrib.auth.models import User
from .ilap import ILAP


class TandaTerimaData(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    nomor_tanda_terima = models.CharField(max_length=50, unique=True, verbose_name="Nomor Tanda Terima")
    tanggal_tanda_terima = models.DateTimeField(verbose_name="Tanggal Tanda Terima")
    id_ilap = models.ForeignKey(
        ILAP,
        on_delete=models.PROTECT,
        db_column="id_ilap",
        verbose_name="ILAP"
    )
    deskripsi = models.CharField(max_length=255, verbose_name="Deskripsi")
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

    def __str__(self):
        return f"{self.nomor_tanda_terima}"

    @property
    def nama_ILAP(self):
        return self.id_ILAP.nama_ILAP

    @property
    def daftar_jenis_data(self):
        return ", ".join(
            [j.nama_jenis_data for j in self.id_ILAP.jenisdataILAP_set.all()]
        )

    @property
    def periode_data(self):
        data = self.id_ILAP.jenisdataILAP_set.first()
        return data.periode_data if data else None