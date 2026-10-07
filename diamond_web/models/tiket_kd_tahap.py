from django.db import models
from .tiket import Tiket


class TiketKdTahap(models.Model):
    """Jumlah baris per KD_TAHAP di tabel I Oracle untuk satu tiket.

    Diisi oleh management command ``sync_tiket_kd_tahap``; setiap kali command
    dijalankan, baris milik tiket yang berhasil di-query diganti seluruhnya.
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
    jumlah_baris = models.IntegerField(verbose_name="Jumlah Baris")

    class Meta:
        verbose_name = "Tiket KD Tahap"
        verbose_name_plural = "Tiket KD Tahap"
        db_table = "tiket_kd_tahap"
        ordering = ["id_tiket", "kd_tahap"]
        constraints = [
            models.UniqueConstraint(fields=["id_tiket", "kd_tahap"], name="tiket_kd_tahap_uniq"),
        ]

    def __str__(self):
        return f"{self.id_tiket_id} - {self.kd_tahap}: {self.jumlah_baris}"
