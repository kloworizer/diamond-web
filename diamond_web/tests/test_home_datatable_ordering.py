"""Tests for the column ordering of the Tugas Saya datatables (home_data).

DataTables sends the sorted column as a positional index, so the server-side
column lists in views/home.py must line up index for index with the column
definitions the template hands each table. When 'Periode Data' was added to the
tables without being added to the server lists, every column after 'Jenis Data'
shifted by one and the baris counters silently sorted by nomor_tiket instead.

Two layers of cover:
  - the numeric columns really do sort ascending/descending, end to end;
  - the template's column definitions still match the server's lists, so the
    next column inserted mid-table cannot re-introduce the same shift.
"""
import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from diamond_web.models import TiketPIC
from diamond_web.models.tiket import Tiket
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory
from diamond_web.views.home import (
    _TIKET_ORDER_COLUMNS,
    _TIKET_ORDER_COLUMNS_DEFAULT,
)


def _params(category, **extra):
    params = {'draw': '1', 'start': '0', 'length': '50', 'category': category}
    params.update(extra)
    return params


def _rows(client, category, col, direction):
    resp = client.get(
        reverse('home_data'),
        _params(category, **{'order[0][column]': str(col), 'order[0][dir]': direction}),
    )
    assert resp.status_code == 200
    return json.loads(resp.content)['data']


# ---------------------------------------------------------------------------
# End-to-end ordering
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBarisColumnOrdering:
    """'Belum Diteliti' is the simplest table carrying a baris counter."""

    def _tiket(self, user, baris_diterima):
        tiket = TiketFactory(
            status_tiket=1, backup=True, tanda_terima=True,
            baris_diterima=baris_diterima,
        )
        TiketPICFactory(id_tiket=tiket, id_user=user,
                        role=TiketPIC.Role.P3DE, active=True)
        return tiket

    def _bundle(self, user):
        # Deliberately created out of order, so a sort that silently falls back
        # to nomor_tiket or id cannot pass by accident.
        self._tiket(user, 50)
        self._tiket(user, 900)
        self._tiket(user, 10)

    def test_baris_diterima_sorts_ascending(self, client, authenticated_user):
        self._bundle(authenticated_user)
        client.force_login(authenticated_user)

        # Index 4: Nomor Tiket, Nama ILAP, Jenis Data, Periode Data, Jml Baris.
        rows = _rows(client, 'belum_diteliti', 4, 'asc')
        assert [r['baris_diterima'] for r in rows] == [10, 50, 900]

    def test_baris_diterima_sorts_descending(self, client, authenticated_user):
        self._bundle(authenticated_user)
        client.force_login(authenticated_user)

        rows = _rows(client, 'belum_diteliti', 4, 'desc')
        assert [r['baris_diterima'] for r in rows] == [900, 50, 10]

    def test_null_counters_sort_as_zero(self, client, pide_user):
        """baris_lengkap is nullable but renders as 0, so it must sort as 0.

        Ordering by the raw column would strand the NULL rows at whichever end
        the backend puts NULLs, which is the opposite end on PostgreSQL and
        SQLite. 'Belum Mulai Proses Identifikasi' is the table that shows the
        column without filtering it to non-zero values.
        """
        for baris_lengkap in (None, 7, 0):
            tiket = TiketFactory(status_tiket=4, baris_lengkap=baris_lengkap)
            TiketPICFactory(id_tiket=tiket, id_user=pide_user,
                            role=TiketPIC.Role.PIDE, active=True)
        client.force_login(pide_user)

        # Index 4: Nomor Tiket, Nama ILAP, Jenis Data, Periode Data, Lengkap.
        rows = _rows(client, 'belum_mulai_proses_identifikasi', 4, 'desc')
        values = [r['baris_lengkap'] for r in rows]
        assert values == [7, 0, 0]

    def test_periode_data_sorts_by_year_then_period(self, client, authenticated_user):
        """The column displays 'Triwulan II 2026', so it sorts by the numbers."""
        for periode, tahun in ((11, 2024), (2, 2026), (7, 2024)):
            tiket = TiketFactory(status_tiket=1, backup=True, tanda_terima=True,
                                 periode=periode, tahun=tahun)
            TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                            role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)

        rows = _rows(client, 'belum_diteliti', 3, 'asc')
        # The response carries only the formatted string, so read the numbers
        # back for the tikets in the order the endpoint returned them.
        ordered = [
            Tiket.objects.values_list('tahun', 'periode').get(nomor_tiket=r['nomor_tiket'])
            for r in rows
        ]
        assert ordered == [(2024, 7), (2024, 11), (2026, 2)]


# ---------------------------------------------------------------------------
# Template <-> view alignment
# ---------------------------------------------------------------------------

_HOME_HTML = Path(settings.BASE_DIR) / 'diamond_web' / 'templates' / 'home.html'

# Columns the template marks orderable:false and always appends last; the
# server lists stop before them.
_NON_ORDERABLE = {'actions', 'is_prioritas'}


def _template_column_sets():
    """{const name: [data keys]} for every `const xxxColumns = [...]` block."""
    source = _HOME_HTML.read_text(encoding='utf-8')
    sets = {}
    for match in re.finditer(r'const (\w+Columns) = \[', source):
        start = match.end() - 1
        depth, end = 0, start
        for i in range(start, len(source)):
            if source[i] == '[':
                depth += 1
            elif source[i] == ']':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        body = source[start:end]
        keys = re.findall(r"data: '([^']+)'", body)
        sets[match.group(1)] = [k for k in keys if k not in _NON_ORDERABLE]
    return sets


def _template_category_map():
    """{category: const name} as getColumnsForCategory() dispatches it."""
    source = _HOME_HTML.read_text(encoding='utf-8')
    mapping = {}
    pattern = re.compile(
        r"if \((?P<cond>category === '[^']+'(?: \|\| category === '[^']+')*)\)"
        r"\s*\{\s*(?:let|const) cols = (?P<name>\w+Columns)"
    )
    for match in pattern.finditer(source):
        categories = re.findall(r"category === '([^']+)'", match.group('cond'))
        for category in categories:
            mapping[category] = match.group('name')
    return mapping


class TestTemplateAlignment:
    """The parsers are asserted on first, so a template rewrite fails loudly
    rather than passing an empty comparison."""

    def test_parsers_find_the_definitions(self):
        assert len(_template_column_sets()) >= 10
        assert len(_template_category_map()) >= 10

    @pytest.mark.parametrize('category, expected', sorted(_TIKET_ORDER_COLUMNS.items()))
    def test_server_columns_match_the_table(self, category, expected):
        name = _template_category_map().get(category)
        assert name is not None, f'{category} has no column set in home.html'
        template_keys = _template_column_sets()[name]

        # The two sides name the date column differently: the table reads it
        # from the 'tanggal' key the view fills per category, while the view
        # orders by the underlying field.
        server_keys = [
            'tanggal' if key.startswith('tgl_') and key != 'tgl_special_request' else key
            for key in expected
        ]
        assert server_keys == template_keys

    def test_default_columns_match_the_fallback_table(self):
        template_keys = _template_column_sets()['tiketCategoryColumns']
        server_keys = [
            'tanggal' if key.startswith('tgl_') else key
            for key in _TIKET_ORDER_COLUMNS_DEFAULT
        ]
        assert server_keys == template_keys
