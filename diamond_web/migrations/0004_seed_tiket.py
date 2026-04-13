# Generated migration - Seed tiket table with random combinations

import random
from datetime import date, datetime, timedelta
from django.db import migrations


# All sub_jenis_data IDs seeded in 0003
ALL_SUB_JENIS_DATA = [
    "AS0010101", "AS0010102",
    "BI0010101", "BI0010102", "BI0010201",
    "BU0010101", "BU0020101", "BU0030101",
    "EI0010101", "EI0010102",
    "KM0330101", "KM0330102", "KM0050101", "KM0260101",
    "LM0030101", "LM0030102", "LM0100101",
    "PL0230101", "PL0230102", "PL0440101",
    "PD0010101", "PD0010201", "PD0020101", "PD0020201",
    "PD0030101", "PD0030201", "PD0040101", "PD0050101",
    "PD0060101", "PD0070101", "PD0080101", "PD0090101",
]

# Map sub_jenis_data → typical periode values (matches PeriodePengiriman seeded)
PERIODE_MAP = {
    "AS0010101": ("Bulanan",   list(range(1, 13))),
    "AS0010102": ("Triwulanan", [1, 2, 3, 4]),
    "BI0010101": ("Harian",    list(range(1, 366))),
    "BI0010102": ("Bulanan",   list(range(1, 13))),
    "BI0010201": ("Bulanan",   list(range(1, 13))),
    "BU0010101": ("Mingguan",  list(range(1, 53))),
    "BU0020101": ("Bulanan",   list(range(1, 13))),
    "BU0030101": ("2 Mingguan", list(range(1, 27))),
    "EI0010101": ("Tahunan",   [1]),
    "EI0010102": ("Semester",  [1, 2]),
    "KM0330101": ("Bulanan",   list(range(1, 13))),
    "KM0330102": ("Triwulanan", [1, 2, 3, 4]),
    "KM0050101": ("Bulanan",   list(range(1, 13))),
    "KM0260101": ("Tahunan",   [1]),
    "LM0030101": ("Bulanan",   list(range(1, 13))),
    "LM0030102": ("Tahunan",   [1]),
    "LM0100101": ("Triwulanan", [1, 2, 3, 4]),
    "PL0230101": ("Bulanan",   list(range(1, 13))),
    "PL0230102": ("Triwulanan", [1, 2, 3, 4]),
    "PL0440101": ("Bulanan",   list(range(1, 13))),
    "PD0010101": ("Bulanan",   list(range(1, 13))),
    "PD0010201": ("Triwulanan", [1, 2, 3, 4]),
    "PD0020101": ("Tahunan",   [1]),
    "PD0020201": ("Bulanan",   list(range(1, 13))),
    "PD0030101": ("Mingguan",  list(range(1, 53))),
    "PD0030201": ("Bulanan",   list(range(1, 13))),
    "PD0040101": ("Bulanan",   list(range(1, 13))),
    "PD0050101": ("Tahunan",   [1]),
    "PD0060101": ("Bulanan",   list(range(1, 13))),
    "PD0070101": ("Triwulanan", [1, 2, 3, 4]),
    "PD0080101": ("Mingguan",  list(range(1, 53))),
    "PD0090101": ("2 Mingguan", list(range(1, 27))),
}

NAMA_PENGIRIM_POOL = [
    "Bpk. Ahmad Fauzi", "Ibu Sari Dewi", "Bpk. Hendra Laksana",
    "Ibu Ratna Sari", "Bpk. Doni Prasetyo", "Ibu Wulan Anggraeni",
    "Bpk. Rizky Maulana", "Ibu Fitria Handayani", "Bpk. Agus Salim",
    "Ibu Nurul Hidayah", "Bpk. Faisal Rahman", "Ibu Lestari Wulandari",
    "Bpk. Joko Santoso", "Ibu Maya Kusuma", "Bpk. Taufik Hidayat",
    "Ibu Rina Marlina", "Bpk. Yusuf Anwar", "Ibu Dewi Permatasari",
    "Bpk. Arif Budiman", "Ibu Indah Rahayu",
]

ALASAN_TIDAK_TERSEDIA_POOL = [
    "Data sedang dalam proses rekap",
    "Data belum selesai dikompilasi",
    "Sistem sedang dalam pemeliharaan",
    "Data masih dalam tahap verifikasi internal",
    "Pengirim sedang cuti",
]

NOMOR_ND_POOL = [
    "ND-220/PJ.092/2025", "ND-315/PJ.092/2025", "ND-410/PJ.092/2025",
    "ND-512/PJ.092/2025", "ND-620/PJ.092/2025", "ND-718/PJ.092/2026",
    "ND-801/PJ.092/2026", "ND-905/PJ.092/2026", "ND-1001/PJ.092/2026",
    "ND-1105/PJ.092/2026",
]


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _random_datetime(start: date, end: date) -> datetime:
    d = _random_date(start, end)
    hour = random.randint(7, 16)
    minute = random.randint(0, 59)
    return datetime(d.year, d.month, d.day, hour, minute)


def seed_tiket(apps, schema_editor):
    """Seeds the Tiket table with ~120 random combinations using reference data."""

    random.seed(42)  # reproducible randomness

    Tiket = apps.get_model("diamond_web", "Tiket")
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    JenisPrioritasData = apps.get_model("diamond_web", "JenisPrioritasData")
    BentukData = apps.get_model("diamond_web", "BentukData")
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    DurasiJatuhTempo = apps.get_model("diamond_web", "DurasiJatuhTempo")

    bentuk_data_list = list(BentukData.objects.all())
    cara_penyampaian_list = list(CaraPenyampaian.objects.all())
    status_penelitian_list = list(StatusPenelitian.objects.all())

    # Fetch all DurasiJatuhTempo for pide and pmde
    durasi_pide_map = {}
    durasi_pmde_map = {}
    for d in DurasiJatuhTempo.objects.select_related("id_sub_jenis_data", "seksi").all():
        sid = d.id_sub_jenis_data.id_sub_jenis_data
        if d.seksi.name == "user_pide":
            durasi_pide_map[sid] = d
        elif d.seksi.name == "user_pmde":
            durasi_pmde_map[sid] = d

    # Fetch all PeriodeJenisData, index by sub_jenis_data id
    periode_by_sub = {}
    for p in PeriodeJenisData.objects.select_related("id_sub_jenis_data_ilap").all():
        sid = p.id_sub_jenis_data_ilap.id_sub_jenis_data
        periode_by_sub.setdefault(sid, []).append(p)

    # Fetch all JenisPrioritasData, index by sub_jenis_data + tahun
    prioritas_map = {}
    for jp in JenisPrioritasData.objects.select_related("id_sub_jenis_data_ilap").all():
        sid = jp.id_sub_jenis_data_ilap.id_sub_jenis_data
        prioritas_map[(sid, jp.tahun)] = jp

    # Status progression scenarios with weights
    # status: 1=Direkam, 2=Diteliti, 3=Dikembalikan, 4=Dikirim ke PIDE,
    #         5=Identifikasi, 6=Pengendalian Mutu, 7=Dibatalkan, 8=Selesai
    STATUS_WEIGHTS = [
        (1, 5),   # Direkam
        (2, 10),  # Diteliti
        (3, 5),   # Dikembalikan
        (4, 15),  # Dikirim ke PIDE
        (5, 15),  # Identifikasi
        (6, 15),  # Pengendalian Mutu
        (7, 5),   # Dibatalkan
        (8, 30),  # Selesai
    ]
    statuses_pool = []
    for status, weight in STATUS_WEIGHTS:
        statuses_pool.extend([status] * weight)

    years = [2024, 2025, 2026]
    date_ranges = {
        2024: (date(2024, 1, 10), date(2024, 12, 20)),
        2025: (date(2025, 1, 10), date(2025, 12, 20)),
        2026: (date(2026, 1, 10), date(2026, 4, 10)),
    }

    # nomor_tiket counter per prefix
    nomor_counter = {}

    # Build tiket list: spread ~4 tickets per sub_jenis_data across years
    tiket_specs = []
    for sub_id in ALL_SUB_JENIS_DATA:
        if sub_id not in periode_by_sub:
            continue
        periode_options = periode_by_sub[sub_id]
        _, periode_values = PERIODE_MAP.get(sub_id, ("Bulanan", list(range(1, 13))))

        # For each year, create 3-5 tickets
        for tahun in years:
            count = random.randint(3, 5)
            for _ in range(count):
                periode_data = random.choice(periode_options)
                periode_val = random.choice(periode_values)
                tiket_specs.append({
                    "sub_id": sub_id,
                    "periode_data": periode_data,
                    "tahun": tahun,
                    "periode": periode_val,
                })

    random.shuffle(tiket_specs)

    created_count = 0
    for spec in tiket_specs:
        try:
            sub_id = spec["sub_id"]
            tahun = spec["tahun"]
            periode_val = spec["periode"]
            periode_data = spec["periode_data"]

            start_date, end_date = date_ranges[tahun]

            # Generate nomor_tiket: {sub_id}{yymmdd}{seq:03d}
            base_date = _random_date(start_date, end_date)
            yymmdd = base_date.strftime("%y%m%d")
            prefix = f"{sub_id}{yymmdd}"
            seq = nomor_counter.get(prefix, 0) + 1
            nomor_counter[prefix] = seq
            nomor_tiket = f"{prefix}{str(seq).zfill(3)}"

            status = random.choice(statuses_pool)

            # Pick random reference data
            bentuk = random.choice(bentuk_data_list)
            cara = random.choice(cara_penyampaian_list)

            # Determine ketersediaan based on bentuk
            if bentuk.deskripsi == "Data Tidak Tersedia":
                ketersediaan = False
                alasan = random.choice(ALASAN_TIDAK_TERSEDIA_POOL)
            else:
                ketersediaan = True
                alasan = None

            # JenisPrioritasData (optional): assign for ~40% of tickets
            jpd = None
            if random.random() < 0.4:
                jpd = prioritas_map.get((sub_id, str(tahun)))

            # Dates
            tgl_terima_dip = _random_datetime(start_date, end_date)
            tgl_terima_vertikal = None
            if random.random() < 0.6:
                tgl_terima_vertikal = _random_datetime(
                    start_date, tgl_terima_dip.date()
                )

            baris_diterima = random.randint(500, 5_000_000)
            penyampaian = random.randint(1, 3)

            # Status-dependent fields
            tgl_teliti = None
            kesesuaian_data = None
            baris_lengkap = None
            baris_tidak_lengkap = None
            id_status_penelitian = None

            tgl_nadine = None
            nomor_nd_nadine = None
            tgl_kirim_pide = None
            id_durasi_jatuh_tempo_pide = durasi_pide_map.get(sub_id)

            baris_i = None
            baris_u = None
            baris_res = None
            baris_cde = None
            tgl_transfer = None
            tgl_rematch = None
            id_durasi_jatuh_tempo_pmde = durasi_pmde_map.get(sub_id)

            sudah_qc = lolos_qc = tidak_lolos_qc = None
            belum_qc = qc_p = qc_x = qc_w = qc_v = None
            qc_a = qc_n = qc_y = qc_z = qc_d = qc_u = qc_c = None

            tgl_dibatalkan = None
            tgl_dikembalikan = None
            tgl_rekam_pide = None

            base_dt = tgl_terima_dip

            if status >= 2:  # Diteliti
                tgl_teliti = datetime(
                    base_dt.year, base_dt.month, base_dt.day,
                    random.randint(7, 16), random.randint(0, 59)
                ) + timedelta(days=random.randint(1, 7))
                id_status_penelitian = random.choice(status_penelitian_list)
                kesesuaian_data = random.randint(80, 100)
                baris_lengkap = int(baris_diterima * kesesuaian_data / 100)
                baris_tidak_lengkap = baris_diterima - baris_lengkap

            if status == 3:  # Dikembalikan
                tgl_dikembalikan = tgl_teliti + timedelta(days=random.randint(1, 5))

            if status >= 4:  # Dikirim ke PIDE
                tgl_kirim_pide = tgl_teliti + timedelta(days=random.randint(1, 3))
                tgl_nadine = tgl_kirim_pide + timedelta(days=random.randint(0, 2))
                nomor_nd_nadine = random.choice(NOMOR_ND_POOL)

            if status >= 5:  # Identifikasi
                tgl_rekam_pide = tgl_kirim_pide + timedelta(days=random.randint(1, 5))
                baris_i = random.randint(100, baris_diterima)
                baris_u = random.randint(0, baris_diterima - baris_i)
                baris_res = random.randint(0, 500)
                baris_cde = random.randint(0, 200)

            if status >= 6:  # Pengendalian Mutu
                tgl_transfer = tgl_rekam_pide + timedelta(days=random.randint(1, 3))
                tgl_rematch = tgl_transfer + timedelta(days=random.randint(0, 2))
                total_qc = baris_i or random.randint(500, 5000)
                sudah_qc = random.randint(int(total_qc * 0.7), total_qc)
                belum_qc = total_qc - sudah_qc
                lolos_qc = random.randint(int(sudah_qc * 0.7), sudah_qc)
                tidak_lolos_qc = sudah_qc - lolos_qc
                qc_p = random.randint(0, lolos_qc)
                qc_x = random.randint(0, max(0, lolos_qc - qc_p))
                qc_w = random.randint(0, 100)
                qc_v = random.randint(0, 100)
                qc_a = random.randint(0, 50)
                qc_n = random.randint(0, 50)
                qc_y = random.randint(0, 50)
                qc_z = random.randint(0, 50)
                qc_d = random.randint(0, 50)
                qc_u = random.randint(0, 50)
                qc_c = random.randint(0, 50)

            if status == 7:  # Dibatalkan
                tgl_dibatalkan = base_dt + timedelta(days=random.randint(1, 10))

            # nomor_surat_pengantar
            nomor_surat = (
                f"B-{random.randint(100, 9999)}/{sub_id[:2]}/"
                f"{random.randint(1, 12):02d}/{tahun}"
            )
            tanggal_surat = _random_datetime(start_date, base_dt.date())

            Tiket.objects.create(
                nomor_tiket=nomor_tiket,
                status_tiket=status,
                id_periode_data=periode_data,
                id_jenis_prioritas_data=jpd,
                periode=periode_val,
                tahun=tahun,
                penyampaian=penyampaian,
                nomor_surat_pengantar=nomor_surat,
                tanggal_surat_pengantar=tanggal_surat,
                nama_pengirim=random.choice(NAMA_PENGIRIM_POOL),
                id_bentuk_data=bentuk,
                id_cara_penyampaian=cara,
                status_ketersediaan_data=ketersediaan,
                alasan_ketidaktersediaan=alasan,
                baris_diterima=baris_diterima,
                satuan_data=1,
                tgl_terima_vertikal=tgl_terima_vertikal,
                tgl_terima_dip=tgl_terima_dip,
                backup=random.random() > 0.3,
                tanda_terima=status >= 2,
                id_status_penelitian=id_status_penelitian,
                tgl_teliti=tgl_teliti,
                kesesuaian_data=kesesuaian_data,
                baris_lengkap=baris_lengkap,
                baris_tidak_lengkap=baris_tidak_lengkap,
                tgl_nadine=tgl_nadine,
                nomor_nd_nadine=nomor_nd_nadine,
                tgl_kirim_pide=tgl_kirim_pide,
                tgl_dibatalkan=tgl_dibatalkan,
                tgl_dikembalikan=tgl_dikembalikan,
                tgl_rekam_pide=tgl_rekam_pide,
                id_durasi_jatuh_tempo_pide=id_durasi_jatuh_tempo_pide,
                baris_i=baris_i,
                baris_u=baris_u,
                baris_res=baris_res,
                baris_cde=baris_cde,
                tgl_transfer=tgl_transfer,
                tgl_rematch=tgl_rematch,
                id_durasi_jatuh_tempo_pmde=id_durasi_jatuh_tempo_pmde,
                sudah_qc=sudah_qc,
                belum_qc=belum_qc,
                lolos_qc=lolos_qc,
                tidak_lolos_qc=tidak_lolos_qc,
                qc_p=qc_p,
                qc_x=qc_x,
                qc_w=qc_w,
                qc_v=qc_v,
                qc_a=qc_a,
                qc_n=qc_n,
                qc_y=qc_y,
                qc_z=qc_z,
                qc_d=qc_d,
                qc_u=qc_u,
                qc_c=qc_c,
            )
            created_count += 1

        except Exception as e:
            print(f"Warning: Could not create tiket for {spec.get('sub_id')} "
                  f"tahun={spec.get('tahun')} periode={spec.get('periode')}: {e}")

    print(f"Seeded {created_count} tiket records.")


def unseed_tiket(apps, schema_editor):
    """Removes all seeded tiket records (clears the entire tiket table)."""
    Tiket = apps.get_model("diamond_web", "Tiket")
    Tiket.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0003_seed_database"),
    ]

    operations = [
        migrations.RunPython(seed_tiket, reverse_code=unseed_tiket),
    ]
