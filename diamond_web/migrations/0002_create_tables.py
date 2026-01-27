# Generated squashed migration - Create all tables

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KategoriIlap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_kategori', models.CharField(max_length=2, unique=True, verbose_name='ID Kategori')),
                ('nama_kategori', models.CharField(max_length=50, verbose_name='Nama Kategori')),
            ],
            options={
                'verbose_name': 'Kategori ILAP',
                'verbose_name_plural': 'Kategori ILAP',
                'db_table': 'kategori_ilap',
                'ordering': ['id_kategori'],
            },
        ),
        migrations.CreateModel(
            name='ILAP',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('id_ilap', models.CharField(max_length=5, unique=True, verbose_name='ID ILAP')),
                ('nama_ilap', models.CharField(max_length=150, verbose_name='Nama ILAP')),
                ('id_kategori', models.ForeignKey(db_column='id_kategori', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.KategoriIlap', verbose_name='ID Kategori')),
            ],
            options={
                'verbose_name': 'ILAP',
                'verbose_name_plural': 'ILAP',
                'db_table': 'ilap',
                'ordering': ['id_ilap'],
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
    ]
