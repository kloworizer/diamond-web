"""Ambil jumlah baris per KD_TAHAP & QC dari tabel I Oracle untuk tiket Pengendalian Mutu & Selesai.

Untuk setiap tiket berstatus Pengendalian Mutu atau Selesai dengan tahun Tanggal
Terima DIP = --tahun, command ini menghitung jumlah baris per KD_TAHAP dan flag
QC milik tiket itu di tabel I-nya, lalu mengganti seluruh baris TiketKdTahap milik tiket
tersebut dengan hasilnya. Lihat diamond_web/utils/tiket_kd_tahap.py untuk query.

Tiket dikelompokkan per tabel dan Oracle di-query sekali per tabel (per 500
tiket), karena NO_TIKET di tabel I tidak ber-index. Query-query itu berjalan
paralel (--workers), masing-masing dengan koneksi Oracle sendiri dan batas
waktu (--timeout), jadi satu tabel yang lambat atau timeout tidak menahan tabel
lain. Penyimpanan ke database tetap dilakukan satu per satu di thread utama.

Query yang gagal (timeout, koneksi putus, ...) diulang di akhir run sampai
--retry kali; error permanen (tabel/kolom tidak ada, tanpa hak akses) tidak
diulang. Tiket di tabel yang tetap gagal dilewati dan barisnya yang lama tidak
disentuh; log mencantumkan perintah untuk mengulang tabel-tabel itu nanti
(--tabel). Tiket yang tidak punya baris di Oracle dikosongkan.

Setiap run menulis log rinci ke sync_logs/kd_tahap_sync_<waktu>.log
(kd_tahap_sync_dryrun_<waktu>.log untuk --dry-run), yang tampil di halaman
Sync Log Status: parameter, query & durasi per tabel, hasil per tiket
dibanding data tersimpan, setiap error lengkap dengan traceback, dan ringkasan.

Satu tiket juga dapat disinkronkan dari halaman detilnya (Sinkronisasi KD Tahap).

Contoh:
    python manage.py sync_tiket_kd_tahap --tahun 2025
    python manage.py sync_tiket_kd_tahap --tahun 2025 --workers 8 --timeout 1800
    python manage.py sync_tiket_kd_tahap --tahun 2025 --tabel KPDE_A,KPDE_B
    python manage.py sync_tiket_kd_tahap --tahun 2025 --dry-run
"""

import logging
import os
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from ...constants.tiket_status import STATUS_LABELS
from ...models.tiket import Tiket
from ...models.tiket_kd_tahap import TiketKdTahap
from ...utils.oracle_sync import OracleDataSyncService, OracleSyncConfigError
from ...utils.tiket_kd_tahap import (
    IDENTIFIER_RE,
    KOLOM_QC,
    KOLOM_TAHAP,
    KOLOM_TIKET,
    KONEKSI,
    QUERY_TIMEOUT,
    SCHEMA,
    STATUS_KD_TAHAP,
    TIKET_PER_QUERY,
    KdTahapError,
    hitung_kd_tahap,
    is_permanen,
    is_timeout,
    label,
    nama_tabel_i,
    pesan_error,
    set_query_timeout,
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

WORKERS = 4
RETRY = 1


def _hasil(lama, baru):
    if lama == baru:
        return HASIL_SAMA if baru else HASIL_KOSONG
    if not lama:
        return HASIL_BARU
    return HASIL_BERUBAH if baru else HASIL_DIKOSONGKAN


def _format_kd(hitungan):
    """'KD/QC=jumlah, ...' untuk log & dry-run."""
    return ', '.join(f"{label(kunci)}={jumlah}" for kunci, jumlah in urutkan(hitungan)) or '-'


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


class Unit:
    """Satu query Oracle: satu batch (<= TIKET_PER_QUERY) tiket satu tabel."""

    def __init__(self, nama_tabel, tabel, tikets):
        self.nama_tabel = nama_tabel
        self.tabel = tabel
        self.tikets = tikets
        self.percobaan = 0
        # Diisi oleh worker.
        self.hitungan = None
        self.error = None
        self.durasi = 0.0


def _query_unit(service, koneksi, timeout, unit, kolom):
    """Jalankan query satu unit di thread worker, dengan koneksi Oracle sendiri.

    Tidak menyentuh ORM Django dan tidak pernah raise: hasil atau error
    disimpan di *unit* dan diproses thread utama. Koneksi baru per unit, karena
    koneksi yang kena call_timeout tidak bisa dipakai lagi.
    """
    unit.percobaan += 1
    unit.hitungan = unit.error = None
    t0 = time.monotonic()
    try:
        with service._connect_oracle(koneksi) as conn:
            set_query_timeout(conn, timeout)
            with conn.cursor() as cursor:
                unit.hitungan = hitung_kd_tahap(cursor, unit.tabel, unit.tikets, *kolom)
    except BaseException as exc:  # noqa: B902 - dilaporkan ke thread utama
        unit.error = exc
    unit.durasi = time.monotonic() - t0
    return unit


class Command(BaseCommand):
    help = (
        "Ambil jumlah baris per KD_TAHAP dari tabel I Oracle untuk tiket "
        "Pengendalian Mutu & Selesai pada satu tahun terima DIP (paralel per tabel)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--tahun', type=int, required=True,
            help='Tahun Tanggal Terima DIP tiket yang diproses (wajib).',
        )
        parser.add_argument(
            '--tabel', default='',
            help='Hanya proses tabel I ini (dipisah koma), mis. untuk mengulang tabel yang gagal.',
        )
        parser.add_argument(
            '--workers', type=int, default=WORKERS,
            help=f'Jumlah query Oracle yang berjalan bersamaan (default: {WORKERS}).',
        )
        parser.add_argument(
            '--timeout', type=int, default=QUERY_TIMEOUT,
            help=(
                f'Batas waktu satu query dalam detik, 0 = tanpa batas (default: {QUERY_TIMEOUT}, '
                'env ORACLE_KD_TAHAP_TIMEOUT).'
            ),
        )
        parser.add_argument(
            '--retry', type=int, default=RETRY,
            help=f'Berapa kali query yang gagal diulang di akhir run (default: {RETRY}).',
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
            '--kolom-qc', default=KOLOM_QC,
            help=f'Nama kolom flag QC di tabel I (default: {KOLOM_QC}).',
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
            'query': 0,
            'query_timeout': 0,
            'baris_kd': 0,
            'hasil': Counter(),
            'errors': [],
            'tabel_gagal': {},  # nama tabel -> pesan error terakhir
        }
        self.log.info(f"=== Sinkronisasi KD Tahap{' (DRY-RUN, tidak menyimpan)' if dry_run else ''} ===")
        self.log.info(
            "Parameter: tahun={tahun} koneksi={koneksi} schema={schema!r} kolom_tiket={kolom_tiket} "
            "kolom_tahap={kolom_tahap} kolom_qc={kolom_qc} workers={workers} timeout={timeout}s retry={retry} "
            "tabel={tabel!r} dry_run={dry_run}".format(**options)
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
            self._tulis_ringkasan(mulai, status_run, options)
            self.log.close()

    def _jalankan(self, options):
        tahun = options['tahun']
        schema = options['schema'].strip()
        kolom_tiket = options['kolom_tiket'].strip()
        kolom_tahap = options['kolom_tahap'].strip()
        kolom_qc = options['kolom_qc'].strip()
        kolom = (kolom_tiket, kolom_tahap, kolom_qc)
        hanya_tabel = {t.strip().upper() for t in options['tabel'].split(',') if t.strip()}

        for opsi, value in (('--kolom-tiket', kolom_tiket), ('--kolom-tahap', kolom_tahap),
                            ('--kolom-qc', kolom_qc)):
            if not IDENTIFIER_RE.match(value):
                raise CommandError(f"{opsi} tidak valid: {value!r}")
        if schema and not IDENTIFIER_RE.match(schema):
            raise CommandError(f"--schema tidak valid: {schema!r}")
        if options['workers'] < 1:
            raise CommandError("--workers minimal 1")
        if options['timeout'] < 0 or options['retry'] < 0:
            raise CommandError("--timeout dan --retry tidak boleh negatif")

        tikets = list(
            Tiket.objects
            .filter(status_tiket__in=STATUS_KD_TAHAP, tgl_terima_dip__year=tahun)
            .select_related('id_periode_data__id_sub_jenis_data_ilap')
            .order_by('id')
        )

        per_tabel = defaultdict(list)
        tidak_valid = []
        for tiket in tikets:
            try:
                nama = nama_tabel_i(tiket)
            except KdTahapError as exc:
                tidak_valid.append((tiket, exc))
                continue
            if not hanya_tabel or nama in hanya_tabel:
                per_tabel[nama].append(tiket)
        if hanya_tabel:
            # Tiket dengan nama tabel tidak valid bukan bagian dari tabel yang diminta.
            tidak_valid = []
            tikets = [t for daftar in per_tabel.values() for t in daftar]
            tidak_ada = sorted(hanya_tabel - set(per_tabel))
            if tidak_ada:
                self.log.warn(f"--tabel tanpa tiket tahun {tahun}: {', '.join(tidak_ada)}")

        self.summary['tiket'] = len(tikets)
        self.summary['tabel'] = len(per_tabel)
        per_status = Counter(STATUS_LABELS.get(t.status_tiket, t.status_tiket) for t in tikets)
        mode = ' (dry-run)' if options['dry_run'] else ''
        self.stdout.write(f"Tiket Pengendalian Mutu & Selesai tahun terima DIP {tahun}: {len(tikets)}{mode}")
        self.log.info(
            f"Tiket ditemukan: {len(tikets)} ("
            + (', '.join(f"{nama}={n}" for nama, n in sorted(per_status.items())) or '-') + ")"
        )
        self.log.info(f"Tabel I: {len(per_tabel)}")
        for tiket, exc in tidak_valid:
            self._catat_gagal(tiket, '-', f"{exc}")
        if not per_tabel:
            self.log.info("Tidak ada tiket untuk diproses.")
            return

        units = []
        for nama_tabel, tikets_tabel in sorted(per_tabel.items()):
            tabel = f"{schema}.{nama_tabel}" if schema else nama_tabel
            for awal in range(0, len(tikets_tabel), TIKET_PER_QUERY):
                units.append(Unit(nama_tabel, tabel, tikets_tabel[awal:awal + TIKET_PER_QUERY]))

        service = OracleDataSyncService(connection_only=True)
        # Gagal cepat bila koneksi memang tidak bisa dibuka, sebelum ratusan
        # query masing-masing gagal dengan error yang sama.
        self.log.info(f"Tes koneksi Oracle '{options['koneksi']}'...")
        try:
            with service._connect_oracle(options['koneksi']):
                pass
        except OracleSyncConfigError as exc:
            raise CommandError(f"Koneksi Oracle '{options['koneksi']}' gagal: {exc}") from exc
        self.log.info(
            f"Koneksi Oracle OK. {len(units)} query untuk {len(per_tabel)} tabel, "
            f"{options['workers']} worker paralel, timeout {options['timeout'] or 'tanpa batas'} detik."
        )

        sisa = units
        for putaran in range(options['retry'] + 1):
            if not sisa:
                break
            if putaran:
                self.stdout.write(f"Mengulang {len(sisa)} query yang gagal (percobaan ke-{putaran + 1})...")
                self.log.info(f"=== Pengulangan ke-{putaran}: {len(sisa)} query ===")
            sisa = self._putaran(service, sisa, options, kolom,
                                 terakhir=putaran == options['retry'])

    def _putaran(self, service, units, options, kolom, terakhir):
        """Jalankan *units* paralel; kembalikan unit gagal yang masih layak diulang."""
        ulang = []
        executor = ThreadPoolExecutor(max_workers=options['workers'], thread_name_prefix='kd_tahap')
        try:
            futures = [
                executor.submit(_query_unit, service, options['koneksi'], options['timeout'],
                                unit, kolom)
                for unit in units
            ]
            for no, future in enumerate(as_completed(futures), start=1):
                unit = future.result()
                self.summary['query'] += 1
                if unit.error is None:
                    self.stdout.write(
                        f"[{no}/{len(units)}] {unit.tabel}: {len(unit.tikets)} tiket OK ({unit.durasi:.1f} detik)"
                    )
                    self._proses_hasil(unit, options['dry_run'])
                    continue

                timeout = is_timeout(unit.error, unit.durasi, options['timeout'])
                self.summary['query_timeout'] += timeout
                permanen = is_permanen(unit.error)
                diulang = not terakhir and not permanen
                self.stdout.write(self.style.WARNING(
                    f"[{no}/{len(units)}] {unit.tabel}: {'TIMEOUT' if timeout else 'GAGAL'} "
                    f"({unit.durasi:.1f} detik){' - akan diulang' if diulang else ''}"
                ))
                self._log_error_unit(unit, options, kolom, timeout, permanen, diulang)
                if diulang:
                    ulang.append(unit)
                else:
                    self._unit_gagal(unit, options['timeout'], timeout)
        except BaseException:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
        executor.shutdown(wait=True)
        return ulang

    def _log_error_unit(self, unit, options, kolom, timeout, permanen, diulang):
        pesan = pesan_error(unit.error)
        if timeout:
            jenis = f"TIMEOUT (melewati {options['timeout']} detik)"
        elif permanen:
            jenis = 'error permanen, tidak diulang'
        else:
            jenis = 'error'
        logger.warning("sync_tiket_kd_tahap %s: %s", unit.tabel, pesan)
        self.log.error(
            f"Query {unit.tabel} gagal [{jenis}] pada percobaan ke-{unit.percobaan} setelah "
            f"{unit.durasi:.2f} detik ({len(unit.tikets)} tiket): {pesan}"
            f"{' -> akan diulang' if diulang else ''}\n"
            f"SQL: SELECT {', '.join(kolom)}, COUNT(*) FROM {unit.tabel} "
            f"WHERE {kolom[0]} IN (<{len(unit.tikets)} tiket>) GROUP BY {', '.join(kolom)}\n"
            f"Tiket: {', '.join(t.nomor_tiket for t in unit.tikets)}",
            unit.error,
        )

    def _unit_gagal(self, unit, batas, timeout):
        pesan = pesan_error(unit.error)
        if timeout:
            pesan = f"query melewati batas waktu {batas} detik ({pesan})"
        self.summary['tabel_gagal'][unit.nama_tabel] = pesan
        for tiket in unit.tikets:
            self._catat_gagal(tiket, unit.tabel, f"query gagal setelah {unit.percobaan} percobaan: {pesan}")

    def _catat_gagal(self, tiket, tabel, pesan):
        self.summary['hasil'][HASIL_GAGAL] += 1
        self.summary['errors'].append(f"{tiket.nomor_tiket} ({tabel}): {pesan}")
        self.log.error(
            f"  {HASIL_GAGAL:<11} tiket={tiket.nomor_tiket} id={tiket.id} "
            f"status={STATUS_LABELS.get(tiket.status_tiket)} tabel={tabel}: {pesan}"
        )

    def _proses_hasil(self, unit, dry_run):
        """Bandingkan hasil query satu unit dengan data tersimpan, lalu simpan (thread utama)."""
        tikets, hitungan = unit.tikets, unit.hitungan
        self.log.info(
            f"Query {unit.tabel}: {len(tikets)} tiket, {sum(len(h) for h in hitungan.values())} baris hasil "
            f"(tiket berisi: {len(hitungan)}), {unit.durasi:.2f} detik"
            + (f", percobaan ke-{unit.percobaan}" if unit.percobaan > 1 else '')
        )

        tersimpan = defaultdict(dict)
        for tiket_id, kd, qc, jumlah in TiketKdTahap.objects.filter(
            id_tiket__in=[t.id for t in tikets]
        ).values_list('id_tiket', 'kd_tahap', 'qc', 'jumlah_baris'):
            tersimpan[tiket_id][(kd, qc)] = jumlah

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
                    self._catat_gagal(tiket, unit.tabel, f"gagal menyimpan: {exc}")
                    continue

            self.summary['hasil'][hasil] += 1
            self.summary['baris_kd'] += len(baru)
            self.log.info(
                f"  {hasil:<11} tiket={tiket.nomor_tiket} id={tiket.id} "
                f"status={STATUS_LABELS.get(tiket.status_tiket)} "
                f"kd_tahap/qc {len(lama)}->{len(baru)} total_baris {sum(lama.values())}->{sum(baru.values())}"
            )
            if baru:
                self.log.info(f"      kd_tahap/qc: {_format_kd(baru)}")
            if hasil == HASIL_BERUBAH:
                beda = [
                    f"{label(kunci)}: {lama.get(kunci, '-')}->{baru.get(kunci, '-')}"
                    for kunci, _ in urutkan({**lama, **baru})
                    if lama.get(kunci) != baru.get(kunci)
                ]
                self.log.info(f"      perubahan ({len(beda)}): {', '.join(beda)}")

    def _perintah_ulang(self, options):
        """Perintah untuk mengulang tabel yang gagal, atau None."""
        gagal = self.summary['tabel_gagal']
        if not gagal:
            return None
        bagian = [f"python manage.py sync_tiket_kd_tahap --tahun {options['tahun']}",
                  f"--tabel {','.join(sorted(gagal))}"]
        if options['koneksi'] != KONEKSI:
            bagian.append(f"--koneksi {options['koneksi']}")
        if options['schema'].strip() != SCHEMA:
            bagian.append(f"--schema {options['schema'].strip() or ''}")
        for opsi, default in (('kolom_tiket', KOLOM_TIKET), ('kolom_tahap', KOLOM_TAHAP), ('kolom_qc', KOLOM_QC)):
            if options[opsi].strip() != default:
                bagian.append(f"--{opsi.replace('_', '-')} {options[opsi].strip()}")
        if any('batas waktu' in p for p in gagal.values()):
            bagian.append(f"--timeout {max(options['timeout'] * 2, 1800)}")
        if options['dry_run']:
            bagian.append('--dry-run')
        return ' '.join(bagian)

    def _tulis_ringkasan(self, mulai, status_run, options):
        s = self.summary
        dry_run = options['dry_run']
        elapsed = (datetime.now() - mulai).total_seconds()
        hasil = s['hasil']
        diproses = sum(n for h, n in hasil.items() if h != HASIL_GAGAL)
        perintah_ulang = self._perintah_ulang(options)

        self.log.info("=== Ringkasan ===")
        self.log.info(f"Status run            : {status_run}{' (dry-run, tidak ada yang disimpan)' if dry_run else ''}")
        self.log.info(f"Tiket ditemukan       : {s['tiket']}")
        self.log.info(f"Tabel I               : {s['tabel']} (gagal: {len(s['tabel_gagal'])})")
        self.log.info(f"Query Oracle          : {s['query']} (timeout: {s['query_timeout']})")
        for h in (HASIL_BARU, HASIL_BERUBAH, HASIL_SAMA, HASIL_DIKOSONGKAN, HASIL_KOSONG, HASIL_GAGAL):
            self.log.info(f"Tiket {h:<16}: {hasil.get(h, 0)}")
        self.log.info(f"Baris KD Tahap/QC     : {s['baris_kd']}")
        self.log.info(f"Waktu eksekusi        : {elapsed:.1f} detik")
        if s['tabel_gagal']:
            self.log.warn(f"Tabel gagal ({len(s['tabel_gagal'])}):")
            for nama, pesan in sorted(s['tabel_gagal'].items()):
                self.log.warn(f"  - {nama}: {pesan}")
            self.log.warn(f"Ulangi tabel yang gagal dengan: {perintah_ulang}")
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
        self.stdout.write(f"- Baris KD Tahap/QC     : {s['baris_kd']}")
        self.stdout.write(f"- Tiket dilewati        : {hasil.get(HASIL_GAGAL, 0)}")
        self.stdout.write(f"- Query timeout         : {s['query_timeout']}")
        self.stdout.write(f"- Waktu eksekusi        : {elapsed:.1f} detik")

        errors = s['errors']
        if errors:
            self.stdout.write(self.style.WARNING(f"Error ({len(errors)}):"))
            for err in errors[:20]:
                self.stdout.write(f"  - {err}")
            if len(errors) > 20:
                self.stdout.write(f"  ... dan {len(errors) - 20} error lainnya")
        if perintah_ulang:
            self.stdout.write(self.style.WARNING(f"Tabel gagal: {len(s['tabel_gagal'])}. Ulangi dengan:"))
            self.stdout.write(f"  {perintah_ulang}")
        self.stdout.write(f"Log: {self.log.path}")
