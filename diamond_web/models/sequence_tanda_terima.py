"""Model for managing the nomor_tanda_terima sequence per year."""

from django.db import models


class SequenceTandaTerima(models.Model):
    """Stores the last used sequence number for Tanda Terima per seksi and year.

    Seksi P3DE and Seksi P3DER number their tanda terima in separate series
    (``…TTD/PJ.1031/…`` and ``…TTD/PJ.1032/…``), so each seksi has its own
    starting point per year.

    This allows administrators to set a custom starting sequence number
    for each year (e.g., start from 100 for 2026 so the next generated
    number is 101). If no entry exists for a given year, the system
    defaults to starting from 1.

    To prevent data integrity issues, entries cannot be edited once
    there are existing TandaTerimaData records for that year.
    """
    class Seksi(models.TextChoices):
        P3DE = 'P3DE', 'P3DE (PJ.1031)'
        P3DER = 'P3DER', 'P3DER (PJ.1032)'

    id = models.AutoField(primary_key=True, verbose_name="ID")
    seksi = models.CharField(
        max_length=5,
        choices=Seksi.choices,
        default=Seksi.P3DE,
        verbose_name="Seksi",
        help_text="Seksi pemilik seri nomor tanda terima"
    )
    tahun = models.IntegerField(
        verbose_name="Tahun",
        help_text="Tahun penerapan sequence"
    )
    nomor_terakhir = models.IntegerField(
        verbose_name="Nomor Terakhir",
        help_text="Nomor terakhir yang digunakan. Nomor berikutnya akan dimulai dari nilai ini + 1."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sequence Tanda Terima"
        verbose_name_plural = "Sequence Tanda Terima"
        db_table = "sequence_tanda_terima"
        ordering = ["-tahun", "seksi"]
        constraints = [
            models.UniqueConstraint(fields=["seksi", "tahun"], name="seq_tt_seksi_tahun_uniq"),
        ]

    def __str__(self):
        return f"{self.seksi} Tahun {self.tahun} - Nomor Terakhir: {self.nomor_terakhir}"

    @property
    def nomor_berikutnya(self):
        """Return the next number in the sequence."""
        return self.nomor_terakhir + 1
