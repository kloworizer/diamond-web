# Generated migration - Seed Jenis Tabel data

from django.db import migrations

JENIS_TABEL_DATA = [
    {"deskripsi": "Master"},
    {"deskripsi": "Transaksi"},
    {"deskripsi": "Unstructured"},
]


def seed_jenis_tabel(apps, schema_editor):
    """Seeds the JenisTabel table with initial data."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    
    for item in JENIS_TABEL_DATA:
        JenisTabel.objects.get_or_create(
            deskripsi=item["deskripsi"],
            defaults={"deskripsi": item["deskripsi"]}
        )


def unseed_jenis_tabel(apps, schema_editor):
    """Removes the initial data from the JenisTabel table."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    descriptions_to_delete = [item["deskripsi"] for item in JENIS_TABEL_DATA]
    JenisTabel.objects.filter(deskripsi__in=descriptions_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0003_seed_kategori_ilap"),
    ]

    operations = [
        migrations.RunPython(seed_jenis_tabel, reverse_code=unseed_jenis_tabel),
    ]
