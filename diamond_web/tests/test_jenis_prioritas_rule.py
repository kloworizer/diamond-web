"""Tests for the single Data Prioritas rule.

A tiket is prioritas when a JenisPrioritasData row for its Sub Jenis Data was in
force on the day the tiket was received — ``start_date <= tgl_terima_dip <=
end_date``, an empty end_date meaning still in force. The record's ``tahun``
field plays no part: it is the year the priority was decreed, while
``Tiket.tahun`` is the year of the data itself, and the two routinely differ.

These tests hold the four shapes of that rule to the same answers, so the rekam
form, the sync, the seksi queues and the backfill command cannot drift apart
again.
"""
from datetime import date, datetime

import pytest
from django.db.models import DateField, Exists, OuterRef
from django.db.models.functions import Cast

from diamond_web.models.jenis_prioritas_data import JenisPrioritasData
from diamond_web.models.tiket import Tiket
from diamond_web.utils.jenis_prioritas import (
    PrioritasIndex,
    as_tanggal,
    is_prioritas_pada,
    prioritas_window_q,
    resolve_jenis_prioritas,
)
from diamond_web.views import seksi_queue as sq

from .conftest import (
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
)

INSIDE = datetime(2025, 6, 15, 9, 30)
BEFORE = datetime(2024, 12, 31, 23, 59)
AFTER = datetime(2026, 1, 1, 0, 0)


@pytest.fixture
def sub_jenis(db):
    return JenisDataILAPFactory(id_sub_jenis_data='KM0330101')


@pytest.fixture
def closed_row(sub_jenis):
    """A row with both ends set, decreed under a year unrelated to any tiket."""
    return JenisPrioritasDataFactory(
        id_sub_jenis_data_ilap=sub_jenis, tahun='2099',
        start_date=date(2025, 1, 1), end_date=date(2025, 12, 31),
    )


@pytest.fixture
def open_row(sub_jenis):
    return JenisPrioritasDataFactory(
        id_sub_jenis_data_ilap=sub_jenis, tahun='2098',
        start_date=date(2025, 1, 1), end_date=None,
    )


def _tiket(sub_jenis, tgl_terima_dip, tahun=2024):
    return TiketFactory(
        id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
        id_jenis_prioritas_data=None, tahun=tahun, tgl_terima_dip=tgl_terima_dip,
    )


def _queue_says_prioritas(tiket):
    """The seksi-queue answer for one tiket, via the Exists() subquery."""
    return (
        Tiket.objects.filter(pk=tiket.pk)
        .annotate(is_prioritas=sq.prioritas_exists())
        .values_list('is_prioritas', flat=True)[0]
    )


def _q_says_prioritas(sub_jenis, tanggal):
    """The Q() form, used directly against the prioritas table."""
    return JenisPrioritasData.objects.filter(
        prioritas_window_q(as_tanggal(tanggal)), id_sub_jenis_data_ilap=sub_jenis,
    ).exists()


@pytest.mark.django_db
class TestTheRule:

    def test_a_date_inside_the_window_is_prioritas(self, sub_jenis, closed_row):
        assert resolve_jenis_prioritas(sub_jenis, INSIDE) == closed_row

    def test_a_date_before_the_window_is_not(self, sub_jenis, closed_row):
        assert resolve_jenis_prioritas(sub_jenis, BEFORE) is None

    def test_a_date_after_the_window_is_not(self, sub_jenis, closed_row):
        assert resolve_jenis_prioritas(sub_jenis, AFTER) is None

    def test_both_edges_count_as_inside(self, sub_jenis, closed_row):
        assert resolve_jenis_prioritas(sub_jenis, datetime(2025, 1, 1, 0, 0)) == closed_row
        assert resolve_jenis_prioritas(sub_jenis, datetime(2025, 12, 31, 23, 59)) == closed_row

    def test_an_empty_end_date_stays_in_force(self, sub_jenis, open_row):
        assert resolve_jenis_prioritas(sub_jenis, datetime(2099, 6, 1)) == open_row

    def test_the_record_tahun_does_not_decide(self, sub_jenis, closed_row):
        """closed_row is decreed for 2099 yet still covers a 2025 receipt."""
        assert closed_row.tahun == '2099'
        assert resolve_jenis_prioritas(sub_jenis, INSIDE) == closed_row

    def test_a_tiket_without_a_receipt_date_is_not_prioritas(self, sub_jenis, closed_row):
        assert resolve_jenis_prioritas(sub_jenis, None) is None

    def test_another_sub_jenis_data_never_matches(self, closed_row, db):
        assert resolve_jenis_prioritas(JenisDataILAPFactory(), INSIDE) is None


@pytest.mark.django_db
class TestEveryFormOfTheRuleAgrees:
    """The four shapes must answer identically, or the menus disagree again."""

    @pytest.mark.parametrize('tanggal,expected', [
        (BEFORE, False),
        (INSIDE, True),
        (AFTER, False),
    ])
    def test_closed_window(self, sub_jenis, closed_row, tanggal, expected):
        tiket = _tiket(sub_jenis, tanggal)
        windows = [(closed_row.start_date, closed_row.end_date)]

        assert (resolve_jenis_prioritas(sub_jenis, tanggal) is not None) is expected
        assert PrioritasIndex().match_pk(sub_jenis.pk, tanggal) == (
            closed_row.pk if expected else None
        )
        assert is_prioritas_pada(windows, tanggal) is expected
        assert _q_says_prioritas(sub_jenis, tanggal) is expected
        assert _queue_says_prioritas(tiket) is expected

    def test_open_window_is_in_force_everywhere(self, sub_jenis, open_row):
        """The seksi queues used to miss this case entirely: their end_date__gte
        can never be satisfied by a NULL, so an open-ended row was invisible."""
        tanggal = datetime(2099, 6, 1)
        tiket = _tiket(sub_jenis, tanggal)

        assert resolve_jenis_prioritas(sub_jenis, tanggal) == open_row
        assert PrioritasIndex().match_pk(sub_jenis.pk, tanggal) == open_row.pk
        assert is_prioritas_pada([(open_row.start_date, open_row.end_date)], tanggal) is True
        assert _q_says_prioritas(sub_jenis, tanggal) is True
        assert _queue_says_prioritas(tiket) is True


@pytest.mark.django_db
class TestPrioritasIndex:

    def test_reads_the_table_once_and_matches_in_memory(self, sub_jenis, closed_row):
        index = PrioritasIndex()
        assert len(index) == JenisPrioritasData.objects.count()
        assert index.match(sub_jenis.pk, INSIDE) == closed_row
        assert index.match(sub_jenis.pk, AFTER) is None

    def test_label_names_the_record(self, sub_jenis, closed_row):
        index = PrioritasIndex()
        assert index.label(closed_row.pk) == str(closed_row)
        assert index.label(None) == '-'

    def test_subs_with_finds_the_owners(self, sub_jenis, closed_row):
        index = PrioritasIndex()
        assert index.subs_with([closed_row.pk]) == {sub_jenis.pk}
        assert index.subs_with([]) == set()


class TestAsTanggal:

    def test_strips_the_time_from_a_datetime(self):
        assert as_tanggal(datetime(2025, 6, 15, 23, 59)) == date(2025, 6, 15)

    def test_passes_a_date_through(self):
        assert as_tanggal(date(2025, 6, 15)) == date(2025, 6, 15)

    def test_anything_else_is_none(self):
        assert as_tanggal(None) is None
        assert as_tanggal('2025-06-15') is None
