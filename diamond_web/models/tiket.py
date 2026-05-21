from django.db import models
from .periode_jenis_data import PeriodeJenisData
from .jenis_prioritas_data import JenisPrioritasData
from .durasi_jatuh_tempo import DurasiJatuhTempo
from .bentuk_data import BentukData
from .cara_penyampaian import CaraPenyampaian
from .status_penelitian import StatusPenelitian
from ..constants.tiket_status import STATUS_LABELS


class Tiket(models.Model):

    STATUS_CHOICES = [(k, v) for k, v in STATUS_LABELS.items()]

    SATUAN_DATA_CHOICES = [
        (1, 'Baris'),
    ]

    id = models.AutoField(primary_key=True, verbose_name="ID")
    nomor_tiket = models.CharField(max_length=17, verbose_name="Nomor Tiket")
    old_db = models.BooleanField(default=False, verbose_name="Old DB")
    status_tiket = models.IntegerField(choices=STATUS_CHOICES, verbose_name="Status Tiket")
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
    periode = models.IntegerField(verbose_name="Periode")
    tahun = models.IntegerField(verbose_name="Tahun")
    penyampaian = models.IntegerField(default=0, verbose_name="Penyampaian")
    nomor_surat_pengantar = models.CharField(max_length=50, verbose_name="Nomor Surat Pengantar")
    tanggal_surat_pengantar = models.DateTimeField(verbose_name="Tanggal Surat Pengantar")
    nama_pengirim = models.CharField(max_length=50, verbose_name="Nama Pengirim")
    id_bentuk_data = models.ForeignKey(
        BentukData,
        on_delete=models.PROTECT,
        db_column="bentuk_data",
        verbose_name="Bentuk Data"
    )
    id_cara_penyampaian = models.ForeignKey(
        CaraPenyampaian,
        on_delete=models.PROTECT,
        db_column="cara_penyampaian",
        verbose_name="Cara Penyampaian"
    )
    status_ketersediaan_data = models.BooleanField(default=True, verbose_name="Status Ketersediaan Data")
    alasan_ketidaktersediaan = models.CharField(max_length=100, null=True, blank=True, verbose_name="Alasan Ketidaktersediaan")
    baris_diterima = models.IntegerField(verbose_name="Baris Diterima")
    satuan_data = models.IntegerField(default=1, choices=SATUAN_DATA_CHOICES, verbose_name="Satuan Data")
    tgl_terima_vertikal = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Terima Vertikal")
    tgl_terima_dip = models.DateTimeField(verbose_name="Tanggal Terima DIP")
    backup = models.BooleanField(default=False, verbose_name="Backup Direkam")
    tanda_terima = models.BooleanField(default=False, verbose_name="Tanda Terima Dibuat")
    id_status_penelitian = models.ForeignKey(
        StatusPenelitian,
        on_delete=models.PROTECT,
        db_column="status_penelitian",
        verbose_name="Status Penelitian",
        null=True,
        blank=True
    )
    tgl_teliti = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Teliti")
    baris_lengkap = models.IntegerField(null=True, blank=True, verbose_name="Baris Lengkap")
    baris_tidak_lengkap = models.IntegerField(null=True, blank=True, verbose_name="Baris Tidak Lengkap")
    tgl_nadine = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Nadine")
    nomor_nd_nadine = models.CharField(max_length=255, null=True, blank=True, verbose_name="Nomor ND Nadine")
    tgl_kirim_pide = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Kirim PIDE")
    tgl_dibatalkan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dibatalkan")
    tgl_dikembalikan = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Dikembalikan")
    tgl_rekam_pide = models.DateTimeField(null=True, blank=True, verbose_name="Tanggal Rekam PIDE")
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
    qc_p = models.IntegerField(null=True, blank=True, verbose_name="QC P")
    qc_x = models.IntegerField(null=True, blank=True, verbose_name="QC X")
    qc_w = models.IntegerField(null=True, blank=True, verbose_name="QC W")
    qc_f = models.IntegerField(null=True, blank=True, verbose_name="QC F")
    qc_a = models.IntegerField(null=True, blank=True, verbose_name="QC A")
    qc_c = models.IntegerField(null=True, blank=True, verbose_name="QC C")
    qc_n = models.IntegerField(null=True, blank=True, verbose_name="QC N")
    qc_y = models.IntegerField(null=True, blank=True, verbose_name="QC Y")
    qc_z = models.IntegerField(null=True, blank=True, verbose_name="QC Z")
    qc_u = models.IntegerField(null=True, blank=True, verbose_name="QC U")
    qc_e = models.IntegerField(null=True, blank=True, verbose_name="QC E")
    qc_v = models.IntegerField(null=True, blank=True, verbose_name="QC V")
    qc_r = models.IntegerField(null=True, blank=True, verbose_name="QC R")
    qc_d = models.IntegerField(null=True, blank=True, verbose_name="QC D")

    class Meta:
        verbose_name = "Tiket"
        verbose_name_plural = "Tiket"
        db_table = "tiket"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["id_periode_data"], name="tiket_periode_data_idx"),
            models.Index(fields=["penyampaian"], name="tiket_penyampaian_idx"),
            models.Index(fields=["tahun", "periode"], name="tiket_thn_prd_idx"),
            models.Index(fields=["id_periode_data", "periode", "tahun", "penyampaian"], name="tiket_lookup_idx"),
            models.Index(fields=["tgl_terima_dip"], name="tiket_terima_dip_idx"),
            models.Index(fields=["tgl_terima_vertikal"], name="tiket_terima_vert_idx"),
        ]

    def __str__(self):
        return f"Tiket {self.id} - Periode {self.periode} Tahun {self.tahun}"
