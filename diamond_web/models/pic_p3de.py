from django.db import models
from django.contrib.auth.models import User
from .jenis_data_ilap import JenisDataILAP

class PICP3DE(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_sub_jenis_data_ilap = models.ForeignKey(
        JenisDataILAP,
        on_delete=models.CASCADE,
        db_column="id_sub_jenis_data_ilap",
        verbose_name="Sub Jenis Data ILAP"
    )
    id_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="id_user",
        verbose_name="User"
    )
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(null=True, blank=True, default=None, verbose_name="End Date")

    class Meta:
        verbose_name = "PIC P3DE"
        verbose_name_plural = "PIC P3DE"
        db_table = "pic_p3de"
        ordering = ["id"]

    def __str__(self):
        return f"{self.id_sub_jenis_data_ilap} - {self.id_user.username}"
