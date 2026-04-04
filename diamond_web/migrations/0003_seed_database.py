# Generated migration - Seed database with initial data

from django.db import migrations

KATEGORI_ILAP_DATA = [
    {"kode": "AS", "nama": "ASOSIASI"},
    {"kode": "BI", "nama": "BANK SENTRAL"},
    {"kode": "BU", "nama": "BADAN USAHA MILIK NEGARA"},
    {"kode": "EI", "nama": "EXCHANGE OF INFORMATION"},
    {"kode": "KM", "nama": "KEMENTERIAN"},
    {"kode": "LK", "nama": "LEMBAGA KEUANGAN"},
    {"kode": "LM", "nama": "LEMBAGA"},
    {"kode": "PD", "nama": "PEMERINTAH DAERAH KABUPATEN/KOTA"},
    {"kode": "PK", "nama": "KPP ATAU KANWIL DJP"},
    {"kode": "PL", "nama": "PIHAK LAIN"},
    {"kode": "PV", "nama": "PEMERINTAH DAERAH PROVINSI"},
]

KATEGORI_WILAYAH_DATA = [
    {"deskripsi": "Regional"},
    {"deskripsi": "Nasional"},
    {"deskripsi": "Internasional"},
]

JENIS_TABEL_DATA = [
    {"deskripsi": "Diidentifikasi"},
    {"deskripsi": "Tidak Diidentifikasi"},
    {"deskripsi": "Tidak Terstruktur"},
]

DASAR_HUKUM_DATA = [
    {"deskripsi": "PMK"},
    {"deskripsi": "PKS"},
    {"deskripsi": "KSWP"},
    {"deskripsi": "EOI"},
    {"deskripsi": "ADHOC"},
    {"deskripsi": "DAPEN"},
]

PERIODE_PENGIRIMAN_DATA = [
    "Harian",
    "Mingguan",
    "2 Mingguan",
    "Bulanan",
    "Triwulanan",
    "Kuartal",
    "Semester",
    "Tahunan",
]

STATUS_DATA_DATA = [
    {"deskripsi": "Data Utama"},
    {"deskripsi": "Pengecualian"},
]

BENTUK_DATA_DATA = [
    {"deskripsi": "Hardcopy"},
    {"deskripsi": "Softcopy"},
]

CARA_PENYAMPAIAN_DATA = [
    {"deskripsi": "Langsung"},
    {"deskripsi": "Online"},
    {"deskripsi": "Nadine"},
]

MEDIA_BACKUP_DATA = [
    {"deskripsi": "NAS"},
    {"deskripsi": "Sharepoint"},
    {"deskripsi": "Datawarehouse"},
]

STATUS_PENELITIAN_DATA = [
    {"deskripsi": "Lengkap"},
    {"deskripsi": "Lengkap Sebagian"},
    {"deskripsi": "Tidak Lengkap"},
]


def seed_kategori_ilap(apps, schema_editor):
    """Seeds the KategoriILAP model with initial data."""
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    for item in KATEGORI_ILAP_DATA:
        KategoriILAP.objects.get_or_create(
            id_kategori=item["kode"], defaults={"nama_kategori": item["nama"]}
        )


def unseed_kategori_ilap(apps, schema_editor):
    """Removes the initial data from the KategoriILAP model."""
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    kodes_to_delete = [item["kode"] for item in KATEGORI_ILAP_DATA]
    KategoriILAP.objects.filter(id_kategori__in=kodes_to_delete).delete()


def seed_kategori_wilayah(apps, schema_editor):
    """Seeds the KategoriWilayah model with initial data."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    for item in KATEGORI_WILAYAH_DATA:
        KategoriWilayah.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_kategori_wilayah(apps, schema_editor):
    """Removes the initial data from the KategoriWilayah model."""
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")
    descriptions_to_delete = [item["deskripsi"] for item in KATEGORI_WILAYAH_DATA]
    KategoriWilayah.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_jenis_tabel(apps, schema_editor):
    """Seeds the JenisTabel model with initial data."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    for item in JENIS_TABEL_DATA:
        JenisTabel.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_jenis_tabel(apps, schema_editor):
    """Removes the initial data from the JenisTabel model."""
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    descriptions_to_delete = [item["deskripsi"] for item in JENIS_TABEL_DATA]
    JenisTabel.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_dasar_hukum(apps, schema_editor):
    """Seeds the DasarHukum model with initial data."""
    DasarHukum = apps.get_model("diamond_web", "DasarHukum")
    for item in DASAR_HUKUM_DATA:
        DasarHukum.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_dasar_hukum(apps, schema_editor):
    """Removes the initial data from the DasarHukum model."""
    DasarHukum = apps.get_model("diamond_web", "DasarHukum")
    descriptions_to_delete = [item["deskripsi"] for item in DASAR_HUKUM_DATA]
    DasarHukum.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_periode_pengiriman(apps, schema_editor):
    """Seeds the PeriodePengiriman model with initial data."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    for periode in PERIODE_PENGIRIMAN_DATA:
        PeriodePengiriman.objects.get_or_create(
            periode_penyampaian=periode,
            defaults={"periode_penerimaan": periode}
        )


def unseed_periode_pengiriman(apps, schema_editor):
    """Removes the initial data from the PeriodePengiriman model."""
    PeriodePengiriman = apps.get_model("diamond_web", "PeriodePengiriman")
    PeriodePengiriman.objects.filter(periode_penyampaian__in=PERIODE_PENGIRIMAN_DATA).delete()


def seed_status_data(apps, schema_editor):
    """Seeds the StatusData model with initial data."""
    StatusData = apps.get_model("diamond_web", "StatusData")
    for item in STATUS_DATA_DATA:
        StatusData.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_status_data(apps, schema_editor):
    """Removes the initial data from the StatusData model."""
    StatusData = apps.get_model("diamond_web", "StatusData")
    descriptions_to_delete = [item["deskripsi"] for item in STATUS_DATA_DATA]
    StatusData.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_bentuk_data(apps, schema_editor):
    """Seeds the BentukData model with initial data."""
    BentukData = apps.get_model("diamond_web", "BentukData")
    for item in BENTUK_DATA_DATA:
        BentukData.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_bentuk_data(apps, schema_editor):
    """Removes the initial data from the BentukData model."""
    BentukData = apps.get_model("diamond_web", "BentukData")
    descriptions_to_delete = [item["deskripsi"] for item in BENTUK_DATA_DATA]
    BentukData.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_cara_penyampaian(apps, schema_editor):
    """Seeds the CaraPenyampaian model with initial data."""
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    for item in CARA_PENYAMPAIAN_DATA:
        CaraPenyampaian.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_cara_penyampaian(apps, schema_editor):
    """Removes the initial data from the CaraPenyampaian model."""
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    descriptions_to_delete = [item["deskripsi"] for item in CARA_PENYAMPAIAN_DATA]
    CaraPenyampaian.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_media_backup(apps, schema_editor):
    """Seeds the MediaBackup model with initial data."""
    MediaBackup = apps.get_model("diamond_web", "MediaBackup")
    for item in MEDIA_BACKUP_DATA:
        MediaBackup.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_media_backup(apps, schema_editor):
    """Removes the initial data from the MediaBackup model."""
    MediaBackup = apps.get_model("diamond_web", "MediaBackup")
    descriptions_to_delete = [item["deskripsi"] for item in MEDIA_BACKUP_DATA]
    MediaBackup.objects.filter(deskripsi__in=descriptions_to_delete).delete()


def seed_status_penelitian(apps, schema_editor):
    """Seeds the StatusPenelitian model with initial data."""
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    for item in STATUS_PENELITIAN_DATA:
        StatusPenelitian.objects.get_or_create(
            deskripsi=item["deskripsi"]
        )


def unseed_status_penelitian(apps, schema_editor):
    """Removes the initial data from the StatusPenelitian model."""
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    descriptions_to_delete = [item["deskripsi"] for item in STATUS_PENELITIAN_DATA]
    StatusPenelitian.objects.filter(deskripsi__in=descriptions_to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_kategori_ilap, reverse_code=unseed_kategori_ilap),
        migrations.RunPython(seed_kategori_wilayah, reverse_code=unseed_kategori_wilayah),
        migrations.RunPython(seed_jenis_tabel, reverse_code=unseed_jenis_tabel),
        migrations.RunPython(seed_dasar_hukum, reverse_code=unseed_dasar_hukum),
        migrations.RunPython(seed_periode_pengiriman, reverse_code=unseed_periode_pengiriman),
        migrations.RunPython(seed_status_data, reverse_code=unseed_status_data),
        migrations.RunPython(seed_bentuk_data, reverse_code=unseed_bentuk_data),
        migrations.RunPython(seed_cara_penyampaian, reverse_code=unseed_cara_penyampaian),
        migrations.RunPython(seed_media_backup, reverse_code=unseed_media_backup),
        migrations.RunPython(seed_status_penelitian, reverse_code=unseed_status_penelitian),
    ]
