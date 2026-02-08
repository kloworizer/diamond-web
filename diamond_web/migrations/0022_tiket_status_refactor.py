# Generated migration to add backup and tanda_terima fields and update status values

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0021_remove_picp3de_id_sub_jenis_data_ilap_and_more'),
    ]

    operations = [
        # Add new boolean fields
        migrations.AddField(
            model_name='tiket',
            name='backup',
            field=models.BooleanField(default=False, verbose_name='Backup Direkam'),
        ),
        migrations.AddField(
            model_name='tiket',
            name='tanda_terima',
            field=models.BooleanField(default=False, verbose_name='Tanda Terima Dibuat'),
        ),
        # Update status values: map old to new
        # 2 (Backup direkam) -> 1 (keep status 1, set backup=True)
        # 3 (Tanda Terima dibuat) -> 1 (keep status 1, set tanda_terima=True)
        # 4 (Diteliti) -> 2
        # 5 (Dikembalikan) -> 3
        # 6 (Dikirim ke PIDE) -> 4
        # 7 (Identifikasi) -> 5
        # 8 (Pengendalian Mutu) -> 6
        # 9 (Dibatalkan) -> 7
        # 10 (Selesai) -> 8
        migrations.RunPython(
            code=lambda apps, schema_editor: update_status_values(apps, schema_editor),
            reverse_code=lambda apps, schema_editor: None,
        ),
    ]


def update_status_values(apps, schema_editor):
    """Update tiket status values and set backup/tanda_terima flags."""
    Tiket = apps.get_model('diamond_web', 'Tiket')
    
    # Map old status to new status
    status_map = {
        2: 1,  # Backup direkam
        3: 1,  # Tanda Terima dibuat
        4: 2,  # Diteliti
        5: 3,  # Dikembalikan
        6: 4,  # Dikirim ke PIDE
        7: 5,  # Identifikasi
        8: 6,  # Pengendalian Mutu
        9: 7,  # Dibatalkan
        10: 8, # Selesai
    }
    
    for tiket in Tiket.objects.all():
        old_status = tiket.status
        
        # Set backup flag for old status 2
        if old_status == 2:
            tiket.backup = True
        
        # Set tanda_terima flag for old status 3
        if old_status == 3:
            tiket.tanda_terima = True
        
        # Map old status to new status
        if old_status in status_map:
            tiket.status = status_map[old_status]
        
        tiket.save()
