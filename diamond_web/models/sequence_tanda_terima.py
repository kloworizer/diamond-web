"""Model for managing the nomor_tanda_terima sequence per year."""

from django.db import models


class SequenceTandaTerima(models.Model):
    """Stores the last used sequence number for Tanda Terima per year.

    This allows administrators to set a custom starting sequence number
    for each year (e.g., start from 100 for 2026 so the next generated
    number is 101). If no entry exists for a given year, the system
    defaults to starting from 1.

    To prevent data integrity issues, entries cannot be edited once
    there are existing TandaTerimaData records for that year.
    """
    id = models.AutoField(primary_key=True, verbose_name="ID")
    tahun = models.IntegerField(
        unique=True,
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
        ordering = ["-tahun"]

    def __str__(self):
        return f"Tahun {self.tahun} - Nomor Terakhir: {self.nomor_terakhir}"

    @property
    def nomor_berikutnya(self):
        """Return the next number in the sequence."""
        return self.nomor_terakhir + 1
