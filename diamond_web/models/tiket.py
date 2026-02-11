from django.db import models
from .periode_jenis_data import PeriodeJenisData
from .jenis_prioritas_data import JenisPrioritasData
from .durasi_jatuh_tempo import DurasiJatuhTempo


class Tiket(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    nomor_tiket = models.CharField(max_length=17, null=True, blank=True, verbose_name="Nomor Tiket")
    id_periode_data = models.ForeignKey(
        PeriodeJenisData,
        on_delete=models.PROTECT,
        db_column="id_periode_data",
        verbose_name="Periode Jenis Data"
    )
    id_jenis_prioritas_data = models.ForeignKey(
        JenisPrioritasData,
        on_delete=models.PROTECT,
        db_column="id_jenis_prioritas_data",
        verbose_name="Jenis Prioritas Data",
        null=True,
        blank=True
    )
    periode = models.IntegerField(null=True, blank=True, verbose_name="Periode")
    tahun = models.IntegerField(null=True, blank=True, verbose_name="Tahun")
    status = models.IntegerField(null=True, blank=True, verbose_name="Status")
    tgl_terima_vertikal = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Terima Vertikal")
    tgl_terima_dip = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Terima DIP")
    tgl_teliti = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Teliti")
    backup = models.BooleanField(default=False, verbose_name="Backup Direkam")
    tanda_terima = models.BooleanField(default=False, verbose_name="Tanda Terima Dibuat")
    baris_p3de = models.IntegerField(null=True, blank=True, verbose_name="Baris P3DE")
    tgl_nadine = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Nadine")
    nomor_nd_nadine = models.CharField(max_length=255, null=True, blank=True, verbose_name="Nomor ND Nadine")
    tgl_kirim_pide = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Kirim PIDE")
    tgl_dibatalkan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dibatalkan")
    tgl_dikembalikan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dikembalikan")
    id_durasi_jatuh_tempo_pide = models.ForeignKey(
        DurasiJatuhTempo,
        on_delete=models.PROTECT,
        db_column="id_durasi_jatuh_tempo_pide",
        verbose_name="Durasi Jatuh Tempo PIDE",
        null=True,
        blank=True,
        related_name='durasi_jatuh_tempo_pide_tikets'
    )
    baris_i = models.IntegerField(null=True, blank=True, verbose_name="Baris I")
    baris_u = models.IntegerField(null=True, blank=True, verbose_name="Baris U")
    baris_res = models.IntegerField(null=True, blank=True, verbose_name="Baris Res")
    baris_cde = models.IntegerField(null=True, blank=True, verbose_name="Baris CDE")
    tgl_transfer = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Transfer")
    tgl_rematch = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Rematch")
    id_durasi_jatuh_tempo_pmde = models.ForeignKey(
        DurasiJatuhTempo,
        on_delete=models.PROTECT,
        db_column="id_durasi_jatuh_tempo_pmde",
        verbose_name="Durasi Jatuh Tempo PMDE",
        null=True,
        blank=True,
        related_name='durasi_jatuh_tempo_pmde_tikets'
    )
    sudah_qc = models.IntegerField(null=True, blank=True, verbose_name="Sudah QC")
    belum_qc = models.IntegerField(null=True, blank=True, verbose_name="Belum QC")
    lolos_qc = models.IntegerField(null=True, blank=True, verbose_name="Lolos QC")
    tidak_lolos_qc = models.IntegerField(null=True, blank=True, verbose_name="Tidak Lolos QC")
    qc_c = models.IntegerField(null=True, blank=True, verbose_name="QC C")

    class Meta:
        verbose_name = "Tiket"
        verbose_name_plural = "Tiket"
        db_table = "tiket"
        ordering = ["id"]

    def __str__(self):
        return f"Tiket {self.id} - Periode {self.periode} Tahun {self.tahun}"
