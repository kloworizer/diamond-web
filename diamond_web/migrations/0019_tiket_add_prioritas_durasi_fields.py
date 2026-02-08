# Generated migration to add jenis_prioritas_data and durasi_jatuh_tempo fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0018_alter_backupdata_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tiket',
            name='id_jenis_prioritas_data',
            field=models.ForeignKey(
                blank=True,
                db_column='id_jenis_prioritas_data',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='diamond_web.jenisprioritasdata',
                verbose_name='Jenis Prioritas Data'
            ),
        ),
        migrations.AddField(
            model_name='tiket',
            name='id_durasi_jatuh_tempo_pide',
            field=models.ForeignKey(
                db_column='id_durasi_jatuh_tempo_pide',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='durasi_jatuh_tempo_pide_tikets',
                to='diamond_web.durasijatuhtempo',
                verbose_name='Durasi Jatuh Tempo PIDE'
            ),
        ),
        migrations.AddField(
            model_name='tiket',
            name='id_durasi_jatuh_tempo_pmde',
            field=models.ForeignKey(
                db_column='id_durasi_jatuh_tempo_pmde',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='durasi_jatuh_tempo_pmde_tikets',
                to='diamond_web.durasijatuhtempo',
                verbose_name='Durasi Jatuh Tempo PMDE'
            ),
        ),
    ]
