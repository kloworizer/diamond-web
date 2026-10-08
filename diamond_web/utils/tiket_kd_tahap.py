"""Jumlah baris per KD_TAHAP & flag QC di tabel I Oracle, per tiket (model TiketKdTahap).

Dipakai oleh management command ``sync_tiket_kd_tahap`` (semua tiket satu tahun
terima DIP) dan oleh menu Sinkronisasi KD Tahap di detil tiket (satu tiket).

Tabel I tiket = JenisDataILAP.nama_tabel_I, di schema BANKDATAPDE pada koneksi
Oracle secondary. NO_TIKET di tabel tersebut tidak ber-index, jadi beberapa
tiket satu tabel di-query sekaligus:

    SELECT NO_TIKET, KD_TAHAP, QC, COUNT(*) FROM BANKDATAPDE.<nama_tabel_I>
    WHERE NO_TIKET IN (...)
    GROUP BY NO_TIKET, KD_TAHAP, QC

Hasilnya per tiket berupa {(kd_tahap, qc): jumlah}; QC kosong = belum di-QC.
"""

import logging
import os
import re
import time
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
KOLOM_QC = 'QC'

# Panjang kd_tahap / qc yang disimpan (model TiketKdTahap). Beberapa tabel
# menyimpan QC di kolom lebar; nilai yang terpotong sama dijumlahkan.
PANJANG_NILAI = 50

# Oracle membatasi IN (...) sampai 1000 nilai; tiap tiket memakai dua nilai.
TIKET_PER_QUERY = 500

# Nama tabel/kolom disisipkan langsung ke SQL (tidak bisa di-bind), jadi hanya
# identifier Oracle polos yang diterima.
IDENTIFIER_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_$#]{0,127}$')


def _detik_env(nama, default):
    try:
        return max(0, int(os.getenv(nama, default)))
    except (TypeError, ValueError):
        return int(default)


# Batas waktu satu query ke tabel I (detik, 0 = tanpa batas). Tabel besar tanpa
# index NO_TIKET bisa butuh beberapa menit; query yang melewati batas ini
# dibatalkan Oracle (call_timeout) dan dicatat sebagai timeout.
QUERY_TIMEOUT = _detik_env('ORACLE_KD_TAHAP_TIMEOUT', '900')

# Error yang menandakan query dibatalkan karena call_timeout.
_KODE_TIMEOUT = ('DPI-1067', 'ORA-03156', 'ORA-01013')

# Koneksi putus. Saat call_timeout habis Oracle kadang hanya memutus koneksi
# (ORA-03113 / DPI-1080) tanpa kode timeout di atas.
_KODE_PUTUS = ('DPY-4011', 'DPI-1080', 'ORA-03113')

# Error yang tetap sama kalau diulang: tabel/kolom tidak ada, tidak ada hak akses.
_KODE_PERMANEN = ('ORA-00942', 'ORA-00904', 'ORA-00903', 'ORA-01031')


def is_timeout(exc, durasi=None, batas=None):
    """True bila *exc* berasal dari call_timeout.

    Koneksi yang putus dihitung timeout bila query sudah berjalan *durasi*
    detik >= *batas* (call_timeout yang dipasang).
    """
    teks = str(exc)
    if any(kode in teks for kode in _KODE_TIMEOUT):
        return True
    return bool(batas) and durasi is not None and durasi >= batas and any(kode in teks for kode in _KODE_PUTUS)


def is_permanen(exc):
    return any(kode in str(exc) for kode in _KODE_PERMANEN)


def pesan_error(exc):
    """Baris pertama pesan error, atau nama kelasnya bila kosong."""
    teks = str(exc).strip()
    return teks.splitlines()[0] if teks else exc.__class__.__name__


def set_query_timeout(conn, detik):
    """Batasi lama setiap query di koneksi ini (detik; 0/None = tanpa batas)."""
    if detik:
        conn.call_timeout = int(detik * 1000)


class KdTahapError(Exception):
    """Jumlah baris KD_TAHAP tidak dapat diambil dari Oracle."""

    def __init__(self, pesan, timeout=False):
        super().__init__(pesan)
        self.timeout = timeout


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


def _nilai(value):
    """Nilai kd_tahap / qc Oracle sebagai teks yang disimpan, None bila kosong."""
    if value is None:
        return None
    teks = str(value).strip()
    return teks[:PANJANG_NILAI] if teks else None


def hitung_kd_tahap(cursor, tabel, tikets, kolom_tiket=KOLOM_TIKET, kolom_tahap=KOLOM_TAHAP,
                    kolom_qc=KOLOM_QC):
    """Jumlah baris per KD_TAHAP & QC untuk *tikets* (paling banyak TIKET_PER_QUERY) di *tabel*.

    Returns {tiket.id: {(kd_tahap, qc): jumlah}}; tiket tanpa baris tidak ada
    di hasilnya. Error Oracle diteruskan ke pemanggil.
    """
    # Kedua format nomor tiket menunjuk ke tiket lokal yang sama.
    tiket_by_nomor = {}
    for tiket in tikets:
        tiket_by_nomor[tiket.nomor_tiket] = tiket
        tiket_by_nomor[nomor_tiket_oracle(tiket.nomor_tiket)] = tiket
    nomors = list(tiket_by_nomor)
    placeholders = ', '.join(f':{i}' for i in range(1, len(nomors) + 1))
    cursor.execute(
        f"SELECT {kolom_tiket}, {kolom_tahap}, {kolom_qc}, COUNT(*) FROM {tabel} "
        f"WHERE {kolom_tiket} IN ({placeholders}) "
        f"GROUP BY {kolom_tiket}, {kolom_tahap}, {kolom_qc}",
        nomors,
    )

    # Dijumlahkan bila kedua format nomor ada di Oracle.
    hitungan = defaultdict(lambda: defaultdict(int))
    for nomor, kd_tahap, qc, jumlah in cursor.fetchall():
        tiket = tiket_by_nomor.get(nomor)
        if tiket is not None:
            hitungan[tiket.id][(_nilai(kd_tahap), _nilai(qc))] += int(jumlah)
    return {tiket_id: dict(per_kd) for tiket_id, per_kd in hitungan.items()}


def urutkan(hitungan):
    """[((kd_tahap, qc), jumlah)] terurut menurut kd_tahap lalu qc, yang kosong di akhir."""
    return sorted(
        hitungan.items(),
        key=lambda kv: tuple((v is None, v or '') for v in kv[0]),
    )


def label(kunci):
    """'KD/QC' untuk log, '(kosong)' untuk nilai kosong."""
    return '/'.join(v if v is not None else '(kosong)' for v in kunci)


def tersimpan(tiket):
    """{(kd_tahap, qc): jumlah_baris} yang saat ini tersimpan untuk tiket."""
    return {
        (kd, qc): jumlah
        for kd, qc, jumlah in TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'qc', 'jumlah_baris')
    }


def simpan_kd_tahap(tiket, hitungan):
    """Ganti seluruh baris TiketKdTahap milik tiket dengan *hitungan*."""
    with transaction.atomic():
        TiketKdTahap.objects.filter(id_tiket=tiket).delete()
        TiketKdTahap.objects.bulk_create([
            TiketKdTahap(id_tiket=tiket, kd_tahap=kd, qc=qc, jumlah_baris=jumlah)
            for (kd, qc), jumlah in urutkan(hitungan)
        ])


def ambil_kd_tahap_tiket(service, tiket, timeout=QUERY_TIMEOUT):
    """Jumlah baris per KD_TAHAP & QC satu tiket dari Oracle: {(kd_tahap, qc): jumlah}.

    Raises KdTahapError bila nama tabel I tidak valid atau query Oracle gagal
    (`.timeout` True bila query melewati *timeout* detik).
    """
    tabel = f"{SCHEMA}.{nama_tabel_i(tiket)}"
    t0 = time.monotonic()
    try:
        with service._connect_oracle(KONEKSI) as conn:
            set_query_timeout(conn, timeout)
            with conn.cursor() as cursor:
                return hitung_kd_tahap(cursor, tabel, [tiket]).get(tiket.id, {})
    except KdTahapError:
        raise
    except Exception as exc:  # OracleSyncConfigError, oracledb.DatabaseError, ...
        pesan = pesan_error(exc)
        logger.warning("KD Tahap tiket %s (%s): %s", tiket.nomor_tiket, tabel, pesan)
        if is_timeout(exc, time.monotonic() - t0, timeout):
            raise KdTahapError(
                f"{tabel}: query melewati batas waktu {timeout} detik ({pesan})", timeout=True,
            ) from exc
        raise KdTahapError(f"{tabel}: {pesan}") from exc
