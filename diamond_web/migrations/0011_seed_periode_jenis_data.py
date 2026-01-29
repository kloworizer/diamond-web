# Generated migration - Seed PeriodeJenisData

from django.db import migrations

# Sample PeriodeJenisData data
PERIODE_JENIS_DATA_MAPPING = [
    {"id_sub_jenis_data": "KM0330101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None},
    {"id_sub_jenis_data": "KM0330102", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None},
    {"id_sub_jenis_data": "LM0030101", "periode": "Tahunan", "start_date": "2024-01-01", "end_date": None},
    {"id_sub_jenis_data": "BI0010101", "periode": "Triwulanan", "start_date": "2024-01-01", "end_date": None},
    {"id_sub_jenis_data": "LM0100101", "periode": "Bulanan", "start_date": "2024-01-01", "end_date": None},
]


def seed_periode_jenis_data(apps, schema_editor):
    """Seeds the PeriodeJenisData model with initial data."""
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    
    for item in PERIODE_JENIS_DATA_MAPPING:
        try:
            jenis_data = JenisDataILAP.objects.get(id_sub_jenis_data=item["id_sub_jenis_data"])
            periode = PeriodePengiriman.objects.get(deskripsi=item["periode"])
            
            PeriodeJenisData.objects.get_or_create(
                id_sub_jenis_data_ilap=jenis_data,
                id_periode_pengiriman=periode,
                defaults={
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                }
            )
        except Exception as e:
            print(f"Warning: Could not create PeriodeJenisData for {item['id_sub_jenis_data']} - {item['periode']}: {e}")


def unseed_periode_jenis_data(apps, schema_editor):
    """Removes the initial data from PeriodeJenisData model."""
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in PERIODE_JENIS_DATA_MAPPING]
    PeriodeJenisData.objects.filter(
        id_sub_jenis_data_ilap__id_sub_jenis_data__in=sub_jenis_data_ids
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0010_seed_klasifikasi_jenis_data"),
    ]

    operations = [
        migrations.RunPython(seed_periode_jenis_data, reverse_code=unseed_periode_jenis_data),
    ]
