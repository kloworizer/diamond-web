# Generated squashed migration - Seed PeriodePengiriman data

from django.db import migrations

PERIODE_PENGIRIMAN_DATA = [
    "Harian",
    "Mingguan",
    "2 Mingguan",
    "Bulanan",
    "Triwulanan",
    "Kuartal",
    "Semester",
    "Tahunan",
]


def seed_periode_pengiriman(apps, schema_editor):
    """Seeds the PeriodePengiriman model with initial data."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    for deskripsi in PERIODE_PENGIRIMAN_DATA:
        PeriodePengiriman.objects.get_or_create(
            deskripsi=deskripsi
        )


def unseed_periode_pengiriman(apps, schema_editor):
    """Removes the initial data from the PeriodePengiriman model."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    PeriodePengiriman.objects.filter(deskripsi__in=PERIODE_PENGIRIMAN_DATA).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0007_seed_klasifikasi_tabel"),
    ]

    operations = [
        migrations.RunPython(seed_periode_pengiriman, reverse_code=unseed_periode_pengiriman),
    ]
