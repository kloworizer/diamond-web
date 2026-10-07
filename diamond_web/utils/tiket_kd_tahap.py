"""Jumlah baris per KD_TAHAP di tabel I Oracle, per tiket (model TiketKdTahap).

Dipakai oleh management command ``sync_tiket_kd_tahap`` (semua tiket satu tahun
terima DIP) dan oleh aksi Sinkronisasi di halaman detil tiket (satu tiket).

Tabel I tiket = JenisDataILAP.nama_tabel_I, di schema BANKDATAPDE pada koneksi
Oracle secondary. NO_TIKET di tabel tersebut tidak ber-index, jadi beberapa
tiket satu tabel di-query sekaligus:

    SELECT NO_TIKET, KD_TAHAP, COUNT(*) FROM BANKDATAPDE.<nama_tabel_I>
    WHERE NO_TIKET IN (...)
    GROUP BY NO_TIKET, KD_TAHAP
"""

import logging
import re
from collections import defaultdict

from django.db import transaction

from ..constants.tiket_status import STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI
from ..models.tiket_kd_tahap import TiketKdTahap

logger = logging.getLogger(__name__)

# Status tiket yang jumlah baris KD_TAHAP-nya diambil.
STATUS_KD_TAHAP = (STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI)

KONEKSI = 'secondary'
SCHEMA = 'BANKDATAPDE'
KOLOM_TIKET = 'NO_TIKET'
KOLOM_TAHAP = 'KD_TAHAP'

# Oracle membatasi IN (...) sampai 1000 nilai; tiap tiket memakai dua nilai.
TIKET_PER_QUERY = 500

# Nama tabel/kolom disisipkan langsung ke SQL (tidak bisa di-bind), jadi hanya
# identifier Oracle polos yang diterima.
IDENTIFIER_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_$#]{0,127}$')


class KdTahapError(Exception):
    """Jumlah baris KD_TAHAP tidak dapat diambil dari Oracle."""


def nomor_tiket_oracle(nomor_tiket):
    """Kembalikan nomor tiket dalam format lama Oracle.

    Sync tiket mengubah no_tiket Oracle 16 karakter berawalan 'E' menjadi
    'EI...' (17 karakter). Di sini dibalik, supaya kedua format ikut dicari.
    """
    if len(nomor_tiket) == 17 and nomor_tiket.startswith('EI'):
        return 'E' + nomor_tiket[2:]
    return nomor_tiket


def nama_tabel_i(tiket):
    """Nama tabel I tiket (huruf besar), atau KdTahapError bila tidak valid."""
    nama = (tiket.id_periode_data.id_sub_jenis_data_ilap.nama_tabel_I or '').strip()
    if not IDENTIFIER_RE.match(nama):
        raise KdTahapError(f"Nama tabel I tidak valid ({nama!r})")
    return nama.upper()


def hitung_kd_tahap(cursor, tabel, tikets, kolom_tiket=KOLOM_TIKET, kolom_tahap=KOLOM_TAHAP):
    """Jumlah baris per KD_TAHAP untuk *tikets* (paling banyak TIKET_PER_QUERY) di *tabel*.

    Returns {tiket.id: {kd_tahap: jumlah}}; tiket tanpa baris tidak ada di
    hasilnya. Error Oracle diteruskan ke pemanggil.
    """
    # Kedua format nomor tiket menunjuk ke tiket lokal yang sama.
    tiket_by_nomor = {}
    for tiket in tikets:
        tiket_by_nomor[tiket.nomor_tiket] = tiket
        tiket_by_nomor[nomor_tiket_oracle(tiket.nomor_tiket)] = tiket
    nomors = list(tiket_by_nomor)
    placeholders = ', '.join(f':{i}' for i in range(1, len(nomors) + 1))
    cursor.execute(
        f"SELECT {kolom_tiket}, {kolom_tahap}, COUNT(*) FROM {tabel} "
        f"WHERE {kolom_tiket} IN ({placeholders}) "
        f"GROUP BY {kolom_tiket}, {kolom_tahap}",
        nomors,
    )

    # Dijumlahkan bila kedua format nomor ada di Oracle.
    hitungan = defaultdict(lambda: defaultdict(int))
    for nomor, kd_tahap, jumlah in cursor.fetchall():
        tiket = tiket_by_nomor.get(nomor)
        if tiket is not None:
            kd = None if kd_tahap is None else str(kd_tahap)
            hitungan[tiket.id][kd] += int(jumlah)
    return {tiket_id: dict(per_kd) for tiket_id, per_kd in hitungan.items()}


def urutkan(hitungan):
    """[(kd_tahap, jumlah)] terurut menurut kd_tahap, kd_tahap kosong di akhir."""
    return sorted(hitungan.items(), key=lambda kv: (kv[0] is None, kv[0] or ''))


def tersimpan(tiket):
    """{kd_tahap: jumlah_baris} yang saat ini tersimpan untuk tiket."""
    return dict(TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'jumlah_baris'))


def simpan_kd_tahap(tiket, hitungan):
    """Ganti seluruh baris TiketKdTahap milik tiket dengan *hitungan*."""
    with transaction.atomic():
        TiketKdTahap.objects.filter(id_tiket=tiket).delete()
        TiketKdTahap.objects.bulk_create([
            TiketKdTahap(id_tiket=tiket, kd_tahap=kd, jumlah_baris=jumlah)
            for kd, jumlah in urutkan(hitungan)
        ])


def ambil_kd_tahap_tiket(service, tiket):
    """Jumlah baris per KD_TAHAP satu tiket dari Oracle: {kd_tahap: jumlah}.

    Raises KdTahapError bila nama tabel I tidak valid atau query Oracle gagal.
    """
    tabel = f"{SCHEMA}.{nama_tabel_i(tiket)}"
    try:
        with service._connect_oracle(KONEKSI) as conn, conn.cursor() as cursor:
            return hitung_kd_tahap(cursor, tabel, [tiket]).get(tiket.id, {})
    except KdTahapError:
        raise
    except Exception as exc:  # OracleSyncConfigError, oracledb.DatabaseError, ...
        pesan = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
        logger.warning("KD Tahap tiket %s (%s): %s", tiket.nomor_tiket, tabel, pesan)
        raise KdTahapError(f"{tabel}: {pesan}") from exc
