# Generated migration - Seed the ILAP → Kanwil mapping (kategori PV) and a
# ready-to-use simulation for "Tanda Terima per Kanwil / per ND Pengantar".
#
# Runs after 0009, which is what makes `ILAPKPP.kpp` / `ILAPKPP.id_kanwil`
# available. Everything here is idempotent (get_or_create), so it also acts as
# a catch-up seeder for databases that already ran 0003/0004 before the PV
# reference data existed.

import importlib
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

from django.db import migrations
from dotenv import dotenv_values


SEED_ENV_VAR = "DB_SEED_ENABLED"
SEED_TABLE_ENV_VAR = "SEED_TABLE"

# Migration 0003 owns the reference data; import it instead of duplicating it.
_seed_0003 = importlib.import_module("diamond_web.migrations.0003_seed_database")


@lru_cache(maxsize=1)
def _get_env_values() -> dict[str, str | None]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    return dotenv_values(env_path)


def _is_seed_enabled() -> bool:
    env_values = _get_env_values()
    raw_value = str(env_values.get(SEED_ENV_VAR, "")).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _get_seed_table_filter() -> set[str] | None:
    env_values = _get_env_values()
    raw_value = str(env_values.get(SEED_TABLE_ENV_VAR, "")).strip()
    if not raw_value:
        return None
    selected = {item.strip().upper() for item in raw_value.split(",") if item and item.strip()}
    return selected or None


def _should_run_seed(seed_key: str) -> bool:
    if not _is_seed_enabled():
        return False
    selected_tables = _get_seed_table_filter()
    if selected_tables is None:
        return True
    return seed_key.upper() in selected_tables


def _run_if_seed_enabled(seed_key: str, seed_func):
    def _wrapped(apps, schema_editor):
        if not _should_run_seed(seed_key):
            return
        return seed_func(apps, schema_editor)

    return _wrapped


# Tikets pre-staged so a developer can open "Kelola Tanda Terima → Tambah",
# pick a Kanwil, pick an ND Pengantar and immediately see matching tikets
# coming from several ILAP at once (PV mapped to Kanwil, PD mapped to KPP).
SIMULASI_TANDA_TERIMA = [
    {
        "kode_kanwil": "090",  # Kanwil DJP Jawa Barat
        "nd_pengantar": [
            {
                "nomor": "B-901/KANWIL-090/06/2026",
                "tanggal": date(2026, 6, 8),
                "sub_jenis_data": ["PV0010101", "PV0010201", "PD0010101"],
            },
            {
                "nomor": "B-902/KANWIL-090/07/2026",
                "tanggal": date(2026, 7, 6),
                "sub_jenis_data": ["PV0010101", "PD0020101"],
            },
        ],
    },
    {
        "kode_kanwil": "100",  # Kanwil DJP Jawa Tengah
        "nd_pengantar": [
            {
                "nomor": "B-903/KANWIL-100/06/2026",
                "tanggal": date(2026, 6, 10),
                "sub_jenis_data": ["PV0020101", "PD0040101"],
            },
            {
                "nomor": "B-904/KANWIL-100/07/2026",
                "tanggal": date(2026, 7, 7),
                "sub_jenis_data": ["PV0020101", "PD0050101"],
            },
        ],
    },
    {
        "kode_kanwil": "120",  # Kanwil DJP Jawa Timur
        "nd_pengantar": [
            {
                "nomor": "B-905/KANWIL-120/06/2026",
                "tanggal": date(2026, 6, 12),
                "sub_jenis_data": ["PV0030101", "PD0070101"],
            },
            {
                "nomor": "B-906/KANWIL-120/07/2026",
                "tanggal": date(2026, 7, 9),
                "sub_jenis_data": ["PV0030101", "PD0090101"],
            },
        ],
    },
]

STATUS_DIREKAM = 1
ACTION_DIREKAM = 1
ACTION_PIC_DITAMBAHKAN = 301
ROLE_P3DE = 1


def seed_ilap_pv(apps, schema_editor):
    """Create the PV (Pemerintah Daerah Provinsi) ILAP reference rows.

    Migration 0003 seeds these for fresh databases, but it still writes the
    long-gone `ILAP.id_kpp` column, so its `seed_ilap` cannot be reused here.
    This re-creates only what is missing, without touching existing rows.
    """
    ILAP = apps.get_model("diamond_web", "ILAP")
    KategoriILAP = apps.get_model("diamond_web", "KategoriILAP")
    KategoriWilayah = apps.get_model("diamond_web", "KategoriWilayah")

    created = 0
    for item in _seed_0003.ILAP_DATA:
        if not item.get("kode_kanwil"):
            continue
        try:
            kategori = KategoriILAP.objects.get(id_kategori=item["id_kategori"])
            kategori_wilayah = KategoriWilayah.objects.get(deskripsi=item["id_kategori_wilayah"])
        except Exception as e:
            print(f"Warning: Could not resolve references for ILAP {item['id_ilap']}: {e}")
            continue

        _, was_created = ILAP.objects.get_or_create(
            id_ilap=item["id_ilap"],
            defaults=_seed_0003.seed_audit_defaults({
                "id_kategori": kategori,
                "nama_ilap": item["nama_ilap"],
                "id_kategori_wilayah": kategori_wilayah,
            })
        )
        if was_created:
            created += 1

    print(f"Seeded {created} ILAP PV records.")


def seed_ilap_kanwil_mapping(apps, schema_editor):
    """Map every ILAP to its wilayah: PD via KPP, PV straight to Kanwil."""
    ILAP = apps.get_model("diamond_web", "ILAP")
    ILAPKPP = apps.get_model("diamond_web", "ILAPKPP")
    KPP = apps.get_model("diamond_web", "KPP")
    Kanwil = apps.get_model("diamond_web", "Kanwil")

    created_kanwil = 0
    created_kpp = 0
    for item in _seed_0003.ILAP_DATA:
        try:
            ilap = ILAP.objects.get(id_ilap=item["id_ilap"])
        except ILAP.DoesNotExist:
            continue

        if item.get("kode_kanwil"):
            kanwil = Kanwil.objects.filter(kode_kanwil=item["kode_kanwil"]).first()
            if kanwil is None:
                print(f"Warning: Kanwil {item['kode_kanwil']} not found for ILAP {item['id_ilap']}.")
                continue
            _, was_created = ILAPKPP.objects.get_or_create(
                id_ilap=ilap,
                id_kanwil=kanwil,
                defaults={"kpp": False, "id_kpp": None},
            )
            created_kanwil += int(was_created)
        elif item.get("kode_kpp"):
            kpp = KPP.objects.filter(kode_kpp=item["kode_kpp"]).first()
            if kpp is None:
                print(f"Warning: KPP {item['kode_kpp']} not found for ILAP {item['id_ilap']}.")
                continue
            _, was_created = ILAPKPP.objects.get_or_create(
                id_ilap=ilap,
                id_kpp=kpp,
                defaults={"kpp": True, "id_kanwil": None},
            )
            created_kpp += int(was_created)

    print(f"Seeded {created_kanwil} ILAP-Kanwil and {created_kpp} ILAP-KPP mappings.")


def seed_reference_catch_up(apps, schema_editor):
    """Re-run the 0003 reference seeders so PV jenis data exists everywhere.

    All of them are get_or_create based, so this is a no-op on databases that
    already carry the data.
    """
    _seed_0003.seed_jenis_data_ilap(apps, schema_editor)
    _seed_0003.seed_klasifikasi_jenis_data(apps, schema_editor)
    _seed_0003.seed_periode_jenis_data(apps, schema_editor)
    _seed_0003.seed_pic(apps, schema_editor)
    _seed_0003.seed_durasi_jatuh_tempo(apps, schema_editor)


def seed_simulasi_tanda_terima(apps, schema_editor):
    """Stage tikets grouped by Kanwil + ND Pengantar, none with a tanda terima.

    Each tiket lands in status "Direkam" with an active P3DE PIC, which is
    exactly the state the Tambah Tanda Terima form selects from.
    """
    Tiket = apps.get_model("diamond_web", "Tiket")
    TiketAction = apps.get_model("diamond_web", "TiketAction")
    TiketPIC = apps.get_model("diamond_web", "TiketPIC")
    PIC = apps.get_model("diamond_web", "PIC")
    PeriodeJenisData = apps.get_model("diamond_web", "PeriodeJenisData")
    BentukData = apps.get_model("diamond_web", "BentukData")
    CaraPenyampaian = apps.get_model("diamond_web", "CaraPenyampaian")
    DurasiJatuhTempo = apps.get_model("diamond_web", "DurasiJatuhTempo")
    User = apps.get_model("auth", "User")

    bentuk = BentukData.objects.exclude(deskripsi="Data Tidak Tersedia").order_by("id").first()
    cara = CaraPenyampaian.objects.order_by("id").first()
    if bentuk is None or cara is None:
        print("Warning: BentukData/CaraPenyampaian not seeded, skipping tanda terima simulation.")
        return

    fallback_p3de = (
        User.objects.filter(groups__name="user_p3de", is_active=True).order_by("id").first()
        or User.objects.order_by("id").first()
    )
    if fallback_p3de is None:
        print("Warning: No user available, skipping tanda terima simulation.")
        return

    durasi_pide = {}
    durasi_pmde = {}
    for d in DurasiJatuhTempo.objects.select_related("id_sub_jenis_data", "seksi").all():
        sid = d.id_sub_jenis_data.id_sub_jenis_data
        if d.seksi.name == "user_pide":
            durasi_pide[sid] = d
        elif d.seksi.name == "user_pmde":
            durasi_pmde[sid] = d

    created = 0
    for kanwil_group in SIMULASI_TANDA_TERIMA:
        for nd_index, nd in enumerate(kanwil_group["nd_pengantar"], start=1):
            tanggal_surat = datetime.combine(nd["tanggal"], datetime.min.time()).replace(hour=9)
            tgl_terima_dip = tanggal_surat + timedelta(days=2)

            for sub_index, sub_id in enumerate(nd["sub_jenis_data"], start=1):
                periode_data = PeriodeJenisData.objects.filter(
                    id_sub_jenis_data_ilap__id_sub_jenis_data=sub_id
                ).order_by("id").first()
                if periode_data is None:
                    print(f"Warning: No PeriodeJenisData for {sub_id}, skipping simulation tiket.")
                    continue

                # nomor_tiket: {sub_id:9}{yymmdd:6}{seq:2} = 17 chars
                seq = nd_index * 10 + sub_index
                nomor_tiket = f"{sub_id}{nd['tanggal'].strftime('%y%m%d')}{seq:02d}"
                if Tiket.objects.filter(nomor_tiket=nomor_tiket).exists():
                    continue

                pic = PIC.objects.filter(
                    tipe="P3DE", id_sub_jenis_data_ilap__id_sub_jenis_data=sub_id
                ).select_related("id_user").order_by("id").first()
                p3de_user = pic.id_user if pic else fallback_p3de

                tiket = Tiket.objects.create(
                    nomor_tiket=nomor_tiket,
                    old_db=False,
                    status_tiket=STATUS_DIREKAM,
                    id_periode_data=periode_data,
                    periode=nd["tanggal"].month,
                    tahun=nd["tanggal"].year,
                    penyampaian=1,
                    nomor_surat_pengantar=nd["nomor"],
                    tanggal_surat_pengantar=tanggal_surat,
                    nama_pengirim="Bpk. Ahmad Fauzi",
                    id_bentuk_data=bentuk,
                    id_cara_penyampaian=cara,
                    status_ketersediaan_data=True,
                    baris_diterima=50_000 + seq * 1_000,
                    satuan_data=1,
                    tgl_terima_dip=tgl_terima_dip,
                    backup=False,
                    tanda_terima=False,
                    id_durasi_jatuh_tempo_pide=durasi_pide.get(sub_id),
                    id_durasi_jatuh_tempo_pmde=durasi_pmde.get(sub_id),
                )

                TiketPIC.objects.create(
                    id_tiket=tiket,
                    id_user=p3de_user,
                    timestamp=tgl_terima_dip + timedelta(microseconds=1),
                    role=ROLE_P3DE,
                    active=True,
                )
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=p3de_user,
                    timestamp=tgl_terima_dip,
                    action=ACTION_DIREKAM,
                    catatan="tiket direkam",
                )
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=p3de_user,
                    timestamp=tgl_terima_dip + timedelta(microseconds=2),
                    action=ACTION_PIC_DITAMBAHKAN,
                    catatan=f"P3DE {p3de_user.username} ditambahkan",
                )
                created += 1

    print(f"Seeded {created} tiket for the tanda terima per Kanwil/ND Pengantar simulation.")


def unseed_ilap_kanwil_mapping(apps, schema_editor):
    """Remove the ILAP→Kanwil mappings and the simulation tikets."""
    ILAPKPP = apps.get_model("diamond_web", "ILAPKPP")
    Tiket = apps.get_model("diamond_web", "Tiket")
    TiketAction = apps.get_model("diamond_web", "TiketAction")
    TiketPIC = apps.get_model("diamond_web", "TiketPIC")
    DetilTandaTerima = apps.get_model("diamond_web", "DetilTandaTerima")

    nd_numbers = [
        nd["nomor"]
        for group in SIMULASI_TANDA_TERIMA
        for nd in group["nd_pengantar"]
    ]
    tiket_ids = list(
        Tiket.objects.filter(nomor_surat_pengantar__in=nd_numbers).values_list("id", flat=True)
    )
    if tiket_ids:
        TiketAction.objects.filter(id_tiket_id__in=tiket_ids).delete()
        TiketPIC.objects.filter(id_tiket_id__in=tiket_ids).delete()
        DetilTandaTerima.objects.filter(id_tiket_id__in=tiket_ids).delete()
        Tiket.objects.filter(id__in=tiket_ids).delete()

    ILAPKPP.objects.filter(kpp=False).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0009_ilapkpp_kanwil_tanda_terima_scope"),
    ]

    operations = [
        migrations.RunPython(
            _run_if_seed_enabled("ILAP", seed_ilap_pv),
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            _run_if_seed_enabled("ILAP", seed_reference_catch_up),
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            _run_if_seed_enabled("ILAP", seed_ilap_kanwil_mapping),
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            _run_if_seed_enabled("TIKET_DATA", seed_simulasi_tanda_terima),
            reverse_code=unseed_ilap_kanwil_mapping,
        ),
    ]
