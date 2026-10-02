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

- re-stamps the auto-sync DIKEMBALIKAN/DIBATALKAN pair. It was stamped with
  Oracle's date-only tgl_transfer (00:00), so on the day PIDE recorded the
  data it read as preceding the IDENTIFIKASI action it followed. It is lifted
  just past the tiket's latest earlier action on that same day — as the sync
  now does — and ``tgl_dikembalikan`` with it when the sync had stamped it
  the same. A pair on a later day than everything before it stays put.

The DIKEMBALIKAN and DIBATALKAN actions are kept, and so are the IDENTIFIKASI
action and ``tgl_transfer`` (both record what really happened at PIDE).

Idempotent: a second run finds no status 3, no Aturan 3 run and no pair
left to lift.

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
from ...utils import lift_time_above

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


def _latest_pair(trail):
    """Split `trail` (ordered by id) around its latest auto-sync pair.

    Returns ``(pair, before)``, both newest first: the auto-sync
    DIKEMBALIKAN/DIBATALKAN actions written in the latest returning run, and
    every action written before them. ``([], [])`` when there is none.
    """
    newest_first = list(reversed(trail))
    start = next((i for i, a in enumerate(newest_first) if _is_auto_sync(a)), None)
    if start is None:
        return [], []
    end = start
    while end < len(newest_first) and _is_auto_sync(newest_first[end]):
        end += 1
    return newest_first[start:end], newest_first[end:]


def aturan_3_actions(trail):
    """The actions Aturan 3 wrote in the run that returned this tiket.

    `trail` is the tiket's actions ordered by id. Empty when the tiket has no
    auto-sync action, or when Aturan 3 did not fire alongside it.
    """
    pair, before = _latest_pair(trail)
    if not pair:
        return []
    anchor = pair[0]
    for shape in ATURAN_3_SHAPES:
        candidates = before[:len(shape)]
        if len(candidates) == len(shape) and all(
            (a.action, a.catatan) == key
            and (key not in STAMPED_TGL_TRANSFER or a.timestamp == anchor.timestamp)
            for a, key in zip(candidates, shape)
        ):
            return candidates
    return []


def lifted_pair_timestamp(trail, stray):
    """Where the latest auto-sync pair belongs once `stray` is gone, or None.

    The pair was stamped with Oracle's date-only tgl_transfer (00:00), so on
    the day PIDE recorded the data it sits before the IDENTIFIKASI action it
    followed. The sync now lifts it past the trail's latest action on the
    same day (``dikembalikan_timestamp``); this does the same for a pair
    already written. None when the pair is already in place.
    """
    pair, before = _latest_pair(trail)
    if not pair:
        return None
    kept = [a.timestamp for a in before if a not in stray]
    lifted = lift_time_above(pair[0].timestamp, max(kept) if kept else None)
    if all(a.timestamp == lifted for a in pair):
        return None
    return lifted


class Command(BaseCommand):
    help = (
        'Fix tikets returned by the sync (Aturan 4): status Dikembalikan → '
        'Dibatalkan, remove the Selesai actions Aturan 3 wrote alongside, and '
        're-stamp the return after the tiket\'s earlier actions of that day'
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
            lift_to = lifted_pair_timestamp(trail, stray)
            if fix_status or stray or lift_to:
                pair, _ = _latest_pair(trail)
                plans.append((tiket, fix_status, stray, pair, lift_to))

        if not plans:
            self.stdout.write(self.style.SUCCESS(
                'Tidak ada tiket Dikembalikan hasil sync yang perlu diperbaiki.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — tidak ada yang ditulis.\n'))

        status_fixed = 0
        actions_deleted = 0
        pairs_lifted = 0
        without_anchor = []
        for tiket, fix_status, stray, pair, lift_to in plans:
            parts = []
            if fix_status:
                parts.append('status Dikembalikan → Dibatalkan')
            if stray:
                parts.append('hapus aksi ' + ', '.join(
                    f'{ACTION_LABELS[a.action]} {a.timestamp:%d/%m/%Y %H:%M}'
                    for a in reversed(stray)
                ))
            # The sync stamped tgl_dikembalikan with the pair's timestamp.
            lift_tgl_dikembalikan = bool(lift_to) and tiket.tgl_dikembalikan == pair[0].timestamp
            if lift_to:
                parts.append(
                    f'waktu Dikembalikan/Dibatalkan {pair[0].timestamp:%d/%m/%Y %H:%M} '
                    f'→ {lift_to:%d/%m/%Y %H:%M}'
                    + (' (juga Tanggal Dikembalikan)' if lift_tgl_dikembalikan else '')
                )
            if not pair:
                without_anchor.append(tiket.nomor_tiket)
                parts.append('[tanpa aksi auto-sync — periksa manual]')
            self.stdout.write(f'  {tiket.nomor_tiket}: ' + '; '.join(parts))

            if not dry_run:
                with transaction.atomic():
                    update_fields = []
                    if fix_status:
                        tiket.status_tiket = STATUS_DIBATALKAN
                        update_fields.append('status_tiket')
                    if lift_tgl_dikembalikan:
                        tiket.tgl_dikembalikan = lift_to
                        update_fields.append('tgl_dikembalikan')
                    if update_fields:
                        tiket.save(update_fields=update_fields)
                    TiketAction.objects.filter(id__in=[a.id for a in stray]).delete()
                    if lift_to:
                        TiketAction.objects.filter(id__in=[a.id for a in pair]).update(timestamp=lift_to)
            status_fixed += fix_status
            actions_deleted += len(stray)
            pairs_lifted += bool(lift_to)

        akan = 'akan ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{len(plans)} tiket: {status_fixed} status {akan}diubah ke Dibatalkan, '
            f'{actions_deleted} aksi Aturan 3 {akan}dihapus, '
            f'{pairs_lifted} pasangan Dikembalikan/Dibatalkan {akan}digeser waktunya.'
        ))
        if without_anchor:
            self.stdout.write(self.style.WARNING(
                f'{len(without_anchor)} tiket berstatus Dikembalikan tanpa aksi auto-sync '
                f'(sync tanpa PIC aktif, atau diubah manual): {", ".join(without_anchor)}'
            ))
