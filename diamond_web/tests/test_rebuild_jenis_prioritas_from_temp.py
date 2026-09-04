"""Tests for ``rebuild_jenis_prioritas_from_temp``.

The command wipes ``jenis_prioritas_data`` and rebuilds it from an imported
``temp_prioritas`` table: one record per Sub Jenis Data per year flagged with 1,
spanning 1 January to 31 December of that year.

Four things are worth pinning down: that only a 1 counts as a flag, that a code
appearing twice is OR-ed rather than crashing the unique constraint, that the
PROTECT-ed tiket FKs are released so the delete can happen at all, and that a
dry run touches nothing.
"""
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from diamond_web.models.jenis_prioritas_data import JenisPrioritasData
from diamond_web.models.tiket import Tiket

from .conftest import (
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    PeriodeJenisDataFactory,
    TiketFactory,
)

YEARS = (2024, 2025, 2026)


def _create_temp_table(rows, years=YEARS, table='temp_prioritas'):
    """Build the import table the way the operator's own import would."""
    cols = ', '.join(f'PRIORITAS_{y} INTEGER' for y in years)
    with connection.cursor() as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
        cursor.execute(
            f'CREATE TABLE {table} '
            f'(TABEL_I VARCHAR(32), ID_TABEL_S VARCHAR(16), {cols})'
        )
        for kode, flags in rows:
            values = [flags.get(y) for y in years]
            placeholders = ', '.join(['%s'] * (2 + len(years)))
            cursor.execute(
                f'INSERT INTO {table} VALUES ({placeholders})',
                [f'TBL_{kode}', kode] + values,
            )


def _run(*args):
    out = StringIO()
    call_command(
        'rebuild_jenis_prioritas_from_temp', *args,
        '--noinput', stdout=out, stderr=StringIO(),
    )
    return out.getvalue()


def _rows_for(kode):
    return sorted(
        JenisPrioritasData.objects
        .filter(id_sub_jenis_data_ilap__id_sub_jenis_data=kode)
        .values_list('tahun', 'start_date', 'end_date')
    )


@pytest.fixture
def sub_jenis(db):
    return JenisDataILAPFactory(id_sub_jenis_data='KM0330101')


@pytest.mark.django_db
class TestGeneration:

    def test_a_flagged_year_becomes_a_full_calendar_year_record(self, sub_jenis):
        _create_temp_table([('KM0330101', {2025: 1})])

        _run()

        assert _rows_for('KM0330101') == [
            ('2025', date(2025, 1, 1), date(2025, 12, 31)),
        ]

    def test_only_a_one_counts_as_flagged(self, sub_jenis):
        _create_temp_table([('KM0330101', {2024: 0, 2025: 1, 2026: None})])

        _run()

        assert [t for t, _, _ in _rows_for('KM0330101')] == ['2025']

    def test_each_flagged_year_gets_its_own_record(self, sub_jenis):
        _create_temp_table([('KM0330101', {2024: 1, 2025: 1, 2026: 1})])

        _run()

        assert [t for t, _, _ in _rows_for('KM0330101')] == ['2024', '2025', '2026']

    def test_a_code_listed_twice_is_or_ed_together(self, sub_jenis):
        """Two physical tables for one sub jenis data. The unique constraint
        allows a single record per (sub jenis data, tahun), so the flags must
        merge rather than collide."""
        _create_temp_table([
            ('KM0330101', {2024: 0, 2025: 1, 2026: 0}),
            ('KM0330101', {2024: 1, 2025: 1, 2026: 0}),
        ])

        output = _run()

        assert [t for t, _, _ in _rows_for('KM0330101')] == ['2024', '2025']
        assert 'digabung (OR)' in output

    def test_an_unknown_code_is_skipped_and_reported(self, sub_jenis):
        _create_temp_table([
            ('KM0330101', {2025: 1}),
            ('TIDAKADA9', {2025: 1}),
        ])

        output = _run()

        assert JenisPrioritasData.objects.count() == 1
        assert 'tidak ada di jenis_data_ilap' in output
        assert 'TIDAKADA9' in output

    def test_the_year_columns_are_discovered_not_hardcoded(self, sub_jenis):
        _create_temp_table([('KM0330101', {2031: 1})], years=(2030, 2031))

        output = _run()

        assert '2030, 2031' in output
        assert [t for t, _, _ in _rows_for('KM0330101')] == ['2031']

    def test_no_nd_is_configurable(self, sub_jenis):
        _create_temp_table([('KM0330101', {2025: 1})])

        _run('--no-nd', 'ND-99/2025')

        assert JenisPrioritasData.objects.get().no_nd == 'ND-99/2025'


@pytest.mark.django_db
class TestWipeAndProtect:

    def test_existing_records_are_replaced(self, sub_jenis):
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=JenisDataILAPFactory(), tahun='2019',
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        _create_temp_table([('KM0330101', {2025: 1})])

        _run()

        assert JenisPrioritasData.objects.count() == 1
        assert JenisPrioritasData.objects.get().tahun == '2025'

    def test_a_protected_tiket_link_is_released_first(self, sub_jenis):
        """Tiket points at a prioritas row with on_delete=PROTECT, so the wipe is
        impossible until the FK is cleared. The command does that itself."""
        lama = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_jenis, tahun='2019',
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        tiket = TiketFactory(
            id_periode_data=PeriodeJenisDataFactory(id_sub_jenis_data_ilap=sub_jenis),
            id_jenis_prioritas_data=lama,
        )
        _create_temp_table([('KM0330101', {2025: 1})])

        output = _run()

        tiket.refresh_from_db()
        assert tiket.id_jenis_prioritas_data is None
        assert not JenisPrioritasData.objects.filter(pk=lama.pk).exists()
        assert 'backfill_tiket_jenis_prioritas' in output  # tells you the next step

    def test_dump_existing_writes_the_old_table_first(self, sub_jenis, tmp_path):
        JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_jenis, tahun='2019',
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
            no_nd='ND-LAMA',
        )
        _create_temp_table([('KM0330101', {2025: 1})])
        dump = tmp_path / 'lama.json'

        _run('--dump-existing', str(dump))

        import json
        saved = json.loads(dump.read_text(encoding='utf-8'))
        assert len(saved) == 1
        assert saved[0]['no_nd'] == 'ND-LAMA'
        assert saved[0]['start_date'] == '2019-01-01'


@pytest.mark.django_db
class TestSafety:

    def test_dry_run_changes_nothing(self, sub_jenis):
        lama = JenisPrioritasDataFactory(
            id_sub_jenis_data_ilap=sub_jenis, tahun='2019',
            start_date=date(2019, 1, 1), end_date=date(2019, 12, 31),
        )
        _create_temp_table([('KM0330101', {2025: 1})])

        output = _run('--dry-run')

        assert JenisPrioritasData.objects.filter(pk=lama.pk).exists()
        assert JenisPrioritasData.objects.count() == 1
        assert 'Dry run' in output

    def test_a_missing_import_table_is_refused(self, sub_jenis):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS temp_prioritas')

        with pytest.raises(CommandError, match='tidak ada di database'):
            _run()

    def test_a_table_without_year_columns_is_refused(self, sub_jenis):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS temp_prioritas')
            cursor.execute('CREATE TABLE temp_prioritas (TABEL_I VARCHAR(32), ID_TABEL_S VARCHAR(16))')

        with pytest.raises(CommandError, match='PRIORITAS_'):
            _run()

    def test_an_import_with_nothing_flagged_is_refused(self, sub_jenis):
        """Wiping the table and putting nothing back is never the intent — most
        likely the import went wrong."""
        JenisPrioritasDataFactory(id_sub_jenis_data_ilap=sub_jenis, tahun='2019')
        _create_temp_table([('KM0330101', {2024: 0, 2025: 0, 2026: 0})])

        with pytest.raises(CommandError, match='Tidak ada satu pun baris bertanda'):
            _run()

        assert JenisPrioritasData.objects.count() == 1

    def test_an_injectable_table_name_is_refused(self, sub_jenis):
        with pytest.raises(CommandError, match='Nama tabel tidak valid'):
            _run('--table', 'temp; DROP TABLE tiket')
