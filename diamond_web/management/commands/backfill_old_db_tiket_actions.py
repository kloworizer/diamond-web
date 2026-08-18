"""Rebuild the workflow audit trail for tikets that came from the old database.

Tikets recorded through the app get one ``TiketAction`` per workflow step, from
``Direkam`` to ``Selesai``. Tikets pulled in by the migration sync
(``old_db=True``) do not: :func:`diamond_web.views.sync_tiket._assign_tiket_pics_sync`
only writes the ``PIC ditambahkan`` (301) rows, and the incremental sync
(``sync_tiket_update``) only logs the transitions it observes *after* the tiket
has landed here. Everything the tiket did before the migration is missing, so
the riwayat aksi of a migrated tiket is empty (or starts mid-workflow) even
though the tiket sits at ``Selesai``.

This command reconstructs the missing steps from what the migration *did*
bring across: the tiket status and its workflow dates (``tgl_terima_dip``,
``tgl_teliti``, ``tgl_kirim_pide``, ``tgl_rekam_pide``, ``tgl_transfer``, ...),
plus the closing date read straight from Oracle, which has no column on Tiket.

It also repairs two things the migration got wrong rather than merely left out:

* **The PIC rows sit at the wrong end of the tiket's life.**
  ``_assign_tiket_pics_sync`` dated ``PIC ditambahkan`` from the sync clock, so
  every migrated tiket shows its PIC history at the moment of the migration run
  — years after the tiket, and after its own ``Selesai``. They are moved to just
  behind ``Direkam``, where the app puts them. A PIC genuinely added later
  through the PIC admin keeps its own date.
* **Rows written by an earlier run of this command are re-dated in place** when
  a better source appears — most of all an Oracle closing date that was not
  available then. Rows written by a user or by the sync are never touched.

Two rules keep the result honest rather than merely complete:

* **A step is only claimed when the tiket's own data supports it.** A cancelled
  tiket that never reached PIDE gets no ``Dikirim ke PIDE`` row, and a tiket
  closed at P3DE (``baris_lengkap == 0`` or data tidak tersedia) is not walked
  through PIDE and PMDE it never saw.
* **Timestamps are never invented on top of a recorded one.** A step whose date
  the migration carried across uses that date verbatim — including the dates
  that contradict each other, which the old data has plenty of. Only a step with
  no date of its own falls back to the latest timestamp so far, and that row
  says so in its catatan.

A tiket currently at ``Dibatalkan`` (7) is a third case, and gets no reconstructed
trail at all — not even ``Direkam``. Several views key off the presence of a
``DIKEMBALIKAN``/``DIBATALKAN`` action without checking whether the tiket is
still open (``home.py``'s "Pengembalian Seluruhnya dari PIDE" card, for one),
so filling in that history for a tiket that is *already* cancelled makes it
resurface there forever with nothing left to do about it. A cancelled migrated
tiket keeps only its ``PIC ditambahkan`` rows; any reconstructed row this
command wrote there on an earlier run is deleted.

Every row this command writes carries a ``(data migrasi)`` marker in its
catatan, which is also how ``--remove`` finds them again.

Actions this command did not write are never touched: a step is skipped when the
tiket already has an action of that type from a user or from
``sync_tiket_update``. Re-running is both safe and the way to pick up dates that
were unavailable before.

Usage::

    python manage.py backfill_old_db_tiket_actions --dry-run
    python manage.py backfill_old_db_tiket_actions
    python manage.py backfill_old_db_tiket_actions --no-oracle
    python manage.py backfill_old_db_tiket_actions --tiket AS001010118031201
    python manage.py backfill_old_db_tiket_actions --dedupe
    python manage.py backfill_old_db_tiket_actions --remove
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Min
from django.utils import timezone

from ...constants.tiket_action_types import (
    PICActionType,
    TiketActionType,
    get_action_label,
)
from ...constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC

# Appended to every catatan written here, so a reconstructed row is never
# mistaken for something a user actually did — and so --remove can find it.
MARKER = ' (data migrasi)'
MARKER_INFERRED = ' (data migrasi, tanggal perkiraan)'

# Only tiket workflow actions (1-11) are reconstructed. Backup (101+), tanda
# terima (201+), PIC (301+) and special request (401+) actions have their own
# source records and are left alone.
WORKFLOW_ACTION_MAX = 100

ROLE_P3DE = TiketPIC.Role.P3DE
ROLE_PIDE = TiketPIC.Role.PIDE
ROLE_PMDE = TiketPIC.Role.PMDE

# Tiket columns the planner reads. Kept explicit so the queryset stays narrow —
# this walks every migrated tiket.
TIKET_FIELDS = (
    'id', 'nomor_tiket', 'status_tiket', 'status_ketersediaan_data',
    'tgl_terima_dip', 'tgl_terima_vertikal', 'tgl_teliti', 'tgl_nadine',
    'nomor_nd_nadine', 'tgl_kirim_pide', 'tgl_rekam_pide', 'tgl_transfer',
    'tgl_rematch', 'tgl_dibatalkan', 'tgl_dikembalikan', 'baris_lengkap',
    'baris_i', 'baris_u', 'baris_res', 'baris_cde', 'sudah_qc', 'belum_qc',
)

# The tiket closing date has no column on Tiket — the migration never brought
# it across. It is read from Oracle and merged into the row under this key, so
# the planner sees it exactly like a column.
CLOSE_DATE_FIELD = 'tgl_close_tiket'
PLANNER_FIELDS = TIKET_FIELDS + (CLOSE_DATE_FIELD,)

# Closing date per tiket, matching the tgl_close_tiket expression in
# sync_tiket_update._TIKET_UPDATE_ORACLE_SQL: the QC date, but only once no row
# is left unchecked. The E -> EI prefix repair mirrors the migration query so
# the keys line up with the nomor_tiket stored here.
_CLOSE_DATE_ORACLE_SQL = """
    SELECT
        CASE
            WHEN LENGTH(no_tiket) = 16 AND SUBSTR(no_tiket,1,1) = 'E'
            THEN SUBSTR(no_tiket, 1, 1) || 'I' || SUBSTR(no_tiket, 2)
            ELSE no_tiket
        END nomor_tiket,
        CASE WHEN SUM(belum_qc) = 0 THEN MAX(tgl_qc) ELSE NULL END tgl_close_tiket
    FROM
        PVPTD.ZA_REKAP_TARIKAN
    GROUP BY
        no_tiket
"""


def _naive(value):
    """Coerce an Oracle datetime for storage. The project runs USE_TZ=False and
    every workflow view writes naive datetimes, so an aware value from the
    driver would sort against the rest inconsistently."""
    if not isinstance(value, datetime):
        return None
    if settings.USE_TZ:
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    return value.replace(tzinfo=None) if timezone.is_aware(value) else value


@dataclass(frozen=True)
class Step:
    """One workflow action to reconstruct.

    ``dates`` lists the tiket fields that can date this step, best source
    first. An empty tuple means the migration carries no date for it at all
    (the completion date, for one, has no column on Tiket) and the step
    inherits the latest timestamp so far.
    """
    action: int
    role: int
    catatan: str
    dates: tuple = field(default=())


# Catatan text mirrors what the live views write for the same action, so a
# migrated riwayat reads like a recorded one apart from the marker.
STEP_DIREKAM = Step(
    TiketActionType.DIREKAM, ROLE_P3DE, 'tiket direkam',
    ('tgl_terima_dip', 'tgl_terima_vertikal'),
)
STEP_DITELITI = Step(
    TiketActionType.DITELITI, ROLE_P3DE, 'Hasil penelitian direkam', ('tgl_teliti',),
)
STEP_DIKIRIM = Step(
    TiketActionType.DIKIRIM_KE_PIDE, ROLE_P3DE, 'tiket dikirim ke PIDE',
    ('tgl_kirim_pide', 'tgl_nadine'),
)
STEP_IDENTIFIKASI = Step(
    TiketActionType.IDENTIFIKASI, ROLE_PIDE, 'Mulai proses identifikasi', ('tgl_rekam_pide',),
)
STEP_TRANSFER = Step(
    TiketActionType.DITRANSFER_KE_PMDE, ROLE_PIDE, 'Tiket ditransfer ke PMDE', ('tgl_transfer',),
)
STEP_REMATCH = Step(
    TiketActionType.REMATCH, ROLE_PIDE, 'Tiket di-rematch oleh PIDE', ('tgl_rematch',),
)
# Both closing steps are dated from Oracle's tgl_close_tiket (the QC date).
# Without it they have no date of their own and inherit the transfer.
STEP_PENGENDALIAN_MUTU = Step(
    TiketActionType.PENGENDALIAN_MUTU, ROLE_PMDE, 'Tiket selesai pengendalian mutu',
    (CLOSE_DATE_FIELD,),
)
STEP_SELESAI_PMDE = Step(
    TiketActionType.SELESAI, ROLE_PMDE, 'Tiket selesai diproses', (CLOSE_DATE_FIELD,),
)
# Two ways a tiket reaches Selesai without ever leaving P3DE, both mirrored from
# RekamPenerimaanDataView / RekamHasilPenelitianView.
STEP_SELESAI_P3DE = Step(
    TiketActionType.SELESAI, ROLE_P3DE, 'Tiket selesai diproses', (CLOSE_DATE_FIELD,),
)
STEP_SELESAI_TIDAK_TERSEDIA = Step(
    TiketActionType.SELESAI, ROLE_P3DE, 'tiket selesai, data tidak tersedia',
    (CLOSE_DATE_FIELD,),
)
STEP_DIKEMBALIKAN = Step(
    TiketActionType.DIKEMBALIKAN, ROLE_PIDE, 'Tiket dikembalikan oleh PIDE', ('tgl_dikembalikan',),
)
STEP_DIBATALKAN = Step(
    TiketActionType.DIBATALKAN, ROLE_P3DE, 'Tiket dibatalkan',
    ('tgl_dibatalkan', 'tgl_dikembalikan'),
)
# DikembalikanTiketView pairs its Dikembalikan row with a Dibatalkan row
# attributed to P3DE; the migrated equivalent says the same thing.
STEP_DIBATALKAN_DARI_PIDE = Step(
    TiketActionType.DIBATALKAN, ROLE_P3DE, 'Tiket dibatalkan (dikembalikan oleh PIDE)',
    ('tgl_dibatalkan', 'tgl_dikembalikan'),
)

# STEP_DIBATALKAN and STEP_DIBATALKAN_DARI_PIDE are never planned any more
# (plan_steps short-circuits Dibatalkan to []) but stay listed here so
# all_generated_catatan() still recognises — and cleans up — rows an earlier
# version of this command wrote for a cancelled tiket.
ALL_STEPS = (
    STEP_DIREKAM, STEP_DITELITI, STEP_DIKIRIM, STEP_IDENTIFIKASI, STEP_TRANSFER,
    STEP_REMATCH, STEP_PENGENDALIAN_MUTU, STEP_SELESAI_PMDE, STEP_SELESAI_P3DE,
    STEP_SELESAI_TIDAK_TERSEDIA, STEP_DIKEMBALIKAN, STEP_DIBATALKAN,
    STEP_DIBATALKAN_DARI_PIDE,
)


def _has_penelitian(t):
    """Did P3DE record a research result for this tiket?

    Only ``tgl_teliti`` and a non-zero ``baris_lengkap`` count here. The sync
    COALESCEs ``baris_lengkap``, ``baris_tidak_lengkap`` and
    ``id_status_penelitian`` to a value for every migrated row, so those three
    are filled in even for a tiket that was never researched; "is not None" on
    them would mark all 48k tikets as researched.
    """
    return bool(t['tgl_teliti'] or (t['baris_lengkap'] or 0) > 0)


def _has_kirim_pide(t):
    """Was the tiket handed over to PIDE (ND Nadine recorded)?"""
    return bool(t['tgl_kirim_pide'] or t['tgl_nadine'] or t['nomor_nd_nadine'])


def _has_identifikasi(t):
    """Did PIDE start identification?"""
    return bool(t['tgl_rekam_pide'])


def _has_pengendalian_mutu(t):
    """Did the tiket reach PMDE? The identified rows and the QC counters are
    written by the transfer, so either is evidence even when tgl_transfer is
    missing."""
    return bool(
        t['tgl_transfer'] or t['sudah_qc'] or t['belum_qc']
        or t['baris_i'] or t['baris_u'] or t['baris_res'] or t['baris_cde']
    )


def plan_steps(t):
    """Return the workflow steps a migrated tiket must have passed through.

    ``t`` is a mapping of :data:`TIKET_FIELDS`. The status says how far the
    tiket got; the dates and counters say which of the earlier steps actually
    happened, which matters for the statuses that can be reached by more than
    one route (Selesai).

    A tiket currently at ``Dibatalkan`` gets no steps at all — not even
    ``Direkam``. Views that look at ``DIKEMBALIKAN``/``DIBATALKAN`` history
    without checking whether the tiket is still open (``home.py``'s
    "Pengembalian Seluruhnya dari PIDE") would otherwise resurface a cancelled
    tiket forever once its history is filled in. A cancelled migrated tiket
    keeps only its ``PIC ditambahkan`` rows, same as if it had never been
    backfilled.
    """
    status = t['status_tiket']
    if status == STATUS_DIBATALKAN:
        return []

    steps = [STEP_DIREKAM]

    if status == STATUS_DIREKAM:
        return steps

    reached_pmde = _has_pengendalian_mutu(t)
    reached_identifikasi = _has_identifikasi(t) or reached_pmde
    reached_pide = _has_kirim_pide(t) or reached_identifikasi
    reached_penelitian = _has_penelitian(t) or reached_pide

    if status == STATUS_DITELITI:
        return steps + [STEP_DITELITI]

    if status == STATUS_DIKEMBALIKAN:
        # Never actually assigned by the app (see status_tiket_flow.md) — a
        # PIDE return sets Dibatalkan, not this — but handled for correctness
        # in case it ever appears. A cancelled-at-DIKEMBALIKAN tiket is not
        # reachable here since STATUS_DIBATALKAN already returned above.
        if reached_penelitian:
            steps.append(STEP_DITELITI)
        if reached_pide:
            steps.append(STEP_DIKIRIM)
        if reached_identifikasi:
            steps.append(STEP_IDENTIFIKASI)
        if reached_pide:
            steps.append(STEP_DIKEMBALIKAN)
        return steps

    if status == STATUS_SELESAI and not reached_pide:
        # Closed at rekam, with nothing to research.
        if not reached_penelitian:
            return steps + [
                STEP_SELESAI_TIDAK_TERSEDIA if not t['status_ketersediaan_data']
                else STEP_SELESAI_P3DE
            ]
        # Closed at P3DE: penelitian found nothing complete (baris_lengkap == 0),
        # so the tiket never went on to PIDE.
        return steps + [STEP_DITELITI, STEP_SELESAI_P3DE]

    # Statuses 4, 5, 6 and the ordinary 8 all went through P3DE in full.
    steps.append(STEP_DITELITI)
    steps.append(STEP_DIKIRIM)
    if status == STATUS_DIKIRIM_KE_PIDE:
        return steps

    steps.append(STEP_IDENTIFIKASI)
    if status == STATUS_IDENTIFIKASI:
        return steps

    steps.append(STEP_TRANSFER)
    if t['tgl_rematch']:
        steps.append(STEP_REMATCH)
    if status == STATUS_PENGENDALIAN_MUTU:
        return steps

    steps.append(STEP_PENGENDALIAN_MUTU)
    steps.append(STEP_SELESAI_PMDE)
    return steps


def resolve_timeline(t, steps):
    """Date each step, yielding ``(step, timestamp, inferred)``.

    A step with a recorded date keeps it untouched, contradictions and all —
    those dates are shown elsewhere on the tiket, so rewriting them here would
    only make the two disagree. A step without one inherits the latest
    timestamp so far and is flagged ``inferred``, which keeps a dateless step
    from sorting above a step that is known to precede it.
    """
    latest = None
    resolved = []
    for step in steps:
        timestamp = None
        for name in step.dates:
            timestamp = t.get(name)
            if timestamp:
                break
        inferred = timestamp is None
        if inferred:
            timestamp = latest
            if timestamp is None:
                # Nothing to anchor to — caller drops the tiket.
                return None
        resolved.append((step, timestamp, inferred))
        if latest is None or timestamp > latest:
            latest = timestamp
    return resolved


def build_catatan(step, inferred):
    """Catatan for a reconstructed row, marked so it is never read as a
    recorded action."""
    return (step.catatan + (MARKER_INFERRED if inferred else MARKER))[:255]


def all_generated_catatan():
    """Every catatan string this command can write — the exact set --remove
    deletes, so a hand-written note is never caught by a LIKE."""
    return {
        build_catatan(step, inferred)
        for step in ALL_STEPS
        for inferred in (False, True)
    }


class Command(BaseCommand):
    help = "Reconstruct the missing workflow audit trail (TiketAction) of migrated (old_db) tikets"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be written without touching the database.',
        )
        parser.add_argument(
            '--tiket', action='append', dest='tiket', metavar='NOMOR_TIKET',
            help='Limit to these nomor tiket. Repeatable.',
        )
        parser.add_argument(
            '--status', type=int, action='append', dest='status', metavar='N',
            help='Limit to these status_tiket values. Repeatable.',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Process at most N tikets (for a trial run on a subset).',
        )
        parser.add_argument(
            '--batch-size', type=int, default=2000,
            help='Rows per bulk insert / per transaction. Default 2000.',
        )
        parser.add_argument(
            '--system-user', default='admin', metavar='USERNAME',
            help='User credited when a tiket has no PIC for the role. Default "admin".',
        )
        parser.add_argument(
            '--no-oracle', action='store_true',
            help='Skip the Oracle lookup for tgl_close_tiket. Pengendalian Mutu and '
                 'Selesai then inherit the previous step timestamp.',
        )
        parser.add_argument(
            '--skip-pic-dates', action='store_true',
            help='Leave the "PIC ditambahkan" timestamps alone instead of re-dating '
                 'the migration batch to the tiket receipt date.',
        )
        parser.add_argument(
            '--skip-cancelled-cleanup', action='store_true',
            help='Leave any backfilled workflow action on a Dibatalkan tiket in place '
                 'instead of deleting it.',
        )
        parser.add_argument(
            '--dedupe', action='store_true',
            help='Also delete exact duplicate actions on migrated tikets (keeps the oldest row).',
        )
        parser.add_argument(
            '--remove', action='store_true',
            help='Delete the actions written by this command instead of creating them.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.batch_size = max(1, options['batch_size'])

        if options['remove']:
            self._remove()
            return

        if options['dedupe']:
            self._dedupe()

        self._backfill(options)

        if not options['skip_cancelled_cleanup']:
            self._cleanup_cancelled(options)

        if not options['skip_pic_dates']:
            self._repair_pic_dates(options)

    # ------------------------------------------------------------------ #
    # Backfill                                                            #
    # ------------------------------------------------------------------ #

    def _backfill(self, options):
        system_user = self._resolve_system_user(options['system_user'])
        tikets = self._select_tikets(options)

        total = tikets.count()
        if not total:
            self.stdout.write(self.style.WARNING('No migrated (old_db) tiket matches the filters.'))
            return

        self.stdout.write(
            f'Scanning {total} migrated tiket'
            f'{" (dry run)" if self.dry_run else ""}...'
        )

        existing = self._existing_workflow_actions(options)
        pic_map = self._active_pic_map(options)
        close_dates = self._close_dates(options)
        ours = all_generated_catatan()

        created_per_action = Counter()
        repaired_per_action = Counter()
        skipped_per_action = Counter()
        tikets_touched = 0
        inferred_rows = 0
        fallback_rows = 0
        undatable = []
        pending = []
        repairs = []

        for t in tikets.values(*TIKET_FIELDS).iterator(chunk_size=self.batch_size):
            t[CLOSE_DATE_FIELD] = close_dates.get(t['nomor_tiket'])
            timeline = resolve_timeline(t, plan_steps(t))
            if timeline is None:
                undatable.append(t['nomor_tiket'])
                continue

            tiket_id = t['id']
            roles = pic_map.get(tiket_id, {})
            wrote = False

            for step, timestamp, inferred in timeline:
                catatan = build_catatan(step, inferred)
                recorded = existing.get((tiket_id, step.action))

                if recorded is not None:
                    # Re-date the rows this command wrote on an earlier run —
                    # an Oracle closing date it did not have then, or a source
                    # date corrected since. Anything a user or the sync wrote
                    # is left exactly as it is.
                    for pk, was_timestamp, was_catatan in recorded:
                        if was_catatan not in ours:
                            skipped_per_action[step.action] += 1
                            continue
                        if was_timestamp == timestamp and was_catatan == catatan:
                            skipped_per_action[step.action] += 1
                            continue
                        repairs.append(TiketAction(
                            pk=pk, timestamp=timestamp, catatan=catatan,
                        ))
                        repaired_per_action[step.action] += 1
                        wrote = True
                    continue

                user_id = roles.get(step.role)
                if user_id is None:
                    user_id = system_user.pk
                    fallback_rows += 1

                pending.append(TiketAction(
                    id_tiket_id=tiket_id,
                    id_user_id=user_id,
                    timestamp=timestamp,
                    action=step.action,
                    catatan=catatan,
                ))
                # Guards against a duplicate within this run, e.g. if a status
                # ever plans the same action twice.
                existing[(tiket_id, step.action)] = []
                created_per_action[step.action] += 1
                inferred_rows += inferred
                wrote = True

            tikets_touched += wrote

            if len(pending) >= self.batch_size:
                self._flush(pending)
                pending = []
            if len(repairs) >= self.batch_size:
                self._flush_repairs(repairs)
                repairs = []

        self._flush(pending)
        self._flush_repairs(repairs)

        self._report(
            total, tikets_touched, created_per_action, repaired_per_action,
            skipped_per_action, inferred_rows, fallback_rows, system_user,
            undatable, close_dates,
        )

    def _select_tikets(self, options):
        qs = Tiket.objects.filter(old_db=True).order_by('id')
        if options['tiket']:
            qs = qs.filter(nomor_tiket__in=options['tiket'])
        if options['status']:
            qs = qs.filter(status_tiket__in=options['status'])
        if options['limit']:
            qs = qs[:options['limit']]
        return qs

    def _resolve_system_user(self, username):
        """The user credited when a tiket has no PIC for a role — 1500-odd
        migrated tikets have no P3DE PIC at all."""
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.filter(is_superuser=True).order_by('pk').first()
        if user is None:
            raise CommandError(
                f'No user "{username}" and no superuser to fall back on. '
                f'Pass --system-user with an existing username.'
            )
        return user

    def _existing_workflow_actions(self, options):
        """``{(tiket_id, action): [TiketAction, ...]}`` for what is already
        recorded, so nothing is written twice — including the transitions
        sync_tiket_update logged itself — and so rows from an earlier run of
        this command can be re-dated in place.

        Values, not model instances: this holds every workflow action on every
        migrated tiket at once, and a run that has already been done once has
        hundreds of thousands of them.
        """
        qs = TiketAction.objects.filter(
            id_tiket__old_db=True, action__lt=WORKFLOW_ACTION_MAX,
        )
        if options['tiket']:
            qs = qs.filter(id_tiket__nomor_tiket__in=options['tiket'])

        existing = defaultdict(list)
        rows = qs.values_list('id_tiket_id', 'action', 'id', 'timestamp', 'catatan')
        for tiket_id, action, pk, timestamp, catatan in rows.iterator(chunk_size=self.batch_size):
            existing[(tiket_id, action)].append((pk, timestamp, catatan))
        return existing

    def _close_dates(self, options):
        """``{nomor_tiket: closing date}`` from Oracle.

        The closing date has no column on Tiket, so without this the two
        closing steps can only inherit the transfer date. Oracle being
        unreachable is not fatal: the run carries on and says which steps went
        undated because of it.
        """
        if options['no_oracle']:
            return {}

        try:
            from ...utils.oracle_sync import OracleDataSyncService

            service = OracleDataSyncService(connection_only=True)
            with service._connect_oracle('primary') as conn:
                with conn.cursor() as cursor:
                    cursor.execute(_CLOSE_DATE_ORACLE_SQL)
                    rows = cursor.fetchall()
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f'Oracle unavailable ({exc.__class__.__name__}: {exc}). Pengendalian Mutu '
                f'and Selesai will inherit the previous step timestamp. '
                f'Re-run once Oracle is reachable to date them properly.'
            ))
            return {}

        close_dates = {}
        for nomor_tiket, tgl_close in rows:
            tgl_close = _naive(tgl_close)
            if not nomor_tiket or tgl_close is None:
                continue
            # The E -> EI repair can fold two raw tiket numbers onto one; keep
            # the later close, matching the MAX(tgl_qc) the grouping already uses.
            current = close_dates.get(nomor_tiket)
            if current is None or tgl_close > current:
                close_dates[nomor_tiket] = tgl_close

        self.stdout.write(f'Read {len(close_dates)} closing date(s) from Oracle.')
        return close_dates

    def _active_pic_map(self, options):
        """``{tiket_id: {role: user_id}}`` from the active PICs.

        Ordered by id so the PIC picked matches the ``.first()`` the workflow
        views and sync_tiket_update use when they attribute an action.
        """
        qs = TiketPIC.objects.filter(id_tiket__old_db=True, active=True)
        if options['tiket']:
            qs = qs.filter(id_tiket__nomor_tiket__in=options['tiket'])

        pic_map = {}
        for tiket_id, role, user_id in qs.order_by('id').values_list(
            'id_tiket_id', 'role', 'id_user_id'
        ):
            pic_map.setdefault(tiket_id, {}).setdefault(role, user_id)
        return pic_map

    def _flush(self, rows):
        """Write one batch. Batches commit independently: the run is
        idempotent, so an interrupted pass is resumed by re-running it."""
        if not rows or self.dry_run:
            return
        with transaction.atomic():
            TiketAction.objects.bulk_create(rows, batch_size=self.batch_size)

    def _flush_repairs(self, rows):
        """Re-date one batch of rows an earlier run of this command wrote."""
        if not rows or self.dry_run:
            return
        with transaction.atomic():
            TiketAction.objects.bulk_update(
                rows, ['timestamp', 'catatan'], batch_size=self.batch_size,
            )

    def _report(self, total, touched, created, repaired, skipped, inferred,
                fallback, system_user, undatable, close_dates):
        created_total = sum(created.values())
        verb = 'Would create' if self.dry_run else 'Created'

        self.stdout.write('')
        self.stdout.write(f'{verb} {created_total} action(s) on {touched} of {total} tiket:')
        for action in sorted(created):
            self.stdout.write(f'  {get_action_label(action):<22} {created[action]:>7}')

        if repaired:
            verb = 'Would re-date' if self.dry_run else 'Re-dated'
            self.stdout.write('')
            self.stdout.write(
                f'{verb} {sum(repaired.values())} action(s) written by an earlier run:'
            )
            for action in sorted(repaired):
                self.stdout.write(f'  {get_action_label(action):<22} {repaired[action]:>7}')

        if skipped:
            self.stdout.write('')
            self.stdout.write(f'Left alone, already correct ({sum(skipped.values())}):')
            for action in sorted(skipped):
                self.stdout.write(f'  {get_action_label(action):<22} {skipped[action]:>7}')

        self.stdout.write('')
        if not close_dates:
            self.stdout.write(self.style.WARNING(
                'No Oracle closing date was read, so Pengendalian Mutu and Selesai '
                'inherited the previous step timestamp.'
            ))
        if inferred:
            self.stdout.write(
                f'{inferred} row(s) had no date of their own and inherited the previous '
                f'step timestamp; their catatan says "tanggal perkiraan".'
            )
        if fallback:
            self.stdout.write(self.style.WARNING(
                f'{fallback} row(s) credited to "{system_user.username}" because the tiket '
                f'has no active PIC for that role.'
            ))
        if undatable:
            self.stdout.write(self.style.WARNING(
                f'{len(undatable)} tiket skipped for having no date at all to anchor the '
                f'timeline: {", ".join(undatable[:10])}'
                f'{" ..." if len(undatable) > 10 else ""}'
            ))

        if self.dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written.'))
        else:
            self.stdout.write(self.style.SUCCESS('Backfill complete.'))

    # ------------------------------------------------------------------ #
    # Cancelled tikets                                                    #
    # ------------------------------------------------------------------ #

    def _cleanup_cancelled(self, options):
        """Strip the reconstructed workflow trail from a tiket now sitting at
        Dibatalkan, leaving only its ``PIC ditambahkan`` rows.

        ``plan_steps`` stopped planning any workflow steps for these tikets,
        but that alone does not touch what an earlier run of this command
        already wrote — the backfill loop only visits the steps a status
        currently plans, so an already-cancelled tiket's old rows are never
        revisited by it. This is the pass that actually removes them.

        Only rows this command wrote are deleted (matched by the exact
        catatan marker set, same as ``--remove``); a genuine Dibatalkan or
        Dikembalikan recorded by a user through the app is left alone.
        """
        qs = TiketAction.objects.filter(
            id_tiket__in=self._select_tikets(options).filter(status_tiket=STATUS_DIBATALKAN),
            action__lt=WORKFLOW_ACTION_MAX,
            catatan__in=all_generated_catatan(),
        )
        tiket_count = qs.values('id_tiket').distinct().count()
        row_count = qs.count()

        if not row_count:
            return

        verb = 'Would delete' if self.dry_run else 'Deleted'
        self.stdout.write('')
        self.stdout.write(
            f'{verb} {row_count} backfilled workflow action(s) on {tiket_count} tiket '
            f'now at Dibatalkan, keeping only "PIC ditambahkan".'
        )

        if self.dry_run:
            return
        for start in range(0, row_count, self.batch_size):
            with transaction.atomic():
                ids = list(qs.values_list('pk', flat=True)[:self.batch_size])
                TiketAction.objects.filter(pk__in=ids).delete()

    # ------------------------------------------------------------------ #
    # PIC action dates                                                    #
    # ------------------------------------------------------------------ #

    def _repair_pic_dates(self, options):
        """Move the migration's ``PIC ditambahkan`` rows to the start of the
        tiket's life.

        ``_assign_tiket_pics_sync`` dated them from the sync clock, so every
        migrated tiket carries its PIC history at the moment of the migration
        run — years after the tiket itself, and after its own Selesai. They
        belong just behind Direkam, which is where RekamPenerimaanDataView puts
        them for a tiket recorded in the app.

        Only the tiket's *first* batch of PIC rows is moved. A PIC genuinely
        added later through the PIC admin is a real later event and keeps its
        date.
        """
        # Scoped by the same selection as the backfill, so --limit really does
        # keep a trial run to a handful of tikets.
        qs = TiketAction.objects.filter(
            id_tiket__in=self._select_tikets(options),
            action=PICActionType.DITAMBAHKAN,
            id_tiket__tgl_terima_dip__isnull=False,
        )

        by_tiket = defaultdict(list)
        rows = qs.order_by('timestamp', 'id').values_list(
            'id_tiket_id', 'id', 'timestamp', 'id_tiket__tgl_terima_dip',
        )
        for tiket_id, pk, timestamp, terima_dip in rows.iterator(chunk_size=self.batch_size):
            by_tiket[tiket_id].append((pk, timestamp, terima_dip))

        if not by_tiket:
            return

        repairs = []
        moved = 0
        left_alone = 0
        for actions in by_tiket.values():
            terima_dip = actions[0][2]
            # The migration wrote a tiket's PIC rows in one go, microseconds
            # apart. Anything past that second was added later, on purpose.
            batch_end = actions[0][1] + timedelta(seconds=1)

            for offset, (pk, timestamp, _) in enumerate(actions, start=1):
                if timestamp > batch_end:
                    left_alone += 1
                    continue
                wanted = terima_dip + timedelta(microseconds=offset)
                if timestamp == wanted:
                    continue
                repairs.append(TiketAction(pk=pk, timestamp=wanted))
                moved += 1

            if len(repairs) >= self.batch_size:
                self._flush_pic_repairs(repairs)
                repairs = []
        self._flush_pic_repairs(repairs)

        verb = 'Would re-date' if self.dry_run else 'Re-dated'
        self.stdout.write('')
        self.stdout.write(
            f'{verb} {moved} "PIC ditambahkan" action(s) across {len(by_tiket)} tiket '
            f'to the tiket receipt date.'
        )
        if left_alone:
            self.stdout.write(
                f'{left_alone} left at their own date, added after the migration.'
            )

    def _flush_pic_repairs(self, rows):
        if not rows or self.dry_run:
            return
        with transaction.atomic():
            TiketAction.objects.bulk_update(rows, ['timestamp'], batch_size=self.batch_size)

    # ------------------------------------------------------------------ #
    # Maintenance                                                         #
    # ------------------------------------------------------------------ #

    def _dedupe(self):
        """Drop exact duplicate actions on migrated tikets, keeping the oldest.

        sync_tiket_update can log the same transition twice when a tiket is
        picked up by two passes, which shows up as a doubled row in the riwayat.
        """
        groups = (
            TiketAction.objects
            .filter(id_tiket__old_db=True)
            .values('id_tiket_id', 'action', 'timestamp', 'id_user_id', 'catatan')
            .annotate(n=Count('id'), keep=Min('id'))
            .filter(n__gt=1)
        )

        doomed = []
        for group in groups:
            keep = group.pop('keep')
            group.pop('n')
            doomed.extend(
                TiketAction.objects.filter(**group).exclude(pk=keep).values_list('pk', flat=True)
            )

        if not doomed:
            self.stdout.write('No duplicate action found on migrated tiket.')
            return

        if self.dry_run:
            self.stdout.write(self.style.WARNING(
                f'Would delete {len(doomed)} duplicate action(s).'
            ))
            return

        for start in range(0, len(doomed), self.batch_size):
            with transaction.atomic():
                TiketAction.objects.filter(pk__in=doomed[start:start + self.batch_size]).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {len(doomed)} duplicate action(s).'))

    def _remove(self):
        """Undo the backfill. Matches on the exact catatan strings written
        here, so a note a user happened to word the same way is left alone."""
        qs = TiketAction.objects.filter(
            id_tiket__old_db=True,
            action__lt=WORKFLOW_ACTION_MAX,
            catatan__in=all_generated_catatan(),
        )
        count = qs.count()
        if not count:
            self.stdout.write('No backfilled action to remove.')
            return
        if self.dry_run:
            self.stdout.write(self.style.WARNING(f'Would delete {count} backfilled action(s).'))
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {count} backfilled action(s).'))
