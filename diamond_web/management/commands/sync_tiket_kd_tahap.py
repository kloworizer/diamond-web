"""Ambil jumlah baris per KD_TAHAP dari tabel I Oracle untuk tiket Pengendalian Mutu & Selesai.

Untuk setiap tiket berstatus Pengendalian Mutu atau Selesai dengan tahun Tanggal
Terima DIP = --tahun, command ini menghitung jumlah baris per KD_TAHAP milik
tiket itu di tabel I-nya, lalu mengganti seluruh baris TiketKdTahap milik tiket
tersebut dengan hasilnya. Lihat diamond_web/utils/tiket_kd_tahap.py untuk query.

Tiket dikelompokkan per tabel dan Oracle di-query sekali per tabel (per 500
tiket), karena NO_TIKET di tabel I tidak ber-index. Tiket yang query tabelnya
gagal dilewati dan barisnya yang lama tidak disentuh. Tiket yang tidak punya
baris di Oracle dikosongkan.

Satu tiket juga dapat disinkronkan dari halaman detilnya (aksi Sinkronisasi).

Contoh:
    python manage.py sync_tiket_kd_tahap --tahun 2025
    python manage.py sync_tiket_kd_tahap --tahun 2025 --dry-run
    python manage.py sync_tiket_kd_tahap --tahun 2025 --koneksi primary --schema LAIN
"""

import logging
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ...models.tiket import Tiket
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

logger = logging.getLogger(__name__)


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
        mode = ' (dry-run)' if dry_run else ''
        self.stdout.write(f"Tiket Pengendalian Mutu & Selesai tahun terima DIP {tahun}: {len(tikets)}{mode}")
        if not tikets:
            return

        summary = {
            'start': timezone.now(),
            'diproses': 0,
            'tanpa_baris': 0,
            'baris_disimpan': 0,
            'dilewati': 0,
            'errors': [],
        }

        per_tabel = defaultdict(list)
        for tiket in tikets:
            try:
                per_tabel[nama_tabel_i(tiket)].append(tiket)
            except KdTahapError as exc:
                summary['dilewati'] += 1
                summary['errors'].append(f"{tiket.nomor_tiket}: {exc}")

        try:
            service = OracleDataSyncService(connection_only=True)
            with service._connect_oracle(options['koneksi']) as conn, conn.cursor() as cursor:
                for no, (nama_tabel, tikets_tabel) in enumerate(sorted(per_tabel.items()), start=1):
                    tabel = f"{schema}.{nama_tabel}" if schema else nama_tabel
                    self.stdout.write(f"[{no}/{len(per_tabel)}] {tabel}: {len(tikets_tabel)} tiket")
                    for awal in range(0, len(tikets_tabel), TIKET_PER_QUERY):
                        self._proses_batch(
                            cursor, tabel, tikets_tabel[awal:awal + TIKET_PER_QUERY],
                            kolom_tiket, kolom_tahap, dry_run, summary,
                        )
        except OracleSyncConfigError as exc:
            raise CommandError(str(exc)) from exc

        self._tulis_ringkasan(summary, dry_run)

    def _proses_batch(self, cursor, tabel, tikets, kolom_tiket, kolom_tahap, dry_run, summary):
        try:
            hitungan = hitung_kd_tahap(cursor, tabel, tikets, kolom_tiket, kolom_tahap)
        except Exception as exc:  # oracledb.DatabaseError and friends
            pesan = str(exc).splitlines()[0]
            summary['dilewati'] += len(tikets)
            summary['errors'].append(f"{tabel} ({len(tikets)} tiket): {pesan}")
            logger.warning("sync_tiket_kd_tahap %s: %s", tabel, pesan)
            return

        for tiket in tikets:
            hasil = hitungan.get(tiket.id, {})
            if dry_run:
                detail = ', '.join(f"{kd}={jumlah}" for kd, jumlah in urutkan(hasil)) or '-'
                self.stdout.write(f"  {tiket.nomor_tiket}: {detail}")
            else:
                simpan_kd_tahap(tiket, hasil)

            summary['diproses'] += 1
            summary['baris_disimpan'] += len(hasil)
            if not hasil:
                summary['tanpa_baris'] += 1

    def _tulis_ringkasan(self, summary, dry_run):
        elapsed = (timezone.now() - summary['start']).total_seconds()
        judul = 'Dry-run selesai (tidak ada yang disimpan).' if dry_run else 'Sinkronisasi KD Tahap selesai.'
        self.stdout.write(self.style.SUCCESS(judul))
        self.stdout.write(f"- Tiket diproses        : {summary['diproses']}")
        self.stdout.write(f"- Tanpa baris di Oracle : {summary['tanpa_baris']}")
        self.stdout.write(f"- Baris KD Tahap        : {summary['baris_disimpan']}")
        self.stdout.write(f"- Tiket dilewati        : {summary['dilewati']}")
        self.stdout.write(f"- Waktu eksekusi        : {elapsed:.1f} detik")

        errors = summary['errors']
        if errors:
            self.stdout.write(self.style.WARNING(f"Error ({len(errors)}):"))
            for err in errors[:20]:
                self.stdout.write(f"  - {err}")
            if len(errors) > 20:
                self.stdout.write(f"  ... dan {len(errors) - 20} error lainnya")
