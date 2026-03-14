# Generated migration - Add periode_penerimaan field to PeriodePengiriman

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0030_periodejenisdata_akhir_penyampaian"),
    ]

    operations = [
        migrations.AddField(
            model_name='periodepengiriman',
            name='periode_penerimaan',
            field=models.CharField(default='', max_length=50, verbose_name='Periode Penerimaan'),
            preserve_default=False,
        ),
    ]
