# Generated migration - Seed Kategori Wilayah data

from django.db import migrations

KATEGORI_WILAYAH_DATA = [
    {"deskripsi": "Regional"},
    {"deskripsi": "Nasional"},
    {"deskripsi": "Internasional"},
]


def seed_kategori_wilayah(apps, schema_editor):
    """Seeds the KategoriWilayah table with initial data."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    
    for item in KATEGORI_WILAYAH_DATA:
        KategoriWilayah.objects.get_or_create(
            deskripsi=item["deskripsi"],
            defaults={"deskripsi": item["deskripsi"]}
        )


def unseed_kategori_wilayah(apps, schema_editor):
    """Removes the initial data from the KategoriWilayah table."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    descriptions_to_delete = [item["deskripsi"] for item in KATEGORI_WILAYAH_DATA]
    KategoriWilayah.objects.filter(deskripsi__in=descriptions_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0005_seed_jenis_tabel"),
    ]

    operations = [
        migrations.RunPython(seed_kategori_wilayah, reverse_code=unseed_kategori_wilayah),
    ]
