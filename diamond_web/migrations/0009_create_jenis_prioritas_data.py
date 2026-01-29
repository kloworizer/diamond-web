from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0008_seed_periode_pengiriman'),  # sesuaikan dengan migration terakhir
    ]

    operations = [
        migrations.CreateModel(
            name='JenisPrioritasData',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, null=True, default=None, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(
                    to='diamond_web.JenisDataILAP',
                    on_delete=django.db.models.deletion.CASCADE,
                    db_column='id_sub_jenis_data_ilap',
                    verbose_name='Sub Jenis Data ILAP'
                )),
                ('no_nd', models.CharField(max_length=20, verbose_name='No ND')),
                ('tahun', models.CharField(max_length=4, verbose_name='Tahun')),
            ],
            options={
                'db_table': 'jenis_prioritas_data',
                'ordering': ['id'],
                'verbose_name': 'Jenis Prioritas Data',
                'verbose_name_plural': 'Jenis Prioritas Data',
            },
        ),
    ]
