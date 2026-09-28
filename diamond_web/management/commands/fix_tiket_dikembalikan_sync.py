"""Retroactive fix for tikets the Oracle sync returned from PIDE (Aturan 4).

Before the fix in :mod:`diamond_web.views.sync_tiket_update`, Aturan 4
(Identifikasi, rows CDE only → dikembalikan) had two defects:

1. It set the tiket to **Dikembalikan (3)**, while PIDE's manual Dikembalikan
   sets **Dibatalkan (7)** — and the sync itself records a DIBATALKAN action.
   Status 3 is a dead end: the tiket can no longer be sent to PIDE, yet it is
   not final either.
2. It overlapped with **Aturan 3** (Identifikasi, belum_qc == 0 → Selesai). A
   CDE-only tiket always has ``belum_qc == 0`` (there is nothing to QC), so
   both rules fired in one run: Aturan 3 wrote DITRANSFER_KE_PMDE,
   PENGENDALIAN_MUTU and SELESAI, then Aturan 4 overwrote the status and wrote
   DIKEMBALIKAN and DIBATALKAN. ``PV034050126071001`` is exactly that.

This command, per tiket:

- sets status Dikembalikan (3) → Dibatalkan (7). Only the sync ever assigned
  status 3, so every tiket still holding it is included; one without an
  auto-sync action in its trail is flagged in the report for a manual look.
- deletes the actions Aturan 3 wrote in the same run. They sit directly
  below the tiket's latest auto-sync DIKEMBALIKAN/DIBATALKAN pair in id
  order (the order they were written), and must match one of the three
  shapes Aturan 3 can leave — SELESAI + PENGENDALIAN_MUTU + DITRANSFER, or
  just the PMDE pair, or just DITRANSFER, depending on which PICs were
  active — with Aturan 3's exact catatan. The transfer and pengendalian mutu
  actions must also carry the auto-sync action's timestamp (both are
  ``tgl_transfer``). Anything else below the pair — an earlier genuine
  round included — is left alone.

The DIKEMBALIKAN and DIBATALKAN actions are kept.

Idempotent: a second run finds no status 3 and no Aturan 3 run left.

Usage::

    python manage.py fix_tiket_dikembalikan_sync --dry-run
    python manage.py fix_tiket_dikembalikan_sync
    python manage.py fix_tiket_dikembalikan_sync --tiket PV034050126071001
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_DIBATALKAN, STATUS_DIKEMBALIKAN
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction

# Catatan written by Aturan 4 (sync_tiket_update.py).
CATATAN_DIKEMBALIKAN = 'Tiket dikembalikan oleh PIDE (auto-sync)'
CATATAN_DIBATALKAN = 'Tiket dibatalkan (dikembalikan oleh PIDE: auto-sync)'

# (action, catatan) of each action Aturan 3 writes.
DITRANSFER = (TiketActionType.DITRANSFER_KE_PMDE, 'Tiket ditransfer ke PMDE')
PENGENDALIAN_MUTU = (TiketActionType.PENGENDALIAN_MUTU, 'Tiket selesai pengendalian mutu')
SELESAI = (TiketActionType.SELESAI, 'Tiket selesai diproses')

# What Aturan 3 can leave, newest first. It writes DITRANSFER when the tiket
# has an active PIDE PIC, and PENGENDALIAN_MUTU + SELESAI together when it has
# an active PMDE PIC — so these three shapes and nothing else.
ATURAN_3_SHAPES = (
    (SELESAI, PENGENDALIAN_MUTU, DITRANSFER),
    (SELESAI, PENGENDALIAN_MUTU),
    (DITRANSFER,),
)
# DITRANSFER and PENGENDALIAN_MUTU are stamped tgl_transfer, like Aturan 4's
# own actions; SELESAI is stamped tgl_close_tiket.
STAMPED_TGL_TRANSFER = (DITRANSFER, PENGENDALIAN_MUTU)

ACTION_LABELS = {
    TiketActionType.DITRANSFER_KE_PMDE: 'Ditransfer ke PMDE',
    TiketActionType.PENGENDALIAN_MUTU: 'Pengendalian Mutu',
    TiketActionType.SELESAI: 'Selesai',
}

AUTO_SYNC_Q = (
    Q(action=TiketActionType.DIKEMBALIKAN, catatan=CATATAN_DIKEMBALIKAN)
    | Q(action=TiketActionType.DIBATALKAN, catatan=CATATAN_DIBATALKAN)
)


def _is_auto_sync(action):
    return (action.action, action.catatan) in (
        (TiketActionType.DIKEMBALIKAN, CATATAN_DIKEMBALIKAN),
        (TiketActionType.DIBATALKAN, CATATAN_DIBATALKAN),
    )


def aturan_3_actions(trail):
    """The actions Aturan 3 wrote in the run that returned this tiket.

    `trail` is the tiket's actions ordered by id. Empty when the tiket has no
    auto-sync action, or when Aturan 3 did not fire alongside it.
    """
    anchors = [a for a in trail if _is_auto_sync(a)]
    if not anchors:
        return []
    anchor = anchors[-1]

    # Newest first, from just below the anchor, past the rest of its own pair.
    before = [a for a in reversed(trail) if a.id < anchor.id]
    while before and _is_auto_sync(before[0]):
        before.pop(0)
    for shape in ATURAN_3_SHAPES:
        candidates = before[:len(shape)]
        if len(candidates) == len(shape) and all(
            (a.action, a.catatan) == key
            and (key not in STAMPED_TGL_TRANSFER or a.timestamp == anchor.timestamp)
            for a, key in zip(candidates, shape)
        ):
            return candidates
    return []


class Command(BaseCommand):
    help = (
        'Fix tikets returned by the sync (Aturan 4): status Dikembalikan → '
        'Dibatalkan, and remove the Selesai actions Aturan 3 wrote alongside'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without touching the database.',
        )
        parser.add_argument(
            '--tiket', action='append', dest='tiket', metavar='NOMOR_TIKET',
            help='Limit to these nomor tiket. Repeatable.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        tikets = Tiket.objects.filter(
            Q(status_tiket=STATUS_DIKEMBALIKAN)
            | Q(id__in=TiketAction.objects.filter(AUTO_SYNC_Q).values('id_tiket'))
        ).order_by('id')
        if options['tiket']:
            tikets = tikets.filter(nomor_tiket__in=options['tiket'])

        plans = []
        for tiket in tikets:
            trail = list(TiketAction.objects.filter(id_tiket=tiket).order_by('id'))
            fix_status = tiket.status_tiket == STATUS_DIKEMBALIKAN
            stray = aturan_3_actions(trail)
            if fix_status or stray:
                plans.append((tiket, fix_status, stray, any(_is_auto_sync(a) for a in trail)))

        if not plans:
            self.stdout.write(self.style.SUCCESS(
                'Tidak ada tiket Dikembalikan hasil sync yang perlu diperbaiki.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — tidak ada yang ditulis.\n'))

        status_fixed = 0
        actions_deleted = 0
        without_anchor = []
        for tiket, fix_status, stray, has_anchor in plans:
            parts = []
            if fix_status:
                parts.append('status Dikembalikan → Dibatalkan')
            if stray:
                parts.append('hapus aksi ' + ', '.join(
                    f'{ACTION_LABELS[a.action]} {a.timestamp:%d/%m/%Y %H:%M}'
                    for a in reversed(stray)
                ))
            if not has_anchor:
                without_anchor.append(tiket.nomor_tiket)
                parts.append('[tanpa aksi auto-sync — periksa manual]')
            self.stdout.write(f'  {tiket.nomor_tiket}: ' + '; '.join(parts))

            if not dry_run:
                with transaction.atomic():
                    if fix_status:
                        tiket.status_tiket = STATUS_DIBATALKAN
                        tiket.save(update_fields=['status_tiket'])
                    TiketAction.objects.filter(id__in=[a.id for a in stray]).delete()
            status_fixed += fix_status
            actions_deleted += len(stray)

        akan = 'akan ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{len(plans)} tiket: {status_fixed} status {akan}diubah ke Dibatalkan, '
            f'{actions_deleted} aksi Aturan 3 {akan}dihapus.'
        ))
        if without_anchor:
            self.stdout.write(self.style.WARNING(
                f'{len(without_anchor)} tiket berstatus Dikembalikan tanpa aksi auto-sync '
                f'(sync tanpa PIC aktif, atau diubah manual): {", ".join(without_anchor)}'
            ))
