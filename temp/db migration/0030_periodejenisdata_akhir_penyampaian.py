# Generated migration - Add akhir_penyampaian field to PeriodeJenisData

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0029_alter_backupdata_id_tiket_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name='periodejenisdata',
            name='akhir_penyampaian',
            field=models.IntegerField(default=0, verbose_name='Akhir Penyampaian'),
            preserve_default=False,
        ),
    ]
