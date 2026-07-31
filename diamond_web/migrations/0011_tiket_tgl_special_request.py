from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0010_seed_ilap_kanwil_mapping'),
    ]

    operations = [
        migrations.AddField(
            model_name='tiket',
            name='tgl_special_request',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Tanggal Jatuh Tempo Permintaan Khusus'),
        ),
    ]
