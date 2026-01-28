# Generated migration - Seed KlasifikasiJenisData

from django.db import migrations

# Sample KlasifikasiJenisData data (mapping jenis data to klasifikasi tabel)
KLASIFIKASI_JENIS_DATA_MAPPING = [
    {"id_sub_jenis_data": "KM0330101", "klasifikasi": "PMK"},
    {"id_sub_jenis_data": "KM0330101", "klasifikasi": "KSWP"},
    {"id_sub_jenis_data": "KM0330102", "klasifikasi": "PMK"},
    {"id_sub_jenis_data": "LM0030101", "klasifikasi": "ADHOC"},
    {"id_sub_jenis_data": "BI0010101", "klasifikasi": "PMK"},
    {"id_sub_jenis_data": "BI0010101", "klasifikasi": "PKS"},
    {"id_sub_jenis_data": "LM0100101", "klasifikasi": "PMK"},
    {"id_sub_jenis_data": "LM0100101", "klasifikasi": "EOI"},
]


def seed_klasifikasi_jenis_data(apps, schema_editor):
    """Seeds the KlasifikasiJenisData model with initial data."""
    KlasifikasiJenisData = apps.get_model("diamond_web", "KlasifikasiJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    KlasifikasiTabel = apps.get_model("diamond_web", "KlasifikasiTabel")
    
    for item in KLASIFIKASI_JENIS_DATA_MAPPING:
        try:
            jenis_data = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            klasifikasi = KlasifikasiTabel.objects.get(deskripsi=item["klasifikasi"])
            
            KlasifikasiJenisData.objects.get_or_create(
                id_jenis_data_ilap=jenis_data,
                id_klasifikasi_tabel=klasifikasi
            )
        except Exception as e:
            print(f"Warning: Could not create KlasifikasiJenisData for {item['id_sub_jenis_data']} - {item['klasifikasi']}: {e}")


def unseed_klasifikasi_jenis_data(apps, schema_editor):
    """Removes the initial data from KlasifikasiJenisData model."""
    KlasifikasiJenisData = apps.get_model("diamond_web", "KlasifikasiJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    
    sub_jenis_data_ids = list(set([item["id_sub_jenis_data"] for item in KLASIFIKASI_JENIS_DATA_MAPPING]))
    KlasifikasiJenisData.objects.filter(
        id_jenis_data_ilap__id_sub_jenis_data__in=sub_jenis_data_ids
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0009_seed_jenis_data_ilap"),
    ]

    operations = [
        migrations.RunPython(seed_klasifikasi_jenis_data, reverse_code=unseed_klasifikasi_jenis_data),
    ]
