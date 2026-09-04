"""Isi aturan durasi jatuh tempo awal, menirukan perilaku yang berlaku sekarang.

Sebelum ini durasi hasil Generate Otomatis berasal dari konstanta di
``views/durasi_jatuh_tempo.py`` (prioritas 45, non prioritas 85, PMDE saja).
Migrasi ini memindahkannya menjadi data, tanpa mengubah hasil apa pun:

* **Aturan umum** per seksi per tahun — PMDE 45/85 dan PIDE 35/90.
* **Pengecualian per sub jenis data**, diturunkan dari isi ``durasi_jatuh_tempo``
  yang ada: sub jenis data yang pada tahun prioritasnya tercatat berdurasi lain
  (di basis data produksi: 36 sub jenis data Bea dan Cukai berdurasi 14 hari)
  mendapat aturannya sendiri, sehingga angka itu tidak lagi bertahan hanya karena
  kebetulan tidak tersentuh generate.

Pengecualian sengaja diturunkan **per sub jenis data, bukan per ILAP**: di dalam
Bea dan Cukai sendiri nilainya campur — 139 baris berdurasi 14 dan 113 baris
berdurasi 45 — jadi aturan setingkat ILAP akan menyeret 113 baris itu ikut
berubah.

Tahun yang diisi hanya sampai tahun berjalan. Tahun berikutnya sengaja dibiarkan
kosong supaya harus ditetapkan sendiri lewat menu Aturan Durasi Jatuh Tempo —
generate melaporkan tahun tanpa aturan dan melewatinya, bukan menebak angkanya.
"""
from datetime import date

from django.db import migrations

START_YEAR = 2019

# Aturan umum yang berlaku sekarang, per nama grup seksi.
DEFAULTS = {
    'user_pmde': {'prioritas': 45, 'non_prioritas': 85},
    'user_pide': {'prioritas': 35, 'non_prioritas': 90},
}


def _prioritas_years(JenisPrioritasData):
    """``{(sub_jenis_data_id, tahun)}`` yang tercakup masa berlaku prioritas."""
    pairs = set()
    for start_date, end_date, sub_id in JenisPrioritasData.objects.values_list(
        'start_date', 'end_date', 'id_sub_jenis_data_ilap_id'
    ):
        if not start_date:
            continue
        akhir = end_date or date(date.today().year, 12, 31)
        for tahun in range(start_date.year, akhir.year + 1):
            pairs.add((sub_id, tahun))
    return pairs


def _exceptions(DurasiJatuhTempo, seksi, prioritas_pairs, durasi_prioritas):
    """Sub jenis data yang durasi prioritasnya berbeda dari aturan umum.

    Hanya baris pada tahun yang memang prioritas yang diperiksa — di tahun lain
    durasinya memang seharusnya nilai non prioritas. Sub jenis data yang
    nilainya tidak konsisten antar tahun dilewati: menebak satu angka untuknya
    bisa mengubah data yang benar.
    """
    per_sub = {}
    for sub_id, start_date, durasi in DurasiJatuhTempo.objects.filter(
        seksi=seksi
    ).values_list('id_sub_jenis_data_id', 'start_date', 'durasi'):
        if not start_date or (sub_id, start_date.year) not in prioritas_pairs:
            continue
        if durasi == durasi_prioritas:
            continue
        per_sub.setdefault(sub_id, set()).add(durasi)

    return {
        sub_id: values.pop()
        for sub_id, values in per_sub.items()
        if len(values) == 1
    }


def seed(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    AturanDurasiJatuhTempo = apps.get_model('diamond_web', 'AturanDurasiJatuhTempo')
    DurasiJatuhTempo = apps.get_model('diamond_web', 'DurasiJatuhTempo')
    JenisPrioritasData = apps.get_model('diamond_web', 'JenisPrioritasData')

    if AturanDurasiJatuhTempo.objects.exists():
        return

    today = date.today()
    years = list(range(START_YEAR, today.year + 1))
    prioritas_pairs = _prioritas_years(JenisPrioritasData)

    rows = []
    for nama_grup, durasi in DEFAULTS.items():
        seksi = Group.objects.filter(name=nama_grup).first()
        if seksi is None:
            continue

        for tahun in years:
            rows.append(AturanDurasiJatuhTempo(
                seksi=seksi,
                tahun=tahun,
                durasi_prioritas=durasi['prioritas'],
                durasi_non_prioritas=durasi['non_prioritas'],
                create_date=today,
                create_by='migrasi',
                update_date=today,
                update_by='migrasi',
            ))

        # Pengecualian berlaku untuk seluruh tahun yang diisi, bukan hanya tahun
        # yang kebetulan prioritas sekarang — supaya sub jenis data itu tetap
        # memakai durasinya sendiri bila kelak jadi prioritas di tahun lain.
        for sub_id, durasi_khusus in _exceptions(
            DurasiJatuhTempo, seksi, prioritas_pairs, durasi['prioritas']
        ).items():
            for tahun in years:
                rows.append(AturanDurasiJatuhTempo(
                    seksi=seksi,
                    tahun=tahun,
                    durasi_prioritas=durasi_khusus,
                    durasi_non_prioritas=durasi['non_prioritas'],
                    id_sub_jenis_data_id=sub_id,
                    create_date=today,
                    create_by='migrasi',
                    update_date=today,
                    update_by='migrasi',
                ))

    AturanDurasiJatuhTempo.objects.bulk_create(rows, batch_size=500)


def unseed(apps, schema_editor):
    AturanDurasiJatuhTempo = apps.get_model('diamond_web', 'AturanDurasiJatuhTempo')
    AturanDurasiJatuhTempo.objects.filter(create_by='migrasi').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('diamond_web', '0015_aturandurasijatuhtempo'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
