# Generated migration for consolidating PIC models
from django.db import migrations, models
import django.db.models.deletion


def migrate_pic_data_forward(apps, schema_editor):
    """Migrate data from old PIC tables to new unified PIC table"""
    PIC = apps.get_model('diamond_web', 'PIC')
    PICP3DE = apps.get_model('diamond_web', 'PICP3DE')
    PICPIDE = apps.get_model('diamond_web', 'PICPIDE')
    PICPMDE = apps.get_model('diamond_web', 'PICPMDE')
    
    # Migrate PICP3DE data
    for old_pic in PICP3DE.objects.all():
        PIC.objects.create(
            tipe='P3DE',
            id_sub_jenis_data_ilap=old_pic.id_sub_jenis_data_ilap,
            id_user=old_pic.id_user,
            start_date=old_pic.start_date,
            end_date=old_pic.end_date
        )
    
    # Migrate PICPIDE data
    for old_pic in PICPIDE.objects.all():
        PIC.objects.create(
            tipe='PIDE',
            id_sub_jenis_data_ilap=old_pic.id_sub_jenis_data_ilap,
            id_user=old_pic.id_user,
            start_date=old_pic.start_date,
            end_date=old_pic.end_date
        )
    
    # Migrate PICPMDE data
    for old_pic in PICPMDE.objects.all():
        PIC.objects.create(
            tipe='PMDE',
            id_sub_jenis_data_ilap=old_pic.id_sub_jenis_data_ilap,
            id_user=old_pic.id_user,
            start_date=old_pic.start_date,
            end_date=old_pic.end_date
        )


def migrate_pic_data_backward(apps, schema_editor):
    """Migrate data back from unified PIC table to old tables (for rollback)"""
    PIC = apps.get_model('diamond_web', 'PIC')
    PICP3DE = apps.get_model('diamond_web', 'PICP3DE')
    PICPIDE = apps.get_model('diamond_web', 'PICPIDE')
    PICPMDE = apps.get_model('diamond_web', 'PICPMDE')
    
    # Migrate back to PICP3DE
    for pic in PIC.objects.filter(tipe='P3DE'):
        PICP3DE.objects.create(
            id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap,
            id_user=pic.id_user,
            start_date=pic.start_date,
            end_date=pic.end_date
        )
    
    # Migrate back to PICPIDE
    for pic in PIC.objects.filter(tipe='PIDE'):
        PICPIDE.objects.create(
            id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap,
            id_user=pic.id_user,
            start_date=pic.start_date,
            end_date=pic.end_date
        )
    
    # Migrate back to PICPMDE
    for pic in PIC.objects.filter(tipe='PMDE'):
        PICPMDE.objects.create(
            id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap,
            id_user=pic.id_user,
            start_date=pic.start_date,
            end_date=pic.end_date
        )


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0019_tiket_add_prioritas_durasi_fields'),
    ]

    operations = [
        # Create new unified PIC table
        migrations.CreateModel(
            name='PIC',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('tipe', models.CharField(choices=[('P3DE', 'PIC P3DE'), ('PIDE', 'PIC PIDE'), ('PMDE', 'PIC PMDE')], db_index=True, max_length=10, verbose_name='Tipe PIC')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('end_date', models.DateField(blank=True, default=None, null=True, verbose_name='End Date')),
                ('id_sub_jenis_data_ilap', models.ForeignKey(db_column='id_sub_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, to='diamond_web.jenisdatailap', verbose_name='Sub Jenis Data ILAP')),
                ('id_user', models.ForeignKey(db_column='id_user', on_delete=django.db.models.deletion.CASCADE, to='auth.user', verbose_name='User')),
            ],
            options={
                'verbose_name': 'PIC',
                'verbose_name_plural': 'PIC',
                'db_table': 'pic',
                'ordering': ['tipe', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='pic',
            index=models.Index(fields=['tipe', 'id_sub_jenis_data_ilap'], name='pic_tipe_id_sub_idx'),
        ),
        # Migrate data from old tables to new table
        migrations.RunPython(migrate_pic_data_forward, migrate_pic_data_backward),
        # Delete old tables (commented out for safety - uncomment after verifying data)
        # migrations.DeleteModel(name='PICP3DE'),
        # migrations.DeleteModel(name='PICPIDE'),
        # migrations.DeleteModel(name='PICPMDE'),
    ]
