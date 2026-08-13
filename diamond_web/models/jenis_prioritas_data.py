from django.db import models
from .jenis_data_ilap import JenisDataILAP
from .audit import AuditTrailModel

class JenisPrioritasData(AuditTrailModel):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    start_date = models.DateField(verbose_name="Start Date")
    end_date = models.DateField(blank=True, null=True, default=None, verbose_name="End Date")
    id_sub_jenis_data_ilap = models.ForeignKey(
        'JenisDataILAP',
        on_delete=models.PROTECT,
        db_column='id_sub_jenis_data_ilap',
        verbose_name='Sub Jenis Data ILAP'
    )
    no_nd = models.CharField(max_length=20, verbose_name='No ND')
    tahun = models.CharField(max_length=4, verbose_name='Tahun')

    class Meta:
        db_table = 'jenis_prioritas_data'
        ordering = ['id']
        indexes = [
            # Serves prioritas_exists(): a correlated EXISTS matching the sub
            # jenis data whose prioritas window covers the tiket's tgl_terima_dip.
            models.Index(
                fields=['id_sub_jenis_data_ilap', 'start_date', 'end_date'],
                name='jpd_sub_dates_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['id_sub_jenis_data_ilap', 'tahun'],
                name='unique_subjenis_tahun'
            )
        ]
        verbose_name = 'Jenis Prioritas Data'
        verbose_name_plural = 'Jenis Prioritas Data'

    def __str__(self):
        return f"{self.id_sub_jenis_data_ilap} - {self.tahun}"
