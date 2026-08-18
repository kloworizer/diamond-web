"""Tests for the ``backfill_old_db_tiket_actions`` command.

The command reconstructs the workflow audit trail of migrated (``old_db``)
tikets, which the migration sync never wrote. Two things are worth pinning
down: which steps a given status/date combination is allowed to claim, and the
fact that a recorded date is never overwritten by a guess.
"""
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from diamond_web.constants.tiket_action_types import PICActionType, TiketActionType
from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.management.commands.backfill_old_db_tiket_actions import (
    CLOSE_DATE_FIELD,
    MARKER,
    MARKER_INFERRED,
    PLANNER_FIELDS,
    Command,
    plan_steps,
    resolve_timeline,
)
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.tiket_pic import TiketPIC

from .conftest import TiketFactory, TiketPICFactory, UserFactory

TERIMA = datetime(2025, 1, 6, 0, 0)
TELITI = datetime(2025, 1, 20, 9, 30)
KIRIM = datetime(2025, 2, 3, 0, 0)
REKAM_PIDE = datetime(2025, 2, 17, 0, 0)
TRANSFER = datetime(2025, 3, 10, 0, 0)
REMATCH = datetime(2025, 4, 1, 0, 0)
CLOSE = datetime(2025, 5, 20, 0, 0)


def _row(**overrides):
    """A migrated tiket as the planner sees it: every field null but the
    receipt date, which the migration always carries across."""
    row = {name: None for name in PLANNER_FIELDS}
    row.update({
        'id': 1,
        'nomor_tiket': 'TEST00000000001',
        'status_tiket': STATUS_DIREKAM,
        'status_ketersediaan_data': True,
        'tgl_terima_dip': TERIMA,
        'baris_lengkap': 0,
    })
    row.update(overrides)
    return row


def _actions(row):
    return [step.action for step in plan_steps(row)]


# --------------------------------------------------------------------------- #
# Which steps a status may claim                                              #
# --------------------------------------------------------------------------- #

class TestPlanSteps:

    def test_direkam_only_records_the_receipt(self):
        assert _actions(_row(status_tiket=STATUS_DIREKAM)) == [TiketActionType.DIREKAM]

    def test_diteliti_adds_the_research_step(self):
        row = _row(status_tiket=STATUS_DITELITI, tgl_teliti=TELITI)
        assert _actions(row) == [TiketActionType.DIREKAM, TiketActionType.DITELITI]

    def test_dikirim_ke_pide_walks_the_p3de_steps(self):
        row = _row(status_tiket=STATUS_DIKIRIM_KE_PIDE, tgl_teliti=TELITI, tgl_kirim_pide=KIRIM)
        assert _actions(row) == [
            TiketActionType.DIREKAM,
            TiketActionType.DITELITI,
            TiketActionType.DIKIRIM_KE_PIDE,
        ]

    def test_identifikasi_stops_at_pide(self):
        row = _row(
            status_tiket=STATUS_IDENTIFIKASI, tgl_teliti=TELITI,
            tgl_kirim_pide=KIRIM, tgl_rekam_pide=REKAM_PIDE,
        )
        assert _actions(row)[-1] == TiketActionType.IDENTIFIKASI

    def test_pengendalian_mutu_ends_at_the_transfer(self):
        row = _row(
            status_tiket=STATUS_PENGENDALIAN_MUTU, tgl_teliti=TELITI,
            tgl_kirim_pide=KIRIM, tgl_rekam_pide=REKAM_PIDE, tgl_transfer=TRANSFER,
        )
        assert _actions(row) == [
            TiketActionType.DIREKAM,
            TiketActionType.DITELITI,
            TiketActionType.DIKIRIM_KE_PIDE,
            TiketActionType.IDENTIFIKASI,
            TiketActionType.DITRANSFER_KE_PMDE,
        ]

    def test_selesai_walks_the_whole_workflow(self):
        row = _row(
            status_tiket=STATUS_SELESAI, tgl_teliti=TELITI, tgl_kirim_pide=KIRIM,
            tgl_rekam_pide=REKAM_PIDE, tgl_transfer=TRANSFER, sudah_qc=10,
        )
        assert _actions(row) == [
            TiketActionType.DIREKAM,
            TiketActionType.DITELITI,
            TiketActionType.DIKIRIM_KE_PIDE,
            TiketActionType.IDENTIFIKASI,
            TiketActionType.DITRANSFER_KE_PMDE,
            TiketActionType.PENGENDALIAN_MUTU,
            TiketActionType.SELESAI,
        ]

    def test_rematch_is_recorded_between_transfer_and_qc(self):
        row = _row(
            status_tiket=STATUS_SELESAI, tgl_teliti=TELITI, tgl_kirim_pide=KIRIM,
            tgl_rekam_pide=REKAM_PIDE, tgl_transfer=TRANSFER, tgl_rematch=REMATCH,
        )
        actions = _actions(row)
        assert actions.index(TiketActionType.DITRANSFER_KE_PMDE) \
            < actions.index(TiketActionType.REMATCH) \
            < actions.index(TiketActionType.PENGENDALIAN_MUTU)

    def test_transfer_is_claimed_from_identified_rows_without_a_transfer_date(self):
        """The transfer writes the I/U/Res/CDE counts, so they stand in for a
        missing tgl_transfer."""
        row = _row(
            status_tiket=STATUS_SELESAI, tgl_teliti=TELITI,
            tgl_kirim_pide=KIRIM, baris_i=120,
        )
        assert TiketActionType.DITRANSFER_KE_PMDE in _actions(row)


class TestPlanStepsForClosedTikets:
    """Dibatalkan and Selesai are reachable by several routes, so the earlier
    steps are claimed only where the tiket's own data supports them."""

    def test_cancelled_before_research_claims_nothing_it_cannot_show(self):
        row = _row(status_tiket=STATUS_DIBATALKAN)
        assert _actions(row) == []

    def test_cancelled_tiket_gets_no_steps_even_with_a_rich_history(self):
        """A cancelled tiket gets nothing reconstructed at all, not even
        Direkam — several views (home.py's "Pengembalian Seluruhnya dari
        PIDE") key off DIKEMBALIKAN/DIBATALKAN history without checking
        whether the tiket is still open, so a filled-in trail on an already-
        cancelled tiket would resurface it there forever."""
        row = _row(
            status_tiket=STATUS_DIBATALKAN, tgl_teliti=TELITI,
            tgl_kirim_pide=KIRIM, tgl_rekam_pide=REKAM_PIDE,
        )
        assert _actions(row) == []

    def test_selesai_at_rekam_when_no_data_was_available(self):
        row = _row(status_tiket=STATUS_SELESAI, status_ketersediaan_data=False)
        steps = plan_steps(row)
        assert [s.action for s in steps] == [TiketActionType.DIREKAM, TiketActionType.SELESAI]
        assert steps[-1].catatan == 'tiket selesai, data tidak tersedia'
        assert steps[-1].role == TiketPIC.Role.P3DE

    def test_selesai_at_p3de_when_research_found_nothing_complete(self):
        row = _row(status_tiket=STATUS_SELESAI, tgl_teliti=TELITI, baris_lengkap=0)
        steps = plan_steps(row)
        assert [s.action for s in steps] == [
            TiketActionType.DIREKAM, TiketActionType.DITELITI, TiketActionType.SELESAI,
        ]
        assert steps[-1].role == TiketPIC.Role.P3DE

    def test_data_tidak_tersedia_still_walks_the_workflow_it_went_through(self):
        """status_ketersediaan_data is 0 on thousands of migrated tikets that
        demonstrably reached PIDE, so it cannot short-circuit the plan on its
        own."""
        row = _row(
            status_tiket=STATUS_SELESAI, status_ketersediaan_data=False,
            tgl_teliti=TELITI, tgl_kirim_pide=KIRIM, tgl_transfer=TRANSFER,
        )
        assert TiketActionType.DIKIRIM_KE_PIDE in _actions(row)
        assert TiketActionType.DITRANSFER_KE_PMDE in _actions(row)

    def test_a_zero_row_count_is_not_read_as_research(self):
        """The sync COALESCEs baris_lengkap to 0 for every migrated row, so a
        zero count is not evidence that penelitian happened. Exercised through
        STATUS_DIKEMBALIKAN, since Dibatalkan itself now plans no steps at all."""
        row = _row(status_tiket=STATUS_DIKEMBALIKAN, baris_lengkap=0)
        assert TiketActionType.DITELITI not in _actions(row)

        row = _row(status_tiket=STATUS_DIKEMBALIKAN, baris_lengkap=42)
        assert TiketActionType.DITELITI in _actions(row)


class TestPlanStepsForDikembalikan:
    """STATUS_DIKEMBALIKAN (3) is never actually assigned by the app — a PIDE
    return sets Dibatalkan, not this (see status_tiket_flow.md) — but the
    planner still handles it correctly if it ever appears."""

    def test_returned_after_handover_keeps_the_steps_it_shows_evidence_for(self):
        row = _row(
            status_tiket=STATUS_DIKEMBALIKAN, tgl_teliti=TELITI,
            tgl_kirim_pide=KIRIM, tgl_rekam_pide=REKAM_PIDE,
        )
        assert _actions(row) == [
            TiketActionType.DIREKAM,
            TiketActionType.DITELITI,
            TiketActionType.DIKIRIM_KE_PIDE,
            TiketActionType.IDENTIFIKASI,
            TiketActionType.DIKEMBALIKAN,
        ]

    def test_returned_before_reaching_pide_claims_nothing_it_cannot_show(self):
        row = _row(status_tiket=STATUS_DIKEMBALIKAN)
        assert _actions(row) == [TiketActionType.DIREKAM]


# --------------------------------------------------------------------------- #
# Dating the steps                                                            #
# --------------------------------------------------------------------------- #

class TestResolveTimeline:

    def test_recorded_dates_are_used_verbatim(self):
        row = _row(status_tiket=STATUS_DITELITI, tgl_teliti=TELITI)
        timeline = resolve_timeline(row, plan_steps(row))
        assert [(ts, inferred) for _, ts, inferred in timeline] == [
            (TERIMA, False), (TELITI, False),
        ]

    def test_out_of_order_dates_are_left_alone(self):
        """Migrated tikets carry dates that contradict each other. They are
        shown elsewhere on the tiket, so rewriting them here would only make
        the two disagree."""
        row = _row(status_tiket=STATUS_DIKIRIM_KE_PIDE, tgl_teliti=TELITI,
                   tgl_kirim_pide=datetime(2025, 1, 10, 0, 0))
        _, kirim_ts, inferred = resolve_timeline(row, plan_steps(row))[-1]
        assert kirim_ts == datetime(2025, 1, 10, 0, 0)
        assert inferred is False

    def test_a_step_without_a_date_inherits_the_latest_one(self):
        row = _row(status_tiket=STATUS_PENGENDALIAN_MUTU, tgl_teliti=TELITI,
                   tgl_kirim_pide=KIRIM, tgl_transfer=TRANSFER)
        by_action = {step.action: (ts, inferred) for step, ts, inferred in
                     resolve_timeline(row, plan_steps(row))}
        # Identifikasi has no tgl_rekam_pide of its own; it may not sort before
        # the handover that is known to precede it.
        assert by_action[TiketActionType.IDENTIFIKASI] == (KIRIM, True)

    def test_inherited_dates_never_run_backwards(self):
        row = _row(status_tiket=STATUS_SELESAI, tgl_teliti=TELITI,
                   tgl_kirim_pide=datetime(2025, 1, 10, 0, 0), tgl_transfer=TRANSFER)
        stamps = [ts for _, ts, inferred in resolve_timeline(row, plan_steps(row)) if inferred]
        assert stamps == sorted(stamps)

    def test_a_tiket_with_no_date_at_all_cannot_be_dated(self):
        assert resolve_timeline(_row(tgl_terima_dip=None), plan_steps(_row())) is None

    def test_the_closing_steps_use_the_oracle_close_date(self):
        row = _row(
            status_tiket=STATUS_SELESAI, tgl_teliti=TELITI, tgl_kirim_pide=KIRIM,
            tgl_rekam_pide=REKAM_PIDE, tgl_transfer=TRANSFER, **{CLOSE_DATE_FIELD: CLOSE},
        )
        by_action = {step.action: (ts, inferred) for step, ts, inferred in
                     resolve_timeline(row, plan_steps(row))}
        assert by_action[TiketActionType.PENGENDALIAN_MUTU] == (CLOSE, False)
        assert by_action[TiketActionType.SELESAI] == (CLOSE, False)

    def test_the_closing_steps_inherit_the_transfer_without_one(self):
        """tgl_close_tiket has no column on Tiket, so a run that could not reach
        Oracle has nothing to date the two closing steps with."""
        row = _row(
            status_tiket=STATUS_SELESAI, tgl_teliti=TELITI, tgl_kirim_pide=KIRIM,
            tgl_rekam_pide=REKAM_PIDE, tgl_transfer=TRANSFER,
        )
        by_action = {step.action: (ts, inferred) for step, ts, inferred in
                     resolve_timeline(row, plan_steps(row))}
        assert by_action[TiketActionType.PENGENDALIAN_MUTU] == (TRANSFER, True)
        assert by_action[TiketActionType.SELESAI] == (TRANSFER, True)


# --------------------------------------------------------------------------- #
# The command end to end                                                      #
# --------------------------------------------------------------------------- #

def _run(*args, close_dates=None):
    """Run the command with the Oracle lookup stubbed out — the tests decide
    which closing dates exist, and never touch a real database link."""
    out = StringIO()
    with patch.object(Command, '_close_dates', return_value=close_dates or {}):
        call_command('backfill_old_db_tiket_actions', *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.fixture
def migrated_tiket(db):
    """A migrated tiket at Selesai with a PIC for each role."""
    tiket = TiketFactory(
        old_db=True, status_tiket=STATUS_SELESAI, tgl_terima_dip=TERIMA,
        tgl_teliti=TELITI, tgl_kirim_pide=KIRIM, tgl_rekam_pide=REKAM_PIDE,
        tgl_transfer=TRANSFER, baris_lengkap=100, sudah_qc=100,
    )
    for role in (TiketPIC.Role.P3DE, TiketPIC.Role.PIDE, TiketPIC.Role.PMDE):
        TiketPICFactory(id_tiket=tiket, id_user=UserFactory(), role=role, active=True)
    return tiket


@pytest.mark.django_db
class TestCommand:

    def _workflow(self, tiket):
        return list(
            TiketAction.objects
            .filter(id_tiket=tiket, action__lt=100)
            .order_by('timestamp', 'id')
            .values_list('action', flat=True)
        )

    def test_writes_the_full_trail_for_a_migrated_tiket(self, migrated_tiket):
        _run()
        assert self._workflow(migrated_tiket) == [
            TiketActionType.DIREKAM,
            TiketActionType.DITELITI,
            TiketActionType.DIKIRIM_KE_PIDE,
            TiketActionType.IDENTIFIKASI,
            TiketActionType.DITRANSFER_KE_PMDE,
            TiketActionType.PENGENDALIAN_MUTU,
            TiketActionType.SELESAI,
        ]

    def test_every_row_is_marked_as_reconstructed(self, migrated_tiket):
        _run()
        catatan = TiketAction.objects.filter(id_tiket=migrated_tiket).values_list('catatan', flat=True)
        assert all(c.endswith(MARKER) or c.endswith(MARKER_INFERRED) for c in catatan)

    def test_each_step_is_credited_to_the_pic_that_owns_it(self, migrated_tiket):
        _run()
        roles = {
            pic.id_user_id: pic.role
            for pic in TiketPIC.objects.filter(id_tiket=migrated_tiket)
        }
        credited = {
            a.action: roles.get(a.id_user_id)
            for a in TiketAction.objects.filter(id_tiket=migrated_tiket, action__lt=100)
        }
        assert credited[TiketActionType.DIREKAM] == TiketPIC.Role.P3DE
        assert credited[TiketActionType.DIKIRIM_KE_PIDE] == TiketPIC.Role.P3DE
        assert credited[TiketActionType.IDENTIFIKASI] == TiketPIC.Role.PIDE
        assert credited[TiketActionType.DITRANSFER_KE_PMDE] == TiketPIC.Role.PIDE
        assert credited[TiketActionType.PENGENDALIAN_MUTU] == TiketPIC.Role.PMDE
        assert credited[TiketActionType.SELESAI] == TiketPIC.Role.PMDE

    def test_a_role_without_a_pic_falls_back_to_the_system_user(self, db):
        system = User.objects.create_user('sysadmin')
        tiket = TiketFactory(old_db=True, status_tiket=STATUS_DIREKAM, tgl_terima_dip=TERIMA)

        output = _run('--system-user', 'sysadmin')

        action = TiketAction.objects.get(id_tiket=tiket, action=TiketActionType.DIREKAM)
        assert action.id_user_id == system.pk
        assert 'no active PIC for that role' in output

    def test_leaves_tikets_recorded_in_the_app_alone(self, db):
        tiket = TiketFactory(old_db=False, status_tiket=STATUS_SELESAI, tgl_terima_dip=TERIMA)
        _run()
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()

    def test_keeps_an_action_the_sync_already_logged(self, migrated_tiket):
        existing = TiketAction.objects.create(
            id_tiket=migrated_tiket,
            id_user=UserFactory(),
            timestamp=TRANSFER,
            action=TiketActionType.DITRANSFER_KE_PMDE,
            catatan='Tiket ditransfer ke PMDE',
        )

        _run()

        transfers = TiketAction.objects.filter(
            id_tiket=migrated_tiket, action=TiketActionType.DITRANSFER_KE_PMDE
        )
        assert [t.pk for t in transfers] == [existing.pk]

    def test_running_twice_changes_nothing(self, migrated_tiket):
        _run()
        before = set(TiketAction.objects.values_list('pk', flat=True))
        _run()
        assert set(TiketAction.objects.values_list('pk', flat=True)) == before

    def test_dry_run_writes_nothing(self, migrated_tiket):
        output = _run('--dry-run')
        assert not TiketAction.objects.exists()
        assert 'Would create' in output

    def test_remove_undoes_the_backfill(self, migrated_tiket):
        recorded = TiketAction.objects.create(
            id_tiket=migrated_tiket, id_user=UserFactory(), timestamp=TELITI,
            action=TiketActionType.DIUBAH, catatan='Baris Diterima: 10 -> 20',
        )
        _run()

        _run('--remove')

        assert [a.pk for a in TiketAction.objects.all()] == [recorded.pk]

    def test_dedupe_drops_repeated_rows_and_keeps_the_oldest(self, migrated_tiket):
        user = UserFactory()
        kept, dupe = (
            TiketAction.objects.create(
                id_tiket=migrated_tiket, id_user=user, timestamp=TRANSFER,
                action=TiketActionType.PENGENDALIAN_MUTU,
                catatan='Tiket selesai pengendalian mutu',
            )
            for _ in range(2)
        )

        _run('--dedupe')

        remaining = TiketAction.objects.filter(action=TiketActionType.PENGENDALIAN_MUTU)
        assert [a.pk for a in remaining] == [kept.pk]
        assert not TiketAction.objects.filter(pk=dupe.pk).exists()

    def test_tiket_filter_limits_the_run(self, migrated_tiket, db):
        other = TiketFactory(old_db=True, status_tiket=STATUS_DIREKAM, tgl_terima_dip=TERIMA)

        _run('--tiket', migrated_tiket.nomor_tiket)

        assert TiketAction.objects.filter(id_tiket=migrated_tiket).exists()
        assert not TiketAction.objects.filter(id_tiket=other).exists()

    def test_the_closing_steps_are_dated_from_oracle(self, migrated_tiket):
        _run(close_dates={migrated_tiket.nomor_tiket: CLOSE})

        closing = TiketAction.objects.filter(
            id_tiket=migrated_tiket,
            action__in=(TiketActionType.PENGENDALIAN_MUTU, TiketActionType.SELESAI),
        )
        assert [a.timestamp for a in closing] == [CLOSE, CLOSE]
        assert all(a.catatan.endswith(MARKER) for a in closing)


@pytest.mark.django_db
class TestCancelledTiketCleanup:
    """A migrated tiket now sitting at Dibatalkan keeps only its PIC rows.

    home.py's "Pengembalian Seluruhnya dari PIDE" card (and anything similar)
    matches on the mere presence of a DIKEMBALIKAN/DIBATALKAN action, with no
    check for whether the tiket is still open — so once these tikets got a
    filled-in trail, they started showing up there permanently, including
    ones nobody can act on any more.
    """

    @pytest.fixture
    def cancelled_tiket(self, db):
        tiket = TiketFactory(old_db=True, status_tiket=STATUS_DIBATALKAN, tgl_terima_dip=TERIMA)
        TiketPICFactory(id_tiket=tiket, id_user=UserFactory(), role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def test_a_cancelled_tiket_gets_nothing_backfilled(self, cancelled_tiket):
        _run()
        assert not TiketAction.objects.filter(
            id_tiket=cancelled_tiket, action__lt=100,
        ).exists()

    def test_an_earlier_runs_trail_is_deleted_down_to_pic_rows_only(self, cancelled_tiket):
        pic_action = TiketAction.objects.create(
            id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
            action=PICActionType.DITAMBAHKAN, catatan='PIC P3DE ditambahkan',
        )
        for action, catatan in (
            (TiketActionType.DIREKAM, 'tiket direkam (data migrasi)'),
            (TiketActionType.DITELITI, 'Hasil penelitian direkam (data migrasi)'),
            (TiketActionType.DIKEMBALIKAN, 'Tiket dikembalikan oleh PIDE (data migrasi, tanggal perkiraan)'),
            (TiketActionType.DIBATALKAN, 'Tiket dibatalkan (dikembalikan oleh PIDE) (data migrasi, tanggal perkiraan)'),
        ):
            TiketAction.objects.create(
                id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
                action=action, catatan=catatan,
            )

        output = _run()

        remaining = list(TiketAction.objects.filter(id_tiket=cancelled_tiket))
        assert [a.pk for a in remaining] == [pic_action.pk]
        assert 'Deleted 4 backfilled workflow action(s) on 1 tiket' in output

    def test_a_genuine_user_recorded_cancellation_is_left_alone(self, cancelled_tiket):
        real = TiketAction.objects.create(
            id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
            action=TiketActionType.DIBATALKAN, catatan='Data duplikat, tiket lain sudah dibuat',
        )

        _run()

        real.refresh_from_db()
        assert real.catatan == 'Data duplikat, tiket lain sudah dibuat'

    def test_dry_run_reports_without_deleting(self, cancelled_tiket):
        TiketAction.objects.create(
            id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
            action=TiketActionType.DIREKAM, catatan='tiket direkam (data migrasi)',
        )

        output = _run('--dry-run')

        assert 'Would delete 1 backfilled workflow action(s)' in output
        assert TiketAction.objects.filter(id_tiket=cancelled_tiket, action=TiketActionType.DIREKAM).exists()

    def test_skip_cancelled_cleanup_leaves_the_old_trail_in_place(self, cancelled_tiket):
        TiketAction.objects.create(
            id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
            action=TiketActionType.DIREKAM, catatan='tiket direkam (data migrasi)',
        )

        _run('--skip-cancelled-cleanup')

        assert TiketAction.objects.filter(id_tiket=cancelled_tiket, action=TiketActionType.DIREKAM).exists()

    def test_running_twice_is_a_no_op_on_the_second_pass(self, cancelled_tiket):
        TiketAction.objects.create(
            id_tiket=cancelled_tiket, id_user=UserFactory(), timestamp=TERIMA,
            action=TiketActionType.DIREKAM, catatan='tiket direkam (data migrasi)',
        )
        _run()

        output = _run()

        assert 'Deleted' not in output


@pytest.mark.django_db
class TestRepairOfAnEarlierRun:
    """The command has already been run against the live database, so it has to
    correct its own rows rather than skip them for existing."""

    def _closing(self, tiket):
        return TiketAction.objects.filter(
            id_tiket=tiket,
            action__in=(TiketActionType.PENGENDALIAN_MUTU, TiketActionType.SELESAI),
        ).order_by('action')

    def test_a_closing_date_that_arrives_later_re_dates_the_rows(self, migrated_tiket):
        _run()  # first run: Oracle unreachable, both closing steps inherit
        assert all(a.timestamp == TRANSFER for a in self._closing(migrated_tiket))
        assert all(MARKER_INFERRED in a.catatan for a in self._closing(migrated_tiket))
        before = set(TiketAction.objects.values_list('pk', flat=True))

        output = _run(close_dates={migrated_tiket.nomor_tiket: CLOSE})

        assert all(a.timestamp == CLOSE for a in self._closing(migrated_tiket))
        assert all(a.catatan.endswith(MARKER) for a in self._closing(migrated_tiket))
        # Repaired in place, not appended as a second set of rows.
        assert set(TiketAction.objects.values_list('pk', flat=True)) == before
        assert 'Re-dated 2 action' in output

    def test_a_row_written_by_someone_else_is_never_re_dated(self, migrated_tiket):
        theirs = TiketAction.objects.create(
            id_tiket=migrated_tiket, id_user=UserFactory(), timestamp=TRANSFER,
            action=TiketActionType.SELESAI, catatan='Tiket selesai diproses)',
        )

        _run(close_dates={migrated_tiket.nomor_tiket: CLOSE})

        theirs.refresh_from_db()
        assert theirs.timestamp == TRANSFER
        assert theirs.catatan == 'Tiket selesai diproses)'

    def test_a_second_run_with_the_same_dates_changes_nothing(self, migrated_tiket):
        dates = {migrated_tiket.nomor_tiket: CLOSE}
        _run(close_dates=dates)
        before = {
            a.pk: (a.timestamp, a.catatan) for a in TiketAction.objects.all()
        }

        _run(close_dates=dates)

        assert {a.pk: (a.timestamp, a.catatan) for a in TiketAction.objects.all()} == before


@pytest.mark.django_db
class TestPICActionDates:
    """The migration dated "PIC ditambahkan" from the sync clock, parking every
    migrated tiket's PIC history years after the tiket itself."""

    def _pic_batch(self, tiket, at, count=3):
        return [
            TiketAction.objects.create(
                id_tiket=tiket, id_user=UserFactory(),
                timestamp=at + timedelta(microseconds=i),
                action=PICActionType.DITAMBAHKAN,
                catatan=f'PIC {i} ditambahkan',
            )
            for i in range(1, count + 1)
        ]

    def test_the_migration_batch_moves_to_just_behind_direkam(self, migrated_tiket):
        sync_clock = datetime(2026, 8, 6, 10, 14, 42)
        batch = self._pic_batch(migrated_tiket, sync_clock)

        _run()

        for offset, action in enumerate(batch, start=1):
            action.refresh_from_db()
            assert action.timestamp == TERIMA + timedelta(microseconds=offset)

    def test_the_batch_order_is_preserved(self, migrated_tiket):
        batch = self._pic_batch(migrated_tiket, datetime(2026, 8, 6, 10, 14, 42))

        _run()

        stamps = [
            TiketAction.objects.get(pk=a.pk).timestamp for a in batch
        ]
        assert stamps == sorted(stamps)

    def test_a_pic_added_after_the_migration_keeps_its_date(self, migrated_tiket):
        self._pic_batch(migrated_tiket, datetime(2026, 8, 6, 10, 14, 42))
        later = TiketAction.objects.create(
            id_tiket=migrated_tiket, id_user=UserFactory(),
            timestamp=datetime(2026, 8, 7, 15, 19, 33),
            action=PICActionType.DITAMBAHKAN,
            catatan='PIC PIDE 123 ditambahkan',
        )

        output = _run()

        later.refresh_from_db()
        assert later.timestamp == datetime(2026, 8, 7, 15, 19, 33)
        assert '1 left at their own date' in output

    def test_skip_pic_dates_leaves_them_alone(self, migrated_tiket):
        sync_clock = datetime(2026, 8, 6, 10, 14, 42)
        batch = self._pic_batch(migrated_tiket, sync_clock)

        _run('--skip-pic-dates')

        for offset, action in enumerate(batch, start=1):
            action.refresh_from_db()
            assert action.timestamp == sync_clock + timedelta(microseconds=offset)

    def test_dry_run_reports_without_moving_them(self, migrated_tiket):
        sync_clock = datetime(2026, 8, 6, 10, 14, 42)
        batch = self._pic_batch(migrated_tiket, sync_clock)

        output = _run('--dry-run')

        assert 'Would re-date 3 "PIC ditambahkan"' in output
        for action in batch:
            action.refresh_from_db()
            assert action.timestamp.date() == sync_clock.date()

    def test_running_twice_leaves_them_settled(self, migrated_tiket):
        self._pic_batch(migrated_tiket, datetime(2026, 8, 6, 10, 14, 42))
        _run()
        before = {
            a.pk: a.timestamp for a in
            TiketAction.objects.filter(action=PICActionType.DITAMBAHKAN)
        }

        _run()

        assert {
            a.pk: a.timestamp for a in
            TiketAction.objects.filter(action=PICActionType.DITAMBAHKAN)
        } == before
