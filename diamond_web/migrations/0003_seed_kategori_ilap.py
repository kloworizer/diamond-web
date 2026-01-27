# Generated squashed migration - Seed KategoriIlap data

from django.db import migrations

KATEGORI_ILAP_DATA = [
    {"kode": "AS", "nama": "ASOSIASI"},
    {"kode": "BI", "nama": "BANK SENTRAL"},
    {"kode": "BU", "nama": "BADAN USAHA MILIK NEGARA"},
    {"kode": "EI", "nama": "EXCHANGE OF INFORMATION"},
    {"kode": "KM", "nama": "KEMENTERIAN"},
    {"kode": "LK", "nama": "LEMBAGA KEUANGAN"},
    {"kode": "LM", "nama": "LEMBAGA"},
    {"kode": "PD", "nama": "PEMERINTAH DAERAH KABUPATEN/KOTA"},
    {"kode": "PK", "nama": "KPP ATAU KANWIL DJP"},
    {"kode": "PL", "nama": "PIHAK LAIN"},
    {"kode": "PV", "nama": "PEMERINTAH DAERAH PROVINSI"},
]


def seed_kategori_ilap(apps, schema_editor):
    """Seeds the KategoriIlap model with initial data."""
    KategoriIlap = apps.get_model("diamond_web", "KategoriIlap")
    for item in KATEGORI_ILAP_DATA:
        KategoriIlap.objects.get_or_create(
            id_kategori=item["kode"], defaults={"nama_kategori": item["nama"]}
        )


def unseed_kategori_ilap(apps, schema_editor):
    """Removes the initial data from the KategoriIlap model."""
    KategoriIlap = apps.get_model("diamond_web", "KategoriIlap")
    kodes_to_delete = [item["kode"] for item in KATEGORI_ILAP_DATA]
    KategoriIlap.objects.filter(id_kategori__in=kodes_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0002_create_tables"),
    ]

    operations = [
        migrations.RunPython(seed_kategori_ilap, reverse_code=unseed_kategori_ilap),
    ]
