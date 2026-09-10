"""Put back the ``TiketPIC`` rows that deleting a PIC row removed.

Deleting a PIC through the PIC menu (``PICDeleteView``) does not deactivate the
tiket assignments the way closing a PIC with an ``end_date`` does — it
**deletes** them. Every tiket of that Sub Jenis Data loses its row from
``tiket_pic`` and keeps only a ``TiketAction`` saying so::

    PIC PIDE 910223210 dihapus

The tikets are then left with nobody assigned: they show up on the home page's
"belum punya PIC" card, they fall out of their PIC's own queue, and no screen
in the app can put the row back for a tiket that has already moved on.

This command restores them, and it takes the **current ``pic`` table** as the
answer to who the PIC is — not the username in the catatan. The person deleted
back then may have been replaced since; what should be on the tiket now is
whoever is the active PIC (no ``end_date``) of that tiket's Sub Jenis Data for
that tipe. A Sub Jenis Data with no active PIC has no answer to give, so its
tikets are reported rather than guessed at.

Scope is exactly the damage: only tikets carrying one of those "dihapus"
actions are considered, so a tiket that never lost anything is never touched.

The audit trail is kept whole. The "dihapus" rows stay where they are, and each
restored assignment adds its own row (``PIC ditambahkan`` / ``PIC diaktifkan
kembali``) marked ``(dikembalikan)``, so the history reads as what actually
happened: deleted, then restored.

Re-running is safe: an assignment that is already active is skipped, and one
that exists but was switched off is reactivated rather than duplicated.

Usage::

    python manage.py restore_tiket_pic_dihapus --dry-run
    python manage.py restore_tiket_pic_dihapus
    python manage.py restore_tiket_pic_dihapus --tipe PIDE --dry-run
    python manage.py restore_tiket_pic_dihapus --user 910223210
    python manage.py restore_tiket_pic_dihapus --tiket AS001010118031201
"""
import re
from collections import Counter, defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ...constants.tiket_action_types import PICActionType
from ...models.pic import PIC
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC

# What PICDeleteView writes: f'{tipe_label} {username} dihapus', where
# tipe_label is the PIC.TipePIC label ("PIC PIDE"). The deactivation path writes
# "... tidak aktif" and the hand-over path "... diganti oleh ...", so matching on
# the "dihapus" ending is what separates a delete from either of those.
CATATAN_RE = re.compile(r'^PIC (P3DE|PIDE|PMDE) (.+) dihapus$')

# Appended to the catatan of every row this command writes, so a restored
# assignment is never read as one an admin made by hand.
MARKER = ' (dikembalikan)'

TIPE_TO_ROLE = {
    PIC.TipePIC.P3DE: TiketPIC.Role.P3DE,
    PIC.TipePIC.PIDE: TiketPIC.Role.PIDE,
    PIC.TipePIC.PMDE: TiketPIC.Role.PMDE,
}

TIPE_LABEL = dict(PIC.TipePIC.choices)


class Command(BaseCommand):
    help = (
        'Kembalikan baris tiket_pic yang terhapus saat PIC dihapus lewat menu PIC, '
        'memakai PIC aktif pada tabel pic sebagai rujukan. Riwayat aksi tiket '
        'dipertahankan. Jalankan dengan --dry-run lebih dulu.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be written without touching the database.',
        )
        parser.add_argument(
            '--tipe', action='append', dest='tipe', metavar='P3DE|PIDE|PMDE',
            help='Limit to these PIC tipe. Repeatable. Default: all three.',
        )
        parser.add_argument(
            '--user', action='append', dest='user', metavar='USERNAME',
            help='Limit to deletions of this username (as written in the catatan). '
                 'Repeatable.',
        )
        parser.add_argument(
            '--tiket', action='append', dest='tiket', metavar='NOMOR_TIKET',
            help='Limit to these nomor tiket. Repeatable.',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Restore at most N tiket/role pairs (for a trial run on a subset).',
        )
        parser.add_argument(
            '--batch-size', type=int, default=2000,
            help='Rows per bulk insert / per transaction. Default 2000.',
        )
        parser.add_argument(
            '--system-user', default='admin', metavar='USERNAME',
            help='User credited on the restored TiketAction rows. Default "admin".',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.batch_size = max(1, options['batch_size'])

        tipes = self._resolve_tipes(options['tipe'])
        system_user = self._resolve_system_user(options['system_user'])

        deletions = self._find_deletions(tipes, options)
        if not deletions:
            self.stdout.write(self.style.WARNING(
                'Tidak ada aksi "PIC <tipe> <user> dihapus" yang cocok dengan filter.'
            ))
            return

        plan = self._build_plan(deletions, options)
        self._report(deletions, plan)

        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                '\nDry run — tidak ada yang ditulis. Jalankan tanpa --dry-run untuk '
                'menerapkannya.'
            ))
            return

        self._apply(plan, system_user)

    # ------------------------------------------------------------------ #
    # Finding the damage                                                  #
    # ------------------------------------------------------------------ #

    def _resolve_tipes(self, raw):
        if not raw:
            return list(TIPE_TO_ROLE)
        tipes = []
        for value in raw:
            tipe = value.strip().upper()
            if tipe not in TIPE_TO_ROLE:
                raise CommandError(f'--tipe harus P3DE, PIDE atau PMDE (dapat "{value}").')
            tipes.append(tipe)
        return tipes

    def _resolve_system_user(self, username):
        """Who the restored TiketAction rows are credited to.

        PICDeleteView credits the deletion to `admin`; the restore follows the
        same convention rather than inventing an attribution of its own.
        """
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.filter(is_superuser=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                f'Tidak ada user "{username}" dan tidak ada superuser sebagai cadangan. '
                f'Berikan --system-user dengan username yang ada.'
            )
        return user

    def _find_deletions(self, tipes, options):
        """``{(tiket_id, tipe): {usernames}}`` from the "dihapus" actions.

        Keyed per tipe, because one tiket can have lost its P3DE, PIDE and PMDE
        PIC in three separate deletions, and each is restored from its own PIC
        rows. The usernames are kept only to report what was deleted — who goes
        back on the tiket comes from the `pic` table.
        """
        qs = TiketAction.objects.filter(
            action=PICActionType.TIDAK_AKTIF,
            catatan__startswith='PIC ',
            catatan__endswith=' dihapus',
        )
        if options['tiket']:
            qs = qs.filter(id_tiket__nomor_tiket__in=options['tiket'])

        wanted_users = set(options['user'] or ())
        wanted_tipes = set(tipes)

        deletions = defaultdict(set)
        for tiket_id, catatan in qs.values_list('id_tiket_id', 'catatan').iterator(
            chunk_size=self.batch_size
        ):
            match = CATATAN_RE.match(catatan or '')
            if not match:
                continue
            tipe, username = match.group(1), match.group(2)
            if tipe not in wanted_tipes:
                continue
            if wanted_users and username not in wanted_users:
                continue
            deletions[(tiket_id, tipe)].add(username)
        return deletions

    # ------------------------------------------------------------------ #
    # Planning                                                            #
    # ------------------------------------------------------------------ #

    def _build_plan(self, deletions, options):
        """Work out the rows to write. Read-only — nothing is saved here."""
        tiket_ids = {tiket_id for tiket_id, _tipe in deletions}

        # The Sub Jenis Data of each affected tiket, and its nomor for reporting.
        tiket_rows = {
            row['id']: row
            for row in Tiket.objects.filter(id__in=tiket_ids).values(
                'id', 'nomor_tiket', 'status_tiket',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data',
                'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
            )
        }

        sub_ids = {
            row['id_periode_data__id_sub_jenis_data_ilap'] for row in tiket_rows.values()
        }
        # The reference: who is the active PIC of each Sub Jenis Data now. Keyed
        # by user, because the pic table does not stop the same person from
        # holding two open rows for one Sub Jenis Data — and a person is either
        # the PIC of a tiket or not, however many pic rows say so.
        reference = defaultdict(dict)
        for sub_id, tipe, user_id, username in PIC.objects.filter(
            id_sub_jenis_data_ilap_id__in=sub_ids, end_date__isnull=True,
        ).values_list('id_sub_jenis_data_ilap_id', 'tipe', 'id_user_id', 'id_user__username'):
            reference[(sub_id, tipe)].setdefault(user_id, username)

        # Rows that survived or were merely switched off, so an existing row is
        # reactivated instead of a second one being created next to it.
        existing = {}
        for row_id, tiket_id, user_id, role, active in TiketPIC.objects.filter(
            id_tiket_id__in=tiket_ids
        ).values_list('id', 'id_tiket_id', 'id_user_id', 'role', 'active'):
            existing[(tiket_id, user_id, role)] = (row_id, active)

        creates = []       # (tiket_id, user_id, username, tipe)
        reactivates = []   # (row_id, tiket_id, user_id, username, tipe)
        already_active = 0
        tanpa_rujukan = {}  # sub jenis data that has no active PIC to restore from
        restored_pairs = 0

        for (tiket_id, tipe), _deleted_usernames in sorted(deletions.items()):
            row = tiket_rows.get(tiket_id)
            if row is None:  # tiket deleted since; nothing to restore onto
                continue
            if options['limit'] is not None and restored_pairs >= options['limit']:
                break

            sub_id = row['id_periode_data__id_sub_jenis_data_ilap']
            pics = reference.get((sub_id, tipe))
            if not pics:
                entry = tanpa_rujukan.setdefault((sub_id, tipe), {
                    'kode': row['id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data'],
                    'nama': row['id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data'],
                    'tipe': tipe,
                    'jumlah_tiket': 0,
                })
                entry['jumlah_tiket'] += 1
                continue

            role = TIPE_TO_ROLE[tipe]
            changed = False
            for user_id, username in pics.items():
                found = existing.get((tiket_id, user_id, role))
                if found is None:
                    creates.append((tiket_id, user_id, username, tipe))
                    changed = True
                elif not found[1]:
                    reactivates.append((found[0], tiket_id, user_id, username, tipe))
                    changed = True
                else:
                    already_active += 1
            if changed:
                restored_pairs += 1

        return {
            'creates': creates,
            'reactivates': reactivates,
            'already_active': already_active,
            'tanpa_rujukan': sorted(tanpa_rujukan.values(), key=lambda e: (e['tipe'], e['kode'])),
            'tiket_rows': tiket_rows,
            'restored_pairs': restored_pairs,
        }

    # ------------------------------------------------------------------ #
    # Reporting                                                           #
    # ------------------------------------------------------------------ #

    def _report(self, deletions, plan):
        per_tipe = Counter(tipe for _tiket_id, tipe in deletions)
        deleted_users = defaultdict(set)
        for (_tiket_id, tipe), usernames in deletions.items():
            deleted_users[tipe] |= usernames

        self.stdout.write(
            f'Aksi "PIC ... dihapus" ditemukan pada {len({t for t, _ in deletions})} tiket '
            f'({len(deletions)} pasangan tiket/tipe).'
        )
        for tipe in sorted(per_tipe):
            users = ', '.join(sorted(deleted_users[tipe]))
            self.stdout.write(f'  {TIPE_LABEL[tipe]:10} {per_tipe[tipe]:>7} tiket   dihapus: {users}')

        creates, reactivates = plan['creates'], plan['reactivates']
        tikets_touched = len({row[0] for row in creates} | {row[1] for row in reactivates})

        self.stdout.write('')
        self.stdout.write(
            f'Akan dikembalikan : {len(creates) + len(reactivates)} penugasan '
            f'pada {tikets_touched} tiket'
        )
        self.stdout.write(f'  dibuat baru     : {len(creates)}')
        self.stdout.write(f'  diaktifkan lagi : {len(reactivates)}')
        self.stdout.write(f'  sudah aktif     : {plan["already_active"]} (dilewati)')

        per_user = Counter(row[3] for row in creates)
        per_user.update(row[3] for row in reactivates)
        for username, jumlah in per_user.most_common():
            self.stdout.write(f'    {username:20} {jumlah:>7}')

        if plan['tanpa_rujukan']:
            total = sum(entry['jumlah_tiket'] for entry in plan['tanpa_rujukan'])
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'{total} tiket tidak bisa dikembalikan: Sub Jenis Data-nya tidak punya '
                f'PIC aktif lagi pada tabel pic. Tetapkan PIC-nya dulu lewat menu PIC, '
                f'lalu jalankan ulang.'
            ))
            for entry in plan['tanpa_rujukan'][:20]:
                self.stdout.write(
                    f'    {entry["tipe"]:5} {entry["kode"]:14} {entry["nama"][:40]:40} '
                    f'{entry["jumlah_tiket"]:>6} tiket'
                )
            if len(plan['tanpa_rujukan']) > 20:
                self.stdout.write(f'    ... dan {len(plan["tanpa_rujukan"]) - 20} Sub Jenis Data lain')

        if self.dry_run:
            sample = [(plan['tiket_rows'][row[0]]['nomor_tiket'], row[3], row[2])
                      for row in creates[:10]]
            if sample:
                self.stdout.write('')
                self.stdout.write('Contoh baris yang akan dibuat:')
                for nomor, tipe, username in sample:
                    self.stdout.write(f'    {nomor:20} {TIPE_LABEL[tipe]:10} {username}')

    # ------------------------------------------------------------------ #
    # Applying                                                            #
    # ------------------------------------------------------------------ #

    def _apply(self, plan, system_user):
        creates, reactivates = plan['creates'], plan['reactivates']
        if not creates and not reactivates:
            self.stdout.write(self.style.SUCCESS(
                'Tidak ada yang perlu dikembalikan.'
            ))
            return

        now = timezone.now()
        actions = [
            TiketAction(
                id_tiket_id=tiket_id,
                id_user=system_user,
                timestamp=now,
                action=PICActionType.DITAMBAHKAN,
                catatan=f'{TIPE_LABEL[tipe]} {username} ditambahkan{MARKER}',
            )
            for tiket_id, _user_id, username, tipe in creates
        ] + [
            TiketAction(
                id_tiket_id=tiket_id,
                id_user=system_user,
                timestamp=now,
                action=PICActionType.DIAKTIFKAN_KEMBALI,
                catatan=f'{TIPE_LABEL[tipe]} {username} diaktifkan kembali{MARKER}',
            )
            for _row_id, tiket_id, _user_id, username, tipe in reactivates
        ]

        with transaction.atomic():
            TiketPIC.objects.bulk_create(
                [
                    TiketPIC(
                        id_tiket_id=tiket_id,
                        id_user_id=user_id,
                        role=TIPE_TO_ROLE[tipe],
                        active=True,
                        timestamp=now,
                    )
                    for tiket_id, user_id, _username, tipe in creates
                ],
                batch_size=self.batch_size,
            )
            row_ids = [row[0] for row in reactivates]
            if row_ids:
                TiketPIC.objects.filter(id__in=row_ids).update(active=True)
                # Rows migrated without a timestamp would otherwise stay empty.
                TiketPIC.objects.filter(
                    id__in=row_ids, timestamp__isnull=True
                ).update(timestamp=now)
            TiketAction.objects.bulk_create(actions, batch_size=self.batch_size)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Selesai: {len(creates)} penugasan dibuat, {len(reactivates)} diaktifkan '
            f'kembali, {len(actions)} baris riwayat ditulis.'
        ))
