"""Retroactive fix for tikets left at Selesai after PIDE revised the tarikan.

Aturan 9 in :mod:`diamond_web.views.sync_tiket_update` reopens a closed tiket
when Oracle reports a *new* ``tgl_transfer`` alongside identification rows. It
can only fire on the sync run that first sees the new date: it compares Oracle's
``tgl_transfer`` against the one already stored on the tiket.

Tikets revised *before* that rule existed are therefore stranded. The sync
already copied the new ``tgl_transfer`` (and the new baris counts) into the
local row, so every later run sees no change and the tiket stays at Selesai
forever. This command finds them and applies what Aturan 9 would have done.

Detection — a tiket is stranded when the composition says so:

  - ``status_tiket == 8`` (Selesai) and ``tgl_rematch`` is NULL
  - ``tgl_transfer`` is set
  - ``baris_i > 0`` and ``belum_qc != 0`` — Aturan 1's composition, i.e. the
    data says this tiket belongs in pengendalian mutu, not closed

…and **either** of two audit-trail signatures holds:

  A. **no** ``DITRANSFER_KE_PMDE`` action carries the tiket's current
     ``tgl_transfer`` — the trail never recorded a transfer on the date the
     tiket now claims; or
  B. ``tgl_transfer`` is **later than the tiket's last SELESAI action** — a
     transfer that post-dates the closure, which cannot happen on a healthy
     tiket.

Signature B exists because A alone has a hole: when
``backfill_old_db_tiket_actions`` runs *after* PIDE revised the transfer date,
it writes a transfer action at the already-revised ``tgl_transfer``, so the
trail looks intact while the tiket is still wrongly closed
(``PD508040123120801`` is exactly that). B catches it on the chronology
instead — closed on the 24th, transferred on the 28th.

Neither signature fires on a healthy migrated tiket: its transfer action sits
on its ``tgl_transfer`` (fails A) and its closure follows the transfer rather
than preceding it (fails B). Verified against the 3.392 migrated tikets that
share the composition filter: zero matches for either.

Idempotency comes from the status change itself — the fix moves the tiket off
status 8, so a second run cannot see it again.

Existing actions are never deleted or re-dated. The closed round genuinely
happened on the data as it stood then; the revision is appended on top of it —
and when the trail already carries a transfer at that date (signature B), no
duplicate is added.

Usage::

    python manage.py fix_tiket_transfer_ulang --dry-run
    python manage.py fix_tiket_transfer_ulang
    python manage.py fix_tiket_transfer_ulang --tiket PD411040126050601
    python manage.py fix_tiket_transfer_ulang --dry-run --verbose
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, Subquery

from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC


class Command(BaseCommand):
    help = (
        'Reopen tikets stuck at Selesai because PIDE revised the tarikan '
        '(new tgl_transfer + baris_i) before Aturan 9 existed'
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
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Process at most N tikets (for a trial run on a subset).',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Print one line per affected tiket.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tikets = self._select_tikets(options)

        total = tikets.count()
        if not total:
            self.stdout.write(self.style.SUCCESS(
                'Tidak ada tiket yang tertahan di Selesai karena revisi tarikan.'
            ))
            return

        self.stdout.write(
            f'{total} tiket tertahan di Selesai padahal komposisi barisnya '
            f'seharusnya Pengendalian Mutu.'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — tidak ada yang ditulis.\n'))

        pics = self._active_pide_pics(tikets)

        reopened = 0
        actions_created = 0
        without_pic = []

        for tiket in tikets:
            pide_user = pics.get(tiket.id)
            # Signature B tikets already carry a transfer action on that date
            # (written by the backfill) — recording a second one would only
            # duplicate the trail.
            needs_action = pide_user is not None and not tiket._transfer_recorded

            detail = (
                f'{tiket.nomor_tiket}: Selesai → Pengendalian Mutu '
                f'(Tgl Transfer:{tiket.tgl_transfer:%d/%m/%Y}, '
                f'I:{tiket.baris_i}, U:{tiket.baris_u}, Belum QC:{tiket.belum_qc})'
            )
            if pide_user is None:
                without_pic.append(tiket.nomor_tiket)
                detail += ' [tanpa PIC PIDE aktif — TiketAction dilewati]'
            elif tiket._transfer_recorded:
                detail += ' [aksi transfer sudah ada di tanggal itu — tidak diduplikasi]'
            if options['verbose'] or dry_run:
                self.stdout.write('  ' + detail)

            if dry_run:
                reopened += 1
                actions_created += 1 if needs_action else 0
                continue

            with transaction.atomic():
                tiket.status_tiket = STATUS_PENGENDALIAN_MUTU
                tiket.save(update_fields=['status_tiket'])
                reopened += 1

                if needs_action:
                    TiketAction.objects.create(
                        id_tiket=tiket, id_user=pide_user,
                        timestamp=tiket.tgl_transfer,
                        action=TiketActionType.DITRANSFER_KE_PMDE,
                        catatan=(
                            'Tiket ditransfer ulang ke PMDE — revisi tarikan '
                            f'oleh PIDE (I:{tiket.baris_i}, U:{tiket.baris_u})'
                        )
                    )
                    actions_created += 1

        verb = 'akan dibuka kembali' if dry_run else 'dibuka kembali'
        self.stdout.write(self.style.SUCCESS(
            f'\n{reopened} tiket {verb} ke Pengendalian Mutu, '
            f'{actions_created} TiketAction "Ditransfer ke PMDE" '
            f'{"akan dibuat" if dry_run else "dibuat"}.'
        ))
        if without_pic:
            self.stdout.write(self.style.WARNING(
                f'{len(without_pic)} tiket tanpa PIC PIDE aktif — status tetap '
                f'diperbarui tetapi tanpa jejak TiketAction: '
                f'{", ".join(without_pic[:10])}'
                + (' …' if len(without_pic) > 10 else '')
            ))

    # ------------------------------------------------------------------ #

    def _select_tikets(self, options):
        """Tikets stranded at Selesai by a tarikan revision — see module docstring."""
        transfer_recorded = TiketAction.objects.filter(
            id_tiket=OuterRef('pk'),
            action=TiketActionType.DITRANSFER_KE_PMDE,
            timestamp=OuterRef('tgl_transfer'),
        )
        last_selesai = Subquery(
            TiketAction.objects.filter(
                id_tiket=OuterRef('pk'), action=TiketActionType.SELESAI,
            ).order_by('-timestamp').values('timestamp')[:1]
        )

        qs = Tiket.objects.filter(
            status_tiket=STATUS_SELESAI,
            tgl_rematch__isnull=True,
            tgl_transfer__isnull=False,
            baris_i__gt=0,
            belum_qc__isnull=False,
        ).exclude(
            belum_qc=0
        ).annotate(
            _transfer_recorded=Exists(transfer_recorded),
            _last_selesai=last_selesai,
        ).filter(
            # A: jejak tidak pernah mencatat transfer pada tanggal yang kini
            # diklaim tiket. B: transfernya justru lebih baru dari penutupannya.
            # Tiket tanpa aksi SELESAI sama sekali tertangkap lewat cabang A —
            # perbandingan terhadap NULL di cabang B tidak pernah benar.
            Q(_transfer_recorded=False) | Q(tgl_transfer__gt=F('_last_selesai'))
        ).order_by('id')

        if options['tiket']:
            qs = qs.filter(nomor_tiket__in=options['tiket'])
        if options['limit']:
            qs = qs[:options['limit']]
        return qs

    def _active_pide_pics(self, tikets):
        """Map ``{tiket_id: user}`` of the first active PIDE PIC, chunked.

        Chunked like the sync does — a single ``IN (...)`` over every tiket id
        blows SQLite's parameter limit.
        """
        ids = list(tikets.values_list('id', flat=True))
        pics = {}
        CHUNK = 500
        for i in range(0, len(ids), CHUNK):
            for pic in TiketPIC.objects.filter(
                id_tiket__in=ids[i:i + CHUNK],
                role=TiketPIC.Role.PIDE,
                active=True,
            ).select_related('id_user').order_by('id'):
                pics.setdefault(pic.id_tiket_id, pic.id_user)
        return pics
