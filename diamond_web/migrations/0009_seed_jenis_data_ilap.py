# Generated migration - Seed JenisDataILAP

from django.db import migrations

# Sample JenisDataILAP data
JENIS_DATA_ILAP_DATA = [
    {
        "id_kategori_ilap": "KM",
        "id_ilap": "KM033",
        "id_jenis_data": "KM03301",
        "id_sub_jenis_data": "KM0330101",
        "nama_jenis_data": "Data Keuangan",
        "nama_sub_jenis_data": "Laporan Realisasi Anggaran",
        "nama_tabel_I": "tabel_realisasi_anggaran_i",
        "nama_tabel_U": "tabel_realisasi_anggaran_u",
        "id_jenis_tabel": "Transaksi",
    },
    {
        "id_kategori_ilap": "KM",
        "id_ilap": "KM033",
        "id_jenis_data": "KM03301",
        "id_sub_jenis_data": "KM0330102",
        "nama_jenis_data": "Data Keuangan",
        "nama_sub_jenis_data": "Laporan Neraca",
        "nama_tabel_I": "tabel_neraca_i",
        "nama_tabel_U": "tabel_neraca_u",
        "id_jenis_tabel": "Transaksi",
    },
    {
        "id_kategori_ilap": "LM",
        "id_ilap": "LM003",
        "id_jenis_data": "LM00301",
        "id_sub_jenis_data": "LM0030101",
        "nama_jenis_data": "Data Statistik",
        "nama_sub_jenis_data": "Data Penduduk",
        "nama_tabel_I": "tabel_penduduk_i",
        "nama_tabel_U": "tabel_penduduk_u",
        "id_jenis_tabel": "Master",
    },
    {
        "id_kategori_ilap": "BI",
        "id_ilap": "BI001",
        "id_jenis_data": "BI00101",
        "id_sub_jenis_data": "BI0010101",
        "nama_jenis_data": "Data Perbankan",
        "nama_sub_jenis_data": "Laporan Posisi Keuangan Bank",
        "nama_tabel_I": "tabel_posisi_keuangan_i",
        "nama_tabel_U": "tabel_posisi_keuangan_u",
        "id_jenis_tabel": "Transaksi",
    },
    {
        "id_kategori_ilap": "LM",
        "id_ilap": "LM010",
        "id_jenis_data": "LM01001",
        "id_sub_jenis_data": "LM0100101",
        "nama_jenis_data": "Data Keuangan",
        "nama_sub_jenis_data": "Laporan Keuangan Lembaga Jasa Keuangan",
        "nama_tabel_I": "tabel_keuangan_ljk_i",
        "nama_tabel_U": "tabel_keuangan_ljk_u",
        "id_jenis_tabel": "Transaksi",
    },
]


def seed_jenis_data_ilap(apps, schema_editor):
    """Seeds the JenisDataILAP model with initial data."""
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    ILAP = apps.get_model("diamond_web", "ILAP")
    JenisTabel = apps.get_model("diamond_web", "JenisTabel")
    
    for item in JENIS_DATA_ILAP_DATA:
        try:
            kategori = KategoriILAP.objects.get(id_kategori=item["id_kategori_ilap"])
            ilap = ILAP.objects.get(id_ilap=item["id_ilap"])
            jenis_tabel = JenisTabel.objects.get(deskripsi=item["id_jenis_tabel"])
            
            JenisDataILAP.objects.get_or_create(
                id_sub_jenis_data=item["id_sub_jenis_data"],
                defaults={
                    "id_kategori_ilap": kategori,
                    "id_ilap": ilap,
                    "id_jenis_data": item["id_jenis_data"],
                    "nama_jenis_data": item["nama_jenis_data"],
                    "nama_sub_jenis_data": item["nama_sub_jenis_data"],
                    "nama_tabel_I": item["nama_tabel_I"],
                    "nama_tabel_U": item["nama_tabel_U"],
                    "id_jenis_tabel": jenis_tabel,
                }
            )
        except Exception as e:
            print(f"Warning: Could not create JenisDataILAP {item['id_sub_jenis_data']}: {e}")


def unseed_jenis_data_ilap(apps, schema_editor):
    """Removes the initial data from JenisDataILAP model."""
    JenisDataILAP = apps.get_model("diamond_web", "JenisDataILAP")
    sub_jenis_data_ids = [item["id_sub_jenis_data"] for item in JENIS_DATA_ILAP_DATA]
    JenisDataILAP.objects.filter(id_sub_jenis_data__in=sub_jenis_data_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0008_seed_periode_pengiriman"),
    ]

    operations = [
        migrations.RunPython(seed_jenis_data_ilap, reverse_code=unseed_jenis_data_ilap),
    ]
