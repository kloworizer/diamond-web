from django.db import models
from .tiket import Tiket


class TiketKdTahap(models.Model):
    """Jumlah baris per KD_TAHAP dan flag QC di tabel I Oracle untuk satu tiket.

    Diisi oleh management command ``sync_tiket_kd_tahap`` dan menu Sinkronisasi
    KD Tahap di detil tiket; setiap sinkronisasi mengganti seluruh baris milik
    tiket tersebut. `qc` kosong = baris yang belum di-QC.
    """
    id = models.AutoField(primary_key=True, verbose_name="ID")
    id_tiket = models.ForeignKey(
        Tiket,
        on_delete=models.CASCADE,
        db_column="id_tiket",
        verbose_name="Tiket",
        related_name="kd_tahap_set",
    )
    kd_tahap = models.CharField(max_length=50, null=True, blank=True, verbose_name="KD Tahap")
    qc = models.CharField(max_length=50, null=True, blank=True, verbose_name="QC")
    jumlah_baris = models.IntegerField(verbose_name="Jumlah Baris")

    class Meta:
        verbose_name = "Tiket KD Tahap"
        verbose_name_plural = "Tiket KD Tahap"
        db_table = "tiket_kd_tahap"
        ordering = ["id_tiket", "kd_tahap", "qc"]
        constraints = [
            models.UniqueConstraint(fields=["id_tiket", "kd_tahap", "qc"], name="tiket_kd_tahap_qc_uniq"),
        ]

    def __str__(self):
        return f"{self.id_tiket_id} - {self.kd_tahap}/{self.qc}: {self.jumlah_baris}"
