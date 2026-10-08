"""Ambil jumlah baris per KD_TAHAP dari tabel I Oracle untuk tiket Pengendalian Mutu & Selesai.

Untuk setiap tiket berstatus Pengendalian Mutu atau Selesai dengan tahun Tanggal
Terima DIP = --tahun, command ini menghitung jumlah baris per KD_TAHAP milik
tiket itu di tabel I-nya, lalu mengganti seluruh baris TiketKdTahap milik tiket
tersebut dengan hasilnya. Lihat diamond_web/utils/tiket_kd_tahap.py untuk query.

Tiket dikelompokkan per tabel dan Oracle di-query sekali per tabel (per 500
tiket), karena NO_TIKET di tabel I tidak ber-index. Tiket yang query tabelnya
gagal dilewati dan barisnya yang lama tidak disentuh. Tiket yang tidak punya
baris di Oracle dikosongkan.

Setiap run menulis log rinci ke sync_logs/kd_tahap_sync_<waktu>.log
(kd_tahap_sync_dryrun_<waktu>.log untuk --dry-run), yang tampil di halaman
Sync Log Status: parameter, query & durasi per tabel, hasil per tiket
dibanding data tersimpan, setiap error lengkap dengan traceback, dan ringkasan.

Satu tiket juga dapat disinkronkan dari halaman detilnya (aksi Sinkronisasi).

Contoh:
    python manage.py sync_tiket_kd_tahap --tahun 2025
    python manage.py sync_tiket_kd_tahap --tahun 2025 --dry-run
    python manage.py sync_tiket_kd_tahap --tahun 2025 --koneksi primary --schema LAIN
"""

import logging
import os
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from ...constants.tiket_status import STATUS_LABELS
from ...models.tiket import Tiket
from ...models.tiket_kd_tahap import TiketKdTahap
from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...utils.tiket_kd_tahap import (
    IDENTIFIER_RE,
    KOLOM_TAHAP,
    KOLOM_TIKET,
    KONEKSI,
    SCHEMA,
    STATUS_KD_TAHAP,
    TIKET_PER_QUERY,
    KdTahapError,
    hitung_kd_tahap,
    nama_tabel_i,
    simpan_kd_tahap,
    urutkan,
)
from ...views.sync_log_status import SYNC_LOGS_DIR

logger = logging.getLogger(__name__)

# Hasil per tiket, dibanding baris TiketKdTahap yang tersimpan sebelum run.
HASIL_BARU = 'BARU'                # belum ada, kini ada baris
HASIL_BERUBAH = 'BERUBAH'          # ada, dan KD Tahap / jumlahnya berubah
HASIL_SAMA = 'SAMA'                # sama persis dengan Oracle
HASIL_DIKOSONGKAN = 'DIKOSONGKAN'  # ada, tetapi Oracle tidak punya baris lagi
HASIL_KOSONG = 'KOSONG'            # tidak ada di keduanya
HASIL_GAGAL = 'GAGAL'              # query gagal / tabel tidak valid; tidak diubah


def _hasil(lama, baru):
    if lama == baru:
        return HASIL_SAMA if baru else HASIL_KOSONG
    if not lama:
        return HASIL_BARU
    return HASIL_BERUBAH if baru else HASIL_DIKOSONGKAN


def _format_kd(hitungan):
    return ', '.join(f"{kd if kd is not None else '(kosong)'}={jumlah}" for kd, jumlah in urutkan(hitungan)) or '-'


class SyncLog:
    """Log teks satu run di sync_logs/, ditulis & di-flush per baris."""

    def __init__(self, tipe, mulai):
        os.makedirs(SYNC_LOGS_DIR, exist_ok=True)
        self.path = os.path.join(SYNC_LOGS_DIR, f"{tipe}_{mulai:%Y-%m-%d_%H-%M-%S}.log")
        self._file = open(self.path, 'a', encoding='utf-8')

    def _tulis(self, level, pesan):
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for baris in str(pesan).splitlines() or ['']:
            self._file.write(f"[{ts}] {level:<5} {baris}\n")
        self._file.flush()

    def info(self, pesan):
        self._tulis('INFO', pesan)

    def warn(self, pesan):
        self._tulis('WARN', pesan)

    def error(self, pesan, exc=None):
        self._tulis('ERROR', pesan)
        if exc is not None:
            self._tulis('ERROR', ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())

    def close(self):
        self._file.close()


class Command(BaseCommand):
    help = (
        "Ambil jumlah baris per KD_TAHAP dari tabel I Oracle untuk tiket "
        "Pengendalian Mutu & Selesai pada satu tahun terima DIP"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--tahun', type=int, required=True,
            help='Tahun Tanggal Terima DIP tiket yang diproses (wajib).',
        )
        parser.add_argument(
            '--schema', default=SCHEMA,
            help=f'Schema/owner tabel I di Oracle (default: {SCHEMA}).',
        )
        parser.add_argument(
            '--kolom-tiket', default=KOLOM_TIKET,
            help=f'Nama kolom nomor tiket di tabel I (default: {KOLOM_TIKET}).',
        )
        parser.add_argument(
            '--kolom-tahap', default=KOLOM_TAHAP,
            help=f'Nama kolom tahap di tabel I (default: {KOLOM_TAHAP}).',
        )
        parser.add_argument(
            '--koneksi', default=KONEKSI, choices=['primary', 'secondary'],
            help=f'Koneksi Oracle yang dipakai (default: {KONEKSI}, tempat tabel {SCHEMA}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Query Oracle dan tampilkan hasil tanpa menyimpan ke database.',
        )

    def handle(self, *args, **options):
        mulai = datetime.now()
        dry_run = options['dry_run']
        self.log = SyncLog('kd_tahap_sync_dryrun' if dry_run else 'kd_tahap_sync', mulai)
        self.summary = {
            'tiket': 0,
            'tabel': 0,
            'tabel_gagal': 0,
            'query': 0,
            'baris_kd': 0,
            'hasil': Counter(),
            'errors': [],
        }
        self.log.info(f"=== Sinkronisasi KD Tahap{' (DRY-RUN, tidak menyimpan)' if dry_run else ''} ===")
        self.log.info(
            "Parameter: tahun={tahun} koneksi={koneksi} schema={schema!r} kolom_tiket={kolom_tiket} "
            "kolom_tahap={kolom_tahap} dry_run={dry_run}".format(**options)
        )
        self.log.info(
            "Status tiket: " + ', '.join(f"{s} ({STATUS_LABELS[s]})" for s in STATUS_KD_TAHAP)
            + f"; maks {TIKET_PER_QUERY} tiket per query"
        )

        status_run = 'GAGAL'
        try:
            self._jalankan(options)
            status_run = 'SELESAI DENGAN ERROR' if self.summary['errors'] else 'SELESAI'
        except CommandError as exc:
            self.log.error(f"Run dihentikan: {exc}", exc.__cause__)
            raise
        except BaseException as exc:  # KeyboardInterrupt juga dicatat
            self.log.error(f"Run dihentikan oleh error tak terduga: {exc!r}", exc)
            raise
        finally:
            self._tulis_ringkasan(mulai, status_run, dry_run)
            self.log.close()

    def _jalankan(self, options):
        tahun = options['tahun']
        schema = options['schema'].strip()
        kolom_tiket = options['kolom_tiket'].strip()
        kolom_tahap = options['kolom_tahap'].strip()
        dry_run = options['dry_run']

        for label, value in (('--kolom-tiket', kolom_tiket), ('--kolom-tahap', kolom_tahap)):
            if not IDENTIFIER_RE.match(value):
                raise CommandError(f"{label} tidak valid: {value!r}")
        if schema and not IDENTIFIER_RE.match(schema):
            raise CommandError(f"--schema tidak valid: {schema!r}")

        tikets = list(
            Tiket.objects
            .filter(status_tiket__in=STATUS_KD_TAHAP, tgl_terima_dip__year=tahun)
            .select_related('id_periode_data__id_sub_jenis_data_ilap')
            .order_by('id')
        )
        self.summary['tiket'] = len(tikets)
        per_status = Counter(STATUS_LABELS.get(t.status_tiket, t.status_tiket) for t in tikets)
        mode = ' (dry-run)' if dry_run else ''
        self.stdout.write(f"Tiket Pengendalian Mutu & Selesai tahun terima DIP {tahun}: {len(tikets)}{mode}")
        self.log.info(
            f"Tiket ditemukan: {len(tikets)} ("
            + (', '.join(f"{label}={n}" for label, n in sorted(per_status.items())) or '-') + ")"
        )
        if not tikets:
            self.log.info("Tidak ada tiket untuk diproses.")
            return

        per_tabel = defaultdict(list)
        for tiket in tikets:
            try:
                per_tabel[nama_tabel_i(tiket)].append(tiket)
            except KdTahapError as exc:
                self._catat_gagal(tiket, '-', f"{exc}")
        self.summary['tabel'] = len(per_tabel)
        self.log.info(f"Tabel I: {len(per_tabel)}")

        try:
            service = OracleDataSyncService(connection_only=True)
            self.log.info(f"Membuka koneksi Oracle '{options['koneksi']}'...")
            with service._connect_oracle(options['koneksi']) as conn, conn.cursor() as cursor:
                self.log.info("Koneksi Oracle terbuka.")
                for no, (nama_tabel, tikets_tabel) in enumerate(sorted(per_tabel.items()), start=1):
                    tabel = f"{schema}.{nama_tabel}" if schema else nama_tabel
                    self.stdout.write(f"[{no}/{len(per_tabel)}] {tabel}: {len(tikets_tabel)} tiket")
                    self.log.info(f"--- [{no}/{len(per_tabel)}] {tabel}: {len(tikets_tabel)} tiket ---")
                    gagal = False
                    for awal in range(0, len(tikets_tabel), TIKET_PER_QUERY):
                        ok = self._proses_batch(
                            cursor, tabel, tikets_tabel[awal:awal + TIKET_PER_QUERY],
                            kolom_tiket, kolom_tahap, dry_run,
                        )
                        gagal = gagal or not ok
                    if gagal:
                        self.summary['tabel_gagal'] += 1
        except OracleSyncConfigError as exc:
            raise CommandError(f"Koneksi Oracle '{options['koneksi']}' gagal: {exc}") from exc

    def _catat_gagal(self, tiket, tabel, pesan):
        self.summary['hasil'][HASIL_GAGAL] += 1
        self.summary['errors'].append(f"{tiket.nomor_tiket} ({tabel}): {pesan}")
        self.log.error(
            f"  {HASIL_GAGAL:<11} tiket={tiket.nomor_tiket} id={tiket.id} "
            f"status={STATUS_LABELS.get(tiket.status_tiket)} tabel={tabel}: {pesan}"
        )

    def _proses_batch(self, cursor, tabel, tikets, kolom_tiket, kolom_tahap, dry_run):
        """Query satu batch dan proses tiketnya. False bila query gagal."""
        nomors = ', '.join(t.nomor_tiket for t in tikets)
        self.summary['query'] += 1
        t0 = time.monotonic()
        try:
            hitungan = hitung_kd_tahap(cursor, tabel, tikets, kolom_tiket, kolom_tahap)
        except Exception as exc:  # oracledb.DatabaseError and friends
            durasi = time.monotonic() - t0
            pesan = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
            logger.warning("sync_tiket_kd_tahap %s: %s", tabel, pesan)
            self.log.error(
                f"Query {tabel} gagal setelah {durasi:.2f} detik ({len(tikets)} tiket): {pesan}\n"
                f"SQL: SELECT {kolom_tiket}, {kolom_tahap}, COUNT(*) FROM {tabel} "
                f"WHERE {kolom_tiket} IN (<{len(tikets)} tiket>) GROUP BY {kolom_tiket}, {kolom_tahap}\n"
                f"Tiket: {nomors}",
                exc,
            )
            for tiket in tikets:
                self._catat_gagal(tiket, tabel, f"query gagal: {pesan}")
            return False

        durasi = time.monotonic() - t0
        self.log.info(
            f"Query {tabel}: {len(tikets)} tiket, {sum(len(h) for h in hitungan.values())} baris hasil "
            f"(tiket berisi: {len(hitungan)}), {durasi:.2f} detik"
        )

        tersimpan = defaultdict(dict)
        for tiket_id, kd, jumlah in TiketKdTahap.objects.filter(
            id_tiket__in=[t.id for t in tikets]
        ).values_list('id_tiket', 'kd_tahap', 'jumlah_baris'):
            tersimpan[tiket_id][kd] = jumlah

        for tiket in tikets:
            baru = hitungan.get(tiket.id, {})
            lama = tersimpan.get(tiket.id, {})
            hasil = _hasil(lama, baru)
            if dry_run:
                self.stdout.write(f"  {tiket.nomor_tiket}: {_format_kd(baru) if baru else '-'}")
            elif hasil != HASIL_SAMA and hasil != HASIL_KOSONG:
                try:
                    simpan_kd_tahap(tiket, baru)
                except Exception as exc:
                    self.log.error(f"Gagal menyimpan KD Tahap tiket {tiket.nomor_tiket}", exc)
                    self._catat_gagal(tiket, tabel, f"gagal menyimpan: {exc}")
                    continue

            self.summary['hasil'][hasil] += 1
            self.summary['baris_kd'] += len(baru)
            self.log.info(
                f"  {hasil:<11} tiket={tiket.nomor_tiket} id={tiket.id} "
                f"status={STATUS_LABELS.get(tiket.status_tiket)} "
                f"kd_tahap {len(lama)}->{len(baru)} total_baris {sum(lama.values())}->{sum(baru.values())}"
            )
            if baru:
                self.log.info(f"      kd_tahap: {_format_kd(baru)}")
            if hasil == HASIL_BERUBAH:
                beda = [
                    f"{kd if kd is not None else '(kosong)'}: {lama.get(kd, '-')}->{baru.get(kd, '-')}"
                    for kd, _ in urutkan({**lama, **baru})
                    if lama.get(kd) != baru.get(kd)
                ]
                self.log.info(f"      perubahan ({len(beda)}): {', '.join(beda)}")
        return True

    def _tulis_ringkasan(self, mulai, status_run, dry_run):
        s = self.summary
        elapsed = (datetime.now() - mulai).total_seconds()
        hasil = s['hasil']
        diproses = sum(n for h, n in hasil.items() if h != HASIL_GAGAL)

        self.log.info("=== Ringkasan ===")
        self.log.info(f"Status run            : {status_run}{' (dry-run, tidak ada yang disimpan)' if dry_run else ''}")
        self.log.info(f"Tiket ditemukan       : {s['tiket']}")
        self.log.info(f"Tabel I               : {s['tabel']} (gagal: {s['tabel_gagal']})")
        self.log.info(f"Query Oracle          : {s['query']}")
        for h in (HASIL_BARU, HASIL_BERUBAH, HASIL_SAMA, HASIL_DIKOSONGKAN, HASIL_KOSONG, HASIL_GAGAL):
            self.log.info(f"Tiket {h:<16}: {hasil.get(h, 0)}")
        self.log.info(f"Baris KD Tahap        : {s['baris_kd']}")
        self.log.info(f"Waktu eksekusi        : {elapsed:.1f} detik")
        if s['errors']:
            self.log.warn(f"Error ({len(s['errors'])}):")
            for err in s['errors']:
                self.log.warn(f"  - {err}")

        if status_run == 'GAGAL':
            self.stderr.write(f"Log: {self.log.path}")
            return
        judul = 'Dry-run selesai (tidak ada yang disimpan).' if dry_run else 'Sinkronisasi KD Tahap selesai.'
        self.stdout.write(self.style.SUCCESS(judul))
        self.stdout.write(f"- Tiket diproses        : {diproses}")
        self.stdout.write(
            f"- Baru / berubah / sama : {hasil.get(HASIL_BARU, 0)} / {hasil.get(HASIL_BERUBAH, 0)} / "
            f"{hasil.get(HASIL_SAMA, 0)}"
        )
        self.stdout.write(f"- Dikosongkan           : {hasil.get(HASIL_DIKOSONGKAN, 0)}")
        self.stdout.write(f"- Tanpa baris di Oracle : {hasil.get(HASIL_KOSONG, 0) + hasil.get(HASIL_DIKOSONGKAN, 0)}")
        self.stdout.write(f"- Baris KD Tahap        : {s['baris_kd']}")
        self.stdout.write(f"- Tiket dilewati        : {hasil.get(HASIL_GAGAL, 0)}")
        self.stdout.write(f"- Waktu eksekusi        : {elapsed:.1f} detik")

        errors = s['errors']
        if errors:
            self.stdout.write(self.style.WARNING(f"Error ({len(errors)}):"))
            for err in errors[:20]:
                self.stdout.write(f"  - {err}")
            if len(errors) > 20:
                self.stdout.write(f"  ... dan {len(errors) - 20} error lainnya")
        self.stdout.write(f"Log: {self.log.path}")
