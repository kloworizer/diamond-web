from django.db import models
from .jenis_data_ilap import JenisDataILAP

class JenisPrioritasData(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(blank=True, null=True, default=None, verbose_name="End Date")
    id_sub_jenis_data_ilap = models.ForeignKey(
        'JenisDataILAP',  # pastikan model ini ada
        on_delete=models.CASCADE,
        db_column='id_sub_jenis_data_ilap',
        verbose_name='Sub Jenis Data ILAP'
    )
    no_nd = models.CharField(max_length=20, verbose_name='No ND')
    tahun = models.CharField(max_length=4, verbose_name='Tahun')

    class Meta:
        db_table = 'jenis_prioritas_data'
        ordering = ['id']
        verbose_name = 'Jenis Prioritas Data'
        verbose_name_plural = 'Jenis Prioritas Data'
