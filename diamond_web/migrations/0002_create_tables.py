# Generated squashed migration - Create all tables

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name='KategoriIlap',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('id_kategori', models.CharField(max_length=2, unique=True, verbose_name='ID Kategori')),
                ('nama_kategori', models.CharField(max_length=50, unique=True, verbose_name='Nama Kategori')),
            ],
            options={
                'verbose_name': 'Kategori ILAP',
                'verbose_name_plural': 'Kategori ILAP',
                'db_table': 'kategori_ilap',
                'ordering': ['id_kategori'],
            },
        ),
        migrations.CreateModel(
            name='KategoriWilayah',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('deskripsi', models.CharField(max_length=50, unique=True, verbose_name='Deskripsi')),
            ],
            options={
                'verbose_name': 'Kategori Wilayah',
                'verbose_name_plural': 'Kategori Wilayah',
                'db_table': 'kategori_wilayah',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='JenisTabel',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('deskripsi', models.CharField(max_length=50, unique=True, verbose_name='Deskripsi')),
            ],
            options={
                'verbose_name': 'Jenis Tabel',
                'verbose_name_plural': 'Jenis Tabel',
                'db_table': 'jenis_tabel',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='KlasifikasiTabel',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('deskripsi', models.CharField(max_length=50, unique=True, verbose_name='Deskripsi')),
            ],
            options={
                'verbose_name': 'Klasifikasi Tabel',
                'verbose_name_plural': 'Klasifikasi Tabel',
                'db_table': 'klasifikasi_tabel',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='PeriodePengiriman',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('deskripsi', models.CharField(max_length=50, unique=True, verbose_name='Deskripsi')),
            ],
            options={
                'verbose_name': 'Periode Pengiriman',
                'verbose_name_plural': 'Periode Pengiriman',
                'db_table': 'periode_pengiriman',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ILAP',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('id_ilap', models.CharField(max_length=5, unique=True, verbose_name='ID ILAP')),
                ('nama_ilap', models.CharField(max_length=150, verbose_name='Nama ILAP')),
                ('id_kategori', models.ForeignKey(db_column='id_kategori', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.KategoriIlap', verbose_name='ID Kategori')),
                ('id_kategori_wilayah', models.ForeignKey(db_column='id_kategori_wilayah', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.KategoriWilayah', verbose_name='Kategori Wilayah')),
            ],
            options={
                'verbose_name': 'ILAP',
                'verbose_name_plural': 'ILAP',
                'db_table': 'ilap',
                'ordering': ['id_ilap'],
            },
        ),
        migrations.CreateModel(
            name='JenisDataILAP',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('id_jenis_data', models.CharField(max_length=7, verbose_name='ID Jenis Data')),
                ('id_sub_jenis_data', models.CharField(max_length=9, verbose_name='ID Sub Jenis Data')),
                ('nama_jenis_data', models.CharField(max_length=255, verbose_name='Nama Jenis Data')),
                ('nama_sub_jenis_data', models.CharField(max_length=255, verbose_name='Nama Sub Jenis Data')),
                ('nama_tabel_I', models.CharField(max_length=255, verbose_name='Nama Tabel I')),
                ('nama_tabel_U', models.CharField(max_length=255, verbose_name='Nama Tabel U')),
                ('id_kategori_ilap', models.ForeignKey(db_column='id_kategori_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.KategoriIlap', verbose_name='Kategori ILAP')),
                ('id_ilap', models.ForeignKey(db_column='id_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.ILAP', verbose_name='ILAP')),
                ('id_jenis_tabel', models.ForeignKey(db_column='id_jenis_tabel', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisTabel', verbose_name='Jenis Tabel')),
            ],
            options={
                'verbose_name': 'Jenis Data ILAP',
                'verbose_name_plural': 'Jenis Data ILAP',
                'db_table': 'jenis_data_ilap',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='KlasifikasiJenisData',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('id_jenis_data_ilap', models.ForeignKey(db_column='id_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Jenis Data ILAP')),
                ('id_klasifikasi_tabel', models.ForeignKey(db_column='id_klasifikasi_tabel', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.KlasifikasiTabel', verbose_name='Klasifikasi Tabel')),
            ],
            options={
                'verbose_name': 'Klasifikasi Jenis Data',
                'verbose_name_plural': 'Klasifikasi Jenis Data',
                'db_table': 'klasifikasi_jenis_data',
                'ordering': ['id'],
                'unique_together': [['id_jenis_data_ilap', 'id_klasifikasi_tabel']],
            },
        ),
        migrations.CreateModel(
            name='PeriodeJenisData',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(db_column='id_sub_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Sub Jenis Data ILAP')),
                ('id_periode_pengiriman', models.ForeignKey(db_column='id_periode_pengiriman', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.PeriodePengiriman', verbose_name='Periode Pengiriman')),
            ],
            options={
                'verbose_name': 'Periode Jenis Data',
                'verbose_name_plural': 'Periode Jenis Data',
                'db_table': 'periode_jenis_data',
                'ordering': ['id'],
            },
        ),
        
    ] 
        migrations.CreateModel(
            name='PICP3DE',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(db_column='id_sub_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Sub Jenis Data ILAP')),
                ('id_user', models.ForeignKey(db_column='id_user', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'PIC P3DE',
                'verbose_name_plural': 'PIC P3DE',
                'db_table': 'pic_p3de',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='PICPIDE',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(db_column='id_sub_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Sub Jenis Data ILAP')),
                ('id_user', models.ForeignKey(db_column='id_user', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'PIC PIDE',
                'verbose_name_plural': 'PIC PIDE',
                'db_table': 'pic_pide',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='PICPMDE',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(db_column='id_sub_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Sub Jenis Data ILAP')),
                ('id_user', models.ForeignKey(db_column='id_user', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'PIC PMDE',
                'verbose_name_plural': 'PIC PMDE',
                'db_table': 'pic_pmde',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='DurasiJatuhTempo',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('durasi', models.IntegerField(verbose_name='Durasi')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data', models.ForeignKey(db_column='id_sub_jenis_data', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.JenisDataILAP', verbose_name='Sub Jenis Data ILAP')),
                ('seksi', models.ForeignKey(db_column='seksi', on_delete=django.db.models.deletion.CASCADE, to='auth.Group', verbose_name='Seksi')),
            ],
            options={
                'verbose_name': 'Durasi Jatuh Tempo',
                'verbose_name_plural': 'Durasi Jatuh Tempo',
                'db_table': 'durasi_jatuh_tempo',
                'ordering': ['id'],
            },
        ),
    ]
