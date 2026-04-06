# Generated migration - Rename deskripsi to periode_penyampaian in PeriodePengiriman

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0031_periodepengiriman_periode_penerimaan"),
    ]

    operations = [
        migrations.RenameField(
            model_name='periodepengiriman',
            old_name='deskripsi',
            new_name='periode_penyampaian',
        ),
    ]
