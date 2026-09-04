"""Bangun ulang tabel Data Prioritas dari tabel impor ``temp_prioritas``.

Perintah ini **menghapus seluruh isi** ``jenis_prioritas_data``, lalu membuatnya
kembali dari tabel impor yang berbentuk satu baris per tabel data, dengan satu
kolom penanda per tahun::

    CREATE TABLE temp_prioritas (
        TABEL_I         VARCHAR(32),
        ID_TABEL_S      VARCHAR(16),   -- = JenisDataILAP.id_sub_jenis_data
        PRIORITAS_2022  INTEGER,
        ...
        PRIORITAS_2026  INTEGER
    );

Setiap kolom ``PRIORITAS_<tahun>`` yang bernilai 1 menghasilkan satu record::

    Sub Jenis Data = ID_TABEL_S
    Tahun          = <tahun>
    Start Date     = 1 Januari <tahun>
    End Date       = 31 Desember <tahun>

Kolom tahunnya **ditemukan sendiri** dari skema tabel (pola ``PRIORITAS_<4
digit>``), jadi menambah ``PRIORITAS_2027`` cukup dengan mengimpor ulang tabelnya
— perintah ini tidak perlu diubah.

Dua hal yang perlu diketahui sebelum menjalankan:

* **FK prioritas pada tiket ikut dikosongkan lebih dulu.** ``Tiket``
  menunjuk ``JenisPrioritasData`` dengan ``on_delete=PROTECT``, jadi selama masih
  ada tiket yang menunjuknya, penghapusan mustahil. Perintah ini mengosongkan
  kolom itu sebagai bagian dari pekerjaannya. **Setelah selesai, jalankan
  ``backfill_tiket_jenis_prioritas``** untuk mengisinya kembali sesuai masa
  berlaku yang baru — sampai itu dijalankan, seluruh tiket tampil bukan prioritas
  di Home (menu Identifikasi & Quality Control tidak terpengaruh, keduanya
  menghitung dari tabel prioritas secara langsung).
* **No ND dan rentang tanggal yang ada sekarang hilang**, diganti nilai yang
  dibangkitkan di sini — tabel impor tidak membawa nomor ND. Pakai
  ``--dump-existing`` untuk menyimpan salinan isi lama lebih dulu.

Satu ``ID_TABEL_S`` yang muncul di lebih dari satu baris (mis. dua tabel fisik
untuk sub jenis data yang sama) **digabung dengan OR**: tahun itu prioritas bila
salah satu barisnya menandainya. Constraint ``unique_subjenis_tahun`` memang
hanya mengizinkan satu record per pasangan sub jenis data + tahun.

Penggunaan::

    python manage.py rebuild_jenis_prioritas_from_temp --dry-run
    python manage.py rebuild_jenis_prioritas_from_temp --dump-existing prioritas-lama.json
    python manage.py rebuild_jenis_prioritas_from_temp --noinput
    python manage.py backfill_tiket_jenis_prioritas --dry-run     # langkah berikutnya
"""
import json
import re
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from ...models.jenis_data_ilap import JenisDataILAP
from ...models.jenis_prioritas_data import JenisPrioritasData
from ...models.tiket import Tiket

DEFAULT_TABLE = 'temp_prioritas'
SUB_COLUMN = 'ID_TABEL_S'
YEAR_COLUMN = re.compile(r'^PRIORITAS_(\d{4})$', re.IGNORECASE)

# Nama tabel impor hanya boleh identifier polos — ia disisipkan ke SQL sebagai
# nama tabel, yang tidak bisa diparameterkan.
SAFE_TABLE_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def discover_year_columns(table):
    """``{tahun: nama kolom}`` untuk setiap kolom ``PRIORITAS_<tahun>``."""
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    years = {}
    for column in description:
        match = YEAR_COLUMN.match(column.name)
        if match:
            years[int(match.group(1))] = column.name
    return years


def read_temp_rows(table, year_columns):
    """Baris tabel impor sebagai ``(kode sub jenis data, {tahun: nilai})``."""
    columns = [SUB_COLUMN] + [year_columns[y] for y in sorted(year_columns)]
    quote = connection.ops.quote_name
    sql = f'SELECT {", ".join(quote(c) for c in columns)} FROM {quote(table)}'
    with connection.cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            kode = (row[0] or '').strip()
            flags = dict(zip(sorted(year_columns), row[1:]))
            yield kode, flags


class Command(BaseCommand):
    help = (
        'Hapus seluruh isi jenis_prioritas_data lalu bangun ulang dari tabel '
        'impor temp_prioritas (satu record per Sub Jenis Data per tahun bertanda)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Laporkan apa yang akan terjadi tanpa menyentuh database.',
        )
        parser.add_argument(
            '--table', default=DEFAULT_TABLE, metavar='NAMA',
            help=f'Nama tabel impor. Default "{DEFAULT_TABLE}".',
        )
        parser.add_argument(
            '--no-nd', default='-', metavar='TEKS',
            help='Nilai kolom No ND untuk record yang dibuat — tabel impor tidak '
                 'membawanya. Default "-".',
        )
        parser.add_argument(
            '--dump-existing', metavar='PATH',
            help='Simpan isi jenis_prioritas_data yang sekarang ke berkas JSON '
                 'sebelum dihapus.',
        )
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Jangan minta konfirmasi.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        table = options['table']

        if not SAFE_TABLE_NAME.match(table):
            raise CommandError(f'Nama tabel tidak valid: "{table}".')
        if table not in connection.introspection.table_names():
            raise CommandError(
                f'Tabel "{table}" tidak ada di database ini. Impor dulu datanya.'
            )

        year_columns = discover_year_columns(table)
        if not year_columns:
            raise CommandError(
                f'Tabel "{table}" tidak punya satu pun kolom PRIORITAS_<tahun>.'
            )
        self.stdout.write(
            f'Tahun yang ditemukan di {table}: '
            f'{", ".join(str(y) for y in sorted(year_columns))}'
        )

        wanted, unknown, collapsed, marked = self._plan(table, year_columns)
        if not wanted:
            raise CommandError(
                f'Tidak ada satu pun baris bertanda prioritas di "{table}" — '
                f'menghapus isi tabel lama tanpa pengganti jelas bukan yang dimaksud.'
            )

        self._report_plan(wanted, unknown, collapsed, marked, year_columns)

        if self.dry_run:
            self.stdout.write(self.style.WARNING('Dry run: tidak ada yang ditulis.'))
            return

        if options['dump_existing']:
            self._dump_existing(options['dump_existing'])

        if options['interactive'] and not self._confirm(options):
            self.stdout.write('Dibatalkan.')
            return

        self._rebuild(wanted, options['no_nd'])

    # ------------------------------------------------------------------ #
    # Perencanaan                                                         #
    # ------------------------------------------------------------------ #

    def _plan(self, table, year_columns):
        """Kumpulkan ``{(sub_id, tahun)}`` yang harus ada, beserta temuannya.

        Kode yang muncul lebih dari sekali digabung dengan OR: satu baris saja
        menandai suatu tahun sudah cukup, karena constraint database hanya
        mengizinkan satu record per sub jenis data per tahun.
        """
        sub_ids = dict(
            JenisDataILAP.objects.values_list('id_sub_jenis_data', 'id')
        )

        wanted = set()
        unknown = set()
        seen_kode = defaultdict(int)
        marked = defaultdict(int)

        for kode, flags in read_temp_rows(table, year_columns):
            if not kode:
                continue
            seen_kode[kode] += 1
            sub_id = sub_ids.get(kode)
            if sub_id is None:
                unknown.add(kode)
                continue
            for tahun, value in flags.items():
                if self._is_marked(value):
                    wanted.add((sub_id, tahun))
                    marked[tahun] += 1

        collapsed = {k for k, n in seen_kode.items() if n > 1}
        return wanted, unknown, collapsed, marked

    @staticmethod
    def _is_marked(value):
        """Apakah sel penanda tahun berarti "prioritas"?

        Kolomnya integer 0/1, tetapi impor dari spreadsheet kerap membawa teks.
        Yang dihitung prioritas hanya nilai 1 — kosong, 0, dan NULL bukan.
        """
        if value is None:
            return False
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return False
            try:
                value = int(value)
            except ValueError:
                return False
        return int(value) == 1

    def _report_plan(self, wanted, unknown, collapsed, marked, year_columns):
        existing = JenisPrioritasData.objects.count()
        linked = Tiket.objects.filter(id_jenis_prioritas_data__isnull=False).count()

        self.stdout.write('')
        self.stdout.write(f'Akan dihapus  : {existing} record jenis_prioritas_data')
        self.stdout.write(f'Akan dibuat   : {len(wanted)} record baru')
        for tahun in sorted(year_columns):
            jumlah = sum(1 for _, y in wanted if y == tahun)
            self.stdout.write(
                f'  {tahun}  {jumlah:>5} sub jenis data'
                f'   ({date(tahun, 1, 1)} s/d {date(tahun, 12, 31)})'
            )

        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            f'FK prioritas pada {linked} tiket dikosongkan lebih dulu '
            f'(PROTECT menghalangi penghapusan). Jalankan '
            f'"backfill_tiket_jenis_prioritas" setelah ini untuk mengisinya kembali.'
        ))

        if collapsed:
            duplikat = sum(marked.values()) - len(wanted)
            self.stdout.write(self.style.WARNING(
                f'{len(collapsed)} kode muncul lebih dari sekali di tabel impor dan '
                f'digabung (OR), menghilangkan {duplikat} tanda kembar: '
                f'{", ".join(sorted(collapsed)[:5])}'
                f'{" ..." if len(collapsed) > 5 else ""}'
            ))
        if unknown:
            self.stdout.write(self.style.WARNING(
                f'{len(unknown)} kode ID_TABEL_S tidak ada di jenis_data_ilap dan '
                f'dilewati: {", ".join(sorted(unknown)[:10])}'
                f'{" ..." if len(unknown) > 10 else ""}'
            ))

    # ------------------------------------------------------------------ #
    # Pelaksanaan                                                         #
    # ------------------------------------------------------------------ #

    def _dump_existing(self, path):
        rows = list(
            JenisPrioritasData.objects
            .order_by('id')
            .values(
                'id', 'id_sub_jenis_data_ilap', 'no_nd', 'tahun',
                'start_date', 'end_date',
            )
        )
        for row in rows:
            for key in ('start_date', 'end_date'):
                if row[key] is not None:
                    row[key] = row[key].isoformat()
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(rows, handle, ensure_ascii=False, indent=2)
        self.stdout.write(f'Salinan {len(rows)} record lama ditulis ke {path}.')

    def _confirm(self, options):
        existing = JenisPrioritasData.objects.count()
        linked = Tiket.objects.filter(id_jenis_prioritas_data__isnull=False).count()
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            f'Ini akan MENGHAPUS {existing} record jenis_prioritas_data '
            f'(berikut No ND dan rentang tanggalnya) dan mengosongkan FK prioritas '
            f'pada {linked} tiket.'
        ))
        if not options['dump_existing']:
            self.stdout.write(self.style.WARNING(
                'Tidak ada salinan yang dibuat — batalkan dan pakai --dump-existing '
                'bila isi lamanya masih diperlukan.'
            ))
        jawab = input('Ketik "ya" untuk melanjutkan: ')
        return jawab.strip().lower() == 'ya'

    def _rebuild(self, wanted, no_nd):
        """Kosongkan FK tiket, hapus tabel lama, tulis yang baru — satu transaksi.

        Satu transaksi supaya tidak ada keadaan setengah jadi: kalau pembuatan
        record baru gagal, tabel lama dan FK tiket kembali seperti semula.
        """
        no_nd = (no_nd or '-')[:20]
        baru = [
            JenisPrioritasData(
                id_sub_jenis_data_ilap_id=sub_id,
                tahun=str(tahun),
                start_date=date(tahun, 1, 1),
                end_date=date(tahun, 12, 31),
                no_nd=no_nd,
            )
            for sub_id, tahun in sorted(wanted)
        ]

        with transaction.atomic():
            dilepas = Tiket.objects.filter(
                id_jenis_prioritas_data__isnull=False
            ).update(id_jenis_prioritas_data=None)
            dihapus, _ = JenisPrioritasData.objects.all().delete()
            JenisPrioritasData.objects.bulk_create(baru, batch_size=1000)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Selesai: {dihapus} record lama dihapus, {len(baru)} record baru dibuat, '
            f'FK prioritas pada {dilepas} tiket dikosongkan.'
        ))
        self.stdout.write(self.style.WARNING(
            'Langkah berikutnya — isi kembali kolom prioritas pada tiket:\n'
            '  python manage.py backfill_tiket_jenis_prioritas --dry-run\n'
            '  python manage.py backfill_tiket_jenis_prioritas --journal prioritas.jsonl'
        ))
