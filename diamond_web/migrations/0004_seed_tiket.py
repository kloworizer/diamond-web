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

# Action IDs (aligned with diamond_web.constants.tiket_action_types)
ACTION_DIREKAM = 1
ACTION_DITELITI = 2
ACTION_DIKEMBALIKAN = 3
ACTION_DIKIRIM_KE_PIDE = 4
ACTION_IDENTIFIKASI = 5
ACTION_PENGENDALIAN_MUTU = 6
ACTION_DIBATALKAN = 7
ACTION_SELESAI = 8
ACTION_DITRANSFER_KE_PMDE = 9
ACTION_BACKUP_DIREKAM = 101
ACTION_TANDA_TERIMA_DIREKAM = 201
ACTION_PIC_DITAMBAHKAN = 301


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def _random_datetime(start: date, end: date) -> datetime:
    d = _random_date(start, end)
    hour = random.randint(7, 16)
    minute = random.randint(0, 59)
    return datetime(d.year, d.month, d.day, hour, minute)


def seed_tiket(apps, schema_editor):
    """Seeds Tiket plus related Tanda Terima and Backup records using reference data."""

    random.seed(42)  # reproducible randomness

    Tiket = apps.get_model("diamond_web", "Tiket")
    PIC = apps.get_model("diamond_web", "PIC")
    TiketPIC = apps.get_model("diamond_web", "TiketPIC")
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    JenisPrioritasData = apps.get_model("diamond_web", "JenisPrioritasData")
    BentukData = apps.get_model("diamond_web", "BentukData")
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    StatusPenelitian = apps.get_model("diamond_web", "StatusPenelitian")
    DurasiJatuhTempo = apps.get_model("diamond_web", "DurasiJatuhTempo")
    TandaTerimaData = apps.get_model("diamond_web", "TandaTerimaData")
    DetilTandaTerima = apps.get_model("diamond_web", "DetilTandaTerima")
    BackupData = apps.get_model("diamond_web", "BackupData")
    TiketAction = apps.get_model("diamond_web", "TiketAction")
    MediaBackup = apps.get_model("diamond_web", "MediaBackup")
    User = apps.get_model("auth", "User")

    bentuk_data_list = list(BentukData.objects.all())
    cara_penyampaian_list = list(CaraPenyampaian.objects.all())
    status_penelitian_list = list(StatusPenelitian.objects.all())
    media_backup_list = list(MediaBackup.objects.all())

    # Users by seksi (group) to mimic actual workflow actors
    p3de_users = list(User.objects.filter(groups__name="user_p3de").distinct())
    pide_users = list(User.objects.filter(groups__name="user_pide").distinct())
    pmde_users = list(User.objects.filter(groups__name="user_pmde").distinct())
    fallback_user = User.objects.order_by("id").first()

    if not p3de_users and fallback_user:
        p3de_users = [fallback_user]
    if not pide_users and fallback_user:
        pide_users = [fallback_user]
    if not pmde_users and fallback_user:
        pmde_users = [fallback_user]

    # nomor_tanda_terima counter per tahun (continue from existing if any)
    tt_counter_by_year = {}
    for tt in TandaTerimaData.objects.all():
        current = tt_counter_by_year.get(tt.tahun_terima, 0)
        if tt.nomor_tanda_terima > current:
            tt_counter_by_year[tt.tahun_terima] = tt.nomor_tanda_terima

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

    # Fetch PIC assignments by sub_jenis_data and tipe
    pic_by_sub_tipe = {}
    for pic in PIC.objects.select_related("id_sub_jenis_data_ilap", "id_user").all():
        sid = pic.id_sub_jenis_data_ilap.id_sub_jenis_data
        key = (sid, pic.tipe)
        pic_by_sub_tipe.setdefault(key, []).append(pic)

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

            # Status-dependent fields (strict timeline per workflow)
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
            t_tanda_terima = base_dt + timedelta(hours=random.randint(1, 8))
            t_backup = t_tanda_terima + timedelta(hours=random.randint(1, 6))
            t_telitian = t_backup + timedelta(days=random.randint(1, 3))
            t_kirim = t_telitian + timedelta(days=random.randint(1, 2))
            t_nadine = t_kirim + timedelta(hours=random.randint(1, 12))
            t_rekam = t_kirim + timedelta(days=random.randint(1, 3))
            t_transfer_pmde = t_rekam + timedelta(days=random.randint(1, 2))
            t_qc = t_transfer_pmde + timedelta(hours=random.randint(1, 8))
            t_done = t_qc + timedelta(days=random.randint(1, 2))
            t_return = t_kirim + timedelta(days=random.randint(1, 3))
            t_cancel = t_telitian + timedelta(days=random.randint(1, 3))

            if status >= 2 or status == 7:
                tgl_teliti = t_telitian
                id_status_penelitian = random.choice(status_penelitian_list)
                kesesuaian_data = random.randint(80, 100)
                baris_lengkap = int(baris_diterima * kesesuaian_data / 100)
                baris_tidak_lengkap = baris_diterima - baris_lengkap

            if status in (3, 4, 5, 6, 8):
                tgl_kirim_pide = t_kirim
                tgl_nadine = t_nadine
                nomor_nd_nadine = random.choice(NOMOR_ND_POOL)

            if status == 3:
                tgl_dikembalikan = t_return

            if status in (5, 6, 8):
                tgl_rekam_pide = t_rekam
                baris_i = random.randint(max(100, int(baris_diterima * 0.5)), baris_diterima)
                baris_u = random.randint(0, max(0, baris_diterima - baris_i))
                baris_res = random.randint(0, 500)
                baris_cde = random.randint(0, 200)

            if status in (6, 8):
                tgl_transfer = t_transfer_pmde
                tgl_rematch = t_transfer_pmde + timedelta(hours=random.randint(1, 12))
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

            if status == 7:
                tgl_dibatalkan = t_cancel

            # nomor_surat_pengantar
            nomor_surat = (
                f"B-{random.randint(100, 9999)}/{sub_id[:2]}/"
                f"{random.randint(1, 12):02d}/{tahun}"
            )
            tanggal_surat = _random_datetime(start_date, base_dt.date())

            # Workflow flags:
            # p3de: rekam penerimaan -> tanda terima -> backup -> penelitian -> kirim PIDE
            # pide: rekam -> identifikasi -> kirim PMDE (or return to p3de)
            # pmde: rekam selesai; p3de may cancel
            # Strict workflow rule: once ticket reaches penelitian (status >= 2),
            # tanda terima and backup must already exist.
            has_tanda_terima = status >= 2
            has_backup = status >= 2

            p3de_user = random.choice(p3de_users) if p3de_users else fallback_user
            pide_user = random.choice(pide_users) if pide_users else fallback_user
            pmde_user = random.choice(pmde_users) if pmde_users else fallback_user

            # Prefer PIC master assignment for this sub-jenis-data (active by tanggal terima)
            flow_date = tgl_terima_dip.date()

            def _pick_pic_user(sid, tipe, fallback):
                candidates = pic_by_sub_tipe.get((sid, tipe), [])
                active = [
                    p for p in candidates
                    if p.start_date <= flow_date and (p.end_date is None or p.end_date >= flow_date)
                ]
                chosen = random.choice(active) if active else (random.choice(candidates) if candidates else None)
                return chosen.id_user if chosen else fallback

            p3de_user = _pick_pic_user(sub_id, "P3DE", p3de_user)
            pide_user = _pick_pic_user(sub_id, "PIDE", pide_user)
            pmde_user = _pick_pic_user(sub_id, "PMDE", pmde_user)

            tiket = Tiket.objects.create(
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
                backup=has_backup,
                tanda_terima=has_tanda_terima,
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

            # Seed Tanda Terima + Detil after p3de rekam penerimaan
            if tiket.tanda_terima:
                tt_year = tiket.tahun
                tt_number = tt_counter_by_year.get(tt_year, 0) + 1
                tt_counter_by_year[tt_year] = tt_number

                ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
                tanda_terima = TandaTerimaData.objects.create(
                    nomor_tanda_terima=tt_number,
                    tahun_terima=tt_year,
                    tanggal_tanda_terima=t_tanda_terima,
                    id_ilap=ilap,
                    id_perekam=p3de_user,
                    active=True,
                )

                DetilTandaTerima.objects.create(
                    id_tanda_terima=tanda_terima,
                    id_tiket=tiket,
                )

            # Seed Backup Data after tanda terima
            if tiket.backup and media_backup_list:
                BackupData.objects.create(
                    id_tiket=tiket,
                    lokasi_backup=f"\\\\backup-server\\diamond\\{sub_id}\\{tahun}\\p{penyampaian}",
                    nama_file=f"{nomor_tiket}.zip",
                    id_media_backup=random.choice(media_backup_list),
                    id_user=p3de_user,
                )

            # Seed TiketPIC for all roles (P3DE, PIDE, PMDE) - all tickets active across all roles
            TiketPIC.objects.create(
                id_tiket=tiket,
                id_user=p3de_user,
                timestamp=base_dt + timedelta(microseconds=1),
                role=1,  # P3DE
                active=True,
            )

            TiketPIC.objects.create(
                id_tiket=tiket,
                id_user=pide_user,
                timestamp=t_kirim + timedelta(microseconds=1),
                role=2,  # PIDE
                active=True,
            )

            TiketPIC.objects.create(
                id_tiket=tiket,
                id_user=pmde_user,
                timestamp=t_transfer_pmde + timedelta(microseconds=1),
                role=3,  # PMDE
                active=True,
            )

            # Seed TiketAction according to strict workflow timeline and final status
            action_rows = [
                (base_dt, p3de_user, ACTION_DIREKAM, "tiket direkam"),
                (base_dt + timedelta(microseconds=2), p3de_user, ACTION_PIC_DITAMBAHKAN, f"P3DE {p3de_user.username} ditambahkan"),
            ]

            if tiket.tanda_terima:
                action_rows.append((t_tanda_terima, p3de_user, ACTION_TANDA_TERIMA_DIREKAM, "tanda terima direkam"))
            if tiket.backup:
                action_rows.append((t_backup, p3de_user, ACTION_BACKUP_DIREKAM, "backup data direkam"))

            if status >= 2 or status == 7:
                action_rows.append((t_telitian, p3de_user, ACTION_DITELITI, "tiket diteliti"))

            if status in (3, 4, 5, 6, 8):
                action_rows.append((t_kirim - timedelta(microseconds=2), p3de_user, ACTION_PIC_DITAMBAHKAN, f"PIDE {pide_user.username} ditambahkan"))
                action_rows.append((t_kirim, p3de_user, ACTION_DIKIRIM_KE_PIDE, "tiket dikirim ke PIDE"))

            if status == 3:
                action_rows.append((t_return, pide_user, ACTION_DIKEMBALIKAN, "tiket dikembalikan ke P3DE"))

            if status in (5, 6, 8):
                action_rows.append((t_rekam, pide_user, ACTION_IDENTIFIKASI, "identifikasi direkam"))

            if status in (6, 8):
                action_rows.append((t_transfer_pmde - timedelta(microseconds=2), pide_user, ACTION_PIC_DITAMBAHKAN, f"PMDE {pmde_user.username} ditambahkan"))
                action_rows.append((t_transfer_pmde, pide_user, ACTION_DITRANSFER_KE_PMDE, "tiket ditransfer ke PMDE"))
                action_rows.append((t_qc, pmde_user, ACTION_PENGENDALIAN_MUTU, "pengendalian mutu direkam"))

            if status == 7:
                action_rows.append((t_cancel, p3de_user, ACTION_DIBATALKAN, "tiket dibatalkan"))

            if status == 8:
                action_rows.append((t_done, pmde_user, ACTION_SELESAI, "tiket selesai"))

            for ts, user_obj, action_id, note in sorted(action_rows, key=lambda x: x[0]):
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=user_obj,
                    timestamp=ts,
                    action=action_id,
                    catatan=note,
                )

            created_count += 1

        except Exception as e:
            print(f"Warning: Could not create tiket for {spec.get('sub_id')} "
                  f"tahun={spec.get('tahun')} periode={spec.get('periode')}: {e}")

    print(f"Seeded {created_count} tiket records.")


def unseed_tiket(apps, schema_editor):
    """Removes seeded tiket records and related backup/tanda-terima detail safely."""
    Tiket = apps.get_model("diamond_web", "Tiket")
    BackupData = apps.get_model("diamond_web", "BackupData")
    TandaTerimaData = apps.get_model("diamond_web", "TandaTerimaData")
    DetilTandaTerima = apps.get_model("diamond_web", "DetilTandaTerima")
    TiketAction = apps.get_model("diamond_web", "TiketAction")
    TiketPIC = apps.get_model("diamond_web", "TiketPIC")

    tiket_ids = list(Tiket.objects.values_list("id", flat=True))
    if not tiket_ids:
        return

    tt_ids = list(
        DetilTandaTerima.objects.filter(id_tiket_id__in=tiket_ids)
        .values_list("id_tanda_terima_id", flat=True)
        .distinct()
    )

    # Remove child records first due to PROTECT constraints
    TiketAction.objects.filter(id_tiket_id__in=tiket_ids).delete()
    TiketPIC.objects.filter(id_tiket_id__in=tiket_ids).delete()
    BackupData.objects.filter(id_tiket_id__in=tiket_ids).delete()
    DetilTandaTerima.objects.filter(id_tiket_id__in=tiket_ids).delete()
    Tiket.objects.filter(id__in=tiket_ids).delete()

    # Remove tanda terima that were created only for those ticket details and are now orphan
    for tt_id in tt_ids:
        if not DetilTandaTerima.objects.filter(id_tanda_terima_id=tt_id).exists():
            TandaTerimaData.objects.filter(id=tt_id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0003_seed_database"),
    ]

    operations = [
        migrations.RunPython(seed_tiket, reverse_code=unseed_tiket),
    ]
