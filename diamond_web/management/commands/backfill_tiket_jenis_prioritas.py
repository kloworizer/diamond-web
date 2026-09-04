"""Selaraskan ``Tiket.id_jenis_prioritas_data`` dengan aturan Data Prioritas.

Sebuah tiket berstatus prioritas bila masa berlaku record ``JenisPrioritasData``
untuk Sub Jenis Data-nya mencakup **tanggal terima DIP** tiket itu
(``start_date <= tgl_terima_dip <= end_date``, ``end_date`` kosong berarti masih
berlaku). Aturannya ada di :mod:`diamond_web.utils.jenis_prioritas` dan dipakai
sama persis oleh form Rekam Tiket, sync, dan antrean seksi.

Kolom itu tetap perlu diselaraskan berkala karena aplikasi hanya menulisnya
**sekali, saat tiket direkam**. Begitu admin menambah, mengubah, atau menutup
sebuah record Data Prioritas, tiket-tiket yang sudah terlanjur direkam tidak ikut
menyesuaikan sendiri. Perintah ini yang menyesuaikannya.

Selain itu, tiket yang direkam sebelum perbaikan aturan ini masih membawa hasil
pencocokan lama yang salah: form rekam dan sync dulu mencocokkan **field Tahun**
record prioritas dengan ``Tiket.tahun`` (tahun *isi data*), bukan masa berlakunya
terhadap tanggal terima. Menjalankan perintah ini sekali akan membetulkan
semuanya sekaligus.

Secara default perintah ini melakukan **rekonsiliasi penuh** — mengisi yang
kosong, memindahkan yang menunjuk record salah, dan mengosongkan yang tidak lagi
memenuhi syarat — supaya seluruh tabel tiket benar-benar sesuai aturan. Pakai
``--fill-only`` bila hanya ingin mengisi yang kosong tanpa menyentuh yang sudah
terisi.

Setiap perubahan dicatat sebagai ``TiketAction`` ``DIUBAH`` bertanda
``(penyesuaian jenis prioritas data)`` di catatannya, sama seperti perubahan
isian tiket lewat aplikasi — matikan dengan ``--no-action`` bila tidak perlu.

Karena FK prioritas tidak menyimpan jejak siapa yang mengisinya, pembatalan tidak
bisa ditebak dari isi database. Karena itu ``--journal`` menulis catatan
perubahan (JSONL) yang bisa dikembalikan persis oleh ``--undo``.

Aman dijalankan berulang: menjalankan lagi setelah selesai tidak mengubah apa pun.

Penggunaan::

    python manage.py backfill_tiket_jenis_prioritas --dry-run
    python manage.py backfill_tiket_jenis_prioritas --journal prioritas.jsonl
    python manage.py backfill_tiket_jenis_prioritas --prioritas-id 42 --dry-run
    python manage.py backfill_tiket_jenis_prioritas --fill-only
    python manage.py backfill_tiket_jenis_prioritas --tiket AS001010118031201
    python manage.py backfill_tiket_jenis_prioritas --undo prioritas.jsonl
"""
import json
from collections import Counter
from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...constants.tiket_action_types import TiketActionType
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...utils.jenis_prioritas import PrioritasIndex

# Ditempel di setiap catatan yang ditulis perintah ini, supaya baris riwayat
# hasil penyesuaian massal tidak pernah terbaca sebagai suntingan seorang user.
MARKER = ' (penyesuaian jenis prioritas data)'

CATATAN_MAX_LENGTH = 255

SUB_FIELD = 'id_periode_data__id_sub_jenis_data_ilap'

# Kolom Tiket yang dibaca pencocok. Ditulis eksplisit supaya queryset tetap
# ramping — perintah ini menyapu seluruh tabel tiket.
TIKET_FIELDS = (
    'id',
    'nomor_tiket',
    'tgl_terima_dip',
    'id_jenis_prioritas_data',
    SUB_FIELD,
)


def build_catatan(old_label, new_label):
    """Catatan satu perubahan, bertanda supaya bisa dikenali kembali."""
    head = f'isian tiket diubah — Jenis Prioritas Data: {old_label} → {new_label}'
    limit = CATATAN_MAX_LENGTH - len(MARKER)
    if len(head) > limit:
        head = head[:limit - 1].rstrip() + '…'
    return head + MARKER


class Command(BaseCommand):
    help = (
        'Selaraskan id_jenis_prioritas_data seluruh tiket dengan masa berlaku '
        'record Data Prioritas terhadap tanggal terima DIP'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Laporkan apa yang akan diubah tanpa menyentuh database.',
        )
        parser.add_argument(
            '--fill-only', action='store_true',
            help='Hanya isi kolom yang kosong. Tiket yang sudah terisi tidak '
                 'dipindahkan maupun dikosongkan.',
        )
        parser.add_argument(
            '--prioritas-id', type=int, action='append', dest='prioritas_id', metavar='ID',
            help='Batasi perubahan ke record Data Prioritas tertentu — biasanya yang '
                 'baru saja ditambahkan admin. Bisa diulang. Pengosongan tetap dinilai '
                 'terhadap seluruh isi tabel.',
        )
        parser.add_argument(
            '--sub-jenis-data', action='append', dest='sub_jenis_data', metavar='KODE',
            help='Batasi ke sub jenis data ini (mis. KM0330101). Bisa diulang.',
        )
        parser.add_argument(
            '--tahun', type=int, action='append', dest='tahun', metavar='N',
            help='Batasi ke tahun data tiket ini. Bisa diulang. Ini hanya penyaring '
                 'cakupan — tahun tidak ikut menentukan status prioritas.',
        )
        parser.add_argument(
            '--tiket', action='append', dest='tiket', metavar='NOMOR_TIKET',
            help='Batasi ke nomor tiket ini. Bisa diulang.',
        )
        parser.add_argument(
            '--status', type=int, action='append', dest='status', metavar='N',
            help='Batasi ke status_tiket ini. Bisa diulang.',
        )
        parser.add_argument(
            '--only-old-db', action='store_true',
            help='Hanya tiket hasil migrasi (old_db=True).',
        )
        parser.add_argument(
            '--skip-old-db', action='store_true',
            help='Lewati tiket hasil migrasi (old_db=True).',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Proses paling banyak N tiket (uji coba di sebagian data).',
        )
        parser.add_argument(
            '--no-action', action='store_true',
            help='Jangan tulis TiketAction "Isian Tiket Diubah" untuk setiap perubahan.',
        )
        parser.add_argument(
            '--system-user', default='admin', metavar='USERNAME',
            help='User yang dicatat pada TiketAction. Default "admin".',
        )
        parser.add_argument(
            '--batch-size', type=int, default=2000,
            help='Jumlah baris per bulk update / per transaksi. Default 2000.',
        )
        parser.add_argument(
            '--journal', metavar='PATH',
            help='Tulis catatan perubahan (JSONL) ke berkas ini, agar bisa '
                 'dikembalikan dengan --undo.',
        )
        parser.add_argument(
            '--undo', metavar='PATH',
            help='Kembalikan perubahan dari berkas journal, bukan menjalankan penyesuaian.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.batch_size = max(1, options['batch_size'])

        if options['undo']:
            self._undo(options)
            return

        if options['only_old_db'] and options['skip_old_db']:
            raise CommandError('--only-old-db dan --skip-old-db tidak bisa dipakai bersamaan.')

        self._reconcile(options)

    # ------------------------------------------------------------------ #
    # Penyesuaian                                                         #
    # ------------------------------------------------------------------ #

    def _reconcile(self, options):
        index = PrioritasIndex()
        if not len(index):
            self.stdout.write(self.style.WARNING(
                'Tabel Jenis Prioritas Data kosong — tidak ada yang bisa dicocokkan.'
            ))
            return

        # Penyaring hasil, bukan penyaring kandidat: pengosongan tetap dinilai
        # terhadap seluruh isi tabel, supaya sebuah tiket tidak pernah
        # dikosongkan hanya karena record prioritasnya sedang tidak ikut disaring.
        wanted_ids = set(options['prioritas_id'] or ())

        system_user = None if options['no_action'] else self._resolve_system_user(
            options['system_user']
        )
        run_ts = datetime.now()

        tikets = self._select_tikets(options, index, wanted_ids)
        total = tikets.count()
        if not total:
            self.stdout.write(self.style.WARNING('Tidak ada tiket yang cocok dengan filter.'))
            return

        self.stdout.write(
            f'Memeriksa {total} tiket terhadap masa berlaku Data Prioritas'
            f'{" (dry run)" if self.dry_run else ""}...'
        )

        journal = self._open_journal(options, run_ts)
        try:
            counters = self._walk(tikets, index, options, wanted_ids, system_user, run_ts, journal)
        finally:
            if journal is not None:
                journal.close()

        self._report(total, counters, index, options)

    def _walk(self, tikets, index, options, wanted_ids, system_user, run_ts, journal):
        """Jalan sekali melewati tiket terpilih, menulis per batch."""
        fill_only = options['fill_only']

        filled = Counter()      # id record -> jumlah kolom kosong yang diisi
        relinked = Counter()    # id record baru -> jumlah yang dipindah
        cleared = 0
        already = 0
        unmatched = 0
        held_back = 0           # perlu diubah tapi ditahan --fill-only

        pending = []
        actions = []

        for t in tikets.values(*TIKET_FIELDS).iterator(chunk_size=self.batch_size):
            current = t['id_jenis_prioritas_data']
            wanted = index.match_pk(t[SUB_FIELD], t['tgl_terima_dip'])

            if wanted == current:
                if current is not None:
                    already += 1
                else:
                    unmatched += 1
                continue

            # tgl_terima_dip wajib pada model Tiket, jadi setiap tiket selalu
            # bisa dinilai — tidak ada kasus "tidak bisa ditentukan" di sini.
            if current is None:
                if wanted_ids and wanted not in wanted_ids:
                    continue
                filled[wanted] += 1
            elif fill_only:
                held_back += 1
                continue
            elif wanted is None:
                cleared += 1
            else:
                if wanted_ids and wanted not in wanted_ids:
                    continue
                relinked[wanted] += 1

            pending.append(Tiket(pk=t['id'], id_jenis_prioritas_data_id=wanted))
            if system_user is not None:
                actions.append(TiketAction(
                    id_tiket_id=t['id'],
                    id_user_id=system_user.pk,
                    timestamp=run_ts,
                    action=TiketActionType.DIUBAH,
                    catatan=build_catatan(index.label(current), index.label(wanted)),
                ))
            if journal is not None:
                journal.write(json.dumps({
                    'tiket_id': t['id'],
                    'nomor_tiket': t['nomor_tiket'],
                    'from': current,
                    'to': wanted,
                }) + '\n')

            if len(pending) >= self.batch_size:
                self._flush(pending, actions)
                pending, actions = [], []

        self._flush(pending, actions)

        return {
            'filled': filled,
            'relinked': relinked,
            'cleared': cleared,
            'already': already,
            'unmatched': unmatched,
            'held_back': held_back,
        }

    def _select_tikets(self, options, index, wanted_ids):
        qs = Tiket.objects.order_by('id')

        if options['only_old_db']:
            qs = qs.filter(old_db=True)
        if options['skip_old_db']:
            qs = qs.filter(old_db=False)
        if options['tiket']:
            qs = qs.filter(nomor_tiket__in=options['tiket'])
        if options['status']:
            qs = qs.filter(status_tiket__in=options['status'])
        if options['tahun']:
            qs = qs.filter(tahun__in=options['tahun'])
        if options['sub_jenis_data']:
            qs = qs.filter(
                **{f'{SUB_FIELD}__id_sub_jenis_data__in': options['sub_jenis_data']}
            )
        if wanted_ids and options['fill_only']:
            # Tanpa pemindahan/pengosongan, hanya tiket dari sub jenis data
            # record-record itu yang bisa berubah — persempit di SQL, jangan
            # seluruh tabel tiket.
            qs = qs.filter(**{f'{SUB_FIELD}__in': index.subs_with(wanted_ids)})
        if options['limit']:
            qs = qs[:options['limit']]
        return qs

    def _resolve_system_user(self, username):
        """User yang dicatat di TiketAction. Perubahan ini tidak berasal dari
        seorang user, jadi dicatat atas nama akun sistem."""
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.filter(is_superuser=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                f'Tidak ada user "{username}" dan tidak ada superuser sebagai cadangan. '
                f'Pakai --system-user dengan username yang ada, atau --no-action.'
            )
        return user

    def _flush(self, tikets, actions):
        """Tulis satu batch. Tiap batch commit sendiri: perintah ini idempoten,
        jadi jalan yang terputus tinggal diulang."""
        if self.dry_run or not tikets:
            return
        with transaction.atomic():
            Tiket.objects.bulk_update(
                tikets, ['id_jenis_prioritas_data'], batch_size=self.batch_size,
            )
            if actions:
                TiketAction.objects.bulk_create(actions, batch_size=self.batch_size)

    def _open_journal(self, options, run_ts):
        path = options['journal']
        if not path:
            return None
        if self.dry_run:
            self.stdout.write(self.style.WARNING('Dry run: journal tidak ditulis.'))
            return None
        handle = open(path, 'w', encoding='utf-8')
        handle.write(json.dumps({
            '_meta': {
                'run_ts': run_ts.isoformat(),
                'fill_only': options['fill_only'],
                'wrote_actions': not options['no_action'],
            }
        }) + '\n')
        return handle

    def _report(self, total, counters, index, options):
        filled = counters['filled']
        relinked = counters['relinked']
        filled_total = sum(filled.values())
        relinked_total = sum(relinked.values())

        self.stdout.write('')
        verb = 'Akan mengisi' if self.dry_run else 'Mengisi'
        self.stdout.write(
            f'{verb} {filled_total} tiket yang kolom prioritasnya kosong '
            f'(dari {total} tiket diperiksa):'
        )
        for pk in sorted(filled, key=lambda p: -filled[p]):
            self.stdout.write(f'  {index.label(pk):<28} {filled[pk]:>7}')

        if relinked_total:
            verb = 'Akan memindah' if self.dry_run else 'Memindah'
            self.stdout.write('')
            self.stdout.write(
                f'{verb} {relinked_total} tiket ke record prioritas yang benar:'
            )
            for pk in sorted(relinked, key=lambda p: -relinked[p]):
                self.stdout.write(f'  {index.label(pk):<28} {relinked[pk]:>7}')

        if counters['cleared']:
            verb = 'Akan mengosongkan' if self.dry_run else 'Mengosongkan'
            self.stdout.write('')
            self.stdout.write(
                f'{verb} {counters["cleared"]} tiket yang tanggal terima DIP-nya '
                f'di luar masa berlaku record prioritas mana pun.'
            )

        self.stdout.write('')
        self.stdout.write(f'{counters["already"]} tiket sudah benar, dibiarkan.')
        self.stdout.write(f'{counters["unmatched"]} tiket memang bukan prioritas.')

        if counters['held_back']:
            self.stdout.write(self.style.WARNING(
                f'{counters["held_back"]} tiket sudah terisi tetapi tidak sesuai aturan, '
                f'ditahan oleh --fill-only. Jalankan tanpa --fill-only untuk '
                f'membetulkannya.'
            ))

        if self.dry_run:
            self.stdout.write(self.style.WARNING('Dry run: tidak ada yang ditulis.'))
            return

        if options['journal'] and (filled_total or relinked_total or counters['cleared']):
            self.stdout.write(
                f'Journal ditulis ke {options["journal"]}; kembalikan dengan '
                f'--undo {options["journal"]}.'
            )
        self.stdout.write(self.style.SUCCESS('Penyesuaian jenis prioritas data selesai.'))

    # ------------------------------------------------------------------ #
    # Pembatalan                                                          #
    # ------------------------------------------------------------------ #

    def _undo(self, options):
        """Kembalikan setiap tiket ke record prioritas yang tercatat di journal.

        Hanya tiket yang isinya masih sama dengan hasil jalan itu yang
        dikembalikan; kalau nilainya sudah berubah lagi sesudahnya (lewat
        aplikasi atau jalan berikutnya), tiket itu dilewati dan dilaporkan,
        bukan ditimpa.
        """
        path = options['undo']
        try:
            with open(path, encoding='utf-8') as handle:
                lines = [json.loads(line) for line in handle if line.strip()]
        except OSError as exc:
            raise CommandError(f'Journal tidak terbaca: {exc}')
        except ValueError as exc:
            raise CommandError(f'Journal rusak: {exc}')

        meta = {}
        if lines and '_meta' in lines[0]:
            meta = lines.pop(0)['_meta']
        if not lines:
            self.stdout.write('Journal kosong — tidak ada yang dikembalikan.')
            return

        wanted = {row['tiket_id']: (row['from'], row['to']) for row in lines}
        current = dict(
            Tiket.objects.filter(pk__in=wanted)
            .values_list('pk', 'id_jenis_prioritas_data')
        )

        reverts = []
        changed_since = 0
        missing = 0
        for tiket_id, (was, became) in wanted.items():
            if tiket_id not in current:
                missing += 1
                continue
            if current[tiket_id] != became:
                changed_since += 1
                continue
            reverts.append(Tiket(pk=tiket_id, id_jenis_prioritas_data_id=was))

        # Baris riwayat yang ditulis jalan itu dikenali dari stempel waktu
        # jalannya plus penanda catatan, jadi riwayat jalan lain tidak ikut
        # terhapus.
        run_ts = meta.get('run_ts')
        actions = TiketAction.objects.none()
        if run_ts and meta.get('wrote_actions', True):
            actions = TiketAction.objects.filter(
                id_tiket_id__in=[t.pk for t in reverts],
                action=TiketActionType.DIUBAH,
                timestamp=datetime.fromisoformat(run_ts),
                catatan__endswith=MARKER,
            )
        action_count = actions.count() if reverts else 0

        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                f'Dry run: akan mengembalikan {len(reverts)} tiket dan menghapus '
                f'{action_count} baris riwayat.'
            ))
        else:
            for start in range(0, len(reverts), self.batch_size):
                with transaction.atomic():
                    Tiket.objects.bulk_update(
                        reverts[start:start + self.batch_size],
                        ['id_jenis_prioritas_data'],
                        batch_size=self.batch_size,
                    )
            if action_count:
                actions.delete()
            self.stdout.write(self.style.SUCCESS(
                f'Mengembalikan {len(reverts)} tiket dan menghapus {action_count} '
                f'baris riwayat.'
            ))

        if changed_since:
            self.stdout.write(self.style.WARNING(
                f'{changed_since} tiket dilewati karena nilainya sudah berubah lagi '
                f'setelah jalan itu.'
            ))
        if missing:
            self.stdout.write(self.style.WARNING(
                f'{missing} tiket di journal sudah tidak ada.'
            ))
