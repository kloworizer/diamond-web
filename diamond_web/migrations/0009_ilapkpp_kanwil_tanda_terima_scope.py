# Generated manually: allow ILAP → Kanwil mapping (kategori PV) and scope
# Tanda Terima per Kanwil / ND Pengantar instead of per ILAP only.

from django.db import migrations, models
import django.db.models.deletion


def flag_existing_relations_as_kpp(apps, schema_editor):
    """Every pre-existing ILAPKPP row was a KPP mapping — keep it that way."""
    ILAPKPP = apps.get_model("diamond_web", "ILAPKPP")
    ILAPKPP.objects.filter(id_kpp__isnull=False).update(kpp=True)


def backfill_tanda_terima_kanwil(apps, schema_editor):
    """Fill `id_kanwil` / `nomor_nd_pengantar` for existing tanda terima.

    Existing records are all ILAP-scoped. Regional ones (ILAP mapped to a
    KPP) also get their Kanwil recorded so the new per-Kanwil listing and
    document generation have something to show, without dropping `id_ilap`.
    """
    TandaTerimaData = apps.get_model("diamond_web", "TandaTerimaData")
    ILAPKPP = apps.get_model("diamond_web", "ILAPKPP")

    kanwil_by_ilap = {}
    for rel in ILAPKPP.objects.select_related("id_kpp").all():
        if rel.id_ilap_id in kanwil_by_ilap:
            continue
        if rel.kpp and rel.id_kpp_id:
            kanwil_by_ilap[rel.id_ilap_id] = rel.id_kpp.id_kanwil_id
        elif rel.id_kanwil_id:
            kanwil_by_ilap[rel.id_ilap_id] = rel.id_kanwil_id

    for tanda_terima in TandaTerimaData.objects.filter(id_kanwil__isnull=True).iterator():
        kanwil_id = kanwil_by_ilap.get(tanda_terima.id_ilap_id)
        if kanwil_id:
            tanda_terima.id_kanwil_id = kanwil_id
            tanda_terima.save(update_fields=["id_kanwil"])


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0008_tiket_special_request'),
    ]

    operations = [
        # --- ILAPKPP: KPP mapping becomes optional, Kanwil mapping added ---
        migrations.AddField(
            model_name='ilapkpp',
            name='kpp',
            field=models.BooleanField(
                default=True,
                help_text='True: ILAP dipetakan ke KPP. False: ILAP dipetakan langsung ke Kanwil.',
                verbose_name='Relasi ke KPP',
            ),
        ),
        migrations.AddField(
            model_name='ilapkpp',
            name='id_kanwil',
            field=models.ForeignKey(
                blank=True,
                db_column='id_kanwil',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ilap_kanwil_relations',
                to='diamond_web.kanwil',
                verbose_name='Kanwil',
            ),
        ),
        migrations.AlterField(
            model_name='ilapkpp',
            name='id_kpp',
            field=models.ForeignKey(
                blank=True,
                db_column='id_kpp',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='diamond_web.kpp',
                verbose_name='KPP',
            ),
        ),
        migrations.AddIndex(
            model_name='ilapkpp',
            index=models.Index(fields=['id_kanwil'], name='ilk_id_kanwil_idx'),
        ),
        migrations.RunPython(
            flag_existing_relations_as_kpp,
            reverse_code=migrations.RunPython.noop,
        ),

        # --- TandaTerimaData: scope per Kanwil and/or ND Pengantar ---
        migrations.AddField(
            model_name='tandaterimadata',
            name='id_kanwil',
            field=models.ForeignKey(
                blank=True,
                db_column='id_kanwil',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='tanda_terima_data',
                to='diamond_web.kanwil',
                verbose_name='Kanwil',
            ),
        ),
        migrations.AddField(
            model_name='tandaterimadata',
            name='nomor_nd_pengantar',
            field=models.CharField(blank=True, max_length=80, verbose_name='Nomor ND Pengantar'),
        ),
        migrations.AlterField(
            model_name='tandaterimadata',
            name='id_ilap',
            field=models.ForeignKey(
                blank=True,
                db_column='id_ilap',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='diamond_web.ilap',
                verbose_name='ILAP',
            ),
        ),
        migrations.RunPython(
            backfill_tanda_terima_kanwil,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
