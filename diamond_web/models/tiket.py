from django.db import models
from .periode_jenis_data import PeriodeJenisData


class Tiket(models.Model):
    id = models.AutoField(primary_key=True, verbose_name="ID")
    nomor_tiket = models.CharField(max_length=17, null=True, blank=True, verbose_name="Nomor Tiket")
    id_periode_data = models.ForeignKey(
        PeriodeJenisData,
        on_delete=models.CASCADE,
        db_column="id_periode_data",
        verbose_name="Periode Jenis Data"
    )
    periode = models.IntegerField(null=True, blank=True, verbose_name="Periode")
    tahun = models.IntegerField(null=True, blank=True, verbose_name="Tahun")
    status = models.IntegerField(null=True, blank=True, verbose_name="Status")
    tgl_terima_vertikal = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Terima Vertikal")
    tgl_terima_dip = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Terima DIP")
    tgl_teliti = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Teliti")
    baris_p3de = models.IntegerField(null=True, blank=True, verbose_name="Baris P3DE")
    tgl_nadine = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Nadine")
    tgl_kirim_pide = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Kirim PIDE")
    tgl_dibatalkan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dibatalkan")
    tgl_dikembalikan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dikembalikan")
    baris_i = models.IntegerField(null=True, blank=True, verbose_name="Baris I")
    baris_u = models.IntegerField(null=True, blank=True, verbose_name="Baris U")
    baris_res = models.IntegerField(null=True, blank=True, verbose_name="Baris Res")
    baris_cde = models.IntegerField(null=True, blank=True, verbose_name="Baris CDE")
    tgl_transfer = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Transfer")
    tgl_rematch = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Rematch")
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
