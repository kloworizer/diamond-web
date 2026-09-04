"""Tests for the ``backfill_tiket_jenis_prioritas`` command.

The command reconciles ``Tiket.id_jenis_prioritas_data`` with the one rule the
whole app now uses: a prioritas row whose validity window covers the tiket's
tgl_terima_dip. Three things are worth pinning down: that the window (not the
tahun) decides, that a full reconciliation fixes the wrong links left behind by
the old tahun rule, and that a journalled run can be reversed exactly.
"""
import json
from datetime import date, datetime
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection

from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.constants.tiket_status import STATUS_DIREKAM, STATUS_SELESAI
from diamond_web.management.commands.backfill_tiket_jenis_prioritas import (
    MARKER,
    build_catatan,
)
from diamond_web.models.jenis_prioritas_data import JenisPrioritasData
from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_action import TiketAction

from .conftest import (
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
)

TERIMA = datetime(2025, 3, 10, 8, 0)


def test_catatan_is_marked_and_fits_the_column():
    catatan = build_catatan('-', 'KM0330101 - 2025')
    assert catatan.endswith(MARKER)
    assert len(catatan) <= TiketAction._meta.get_field('catatan').max_length


def test_a_long_catatan_keeps_its_marker():
    catatan = build_catatan('X' * 200, 'Y' * 200)
    assert catatan.endswith(MARKER)
    assert len(catatan) <= TiketAction._meta.get_field('catatan').max_length


# --------------------------------------------------------------------------- #
# The command end to end                                                      #
# --------------------------------------------------------------------------- #

def _run(*args):
    out = StringIO()
    call_command('backfill_tiket_jenis_prioritas', *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.fixture
def admin_account(db):
    """The account the command credits its TiketAction rows to. The seed
    migration already creates it, so this only guarantees it is there."""
    user, _ = User.objects.get_or_create(username='admin')
    return user


@pytest.fixture
def sub_jenis(db):
    return JenisDataILAPFactory(id_sub_jenis_data='KM0330101')


@pytest.fixture
def prioritas(sub_jenis):
    """The Data Prioritas row an admin adds after the fact. Its tahun is
    deliberately unrelated to the tiket's — only the window counts."""
    return JenisPrioritasDataFactory(
        id_sub_jenis_data_ilap=sub_jenis, tahun='2099',
        start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
    )


@pytest.fixture
def tiket(sub_jenis):
    """A tiket recorded before the prioritas row existed: FK still empty."""
    return TiketFactory(
        id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
        id_jenis_prioritas_data=None,
        tahun=2024,
        status_tiket=STATUS_DIREKAM,
        tgl_terima_dip=TERIMA,
    )


def _reload(tiket):
    return Tiket.objects.get(pk=tiket.pk).id_jenis_prioritas_data_id


@pytest.mark.django_db
class TestTheWindowDecides:

    def test_fills_when_the_window_covers_the_receipt_date(
        self, admin_account, prioritas, tiket
    ):
        """The tiket's tahun (2024) matches nothing; the window (2025) does."""
        _run()
        assert _reload(tiket) == prioritas.pk

    def test_leaves_a_tiket_received_outside_the_window_empty(
        self, admin_account, prioritas, sub_jenis
    ):
        outside = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=None, tahun=2099, tgl_terima_dip=datetime(2026, 1, 5),
        )
        _run()
        assert _reload(outside) is None

    def test_an_open_ended_row_stays_in_force(self, admin_account, sub_jenis, tiket):
        """End Date kosong berarti masih berlaku, bukan tidak pernah berlaku."""
        row = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_jenis, tahun='2099',
            start_date=date(2025, 1, 1), end_date=None,
        )
        _run()
        assert _reload(tiket) == row.pk

    def test_the_window_edges_are_inclusive(self, admin_account, sub_jenis):
        row = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_jenis, tahun='2099',
            start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        )
        periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis)
        first = TiketFactory(
            id_periode_data=periode, id_jenis_prioritas_data=None,
            tgl_terima_dip=datetime(2025, 1, 1, 0, 0),
        )
        last = TiketFactory(
            id_periode_data=periode, id_jenis_prioritas_data=None,
            tgl_terima_dip=datetime(2025, 12, 31, 23, 59),
        )
        _run()
        assert _reload(first) == row.pk
        assert _reload(last) == row.pk

    def test_a_tiket_of_another_sub_jenis_data_is_left_empty(self, admin_account, prioritas):
        other = TiketFactory(id_jenis_prioritas_data=None, tgl_terima_dip=TERIMA)
        _run()
        assert _reload(other) is None

    def test_every_tiket_can_be_judged(self, db):
        """tgl_terima_dip is NOT NULL on Tiket, so the rule always has a date to
        stand on — there is no "cannot be determined" case to handle."""
        assert not Tiket._meta.get_field('tgl_terima_dip').null


@pytest.mark.django_db
class TestReconciliation:

    def test_repairs_a_link_left_by_the_old_tahun_rule(
        self, admin_account, prioritas, sub_jenis
    ):
        """Tikets recorded before the fix point at whatever the tahun match
        produced. A full run moves them onto the row the window says."""
        stray = JenisPrioritasDataFactory(tahun='2024')
        mislinked = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=stray, tahun=2024, tgl_terima_dip=TERIMA,
        )
        _run()
        assert _reload(mislinked) == prioritas.pk

    def test_clears_a_link_the_window_no_longer_supports(self, admin_account, sub_jenis):
        stray = JenisPrioritasDataFactory(tahun='2019')
        tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=stray, tgl_terima_dip=TERIMA,
        )
        _run()
        assert _reload(tiket) is None

    def test_fill_only_leaves_every_existing_link_alone(
        self, admin_account, prioritas, sub_jenis, tiket
    ):
        stray = JenisPrioritasDataFactory(tahun='2019')
        mislinked = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=stray, tgl_terima_dip=TERIMA,
        )

        output = _run('--fill-only')

        assert _reload(mislinked) == stray.pk
        assert _reload(tiket) == prioritas.pk
        assert '--fill-only' in output

    def test_running_again_changes_nothing(self, admin_account, prioritas, tiket):
        _run()
        _run()
        assert _reload(tiket) == prioritas.pk
        assert TiketAction.objects.filter(id_tiket=tiket, action=TiketActionType.DIUBAH).count() == 1

    def test_dry_run_writes_nothing(self, admin_account, prioritas, tiket):
        output = _run('--dry-run')
        assert _reload(tiket) is None
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()
        assert 'Dry run' in output

    def test_the_change_is_recorded_in_the_audit_trail(self, admin_account, prioritas, tiket):
        _run()
        action = TiketAction.objects.get(id_tiket=tiket, action=TiketActionType.DIUBAH)
        assert action.catatan.endswith(MARKER)
        assert action.id_user_id == admin_account.pk

    def test_no_action_leaves_the_audit_trail_alone(self, admin_account, prioritas, tiket):
        _run('--no-action')
        assert _reload(tiket) == prioritas.pk
        assert not TiketAction.objects.filter(id_tiket=tiket).exists()


@pytest.mark.django_db
class TestScoping:

    def test_prioritas_id_limits_the_run_to_the_row_just_added(
        self, admin_account, prioritas, tiket, sub_jenis
    ):
        other_sub = JenisDataILAPFactory(id_sub_jenis_data='KM0330102')
        other_row = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=other_sub, tahun='2099',
            start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
        )
        other_tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=other_sub),
            id_jenis_prioritas_data=None, tgl_terima_dip=TERIMA,
        )

        _run('--prioritas-id', str(other_row.pk))

        assert _reload(other_tiket) == other_row.pk
        assert _reload(tiket) is None

    def test_clearing_still_reads_the_whole_table_under_prioritas_id(
        self, admin_account, prioritas, sub_jenis
    ):
        """--prioritas-id narrows what may be written, never what counts as a
        match — otherwise filtering would empty tikets that are still prioritas."""
        tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=prioritas, tgl_terima_dip=TERIMA,
        )
        unrelated = JenisPrioritasDataFactory(tahun='2025')

        _run('--prioritas-id', str(unrelated.pk))

        assert _reload(tiket) == prioritas.pk

    def test_tiket_limits_the_run_to_the_named_tiket(self, admin_account, prioritas, sub_jenis):
        periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis)
        wanted = TiketFactory(
            nomor_tiket='KM03301012503001', id_periode_data=periode,
            id_jenis_prioritas_data=None, tgl_terima_dip=TERIMA,
        )
        untouched = TiketFactory(
            nomor_tiket='KM03301012503002', id_periode_data=periode,
            id_jenis_prioritas_data=None, tgl_terima_dip=TERIMA,
        )

        _run('--tiket', 'KM03301012503001')

        assert _reload(wanted) == prioritas.pk
        assert _reload(untouched) is None

    def test_status_limits_the_run(self, admin_account, prioritas, sub_jenis):
        periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis)
        selesai = TiketFactory(
            id_periode_data=periode, id_jenis_prioritas_data=None,
            status_tiket=STATUS_SELESAI, tgl_terima_dip=TERIMA,
        )
        direkam = TiketFactory(
            id_periode_data=periode, id_jenis_prioritas_data=None,
            status_tiket=STATUS_DIREKAM, tgl_terima_dip=TERIMA,
        )

        _run('--status', str(STATUS_DIREKAM))

        assert _reload(direkam) == prioritas.pk
        assert _reload(selesai) is None

    def test_skip_old_db_leaves_migrated_tikets_alone(self, admin_account, prioritas, sub_jenis):
        migrated = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=None, old_db=True, tgl_terima_dip=TERIMA,
        )
        _run('--skip-old-db')
        assert _reload(migrated) is None


@pytest.mark.django_db
class TestJournalAndUndo:

    def test_a_journalled_run_can_be_reversed_exactly(
        self, admin_account, prioritas, tiket, tmp_path
    ):
        journal = tmp_path / 'prioritas.jsonl'
        _run('--journal', str(journal))
        assert _reload(tiket) == prioritas.pk

        _run('--undo', str(journal))

        assert _reload(tiket) is None
        assert not TiketAction.objects.filter(
            id_tiket=tiket, catatan__endswith=MARKER
        ).exists()

    def test_the_journal_records_both_ends_of_every_change(
        self, admin_account, prioritas, tiket, tmp_path
    ):
        journal = tmp_path / 'prioritas.jsonl'
        _run('--journal', str(journal))

        lines = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
        assert lines[0]['_meta']['fill_only'] is False
        assert lines[1] == {
            'tiket_id': tiket.pk,
            'nomor_tiket': tiket.nomor_tiket,
            'from': None,
            'to': prioritas.pk,
        }

    def test_undo_skips_a_tiket_that_changed_again_afterwards(
        self, admin_account, prioritas, tiket, tmp_path
    ):
        journal = tmp_path / 'prioritas.jsonl'
        _run('--journal', str(journal))

        later = JenisPrioritasDataFactory(tahun='2031')
        Tiket.objects.filter(pk=tiket.pk).update(id_jenis_prioritas_data=later)

        output = _run('--undo', str(journal))

        assert _reload(tiket) == later.pk
        assert 'sudah berubah lagi' in output

    def test_undo_leaves_an_unrelated_audit_row_alone(
        self, admin_account, prioritas, tiket, tmp_path
    ):
        hand_written = TiketAction.objects.create(
            id_tiket=tiket, id_user=admin_account, timestamp=datetime(2025, 4, 1),
            action=TiketActionType.DIUBAH, catatan='isian tiket diubah — Periode: 1 → 2',
        )
        journal = tmp_path / 'prioritas.jsonl'
        _run('--journal', str(journal))
        _run('--undo', str(journal))

        assert TiketAction.objects.filter(pk=hand_written.pk).exists()


@pytest.mark.django_db
def test_an_empty_prioritas_table_is_reported_not_acted_on(admin_account, tiket):
    JenisPrioritasData.objects.all().delete()
    output = _run()
    assert 'kosong' in output
    assert _reload(tiket) is None


@pytest.mark.django_db(transaction=True)
class TestDanglingLink:
    """A FK pointing at a prioritas row that no longer exists.

    The database will not normally allow this: the FK is ``on_delete=PROTECT``
    (so deleting a referenced row is refused, never cascaded to NULL) and the
    constraint is enforced at the database level too. It can only arise from
    something that bypasses both — raw SQL, or a restore taken with constraints
    off. These tests need ``transaction=True`` for exactly that reason: the
    pragma that turns FK checking off cannot take effect inside a transaction.
    """

    def _dangle(self, tiket, missing_pk=999999):
        """Point the tiket at a prioritas row that does not exist."""
        with connection.constraint_checks_disabled():
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE tiket SET id_jenis_prioritas_data = %s WHERE id = %s',
                    [missing_pk, tiket.pk],
                )
        assert _reload(tiket) == missing_pk
        return missing_pk

    def test_a_dangling_link_is_cleared_when_nothing_matches(
        self, admin_account, prioritas, sub_jenis
    ):
        outside = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=None, tgl_terima_dip=datetime(2026, 1, 5),
        )
        missing_pk = self._dangle(outside)

        _run()

        assert _reload(outside) is None
        catatan = TiketAction.objects.get(id_tiket=outside).catatan
        assert f'#{missing_pk}' in catatan  # traceable in the audit trail

    def test_a_dangling_link_is_repointed_when_a_row_does_match(
        self, admin_account, prioritas, sub_jenis
    ):
        inside = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=None, tgl_terima_dip=TERIMA,
        )
        self._dangle(inside)

        _run()

        assert _reload(inside) == prioritas.pk

    def test_fill_only_leaves_a_dangling_link_in_place(
        self, admin_account, prioritas, sub_jenis
    ):
        """--fill-only only ever touches empty columns, so it cannot repair one."""
        outside = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=None, tgl_terima_dip=datetime(2026, 1, 5),
        )
        missing_pk = self._dangle(outside)

        _run('--fill-only')

        assert _reload(outside) == missing_pk
