import django.db.models.deletion
from django.db import migrations, models


# Child rows the canonical parent already has an equivalent of. Repointing
# those would leave duplicates behind, so the merge drops them instead. Most
# come straight from each model's own unique constraint; durasi_jatuh_tempo
# declares none, but the rows hanging off the duplicate parents are the seeded
# yearly defaults, identical to the ones the canonical parent already carries.
DEDUPE_FIELDS = {
    "klasifikasijenisdata": ("id_klasifikasi_tabel_id",),
    "jenisprioritasdata": ("tahun",),
    "durasijatuhtempo": ("seksi_id", "durasi", "start_date", "end_date"),
}


def backfill_and_merge(apps, schema_editor):
    """Move the table names into their own rows, then collapse duplicate parents.

    Runs before the unique constraint on `id_sub_jenis_data` is added, and is
    what makes that constraint satisfiable: the duplicate parents exist only to
    carry a second or third table name, and once those names have a home of
    their own the extra parents have nothing left to hold.
    """
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    NamaTabelJenisData = apps.get_model("diamond_web", "NamaTabelJenisData")

    # 1. Every jenis data carrying a table name gets it as its utama row.
    NamaTabelJenisData.objects.bulk_create(
        [
            NamaTabelJenisData(
                id_jenis_data_ilap_id=pk,
                nama_tabel_I=tabel_i,
                nama_tabel_U=tabel_u or "",
                utama=True,
                aktif=True,
            )
            for pk, tabel_i, tabel_u in (
                JenisDataILAP.objects
                .exclude(nama_tabel_I="")
                .exclude(nama_tabel_I__isnull=True)
                .values_list("id", "nama_tabel_I", "nama_tabel_U")
            )
        ],
        batch_size=1000,
    )

    # 2. Collapse the sub jenis data recorded as several parent rows. The
    #    lowest id is the canonical one: Meta.ordering is ["id"], so it is the
    #    row every single-value lookup has been picking all along, and keeping
    #    it means the merge changes nothing a reader sees.
    duplicated = list(
        JenisDataILAP.objects
        .values("id_sub_jenis_data")
        .annotate(n=models.Count("id"))
        .filter(n__gt=1)
        .values_list("id_sub_jenis_data", flat=True)
    )

    related = [
        (rel.related_model, rel.field.name)
        for rel in JenisDataILAP._meta.related_objects
        if (rel.one_to_many or rel.one_to_one)
        and rel.related_model._meta.model_name != "namatabeljenisdata"
    ]

    for kode in duplicated:
        rows = list(JenisDataILAP.objects.filter(id_sub_jenis_data=kode).order_by("id"))
        canonical, secondaries = rows[0], rows[1:]

        for secondary in secondaries:
            # The secondary's table name joins the canonical as a non-utama row.
            for nama_tabel in NamaTabelJenisData.objects.filter(id_jenis_data_ilap=secondary):
                already_there = NamaTabelJenisData.objects.filter(
                    id_jenis_data_ilap=canonical,
                    nama_tabel_I=nama_tabel.nama_tabel_I,
                ).exists()
                if already_there:
                    nama_tabel.delete()
                else:
                    nama_tabel.id_jenis_data_ilap = canonical
                    nama_tabel.utama = False
                    nama_tabel.save(update_fields=["id_jenis_data_ilap", "utama"])

            # Everything else hanging off the secondary moves across, minus the
            # rows the canonical already has an equivalent of.
            for model, field_name in related:
                dedupe = DEDUPE_FIELDS.get(model._meta.model_name, ())
                for child in model.objects.filter(**{field_name: secondary}):
                    if dedupe:
                        clash = model.objects.filter(
                            **{field_name: canonical},
                            **{f: getattr(child, f) for f in dedupe},
                        ).exists()
                        if clash:
                            child.delete()
                            continue
                    setattr(child, field_name, canonical)
                    child.save(update_fields=[field_name])

            # PROTECT on the remaining relations makes this the safety net: if
            # anything was missed above, the migration stops here instead of
            # quietly dropping it.
            secondary.delete()

    # 3. Restore the invariant the cache columns depend on: a jenis data with
    #    table names has exactly one utama, and the parent mirrors it.
    without_utama = list(
        NamaTabelJenisData.objects
        .values("id_jenis_data_ilap")
        .annotate(n_utama=models.Count("id", filter=models.Q(utama=True)))
        .filter(n_utama=0)
        .values_list("id_jenis_data_ilap", flat=True)
    )
    for jdi_id in without_utama:
        first = (
            NamaTabelJenisData.objects
            .filter(id_jenis_data_ilap_id=jdi_id)
            .order_by("id")
            .first()
        )
        first.utama = True
        first.save(update_fields=["utama"])
        JenisDataILAP.objects.filter(id=jdi_id).update(
            nama_tabel_I=first.nama_tabel_I,
            nama_tabel_U=first.nama_tabel_U,
        )


def drop_nama_tabel_rows(apps, schema_editor):
    """The parent rows the merge collapsed cannot be brought back.

    Reversing only empties the new table so the operations above it can be
    reversed in turn; restoring the duplicate parents needs the database backup
    taken before this migration ran.
    """
    NamaTabelJenisData = apps.get_model("diamond_web", "NamaTabelJenisData")
    NamaTabelJenisData.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0014_kasubdit_pde_group'),
    ]

    operations = [
        migrations.CreateModel(
            name='NamaTabelJenisData',
            fields=[
                ('create_date', models.DateField(blank=True, null=True, verbose_name='Create Date')),
                ('create_by', models.CharField(blank=True, max_length=9, null=True, verbose_name='Create By')),
                ('update_date', models.DateField(blank=True, null=True, verbose_name='Update Date')),
                ('update_by', models.CharField(blank=True, max_length=9, null=True, verbose_name='Update By')),
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('nama_tabel_I', models.CharField(max_length=255, verbose_name='Nama Tabel I')),
                ('nama_tabel_U', models.CharField(blank=True, max_length=255, verbose_name='Nama Tabel U')),
                ('utama', models.BooleanField(default=False, verbose_name='Utama')),
                ('aktif', models.BooleanField(default=True, verbose_name='Aktif')),
            ],
            options={
                'verbose_name': 'Nama Tabel Jenis Data',
                'verbose_name_plural': 'Nama Tabel Jenis Data',
                'db_table': 'nama_tabel_jenis_data',
                'ordering': ['-utama', 'id'],
            },
        ),
        migrations.AddField(
            model_name='namatabeljenisdata',
            name='id_jenis_data_ilap',
            field=models.ForeignKey(db_column='id_jenis_data_ilap', on_delete=django.db.models.deletion.CASCADE, related_name='nama_tabel_set', to='diamond_web.jenisdatailap', verbose_name='Jenis Data ILAP'),
        ),
        migrations.AddIndex(
            model_name='namatabeljenisdata',
            index=models.Index(fields=['nama_tabel_I'], name='ntjd_tabel_i_idx'),
        ),
        migrations.AddIndex(
            model_name='namatabeljenisdata',
            index=models.Index(fields=['id_jenis_data_ilap', 'aktif'], name='ntjd_jdi_aktif_idx'),
        ),
        migrations.AddConstraint(
            model_name='namatabeljenisdata',
            constraint=models.UniqueConstraint(fields=('id_jenis_data_ilap', 'nama_tabel_I'), name='ntjd_unik_per_jenis_data'),
        ),
        migrations.AddConstraint(
            model_name='namatabeljenisdata',
            constraint=models.UniqueConstraint(condition=models.Q(('utama', True)), fields=('id_jenis_data_ilap',), name='ntjd_satu_utama'),
        ),
        # The constraints above are in force while the merge runs, so a mistake
        # in it surfaces here rather than as bad data later.
        migrations.RunPython(backfill_and_merge, drop_nama_tabel_rows),
        # Last: only satisfiable once the merge has collapsed the duplicates.
        migrations.AddConstraint(
            model_name='jenisdatailap',
            constraint=models.UniqueConstraint(fields=('id_sub_jenis_data',), name='jdi_sub_jenis_data_unik'),
        ),
    ]
