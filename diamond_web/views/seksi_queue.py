"""Shared machinery behind the per-seksi queue pages.

Quality Control (PMDE) and Identifikasi (PIDE) are one page read by two seksi: a
filter panel over the queue that seksi is working through, three summary
sections above a chart of the work still left per jatuh tempo, and the queue
itself as a table. What differs between them is only which queue is theirs,
which PIC leads it, and which pair of dates their deadline counts from, so that
much is gathered into a :class:`Deadline` and the rest lives here once.

The filtering works the same way the tiket list page's does: a panel of Select2
multi-selects, each of which narrows both the table and the remaining dropdowns.
The tiket status filter is absent — every row in a queue shares its status by
definition — while a Prioritas Ya/Tidak filter and a Jatuh Tempo threshold are
added, since both are columns of these tables.
"""

from collections import defaultdict
from datetime import date

from django.contrib.auth.models import User
from django.db import connection as db_connection
from django.db.models import (
    DateField, Exists, IntegerField, OuterRef, Q, Subquery, Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from django.utils.html import escape

from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.jenis_tabel import JenisTabel
from ..models.kategori_wilayah import KategoriWilayah
from ..models.status_penelitian import StatusPenelitian
from ..models.tiket_pic import TiketPIC
from ..utils.pic_profil import pic_display_name, pic_profil_link
from ..utils.wilayah import kanwil_value_paths, tiket_in_kanwil_q


# Query path from Tiket to the JenisDataILAP row that carries most of the
# descriptive fields the filters key off.
SUB = 'id_periode_data__id_sub_jenis_data_ilap'
ILAP = f'{SUB}__id_ilap'
PENGIRIMAN = 'id_periode_data__id_periode_pengiriman'

_PERIODE_TYPE_LABELS = {
    'bulanan': 'Bulanan',
    'triwulanan': 'Triwulanan',
    'semester': 'Semester',
    'tahunan': 'Tahunan',
}

_BULAN_NAMES = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
]

# The thresholds the Jatuh Tempo dropdown offers, in days. They nest by
# construction — every tiket under 10 days is also under 30 — so selecting
# several of them is the union, which is simply the widest one.
JATUH_TEMPO_LIMITS = (10, 30, 60)


def prioritas_exists():
    """Exists() matching tikets whose data was prioritas when it was received."""
    return Exists(
        JenisPrioritasData.objects.filter(
            id_sub_jenis_data_ilap=OuterRef(SUB),
            start_date__lte=Cast(OuterRef('tgl_terima_dip'), DateField()),
            end_date__gte=Cast(OuterRef('tgl_terima_dip'), DateField()),
        )
    )


class Deadline:
    """How one seksi counts the deadline of a tiket in its queue.

    A deadline is a base date plus the durasi that the tiket's sub jenis data
    had on that date. Both halves are per-seksi: PMDE counts from the transfer
    that handed it the tiket, PIDE from the day the tiket reached it, and each
    reads the DurasiJatuhTempo rows recorded against its own seksi.

    Either seksi may see its count start again — a rematch hands a tiket back to
    PMDE, and identification proper begins after PIDE has received one — so the
    base date is a pair, the later field winning whenever it is set.

    Args:
        seksi: Name of the auth group the DurasiJatuhTempo rows are keyed by.
        start_field: The date the tiket entered this seksi's queue.
        restart_field: The date the count starts again from, when it is set.
    """

    def __init__(self, seksi, start_field, restart_field):
        self.seksi = seksi
        self.start_field = start_field
        self.restart_field = restart_field

    # -- As query expressions -------------------------------------------------

    def base_date_expr(self):
        """The date the deadline counts from, as a correlated expression.

        Each side is cast separately so Coalesce resolves to a DateField despite
        the OuterRefs.
        """
        return Coalesce(
            Cast(OuterRef(self.restart_field), DateField()),
            Cast(OuterRef(self.start_field), DateField()),
        )

    @property
    def base_sql(self):
        """The same base date in raw SQL, for the deadline_date annotation."""
        return f'COALESCE("tiket"."{self.restart_field}", "tiket"."{self.start_field}")'

    def durasi_subquery(self):
        """Subquery yielding the DurasiJatuhTempo active at the base date.

        A tiket's deadline is its base date plus the durasi that applied on that
        date, so the row is picked by that date rather than by today.
        """
        base_date = self.base_date_expr()
        return DurasiJatuhTempo.objects.filter(
            id_sub_jenis_data=OuterRef(SUB),
            seksi__name=self.seksi,
            start_date__lte=base_date,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=base_date)
        ).order_by('-start_date').values('durasi')[:1]

    def annotate_durasi(self, qs):
        """Annotate `active_durasi`, 0 standing for "no durasi covers this"."""
        return qs.annotate(
            active_durasi=Coalesce(
                Subquery(self.durasi_subquery(), output_field=IntegerField()),
                Value(0),
            ),
        )

    def deadline_date_expr(self):
        """The deadline itself as a sortable date column.

        Correlated subquery embedded in RawSQL (no params) to avoid
        parameter-binding issues with nested expressions.
        SQLite (dev): DATE(date, '+' || days || ' days')
        PostgreSQL (prod): (date::date + days * INTERVAL '1 day')::date
        """
        base = self.base_sql
        durasi_sql = f"""
            (SELECT "durasi_jatuh_tempo"."durasi"
             FROM "durasi_jatuh_tempo"
             INNER JOIN "auth_group" ON ("durasi_jatuh_tempo"."seksi" = "auth_group"."id")
             WHERE ("durasi_jatuh_tempo"."id_sub_jenis_data" = "periode_jenis_data"."id_sub_jenis_data_ilap"
               AND "auth_group"."name" = '{self.seksi}'
               AND "durasi_jatuh_tempo"."start_date" <= {{base_date}}
               AND ("durasi_jatuh_tempo"."end_date" IS NULL
                    OR "durasi_jatuh_tempo"."end_date" >= {{base_date}}))
             ORDER BY "durasi_jatuh_tempo"."start_date" DESC LIMIT 1)
        """
        if db_connection.vendor == 'sqlite':
            sql = (
                f"DATE({base}, '+' || CAST(COALESCE("
                + durasi_sql.format(base_date=f'DATE({base})')
                + ", 0) AS TEXT) || ' days')"
            )
        else:
            sql = (
                f"({base}::date + COALESCE("
                + durasi_sql.format(base_date=f'{base}::date')
                + ", 0) * INTERVAL '1 day')::date"
            )
        return RawSQL(sql, [], output_field=DateField())

    # -- In Python ------------------------------------------------------------

    def day(self, start_value, restart_value, durasi):
        """The deadline date, or None when there is no deadline to count.

        Counting starts from the restart date when the tiket has one and from
        the start date otherwise. A durasi of 0 means no active DurasiJatuhTempo
        covers that date, so there is nothing to count from — the '-' the table
        shows in its Deadline and Jatuh Tempo columns, not a deadline of "today".
        """
        base_date = restart_value or start_value
        if not base_date or not durasi:
            return None
        deadline = base_date + timezone.timedelta(days=durasi)
        return deadline.date() if hasattr(deadline, 'date') else deadline

    def day_of(self, tiket):
        """The deadline date of an annotated tiket row."""
        return self.day(
            getattr(tiket, self.start_field),
            getattr(tiket, self.restart_field),
            tiket.active_durasi,
        )

    def cells(self, tiket):
        """The Deadline and Jatuh Tempo cells of one table row.

        `sisa_hari` comes along raw as well, since the frontend colours the row
        by it rather than by re-parsing the text.
        """
        deadline_day = self.day_of(tiket)
        if deadline_day is None:
            return {
                'deadline': {'display': '-', 'sort': ''},
                'jatuh_tempo': {'display': '-', 'sort': ''},
                'sisa_hari': None,
            }
        sisa_hari = (deadline_day - date.today()).days
        return {
            'deadline': {
                'display': deadline_day.strftime('%d/%m/%Y'),
                'sort': deadline_day.strftime('%Y-%m-%d'),
            },
            'jatuh_tempo': {'display': f'{sisa_hari} hari', 'sort': str(sisa_hari)},
            'sisa_hari': sisa_hari,
        }

    def jatuh_tempo_ids(self, qs, limit):
        """Ids of the tikets in `qs` whose jatuh tempo is under `limit` days.

        Jatuh tempo is not a column: it is the deadline — the tiket's base date
        plus the durasi that was active then — counted from today, so the
        comparison is made here over the same computation the table renders and
        the chart plots, rather than reassembled in SQL a third time.
        """
        rows = self.annotate_durasi(qs).values_list(
            'id', self.start_field, self.restart_field, 'active_durasi',
        )

        today = date.today()
        ids = []
        for tiket_id, start_value, restart_value, durasi in rows:
            deadline_day = self.day(start_value, restart_value, durasi)
            if deadline_day is None:
                continue
            if (deadline_day - today).days < limit:
                ids.append(tiket_id)
        return ids


# ---------------------------------------------------------------------------
# Filter panel
# ---------------------------------------------------------------------------

def split(value):
    """Split a comma-separated multi-select value into clean parts."""
    if not value:
        return []
    return [part.strip() for part in value.split(',') if part.strip()]


def _in(path):
    """Build an applier filtering `path` against the selected values."""
    def apply(qs, values):
        return qs.filter(**{f'{path}__in': values})
    return apply


def _int_in(path):
    """Like `_in`, but for integer columns — non-numeric input matches nothing."""
    def apply(qs, values):
        ints = []
        for value in values:
            try:
                ints.append(int(value))
            except ValueError:
                pass
        return qs.filter(**{f'{path}__in': ints}) if ints else qs.none()
    return apply


def _bool_in(path):
    """Applier for the Ya/Tidak dropdowns, whose values are '1' and '0'."""
    def apply(qs, values):
        return qs.filter(**{f'{path}__in': [value == '1' for value in values]})
    return apply


def _pic_in(role):
    """Applier matching tikets whose active PIC for `role` is one of the users."""
    def apply(qs, values):
        return qs.filter(
            tiketpic__role=role, tiketpic__active=True,
            tiketpic__id_user_id__in=values,
        )
    return apply


def _filter_periode(qs, values):
    """Applier for the `<type>:<number>` periode values (e.g. `bulanan:3`).

    The number alone is ambiguous — periode 3 is March for a monthly ILAP but
    the third quarter for a quarterly one — so the type half also constrains
    periode_penerimaan.
    """
    combined = Q()
    for value in values:
        periode_type, _, periode_value = value.partition(':') if ':' in value else ('', '', value)
        try:
            selector = Q(periode=int(periode_value))
        except ValueError:
            continue
        label = _PERIODE_TYPE_LABELS.get(periode_type)
        if label:
            selector &= Q(**{f'{PENGIRIMAN}__periode_penerimaan': label})
        combined |= selector
    return qs.filter(combined) if combined else qs


def _filter_prioritas(qs, values):
    """Applier for the Prioritas Ya/Tidak dropdown.

    Selecting both is the same as selecting neither, so it falls through
    without adding a clause.
    """
    wanted = {value == '1' for value in values}
    if len(wanted) != 1:
        return qs
    return qs.filter(prioritas_exists()) if wanted.pop() else qs.exclude(prioritas_exists())


def _build_filter_jatuh_tempo(deadline):
    """Applier for the Jatuh Tempo dropdown, counting by `deadline`.

    An overdue tiket is under every threshold, its jatuh tempo being negative,
    and a tiket with no deadline is under none of them — the same rows the
    table shows a '-' for.
    """
    def apply(qs, values):
        limits = []
        for value in values:
            try:
                limit = int(value)
            except ValueError:
                continue
            if limit in JATUH_TEMPO_LIMITS:
                limits.append(limit)
        if not limits:
            return qs.none()
        return qs.filter(id__in=deadline.jatuh_tempo_ids(qs, max(limits)))
    return apply


def build_filter_appliers(deadline):
    """Every dropdown on the filter panel, in the order the panel renders them.

    The key is both the request parameter and the `filter_options` key the
    template reads back, so adding a filter means adding one entry here, one
    entry in FILTER_OPTIONS below, and one <select> in the template.

    Only the last one depends on the seksi, jatuh tempo being counted from that
    seksi's own deadline.
    """
    return {
        'nomor_tiket': _in('nomor_tiket'),
        'tahun': _int_in('tahun'),
        'periode': _filter_periode,
        'periode_pengiriman': _in(f'{PENGIRIMAN}__periode_penyampaian'),
        'periode_penerimaan': _in(f'{PENGIRIMAN}__periode_penerimaan'),
        'pic_p3de': _pic_in(TiketPIC.Role.P3DE),
        'pic_pide': _pic_in(TiketPIC.Role.PIDE),
        'pic_pmde': _pic_in(TiketPIC.Role.PMDE),
        'kategori_ilap': _in(f'{ILAP}__id_kategori__id'),
        'ilap': _in(f'{ILAP}__id'),
        'jenis_data': _in(f'{SUB}__id_jenis_data'),
        'sub_jenis_data': _in(f'{SUB}__id_sub_jenis_data'),
        'nama_tabel': _in(f'{SUB}__nama_tabel_I'),
        'kanwil': lambda qs, values: qs.filter(tiket_in_kanwil_q(values)),
        'kpp': _in(f'{ILAP}__ilap_kpp_relations__id_kpp__id'),
        'kategori_wilayah': _in(f'{ILAP}__id_kategori_wilayah__id'),
        'jenis_tabel': _in(f'{SUB}__id_jenis_tabel__id'),
        'dasar_hukum': _in(f'{SUB}__klasifikasijenisdata__id_klasifikasi_tabel__id'),
        'status_penelitian': _in('id_status_penelitian_id'),
        'status_ketersediaan_data': _bool_in('status_ketersediaan_data'),
        'special_request': _bool_in('special_request'),
        'prioritas': _filter_prioritas,
        # Last, because it is the only applier that has to read rows to decide.
        'jatuh_tempo': _build_filter_jatuh_tempo(deadline),
    }


# Filters that reach a tiket through a to-many join, so a tiket can match more
# than once and the result needs de-duplicating. The rest walk plain foreign
# keys, where DISTINCT would only cost a sort.
MULTI_ROW_FILTERS = frozenset({
    'pic_p3de', 'pic_pide', 'pic_pmde', 'kanwil', 'kpp', 'dasar_hukum',
})


def selected_filters(params, appliers):
    """Read every filter parameter, dropping the ones left on '-- Semua --'."""
    selected = {}
    for key in appliers:
        values = split(params.get(key, ''))
        if values:
            selected[key] = values
    return selected


def apply_filters(qs, selected, appliers, exclude=None):
    """Apply the selected filters, optionally skipping one dropdown's own key.

    Skipping is what keeps a dropdown from narrowing itself: a dropdown's
    options are built from everything the *other* dropdowns allow, so the
    values already chosen in it stay selectable.
    """
    applied = set()
    for key, values in selected.items():
        if key == exclude:
            continue
        qs = appliers[key](qs, values)
        applied.add(key)
    return qs.distinct() if applied & MULTI_ROW_FILTERS else qs


# ---------------------------------------------------------------------------
# Options for each dropdown
# ---------------------------------------------------------------------------

def _distinct_options(qs, paths, label=None):
    """Collect `{'id', 'name'}` option dicts from distinct values of `paths`.

    Args:
        qs: Queryset to read from.
        paths: Field paths — the first one is the option id.
        label: Callable receiving every path value and returning the display
            name. Defaults to showing the id itself.
    """
    options = []
    seen = set()
    for row in qs.values_list(*paths).distinct():
        value = row[0]
        if value is None or value == '' or value in seen:
            continue
        seen.add(value)
        options.append({'id': str(value), 'name': label(*row) if label else str(value)})
    return options


def _pic_options(qs, role):
    """PIC options for `role`, drawn from the tikets actually in the result set."""
    rows = qs.filter(
        tiketpic__role=role, tiketpic__active=True,
    ).values_list(
        'tiketpic__id_user__id',
        'tiketpic__id_user__username',
        'tiketpic__id_user__first_name',
        'tiketpic__id_user__last_name',
    ).distinct()

    options = []
    seen = set()
    for user_id, username, first_name, last_name in rows:
        if user_id is None or user_id in seen:
            continue
        seen.add(user_id)
        full_name = f'{first_name or ""} {last_name or ""}'.strip()
        options.append({
            'id': str(user_id),
            'name': f'{username} - {full_name}' if full_name else username,
        })
    options.sort(key=lambda option: option['name'])
    return options


def _periode_options(qs):
    """Periode options, labelled by the periode_penerimaan of their tikets."""
    bulanan, triwulan, semester, tahunan = {}, {}, {}, {}
    rows = qs.values_list('periode', f'{PENGIRIMAN}__periode_penerimaan').distinct()
    for periode, penerimaan in rows:
        if periode is None:
            continue
        penerimaan = (penerimaan or '').strip().lower()
        index = int(periode)
        if 'triwulan' in penerimaan and 1 <= index <= 4:
            triwulan[index] = {'id': f'triwulanan:{index}', 'name': f'Triwulan {index}'}
        elif 'semester' in penerimaan and 1 <= index <= 2:
            semester[index] = {'id': f'semester:{index}', 'name': f'Semester {index}'}
        elif 'tahunan' in penerimaan:
            tahunan[1] = {'id': 'tahunan:1', 'name': 'Tahunan'}
        elif 1 <= index <= 12:
            bulanan[index] = {'id': f'bulanan:{index}', 'name': _BULAN_NAMES[index - 1]}

    options = []
    for group in (bulanan, triwulan, semester, tahunan):
        options.extend(group[index] for index in sorted(group))
    return options


def _kanwil_options(qs):
    """Kanwil options covering both the direct and the via-KPP ILAP mappings."""
    options = []
    seen = set()
    for paths in kanwil_value_paths():
        for kanwil_id, kode, nama in qs.values_list(*paths).distinct():
            if kanwil_id and kanwil_id not in seen:
                seen.add(kanwil_id)
                options.append({'id': str(kanwil_id), 'name': f'{kode} - {nama}'})
    options.sort(key=lambda option: option['name'])
    return options


def _status_penelitian_options(qs):
    """Status penelitian options present in the result set, in model order."""
    ids = {
        value for value in qs.values_list('id_status_penelitian_id', flat=True).distinct()
        if value is not None
    }
    return [
        {'id': str(status.id), 'name': status.deskripsi}
        for status in StatusPenelitian.objects.filter(id__in=ids).order_by('id')
    ]


def _yes_no_options(qs, field):
    """Ya/Tidak options, offering only the values the result set actually has."""
    present = set(qs.values_list(field, flat=True).distinct())
    options = []
    if True in present:
        options.append({'id': '1', 'name': 'Ya'})
    if False in present:
        options.append({'id': '0', 'name': 'Tidak'})
    return options


def _prioritas_options(qs):
    """Ya/Tidak options for prioritas, offering only the values in the result set."""
    options = []
    if qs.filter(prioritas_exists()).exists():
        options.append({'id': '1', 'name': 'Ya'})
    if qs.exclude(prioritas_exists()).exists():
        options.append({'id': '0', 'name': 'Tidak'})
    return options


def _jatuh_tempo_options(_qs):
    """The fixed Jatuh Tempo thresholds.

    Alone among the dropdowns these are not read off the result set: a
    threshold is a question the user asks — "what falls due within 30 days?" —
    and one that currently matches nothing is still worth being able to ask.
    """
    return [{'id': str(limit), 'name': f'< {limit} hari'} for limit in JATUH_TEMPO_LIMITS]


def _kode_nama(_id, kode, nama):
    """Label a lookup row as `<kode> - <nama>`, keeping the id out of the text."""
    return f'{kode} - {nama}'


FILTER_OPTIONS = {
    'nomor_tiket': lambda qs: _distinct_options(qs.order_by('nomor_tiket'), ('nomor_tiket',)),
    'tahun': lambda qs: _distinct_options(qs.order_by('tahun'), ('tahun',)),
    'periode': _periode_options,
    'periode_pengiriman': lambda qs: _distinct_options(
        qs, (f'{PENGIRIMAN}__periode_penyampaian',)),
    'periode_penerimaan': lambda qs: _distinct_options(
        qs, (f'{PENGIRIMAN}__periode_penerimaan',)),
    'pic_p3de': lambda qs: _pic_options(qs, TiketPIC.Role.P3DE),
    'pic_pide': lambda qs: _pic_options(qs, TiketPIC.Role.PIDE),
    'pic_pmde': lambda qs: _pic_options(qs, TiketPIC.Role.PMDE),
    'kategori_ilap': lambda qs: _distinct_options(
        qs,
        (f'{ILAP}__id_kategori__id', f'{ILAP}__id_kategori__id_kategori',
         f'{ILAP}__id_kategori__nama_kategori'),
        _kode_nama,
    ),
    'ilap': lambda qs: _distinct_options(
        qs,
        (f'{ILAP}__id', f'{ILAP}__id_ilap', f'{ILAP}__nama_ilap'),
        _kode_nama,
    ),
    'jenis_data': lambda qs: _distinct_options(
        qs,
        (f'{SUB}__id_jenis_data', f'{SUB}__nama_jenis_data'),
        lambda kode, nama: f'{kode} - {nama}',
    ),
    'sub_jenis_data': lambda qs: _distinct_options(
        qs,
        (f'{SUB}__id_sub_jenis_data', f'{SUB}__nama_sub_jenis_data'),
        lambda kode, nama: f'{kode} - {nama}',
    ),
    # The nama tabel is its own id: it is free text on the sub jenis data row
    # rather than a lookup, so the value filtered on is the name itself.
    'nama_tabel': lambda qs: _distinct_options(
        qs.order_by(f'{SUB}__nama_tabel_I'), (f'{SUB}__nama_tabel_I',)),
    'kanwil': _kanwil_options,
    'kpp': lambda qs: _distinct_options(
        qs,
        (f'{ILAP}__ilap_kpp_relations__id_kpp__id',
         f'{ILAP}__ilap_kpp_relations__id_kpp__kode_kpp',
         f'{ILAP}__ilap_kpp_relations__id_kpp__nama_kpp'),
        _kode_nama,
    ),
    'kategori_wilayah': lambda qs: _distinct_options(
        qs,
        (f'{ILAP}__id_kategori_wilayah__id', f'{ILAP}__id_kategori_wilayah__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'jenis_tabel': lambda qs: _distinct_options(
        qs,
        (f'{SUB}__id_jenis_tabel__id', f'{SUB}__id_jenis_tabel__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'dasar_hukum': lambda qs: _distinct_options(
        qs,
        (f'{SUB}__klasifikasijenisdata__id_klasifikasi_tabel__id',
         f'{SUB}__klasifikasijenisdata__id_klasifikasi_tabel__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'status_penelitian': _status_penelitian_options,
    'status_ketersediaan_data': lambda qs: _yes_no_options(qs, 'status_ketersediaan_data'),
    'special_request': lambda qs: _yes_no_options(qs, 'special_request'),
    'prioritas': _prioritas_options,
    'jatuh_tempo': _jatuh_tempo_options,
}


def filter_options(scoped_qs, selected, appliers):
    """Build the option list for every dropdown, each excluding its own filter."""
    # Jatuh tempo is narrowed away once, up front, instead of once per dropdown:
    # it is the one filter that reads rows to decide, and the filters are
    # conjunctive, so applying it first gives every builder the same result set
    # it would have got anyway. Its own options are the fixed thresholds, so
    # nothing is lost by it not being excluded from its own dropdown.
    selected = dict(selected)
    jatuh_tempo = selected.pop('jatuh_tempo', None)
    if jatuh_tempo:
        scoped_qs = appliers['jatuh_tempo'](scoped_qs, jatuh_tempo)

    return {
        key: builder(apply_filters(scoped_qs, selected, appliers, exclude=key))
        for key, builder in FILTER_OPTIONS.items()
    }


# Filters that only mean anything for a tiket already in the queue the page
# lists, so they are dropped from its upstream sections. Jatuh tempo counts from
# a date an upstream tiket does not have yet, so keeping it would report every
# upstream queue as empty rather than unfiltered.
QUEUE_ONLY_FILTERS = frozenset({'jatuh_tempo'})


def upstream_selected(selected):
    """The selected filters that still mean something upstream of the queue."""
    return {
        key: values for key, values in selected.items() if key not in QUEUE_ONLY_FILTERS
    }


# ---------------------------------------------------------------------------
# Summary sections above the chart
# ---------------------------------------------------------------------------

def baris_data(status_tiket, baris_lengkap, baris_i, baris_u, baris_cde, baris_res):
    """The row count that stands for a tiket's data at its current status.

    Before a tiket reaches PIDE the only count taken is the P3DE one, so baris
    lengkap is the figure. From Dikirim ke PIDE onwards identification has split
    that figure into I/U/CDE/Res and baris I is the part still to be processed —
    except while the split is still all zeros, identification not having recorded
    anything yet, where baris lengkap remains the only count there is.
    """
    if status_tiket in (STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI):
        split_total = (baris_i or 0) + (baris_u or 0) + (baris_cde or 0) + (baris_res or 0)
        if split_total != 0:
            return baris_i or 0
    return baris_lengkap or 0


# The columns `baris_data` reads, in the order it takes them.
BARIS_DATA_FIELDS = (
    'status_tiket', 'baris_lengkap', 'baris_i', 'baris_u', 'baris_cde', 'baris_res',
)


def pic_id_expr(role):
    """The id of a tiket's active PIC for `role`, as a correlated subquery.

    One PIC per role is what the workflow assigns, so the first row is the row;
    a tiket without one yields NULL, which the callers read as "nobody".
    """
    return Subquery(
        TiketPIC.objects.filter(
            id_tiket=OuterRef('pk'), role=role, active=True,
        ).values('id_user_id')[:1],
        output_field=IntegerField(),
    )


def jenis_tabel_kinds():
    """The `(id, deskripsi)` pairs every breakdown lists, in reference order.

    Read once for all of a page's sections, so every one of them reads its rows
    in the same order and the three can be compared straight across.
    """
    return list(JenisTabel.objects.order_by('id').values_list('id', 'deskripsi'))


class Split:
    """One dimension a queue's figures are broken down along.

    A queue answers more than one question about the same tikets — what kind of
    table their data is, what sort of wilayah their ILAP covers — and each is
    the same figures counted a different way. A split names one of those
    questions: where to read a tiket's answer from, and every answer there is,
    so the ones nothing landed in still get a line.

    Args:
        key: The payload key its entries come back under.
        label: What to call the dimension where it is shown.
        path: The field path holding the id of the entry a tiket belongs to.
        entries: `(id, name)` pairs, in the order the lines should read.
    """

    def __init__(self, key, label, path, entries):
        self.key = key
        self.label = label
        self.path = path
        self.entries = entries


def jenis_tabel_split():
    """The split by jenis tabel — what decides how a tiket's data is handled.

    Read fresh for each page's summary, so every section of it reads its lines
    in the same order and they can be compared straight across.
    """
    return Split(
        'jenis_tabel', 'Jenis Tabel', f'{SUB}__id_jenis_tabel__id',
        list(JenisTabel.objects.order_by('id').values_list('id', 'deskripsi')),
    )


def kategori_wilayah_split():
    """The split by the kategori wilayah of the tiket's ILAP.

    The same tikets counted by reach rather than by handling — regional,
    nasional, internasional — which is the other question asked of a load.
    """
    return Split(
        'kategori_wilayah', 'Kategori Wilayah', f'{ILAP}__id_kategori_wilayah__id',
        list(KategoriWilayah.objects.order_by('id').values_list('id', 'deskripsi')),
    )


def prioritas_windows():
    """Every prioritas period, grouped by the sub jenis data it applies to.

    Read once for a whole summary rather than asked per tiket. Whether a tiket
    was prioritas is an EXISTS over a date range, and asking it of every row of
    four queues is thousands of correlated subqueries; the table it would ask is
    a few hundred rows, so the whole of it is carried in memory instead and the
    question answered in Python.
    """
    windows = defaultdict(list)
    rows = JenisPrioritasData.objects.values_list(
        'id_sub_jenis_data_ilap', 'start_date', 'end_date',
    )
    for sub_id, start_date, end_date in rows:
        windows[sub_id].append((start_date, end_date))
    return windows


def _was_prioritas(windows, sub_id, tgl_terima_dip):
    """Whether the data was prioritas on the day the tiket was received.

    The same rule :func:`prioritas_exists` applies in SQL — a window covering
    tgl_terima_dip — answered against the windows read up front.
    """
    if tgl_terima_dip is None:
        return False
    day = tgl_terima_dip.date() if hasattr(tgl_terima_dip, 'date') else tgl_terima_dip
    for start_date, end_date in windows.get(sub_id, ()):
        if start_date <= day and (end_date is None or end_date >= day):
            return True
    return False


class Weighting:
    """How heavy a tiket's rows are, over and above how many there are.

    A queue's size is not its load. The same thousand rows are more work when
    they have to be identified field by field, more when they belong to a
    regional ILAP that has to be checked back against the unit that sent it,
    more when the data was prioritas on arrival, and more when they are in front
    of the PIC now rather than still upstream. Each of those is a factor on the
    row count, and their product is what this returns.

    The tiket count is deliberately absent: quality control is done row by row,
    so one tiket of a million rows is a thousand tikets of a thousand.

    Args:
        section_weight: How much this queue counts for against the others.
        entry_weights: One `{entry_id: weight}` mapping per split, in the order
            of the splits it will be scored against.
        default_weight: The weight of a value none of those mappings names — a
            reference row added since, or a tiket with none set.
        prioritas_weight: The factor applied when the data was prioritas.
        windows: The lookup from :func:`prioritas_windows`.
        deadline: The :class:`Deadline` this queue is counted against, when it
            has one. Only the queue a seksi is actually working has a deadline
            of its own — what is still upstream has not started its count, and
            what is finished is long past it — so the other queues pass None and
            are scored without the jatuh tempo term.
        jatuh_tempo_weights: `(days, weight)` pairs, heaviest first, applied to
            the first one the tiket's jatuh tempo falls under. A tiket past its
            deadline has a negative jatuh tempo, so it falls under every band
            and takes the first.
    """

    def __init__(self, section_weight, entry_weights, default_weight,
                 prioritas_weight, windows, deadline=None,
                 jatuh_tempo_weights=()):
        self.section_weight = section_weight
        self.entry_weights = entry_weights
        self.default_weight = default_weight
        self.prioritas_weight = prioritas_weight
        self.windows = windows
        self.deadline = deadline
        self.jatuh_tempo_weights = jatuh_tempo_weights

    @property
    def fields(self):
        """The columns a scored row carries beyond the ones already read."""
        fields = [SUB, 'tgl_terima_dip']
        if self.deadline is not None:
            fields += [
                self.deadline.start_field, self.deadline.restart_field, 'active_durasi',
            ]
        return fields

    def annotate(self, qs):
        """Add whatever the score reads that is not a plain column."""
        return self.deadline.annotate_durasi(qs) if self.deadline is not None else qs

    def _jatuh_tempo_weight(self, start_value, restart_value, durasi):
        """The factor for how close this tiket's deadline is.

        A tiket with no deadline to count — no durasi covers its base date — is
        left at 1: nothing is known about its urgency, and guessing at it would
        move a PIC up the table for a gap in the reference data.
        """
        deadline_day = self.deadline.day(start_value, restart_value, durasi)
        if deadline_day is None:
            return 1.0
        sisa_hari = (deadline_day - date.today()).days
        for days, weight in self.jatuh_tempo_weights:
            if sisa_hari < days:
                return weight
        return 1.0

    def score(self, baris, entry_ids, extras):
        """The weighted load of one tiket, zero when it carries no rows.

        Args:
            extras: The values of :attr:`fields`, in that order.
        """
        if not baris:
            return 0.0
        weight = self.section_weight
        for weights, entry_id in zip(self.entry_weights, entry_ids):
            weight *= weights.get(entry_id, self.default_weight)
        if _was_prioritas(self.windows, extras[0], extras[1]):
            weight *= self.prioritas_weight
        if self.deadline is not None:
            weight *= self._jatuh_tempo_weight(*extras[2:5])
        return baris * weight


def _empty_section(splits):
    """A section with every entry of every split present and nothing counted.

    Every entry gets a place, including the ones with nothing pending: a zero
    there is a fact worth reading, and a line that vanished under a filter would
    shuffle the ones around it.
    """
    return {
        'tikets': 0,
        'baris': 0,
        'beban': 0.0,
        'splits': {
            split.key: {
                entry_id: {'name': name, 'tikets': 0, 'baris': 0, 'beban': 0.0}
                for entry_id, name in split.entries
            }
            for split in splits
        },
    }


def _count_tiket(section, split_keys, entry_ids, baris, beban):
    """Add one tiket, its rows and its weighted load to `section`.

    A tiket whose value on a split is not one of that split's entries — an unset
    one, or a reference row read after the section was built — still counts
    towards the totals, since it is a tiket in the queue, but has no line to
    land in there.
    """
    section['tikets'] += 1
    section['baris'] += baris
    section['beban'] += beban
    for key, entry_id in zip(split_keys, entry_ids):
        entry = section['splits'][key].get(entry_id)
        if entry is not None:
            entry['tikets'] += 1
            entry['baris'] += baris
            entry['beban'] += beban


def _finished(section):
    """The payload shape of a section, each split's entries as an ordered list.

    The load is rounded on the way out: it is an index built from ratios, and
    the digits past the point would read as a precision it does not have.
    """
    return {
        'tikets': section['tikets'],
        'baris': section['baris'],
        'beban': round(section['beban']),
        'splits': {
            key: [
                dict(entry, beban=round(entry['beban'])) for entry in entries.values()
            ]
            for key, entries in section['splits'].items()
        },
    }


def queue_breakdown(qs, kinds, baris_fields, baris_of):
    """A queue's tikets and rows, split by the jenis tabel of their data.

    The one-dimension form, for the pages whose summary is a card per queue.
    Its `breakdown` key is that single split, unwrapped.

    Args:
        qs: The tikets to summarise, already filtered.
        kinds: `(id, deskripsi)` pairs, in the order the rows should read.
        baris_fields: Field names to read for the row count.
        baris_of: Callable receiving those fields and returning the row count.
    """
    split = Split('jenis_tabel', 'Jenis Tabel', f'{SUB}__id_jenis_tabel__id', kinds)
    section = _finished(_accumulate(qs, [split], baris_fields, baris_of))
    return {
        'tikets': section['tikets'],
        'baris': section['baris'],
        'breakdown': section['splits']['jenis_tabel'],
    }


def _row_columns(splits, baris_fields, weighting, *leading):
    """The columns one pass reads, and where each group of them starts.

    Named here once because the reader and the loop have to agree on the layout
    of a tuple that changes with the splits it was asked for.
    """
    columns = list(leading)
    columns += [split.path for split in splits]
    columns += list(baris_fields)
    if weighting is not None:
        columns += weighting.fields
    return columns


def _accumulate(qs, splits, baris_fields, baris_of, weighting=None):
    """Sum `qs` into one working section, split every way `splits` asks.

    The rows are read and summed here rather than aggregated in SQL because `id`
    leads each tuple, so the DISTINCT that the to-many filters add collapses a
    tiket matched twice into one row instead of counting it twice.
    """
    section = _empty_section(splits)
    keys = [split.key for split in splits]
    depth = len(splits)
    end = 1 + depth + len(baris_fields)

    if weighting is not None:
        qs = weighting.annotate(qs)
    rows = qs.values_list(*_row_columns(splits, baris_fields, weighting, 'id'))
    for row in rows:
        entry_ids = row[1:1 + depth]
        baris = baris_of(*row[1 + depth:end])
        beban = weighting.score(baris, entry_ids, row[end:]) if weighting else 0.0
        _count_tiket(section, keys, entry_ids, baris, beban)
    return section


def queue_breakdown_per_pic(qs, splits, baris_fields, baris_of, role, weighting=None):
    """:func:`_accumulate` again, one section per PIC of `role`.

    Args:
        role: The PIC role the queue is grouped by.
        weighting: The :class:`Weighting` scoring this queue's load, or None to
            count rows without weighing them.

    Returns:
        tuple: `({pic_id: section}, total_section)`, where a `pic_id` of None
        holds the tikets with no active PIC — they carry work like any other
        tiket, so they keep a line of their own rather than being dropped. The
        total is accumulated in the same pass, so a page showing both reads the
        queue once instead of twice.
    """
    per_pic = {}
    total = _empty_section(splits)
    keys = [split.key for split in splits]
    depth = len(splits)
    end = 2 + depth + len(baris_fields)

    if weighting is not None:
        qs = weighting.annotate(qs)
    rows = qs.annotate(pic_id=pic_id_expr(role)).values_list(
        *_row_columns(splits, baris_fields, weighting, 'id', 'pic_id')
    )
    for row in rows:
        pic_id = row[1]
        entry_ids = row[2:2 + depth]
        baris = baris_of(*row[2 + depth:end])
        beban = weighting.score(baris, entry_ids, row[end:]) if weighting else 0.0
        _count_tiket(total, keys, entry_ids, baris, beban)
        if pic_id not in per_pic:
            per_pic[pic_id] = _empty_section(splits)
        _count_tiket(per_pic[pic_id], keys, entry_ids, baris, beban)

    return {pic_id: _finished(section) for pic_id, section in per_pic.items()}, _finished(total)


def pic_summary(sections, role, can_view, no_pic_label):
    """The summary table: one line per PIC, and the totals line under them.

    Every section is the same queue read a different way — the queue this page
    lists, then the ones upstream of it — so a PIC's line puts all of them side
    by side and says how much of each is theirs. Which PIC appear is decided by
    the filtered sections themselves rather than by the seksi's roster, so
    narrowing the filter panel narrows the rows too.

    A PIC present in one section but not another still gets a full line, the
    sections they hold nothing in reading as zeros — a line that changed width
    between one PIC and the next would not be a table.

    Args:
        sections: `{key: (qs, splits, baris_fields, baris_of, weighting)}`, one
            entry per column group, in the order the groups are rendered. A
            section is broken down by the :class:`Split` list it is given and by
            no others, so one passing an empty list is the tiket and row totals
            alone; `weighting` is the :class:`Weighting` scoring its load, or
            None to leave the load at zero.
        role: The PIC role the lines are keyed by.
        can_view: The predicate from `pic_profil_visibility`, deciding whether a
            name is rendered as a link to its Profil PIC page.
        no_pic_label: What to call the line holding the tikets with no PIC.

    Returns:
        tuple: `(rows, totals)` — the per-PIC lines, and `{key: section}` for
        the line under them, with the whole table's load under `beban`.
    """
    per_pic = {}
    totals = {}
    for key, (qs, splits, baris_fields, baris_of, weighting) in sections.items():
        per_pic[key], totals[key] = queue_breakdown_per_pic(
            qs, splits, baris_fields, baris_of, role, weighting,
        )

    pic_ids = {pic_id for breakdowns in per_pic.values() for pic_id in breakdowns}
    users = User.objects.in_bulk([pic_id for pic_id in pic_ids if pic_id is not None])

    # By name, with the line for "nobody" last: it is not a person, and holding
    # its place at the foot keeps it from moving as PIC come and go.
    ordered = sorted(
        pic_ids,
        key=lambda pic_id: (
            pic_id is None, pic_display_name(users.get(pic_id)).lower(),
        ),
    )

    rows = []
    for pic_id in ordered:
        user = users.get(pic_id)
        row_sections = {
            key: per_pic[key].get(pic_id) or _finished(_empty_section(section[1]))
            for key, section in sections.items()
        }
        rows.append({
            'name': pic_display_name(user) if user else no_pic_label,
            # Linked to the Profil PIC page, like every other name in the app;
            # the line with no PIC behind it is plain text, there being nobody
            # for it to lead to.
            'pic': pic_profil_link(user, can_view) if user else escape(no_pic_label),
            'sections': row_sections,
            # A PIC's whole load is what the queues add up to, and a detail
            # line's is the part of it that line accounts for. Both are summed
            # across the groups here rather than in the browser, so the column
            # the table sorts by is a figure the server stands behind.
            'beban': sum(section['beban'] for section in row_sections.values()),
            'detail': _detail_beban(row_sections),
        })
    return rows, dict(totals, beban=sum(total['beban'] for total in totals.values()))


def _detail_beban(row_sections):
    """Each split entry's load, summed across the groups, in entry order."""
    detail = {}
    for section in row_sections.values():
        for key, entries in section['splits'].items():
            running = detail.setdefault(key, [0] * len(entries))
            for index, entry in enumerate(entries):
                running[index] += entry['beban']
    return detail


# ---------------------------------------------------------------------------
# Chart: Jml Progress per Jatuh Tempo, one line per PIC of the seksi
# ---------------------------------------------------------------------------

# Eight categorical hues, in this fixed order. Past the eighth PIC the hues
# start over with a dashed stroke instead of a ninth colour, because a
# generated hue would be indistinguishable from an existing one for a
# colourblind reader while a dash pattern is legible to everyone.
CHART_COLORS = [
    '#2a78d6', '#eb6834', '#1baf7a', '#eda100',
    '#e87ba4', '#008300', '#4a3aa7', '#e34948',
]

# Tikets in the queue with no active PIC still carry progress, so they get their
# own line — deliberately a neutral grey, since "nobody" is not an identity.
CHART_NO_PIC_COLOR = '#94a3b8'


def pic_styles(scoped_qs, role, no_pic_label):
    """Assign each PIC a stable colour and stroke, keyed by user id.

    The assignment is made over the *unfiltered* scope, so narrowing the filter
    panel never repaints the lines that survive: a reader who learned that a
    given PIC is the blue line keeps that reading across every filter.
    """
    rows = TiketPIC.objects.filter(
        id_tiket__in=scoped_qs, role=role, active=True, id_user__isnull=False,
    ).values_list(
        'id_user__id', 'id_user__username',
        'id_user__first_name', 'id_user__last_name',
    ).distinct()

    names = {}
    for user_id, username, first_name, last_name in rows:
        full_name = f'{first_name or ""} {last_name or ""}'.strip()
        names[user_id] = full_name or username

    styles = {}
    for index, user_id in enumerate(sorted(names, key=lambda uid: names[uid])):
        styles[user_id] = {
            'name': names[user_id],
            'color': CHART_COLORS[index % len(CHART_COLORS)],
            'dashed': index >= len(CHART_COLORS),
        }
    styles[None] = {'name': no_pic_label, 'color': CHART_NO_PIC_COLOR, 'dashed': True}
    return styles


def chart_data(scoped_qs, selected, appliers, deadline, role, no_pic_label,
               progress_fields, progress_of):
    """Jml Progress summed per jatuh tempo, split into one series per PIC.

    The x axis is the Jatuh Tempo column of the table — days left until the
    deadline, negative once it has passed — and the y axis is the Jml Progress
    of every tiket sharing that value. Tikets without a deadline are left out,
    matching the '-' the table shows for them.

    Args:
        progress_fields: Field names holding the tiket's remaining work.
        progress_of: Callable receiving those fields and returning that figure.
    """
    styles = pic_styles(scoped_qs, role, no_pic_label)

    rows = deadline.annotate_durasi(
        apply_filters(scoped_qs, selected, appliers)
    ).annotate(
        pic_id=pic_id_expr(role),
        # `id` keeps DISTINCT (added by the to-many filters) from collapsing two
        # different tikets that happen to agree on every other column here.
    ).values_list(
        'id', 'pic_id', deadline.start_field, deadline.restart_field,
        'active_durasi', *progress_fields,
    )

    totals = defaultdict(int)
    days = set()
    today = date.today()
    for _tiket_id, pic_id, start_value, restart_value, durasi, *progress in rows:
        deadline_day = deadline.day(start_value, restart_value, durasi)
        if deadline_day is None:
            continue
        sisa = (deadline_day - today).days
        days.add(sisa)
        totals[(pic_id, sisa)] += progress_of(*progress)

    categories = sorted(days)
    pic_ids = {pic_id for pic_id, _sisa in totals}

    # Series follow the palette order rather than their totals, so the legend
    # reads the same way from one filter to the next.
    ordered = [pic_id for pic_id in styles if pic_id in pic_ids]
    series = []
    for pic_id in ordered:
        style = styles[pic_id]
        series.append({
            'name': style['name'],
            'color': style['color'],
            'dashed': style['dashed'],
            # A missing (pic, day) pair is a real zero — that PIC has no tiket
            # falling due then — so the line stays continuous instead of broken.
            'data': [totals.get((pic_id, day), 0) for day in categories],
        })

    return {
        'categories': [f'{day} hari' for day in categories],
        'series': series,
    }


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------

def pic_scope(tikets, user, role, is_supervisor):
    """Narrow `tikets` to what `user` is allowed to see in this seksi.

    Kasi supervise the whole seksi, so they see every tiket rather than only the
    ones they are the active PIC for (the same rule the tiket list applies to
    kasi). Everyone else stays scoped to their own assignments.
    """
    if is_supervisor(user):
        return tikets
    pic_tiket_ids = TiketPIC.objects.filter(
        id_user=user, role=role, active=True,
    ).values_list('id_tiket', flat=True)
    return tikets.filter(id__in=pic_tiket_ids)
