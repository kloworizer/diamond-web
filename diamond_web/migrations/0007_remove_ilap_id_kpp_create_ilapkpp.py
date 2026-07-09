# Generated manually to remove ilap.id_kpp and create ilap_kpp table
# Includes data migration to preserve existing ilap.id_kpp values

from django.db import migrations, models
import django.db.models.deletion


def copy_ilap_kpp_data(apps, schema_editor):
    """Copy existing ILAP.id_kpp values to the new ILAPKPP junction table."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    ILAPKPP = apps.get_model("diamond_web", "ILAPKPP")
    
    for ilap in ILAP.objects.all().iterator():
        # Get the old id_kpp value (still available before RemoveField)
        kpp_id = getattr(ilap, 'id_kpp_id', None)
        if kpp_id is not None:
            ILAPKPP.objects.get_or_create(
                id_ilap=ilap,
                id_kpp_id=kpp_id,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0006_sequencetandaterima'),
    ]

    operations = [
        # Step 1: Create the ILAPKPP junction table FIRST (before removing data)
        migrations.CreateModel(
            name='ILAPKPP',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('id_ilap', models.ForeignKey(
                    db_column='id_ilap',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='ilap_kpp_relations',
                    to='diamond_web.ilap',
                    verbose_name='ILAP',
                )),
                ('id_kpp', models.ForeignKey(
                    db_column='id_kpp',
                    on_delete=django.db.models.deletion.PROTECT,
                    to='diamond_web.kpp',
                    verbose_name='KPP',
                )),
            ],
            options={
                'verbose_name': 'ILAP KPP',
                'verbose_name_plural': 'ILAP KPP',
                'db_table': 'ilap_kpp',
                'ordering': ['id'],
            },
        ),
        # Step 2: Add indexes for the new table
        migrations.AddIndex(
            model_name='ilapkpp',
            index=models.Index(fields=['id_ilap'], name='ilk_id_ilap_idx'),
        ),
        migrations.AddIndex(
            model_name='ilapkpp',
            index=models.Index(fields=['id_kpp'], name='ilk_id_kpp_idx'),
        ),
        # Step 3: Copy existing ILAP.id_kpp data to ILAPKPP before removing the field
        migrations.RunPython(
            copy_ilap_kpp_data,
            reverse_code=migrations.RunPython.noop,
        ),
        # Step 4: Remove the old index on id_kpp
        migrations.RemoveIndex(
            model_name='ilap',
            name='ilap_kpp_idx',
        ),
        # Step 5: Remove the id_kpp field from ILAP
        migrations.RemoveField(
            model_name='ilap',
            name='id_kpp',
        ),
    ]
