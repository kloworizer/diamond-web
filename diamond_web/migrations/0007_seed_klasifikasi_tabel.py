# Generated migration - Seed Klasifikasi Tabel data

from django.db import migrations

KLASIFIKASI_TABEL_DATA = [
    {"deskripsi": "PMK"},
    {"deskripsi": "PKS"},
    {"deskripsi": "KSWP"},
    {"deskripsi": "EOI"},
    {"deskripsi": "ADHOC"},
    {"deskripsi": "DAPEN"},
]


def seed_klasifikasi_tabel(apps, schema_editor):
    """Seeds the KlasifikasiTabel table with initial data."""
    KlasifikasiTabel = apps.get_model("diamond_web", "KlasifikasiTabel")
    
    for item in KLASIFIKASI_TABEL_DATA:
        KlasifikasiTabel.objects.get_or_create(
            deskripsi=item["deskripsi"],
            defaults={"deskripsi": item["deskripsi"]}
        )


def unseed_klasifikasi_tabel(apps, schema_editor):
    """Removes the initial data from the KlasifikasiTabel table."""
    KlasifikasiTabel = apps.get_model("diamond_web", "KlasifikasiTabel")
    descriptions_to_delete = [item["deskripsi"] for item in KLASIFIKASI_TABEL_DATA]
    KlasifikasiTabel.objects.filter(deskripsi__in=descriptions_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0006_seed_kategori_wilayah"),
    ]

    operations = [
        migrations.RunPython(seed_klasifikasi_tabel, reverse_code=unseed_klasifikasi_tabel),
    ]
