"""Retroactive fix for tikets closed as Selesai on a tarikan of Res/CDE rows only.

A tarikan whose rows are all Res and/or CDE (no I, no U) means PIDE returns
the data: when Res + CDE make up every complete row (``baris_lengkap``), the
sync now cancels the tiket the way PIDE's Kembalikan does (Aturan 4 in
:mod:`diamond_web.views.sync_tiket_update`). Before that, such tikets were
closed as Selesai: by the sync's Aturan 3 / 5B, or by the old_db migration.

This command applies Aturan 4 to those tikets, per tiket:

- status Selesai (8) → Dibatalkan (7), ``tgl_dikembalikan`` set,
  ``tgl_rekam_pide`` cleared and the tarikan counts cleared
  (``KOLOM_TARIKAN_DIBATALKAN``; ``baris_cde`` stays), as every cancel does;
- deletes the run that closed it: the tiket's newest workflow actions, as
  long as they are Ditransfer ke PMDE / Pengendalian Mutu / Selesai and
  include a Selesai. Earlier steps (Identifikasi and before) and non-workflow
  actions (PIC changes, isian edits) are kept;
- writes the DIKEMBALIKAN (PIDE PIC) and DIBATALKAN (P3DE PIC) actions with
  Aturan 4's own catatan, stamped ``tgl_transfer`` (else the deleted Selesai
  action's time) lifted past the kept trail on the same day. Without an
  active PIC of the role the action is skipped and the tiket is flagged.

Tikets with Res/CDE rows only whose Res + CDE do not equal Baris Lengkap are
not changed: their status is the PIC's to change. They are listed for review.

No notification is sent. ``tgl_transfer`` is kept.

Idempotent: a fixed tiket is no longer Selesai.

Usage::

    python manage.py fix_tiket_selesai_res_cde --dry-run
    python manage.py fix_tiket_selesai_res_cde
    python manage.py fix_tiket_selesai_res_cde --tiket PD050070123092002
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ...constants.tiket_action_types import TiketActionType, get_action_label
from ...constants.tiket_status import STATUS_DIBATALKAN, STATUS_SELESAI
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...utils import lift_time_above
from ...utils.tiket_dibatalkan import kosongkan_kolom_tarikan
from ...views.sync_tiket_update import (
    _STATUS_ACTIONS,
    CATATAN_DIBATALKAN_AUTO_SYNC,
    CATATAN_DIKEMBALIKAN_AUTO_SYNC,
    _res_cde_lengkap,
)

# The workflow actions a close writes, from Aturan 1-3/5 or the migration.
AKSI_PENUTUPAN = {
    TiketActionType.DITRANSFER_KE_PMDE,
    TiketActionType.PENGENDALIAN_MUTU,
    TiketActionType.SELESAI,
}


def aksi_penutupan(trail):
    """The run of actions that closed the tiket, newest first, or [].

    `trail` is the tiket's actions ordered by id. The run is the newest
    workflow actions while they are transfer / pengendalian mutu / selesai,
    and it counts only if it holds a Selesai.
    """
    run = []
    for action in reversed(trail):
        if action.action not in _STATUS_ACTIONS:
            continue
        if action.action not in AKSI_PENUTUPAN:
            break
        run.append(action)
    return run if any(a.action == TiketActionType.SELESAI for a in run) else []


def komposisi(tiket):
    if tiket.baris_res and tiket.baris_cde:
        return 'Res+CDE'
    return 'Res' if tiket.baris_res else 'CDE'


def _baris(tiket):
    return (
        f'Res {tiket.baris_res or 0} + CDE {tiket.baris_cde or 0}, '
        f'Baris Lengkap {tiket.baris_lengkap if tiket.baris_lengkap is not None else "-"}'
    )


class Command(BaseCommand):
    help = (
        'Fix tikets closed as Selesai whose tarikan is Res/CDE rows only and '
        'Res + CDE = Baris Lengkap: dikembalikan PIDE → Dibatalkan, as Aturan 4 does'
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
            Q(baris_i__isnull=True) | Q(baris_i=0),
            Q(baris_u__isnull=True) | Q(baris_u=0),
            Q(baris_res__gt=0) | Q(baris_cde__gt=0),
            status_tiket=STATUS_SELESAI,
        ).order_by('id')
        if options['tiket']:
            tikets = tikets.filter(nomor_tiket__in=options['tiket'])

        diperbaiki, tidak_lengkap = [], []
        for tiket in tikets:
            if _res_cde_lengkap(tiket.baris_res, tiket.baris_cde, tiket.baris_lengkap):
                diperbaiki.append(tiket)
            else:
                tidak_lengkap.append(tiket)

        if not diperbaiki and not tidak_lengkap:
            self.stdout.write(self.style.SUCCESS(
                'Tidak ada tiket Selesai dengan baris Res/CDE saja yang perlu diperbaiki.'
            ))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — tidak ada yang ditulis.\n'))

        per_komposisi = {}
        aksi_dihapus = 0
        tanpa_pic = []
        for tiket in diperbaiki:
            trail = list(TiketAction.objects.filter(id_tiket=tiket).order_by('id'))
            hapus = aksi_penutupan(trail)
            kept = [a.timestamp for a in trail if a not in hapus]
            selesai = next((a.timestamp for a in hapus if a.action == TiketActionType.SELESAI), None)
            waktu = lift_time_above(
                tiket.tgl_transfer or selesai or timezone.now(),
                max(kept) if kept else None,
            )
            pics = {
                role: TiketPIC.objects.filter(
                    id_tiket=tiket, role=role, active=True,
                ).select_related('id_user').first()
                for role in (TiketPIC.Role.PIDE, TiketPIC.Role.P3DE)
            }
            aksi_baru = (
                (TiketPIC.Role.PIDE, TiketActionType.DIKEMBALIKAN, CATATAN_DIKEMBALIKAN_AUTO_SYNC),
                (TiketPIC.Role.P3DE, TiketActionType.DIBATALKAN, CATATAN_DIBATALKAN_AUTO_SYNC),
            )
            dilewati = [TiketPIC.Role(role).label for role, _, _ in aksi_baru if not pics[role]]

            # Read before the cancel clears baris_res.
            jenis = komposisi(tiket)
            parts = [f'{jenis} ({_baris(tiket)})', 'status Selesai → Dibatalkan']
            if hapus:
                parts.append('hapus aksi ' + ', '.join(
                    f'{get_action_label(a.action)} {a.timestamp:%d/%m/%Y %H:%M}' for a in reversed(hapus)
                ))
            parts.append(f'aksi Dikembalikan/Dibatalkan {waktu:%d/%m/%Y %H:%M}')
            if dilewati:
                tanpa_pic.append(tiket.nomor_tiket)
                parts.append(f'[tanpa PIC {"/".join(dilewati)} aktif — aksinya dilewati]')
            self.stdout.write(f'  {tiket.nomor_tiket}: ' + '; '.join(parts))

            if not dry_run:
                with transaction.atomic():
                    tiket.status_tiket = STATUS_DIBATALKAN
                    tiket.tgl_dikembalikan = waktu
                    tiket.tgl_rekam_pide = None
                    kosongkan_kolom_tarikan(tiket)
                    tiket.save()
                    TiketAction.objects.filter(id__in=[a.id for a in hapus]).delete()
                    for role, action, catatan in aksi_baru:
                        if pics[role]:
                            TiketAction.objects.create(
                                id_tiket=tiket, id_user=pics[role].id_user,
                                timestamp=waktu, action=action, catatan=catatan,
                            )
            per_komposisi[jenis] = per_komposisi.get(jenis, 0) + 1
            aksi_dihapus += len(hapus)

        akan = 'akan ' if dry_run else ''
        rincian = ', '.join(f'{n} {k}' for k, n in sorted(per_komposisi.items())) or '0'
        self.stdout.write(self.style.SUCCESS(
            f'\n{len(diperbaiki)} tiket {akan}diubah Selesai → Dibatalkan ({rincian}), '
            f'{aksi_dihapus} aksi penutupan {akan}dihapus.'
        ))
        if tanpa_pic:
            self.stdout.write(self.style.WARNING(
                f'{len(tanpa_pic)} tiket tanpa PIC PIDE/P3DE aktif, aksinya dilewati: {", ".join(tanpa_pic)}'
            ))
        if tidak_lengkap:
            self.stdout.write(self.style.WARNING(
                f'{len(tidak_lengkap)} tiket Selesai dengan baris Res/CDE saja tetapi Res + CDE ≠ '
                f'Baris Lengkap, tidak diubah (status diubah manual oleh PIC):'
            ))
            for tiket in tidak_lengkap:
                self.stdout.write(f'  {tiket.nomor_tiket}: {komposisi(tiket)} ({_baris(tiket)})')
