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

from django.db import connection as db_connection
from django.db.models import (
    DateField, Exists, IntegerField, OuterRef, Q, Subquery, Value,
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.jenis_tabel import JenisTabel
from ..models.status_penelitian import StatusPenelitian
from ..models.tiket_pic import TiketPIC
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


def jenis_tabel_kinds():
    """The `(id, deskripsi)` pairs every breakdown lists, in reference order.

    Read once for all of a page's sections, so every one of them reads its rows
    in the same order and the three can be compared straight across.
    """
    return list(JenisTabel.objects.order_by('id').values_list('id', 'deskripsi'))


def queue_breakdown(qs, kinds, baris_fields, baris_of):
    """A queue's tikets and rows, split by the jenis tabel of their data.

    Jenis tabel is what decides how a tiket's data is handled — diidentifikasi,
    tidak diidentifikasi or tidak terstruktur — so every queue is broken down
    along it rather than along status.

    Every jenis tabel in `kinds` gets a row, including the ones with nothing
    pending: a zero there is a fact worth reading, and a row that vanished under
    a filter would shuffle the rows around it.

    Args:
        qs: The tikets to summarise, already filtered.
        kinds: `(id, deskripsi)` pairs, in the order the rows should read.
        baris_fields: Field names to read for the row count.
        baris_of: Callable receiving those fields and returning the row count.

    The rows are read and summed here rather than aggregated in SQL because `id`
    leads each tuple, so the DISTINCT that the to-many filters add collapses a
    tiket matched twice into one row instead of counting it twice.
    """
    breakdown = {
        kind_id: {'name': deskripsi, 'tikets': 0, 'baris': 0}
        for kind_id, deskripsi in kinds
    }

    tikets = 0
    baris_total = 0
    rows = qs.values_list('id', f'{SUB}__id_jenis_tabel__id', *baris_fields)
    for _tiket_id, jenis_tabel_id, *values in rows:
        baris = baris_of(*values)
        tikets += 1
        baris_total += baris
        entry = breakdown.get(jenis_tabel_id)
        if entry is not None:
            entry['tikets'] += 1
            entry['baris'] += baris

    return {'tikets': tikets, 'baris': baris_total, 'breakdown': list(breakdown.values())}


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
        pic_id=Subquery(
            TiketPIC.objects.filter(
                id_tiket=OuterRef('pk'), role=role, active=True,
            ).values('id_user_id')[:1],
            output_field=IntegerField(),
        ),
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
