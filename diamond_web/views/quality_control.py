"""Quality Control page - PMDE User Quality Control view.

This module provides a page for PMDE users to view and monitor tickets that
are in the quality control process (status = Pengendalian Mutu). Displays a
DataTable with comprehensive columns including ILAP info, PIC, deadline
calculations, and QC progress.

Filtering works the same way as the tiket list page: a panel of Select2
multi-selects above the table, each of which narrows both the table and the
remaining dropdowns. The tiket status filter is absent (every row here is in
Pengendalian Mutu by definition) and a Prioritas Ya/Tidak filter is added,
since prioritas is a column of this table.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.db import connection as db_connection
from django.db.models import Q, Value, Prefetch
from django.db.models.functions import Cast
from django.db.models import (
    DateField, IntegerField, Subquery, OuterRef,
    Exists
)
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date

from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.status_penelitian import StatusPenelitian
from ..constants.tiket_status import STATUS_PENGENDALIAN_MUTU
from ..utils.wilayah import kanwil_value_paths, tiket_in_kanwil_q
from .mixins import is_kasi_pmde


# Query path from Tiket to the JenisDataILAP row that carries most of the
# descriptive fields the filters key off.
_SUB = 'id_periode_data__id_sub_jenis_data_ilap'
_ILAP = f'{_SUB}__id_ilap'
_PENGIRIMAN = 'id_periode_data__id_periode_pengiriman'

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


def _is_pmde_user(user):
    """Check if user is PMDE user, admin or the PMDE supervisor (kasi)."""
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde', 'kasi_pmde']
    ).exists()


class QualityControlView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display Quality Control page for PMDE users.

    Shows a DataTable of tickets assigned to the current PMDE user that
    are in the quality control process (status = Pengendalian Mutu).

    Template: quality_control/list.html
    """
    template_name = 'quality_control/list.html'

    def test_func(self):
        """Verify user is PMDE user or admin."""
        return _is_pmde_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


def _scoped_queryset(user):
    """Tikets in Pengendalian Mutu that `user` is allowed to see.

    Kasi PMDE supervise the whole seksi, so they see every tiket in QC rather
    than only the ones they are the active PIC for (same rule the tiket list
    applies to kasi). Everyone else stays scoped to their own assignments.
    """
    tikets = Tiket.objects.filter(status_tiket=STATUS_PENGENDALIAN_MUTU)
    if not is_kasi_pmde(user):
        pmde_tiket_ids = TiketPIC.objects.filter(
            id_user=user, role=TiketPIC.Role.PMDE, active=True
        ).values_list('id_tiket', flat=True)
        tikets = tikets.filter(id__in=pmde_tiket_ids)
    return tikets


def _prioritas_exists():
    """Exists() matching tikets whose data was prioritas when it was received."""
    return Exists(
        JenisPrioritasData.objects.filter(
            id_sub_jenis_data_ilap=OuterRef(_SUB),
            start_date__lte=Cast(OuterRef('tgl_terima_dip'), DateField()),
            end_date__gte=Cast(OuterRef('tgl_terima_dip'), DateField()),
        )
    )


def _split(value):
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
            selector &= Q(**{f'{_PENGIRIMAN}__periode_penerimaan': label})
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
    return qs.filter(_prioritas_exists()) if wanted.pop() else qs.exclude(_prioritas_exists())


# Every dropdown on the filter panel, in the order the panel renders them.
# The key is both the request parameter and the `filter_options` key the
# template reads back, so adding a filter means adding one entry here, one
# entry in FILTER_OPTIONS below, and one <select> in the template.
FILTER_APPLIERS = {
    'nomor_tiket': _in('nomor_tiket'),
    'tahun': _int_in('tahun'),
    'periode': _filter_periode,
    'periode_pengiriman': _in(f'{_PENGIRIMAN}__periode_penyampaian'),
    'periode_penerimaan': _in(f'{_PENGIRIMAN}__periode_penerimaan'),
    'pic_p3de': _pic_in(TiketPIC.Role.P3DE),
    'pic_pide': _pic_in(TiketPIC.Role.PIDE),
    'pic_pmde': _pic_in(TiketPIC.Role.PMDE),
    'kategori_ilap': _in(f'{_ILAP}__id_kategori__id'),
    'ilap': _in(f'{_ILAP}__id'),
    'jenis_data': _in(f'{_SUB}__id_jenis_data'),
    'sub_jenis_data': _in(f'{_SUB}__id_sub_jenis_data'),
    'kanwil': lambda qs, values: qs.filter(tiket_in_kanwil_q(values)),
    'kpp': _in(f'{_ILAP}__ilap_kpp_relations__id_kpp__id'),
    'kategori_wilayah': _in(f'{_ILAP}__id_kategori_wilayah__id'),
    'jenis_tabel': _in(f'{_SUB}__id_jenis_tabel__id'),
    'dasar_hukum': _in(f'{_SUB}__klasifikasijenisdata__id_klasifikasi_tabel__id'),
    'status_penelitian': _in('id_status_penelitian_id'),
    'status_ketersediaan_data': _bool_in('status_ketersediaan_data'),
    'special_request': _bool_in('special_request'),
    'prioritas': _filter_prioritas,
}


# Filters that reach a tiket through a to-many join, so a tiket can match more
# than once and the result needs de-duplicating. The rest walk plain foreign
# keys, where DISTINCT would only cost a sort.
_MULTI_ROW_FILTERS = frozenset({
    'pic_p3de', 'pic_pide', 'pic_pmde', 'kanwil', 'kpp', 'dasar_hukum',
})


def _selected_filters(params):
    """Read every filter parameter, dropping the ones left on '-- Semua --'."""
    selected = {}
    for key in FILTER_APPLIERS:
        values = _split(params.get(key, ''))
        if values:
            selected[key] = values
    return selected


def _apply_filters(qs, selected, exclude=None):
    """Apply the selected filters, optionally skipping one dropdown's own key.

    Skipping is what keeps a dropdown from narrowing itself: a dropdown's
    options are built from everything the *other* dropdowns allow, so the
    values already chosen in it stay selectable.
    """
    applied = set()
    for key, values in selected.items():
        if key == exclude:
            continue
        qs = FILTER_APPLIERS[key](qs, values)
        applied.add(key)
    return qs.distinct() if applied & _MULTI_ROW_FILTERS else qs


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
    rows = qs.values_list('periode', f'{_PENGIRIMAN}__periode_penerimaan').distinct()
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
    if qs.filter(_prioritas_exists()).exists():
        options.append({'id': '1', 'name': 'Ya'})
    if qs.exclude(_prioritas_exists()).exists():
        options.append({'id': '0', 'name': 'Tidak'})
    return options


def _kode_nama(_id, kode, nama):
    """Label a lookup row as `<kode> - <nama>`, keeping the id out of the text."""
    return f'{kode} - {nama}'


FILTER_OPTIONS = {
    'nomor_tiket': lambda qs: _distinct_options(qs.order_by('nomor_tiket'), ('nomor_tiket',)),
    'tahun': lambda qs: _distinct_options(qs.order_by('tahun'), ('tahun',)),
    'periode': _periode_options,
    'periode_pengiriman': lambda qs: _distinct_options(
        qs, (f'{_PENGIRIMAN}__periode_penyampaian',)),
    'periode_penerimaan': lambda qs: _distinct_options(
        qs, (f'{_PENGIRIMAN}__periode_penerimaan',)),
    'pic_p3de': lambda qs: _pic_options(qs, TiketPIC.Role.P3DE),
    'pic_pide': lambda qs: _pic_options(qs, TiketPIC.Role.PIDE),
    'pic_pmde': lambda qs: _pic_options(qs, TiketPIC.Role.PMDE),
    'kategori_ilap': lambda qs: _distinct_options(
        qs,
        (f'{_ILAP}__id_kategori__id', f'{_ILAP}__id_kategori__id_kategori',
         f'{_ILAP}__id_kategori__nama_kategori'),
        _kode_nama,
    ),
    'ilap': lambda qs: _distinct_options(
        qs,
        (f'{_ILAP}__id', f'{_ILAP}__id_ilap', f'{_ILAP}__nama_ilap'),
        _kode_nama,
    ),
    'jenis_data': lambda qs: _distinct_options(
        qs,
        (f'{_SUB}__id_jenis_data', f'{_SUB}__nama_jenis_data'),
        lambda kode, nama: f'{kode} - {nama}',
    ),
    'sub_jenis_data': lambda qs: _distinct_options(
        qs,
        (f'{_SUB}__id_sub_jenis_data', f'{_SUB}__nama_sub_jenis_data'),
        lambda kode, nama: f'{kode} - {nama}',
    ),
    'kanwil': _kanwil_options,
    'kpp': lambda qs: _distinct_options(
        qs,
        (f'{_ILAP}__ilap_kpp_relations__id_kpp__id',
         f'{_ILAP}__ilap_kpp_relations__id_kpp__kode_kpp',
         f'{_ILAP}__ilap_kpp_relations__id_kpp__nama_kpp'),
        _kode_nama,
    ),
    'kategori_wilayah': lambda qs: _distinct_options(
        qs,
        (f'{_ILAP}__id_kategori_wilayah__id', f'{_ILAP}__id_kategori_wilayah__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'jenis_tabel': lambda qs: _distinct_options(
        qs,
        (f'{_SUB}__id_jenis_tabel__id', f'{_SUB}__id_jenis_tabel__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'dasar_hukum': lambda qs: _distinct_options(
        qs,
        (f'{_SUB}__klasifikasijenisdata__id_klasifikasi_tabel__id',
         f'{_SUB}__klasifikasijenisdata__id_klasifikasi_tabel__deskripsi'),
        lambda _id, deskripsi: deskripsi,
    ),
    'status_penelitian': _status_penelitian_options,
    'status_ketersediaan_data': lambda qs: _yes_no_options(qs, 'status_ketersediaan_data'),
    'special_request': lambda qs: _yes_no_options(qs, 'special_request'),
    'prioritas': _prioritas_options,
}


def _filter_options(scoped_qs, selected):
    """Build the option list for every dropdown, each excluding its own filter."""
    return {
        key: builder(_apply_filters(scoped_qs, selected, exclude=key))
        for key, builder in FILTER_OPTIONS.items()
    }


@login_required
@user_passes_test(_is_pmde_user)
@require_http_methods(["POST", "GET"])
@csrf_protect
def quality_control_data(request):
    """DataTables server-side endpoint for Quality Control page.

    With ``get_filter_options=1`` it returns the option lists for the filter
    panel instead of table rows; every other request returns a page of rows
    narrowed by the same filter parameters.
    """
    params = request.POST if request.method == 'POST' else request.GET

    scoped = _scoped_queryset(request.user)
    selected = _selected_filters(params)

    if params.get('get_filter_options'):
        return JsonResponse({'filter_options': _filter_options(scoped, selected)})

    draw = int(params.get('draw', '1'))
    start = int(params.get('start', '0'))
    length = int(params.get('length', '10'))

    records_total = scoped.count()

    # Subquery: active durasi for each ticket's sub_jenis_data & tgl_transfer range
    durasi_subq = DurasiJatuhTempo.objects.filter(
        id_sub_jenis_data=OuterRef(f'{_SUB}'),
        seksi__name='user_pmde',
        start_date__lte=Cast(OuterRef('tgl_transfer'), DateField()),
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=Cast(OuterRef('tgl_transfer'), DateField()))
    ).order_by('-start_date').values('durasi')[:1]

    tikets = _apply_filters(scoped, selected).select_related(
        f'{_ILAP}',
        f'{_SUB}__id_jenis_tabel',
    ).prefetch_related(
        Prefetch('tiketpic_set', queryset=TiketPIC.objects.select_related('id_user')),
    ).annotate(
        tgl_transfer_date=Cast('tgl_transfer', DateField()),
        tgl_rematch_date=Cast('tgl_rematch', DateField()),
        # Active durasi, used both for sorting and to compute the deadline below.
        active_durasi=Coalesce(
            Subquery(durasi_subq, output_field=IntegerField()),
            Value(0)
        ),
    ).annotate(
        is_prioritas=_prioritas_exists(),
    ).annotate(
        # Compute deadline date = tgl_transfer + active_durasi days.
        # Correlated subquery embedded in RawSQL (no params) to avoid
        # parameter-binding issues with nested expressions.
        # SQLite (dev): DATE(date, '+' || days || ' days')
        # PostgreSQL (prod): (date::date + days * INTERVAL '1 day')::date
        deadline_date=RawSQL(
            """
            DATE("tiket"."tgl_transfer", '+' || CAST(COALESCE(
                (SELECT "durasi_jatuh_tempo"."durasi"
                 FROM "durasi_jatuh_tempo"
                 INNER JOIN "auth_group" ON ("durasi_jatuh_tempo"."seksi" = "auth_group"."id")
                 WHERE ("durasi_jatuh_tempo"."id_sub_jenis_data" = "periode_jenis_data"."id_sub_jenis_data_ilap"
                   AND "auth_group"."name" = 'user_pmde'
                   AND "durasi_jatuh_tempo"."start_date" <= DATE("tiket"."tgl_transfer")
                   AND ("durasi_jatuh_tempo"."end_date" IS NULL
                        OR "durasi_jatuh_tempo"."end_date" >= DATE("tiket"."tgl_transfer")))
                 ORDER BY "durasi_jatuh_tempo"."start_date" DESC LIMIT 1
            ), 0) AS TEXT) || ' days')
            """ if db_connection.vendor == 'sqlite' else
            """
            ("tiket"."tgl_transfer"::date + COALESCE(
                (SELECT "durasi_jatuh_tempo"."durasi"
                 FROM "durasi_jatuh_tempo"
                 INNER JOIN "auth_group" ON ("durasi_jatuh_tempo"."seksi" = "auth_group"."id")
                 WHERE ("durasi_jatuh_tempo"."id_sub_jenis_data" = "periode_jenis_data"."id_sub_jenis_data_ilap"
                   AND "auth_group"."name" = 'user_pmde'
                   AND "durasi_jatuh_tempo"."start_date" <= "tiket"."tgl_transfer"::date
                   AND ("durasi_jatuh_tempo"."end_date" IS NULL
                        OR "durasi_jatuh_tempo"."end_date" >= "tiket"."tgl_transfer"::date))
                 ORDER BY "durasi_jatuh_tempo"."start_date" DESC LIMIT 1
            ), 0) * INTERVAL '1 day')::date
            """,
            [],
            output_field=DateField(),
        ),
    )

    records_filtered = tikets.count()

    # ---- Server-side sorting ----
    order_map = {
        0: f'{_SUB}__nama_tabel_I',
        1: 'id',
        2: 'nomor_tiket',
        3: f'{_ILAP}__nama_ilap',
        4: f'{_SUB}__nama_sub_jenis_data',
        5: f'{_SUB}__id_jenis_tabel__deskripsi',
        6: 'tgl_transfer_date',
        7: 'tgl_rematch_date',
        8: 'deadline_date',
        # Jatuh tempo is the deadline counted from today, so it sorts the same way.
        9: 'deadline_date',
        10: 'is_prioritas',
        11: 'baris_i',
        12: 'sudah_qc',
        13: 'belum_qc',
    }

    # Read sort column and direction from DataTables params
    order_col_index = params.get('order[0][column]')
    order_dir = params.get('order[0][dir]', 'asc')

    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = order_map.get(idx, 'id')
            if order_dir == 'desc':
                col = '-' + col
            tikets = tikets.order_by(col)
        except (ValueError, TypeError):
            tikets = tikets.order_by('-id')
    else:
        tikets = tikets.order_by('-id')

    page = list(tikets[start:start + length])

    # Build response data
    data = []
    for tiket in page:
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        ilap = sub_jenis_data.id_ilap
        jenis_tabel = sub_jenis_data.id_jenis_tabel

        # Get PIC PMDE name from the prefetched assignments
        pic_pmde = next(
            (pic for pic in tiket.tiketpic_set.all()
             if pic.role == TiketPIC.Role.PMDE and pic.active and pic.id_user),
            None,
        )
        pic_pmde_name = ''
        if pic_pmde:
            pic_pmde_name = pic_pmde.id_user.get_full_name() or pic_pmde.id_user.username

        # Deadline from the annotated durasi — 0 means no active DurasiJatuhTempo
        # covers this tiket's tgl_transfer, so there is nothing to count from.
        deadline = '-'
        jatuh_tempo = '-'
        deadline_sort_iso = ''
        sisa_hari = None
        if tiket.tgl_transfer and tiket.active_durasi:
            deadline_dt = tiket.tgl_transfer + timezone.timedelta(days=tiket.active_durasi)
            deadline_day = deadline_dt.date() if hasattr(deadline_dt, 'date') else deadline_dt
            deadline = deadline_day.strftime('%d/%m/%Y')
            deadline_sort_iso = deadline_day.strftime('%Y-%m-%d')
            sisa_hari = (deadline_day - date.today()).days
            jatuh_tempo = f'{sisa_hari} hari'

        row = {
            'nama_tabel': sub_jenis_data.nama_tabel_I or '',
            'pic_pmde': pic_pmde_name,
            'nomor_tiket': tiket.nomor_tiket,
            'nama_ilap': ilap.nama_ilap if ilap else '',
            'sub_jenis_data': sub_jenis_data.nama_sub_jenis_data or '',
            'jenis_tabel': jenis_tabel.deskripsi if jenis_tabel else '',
            'deadline': {'display': deadline, 'sort': deadline_sort_iso},
            'tgl_transfer': {
                'display': tiket.tgl_transfer.strftime('%d/%m/%Y') if tiket.tgl_transfer else '-',
                'sort': tiket.tgl_transfer.strftime('%Y-%m-%d') if tiket.tgl_transfer else '',
            },
            'tgl_rematch': {
                'display': tiket.tgl_rematch.strftime('%d/%m/%Y') if tiket.tgl_rematch else '-',
                'sort': tiket.tgl_rematch.strftime('%Y-%m-%d') if tiket.tgl_rematch else '',
            },
            'jatuh_tempo': {
                'display': jatuh_tempo,
                'sort': '' if sisa_hari is None else str(sisa_hari),
            },
            'prioritas': 'Ya' if tiket.is_prioritas else 'Tidak',
            'jml_baris_i': tiket.baris_i or 0,
            'jml_selesai': tiket.sudah_qc or 0,
            'jml_progress': tiket.belum_qc or 0,
            'sisa_hari': sisa_hari,  # numeric for frontend row coloring
            'action': f'<a href="{reverse("tiket_detail", args=[tiket.id])}" class="btn btn-sm btn-primary" title="Lihat Detail"><i class="feather-eye"></i></a>',
        }
        data.append(row)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data
    })
