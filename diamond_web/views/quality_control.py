"""Quality Control page - PMDE User Quality Control view.

This module provides a page for PMDE users to view and monitor tickets that
are in the quality control process (status = Pengendalian Mutu). Displays a
DataTable with comprehensive columns including ILAP info, PIC, deadline
calculations, and QC progress.

The page itself — filter panel, summary sections, chart and table — is the one
`seksi_queue` builds for every seksi; what is decided here is which queue is
PMDE's, that its deadline counts from the transfer (or the rematch that handed
the tiket back), and that the work left on a row is the rows it has still to
check. The Identifikasi page is the same page read by PIDE.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.db.models import DateField, Exists, OuterRef, Prefetch
from django.db.models.functions import Cast

from . import seksi_queue as sq
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..constants.tiket_action_types import TiketActionType
from ..constants.tiket_status import (
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
    STATUSES_DI_P3DE,
    STATUSES_DI_PIDE,
)
from ..utils.pic_profil import pic_profil_link, pic_profil_visibility
from .mixins import is_kasi_pmde

__all__ = ['QualityControlView', 'quality_control_data']


# A rematched tiket starts its count again from tgl_rematch, so that date wins
# over tgl_transfer whenever it is set.
DEADLINE = sq.Deadline(
    seksi='user_pmde', start_field='tgl_transfer', restart_field='tgl_rematch',
)

# Kept module-level under their old names: the filter panel is exercised
# through them, and the PMDE home card counts jatuh tempo by the same rule this
# page does, which is what stops the two from disagreeing about when a tiket
# falls due.
FILTER_APPLIERS = sq.build_filter_appliers(DEADLINE)
FILTER_OPTIONS = sq.FILTER_OPTIONS


def jatuh_tempo_ids(qs, limit):
    """Ids of the tikets in `qs` falling due within `limit` days, PMDE's count."""
    return DEADLINE.jatuh_tempo_ids(qs, limit)


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
        """Add the header of the summary table, and the detail lines under it.

        The detail lines are reference data — the jenis tabel and the kategori
        wilayah — which the page cannot spell out in its markup: a row added to
        either table has to appear as a line here, exactly as it appears in
        every breakdown the endpoint sends back. The endpoint reads the same
        lists in the same order, so a line of figures lands beside the name it
        belongs to.
        """
        context = super().get_context_data(**kwargs)
        splits = summary_splits()
        details = [
            {
                'key': split.key,
                'label': split.label,
                # `hue` is the palette slot the line is marked in, assigned by
                # position and wrapping after the palette runs out — see the
                # .sq-kind-* rules. Decided here rather than in the template
                # because the template language has no modulo.
                'entries': [
                    {'name': name, 'hue': index % SUMMARY_KIND_HUES}
                    for index, (_entry_id, name) in enumerate(split.entries)
                ],
            }
            for split in splits
        ]
        context.update({
            'summary_sections': SUMMARY_SECTIONS,
            'summary_details': details,
            'beban_info': _beban_info(splits),
            'summary_section_keys': ','.join(
                section['key'] for section in SUMMARY_SECTIONS
            ),
            'summary_section_variants': ','.join(
                section['variant'] for section in SUMMARY_SECTIONS
            ),
            'summary_default_sort': SUMMARY_DEFAULT_SORT,
        })
        return context


def _pmde_scope(tikets, user):
    """Narrow `tikets` to what `user` is allowed to see as PMDE."""
    return sq.pic_scope(tikets, user, TiketPIC.Role.PMDE, is_kasi_pmde)


def _scoped_queryset(user):
    """Tikets in Pengendalian Mutu that `user` is allowed to see."""
    return _pmde_scope(Tiket.objects.filter(status_tiket=STATUS_PENGENDALIAN_MUTU), user)


def _upstream_queryset(user, statuses):
    """Tikets in `statuses` that `user` is allowed to see, for the P3DE and PIDE
    sections of the summary.

    The same scope as the page's own queue, over the statuses upstream of
    quality control instead. A PMDE PIC is assigned when a tiket is recorded
    rather than when it is transferred (see rekam_tiket), so a pelaksana already
    has assignments among these: they are the work heading towards them, which
    is what makes them worth a section on this page.
    """
    return _pmde_scope(Tiket.objects.filter(status_tiket__in=statuses), user)


# How far back the finished work on the right of the summary reaches. Two
# windows rather than one, because "how much is this person getting through" is
# a question asked at two ranges: the quarter just gone, which is recent enough
# to say how they are working now, and the year, which is long enough to say how
# they work.
#
# The quarter sits inside the year rather than beside it — a tiket closed last
# week is counted in both columns. The wider column is the longer view of the
# same work, not a different set of it, which is what makes the pair readable as
# a zoom: whatever is in the quarter is part of what is in the year.
SELESAI_WINDOW_DAYS = 90
SELESAI_TAHUN_WINDOW_DAYS = 365


def _selesai_queryset(user, days):
    """Tikets `user` may see that finished quality control in the last `days`.

    Completion is not a date on the tiket — it is the SELESAI action written
    when the tiket was closed (see selesaikan_tiket) — so the window is read
    from the action log rather than from a column. The status is checked as
    well, so a tiket closed and then reopened is counted where it is now and not
    where it has been.
    """
    since = timezone.now() - timedelta(days=days)
    return _pmde_scope(
        Tiket.objects.filter(status_tiket=STATUS_SELESAI).filter(
            Exists(TiketAction.objects.filter(
                id_tiket=OuterRef('pk'),
                action=TiketActionType.SELESAI,
                timestamp__gte=since,
            ))
        ),
        user,
    )


def _belum_qc(belum_qc):
    """The row count a tiket in quality control still has left to check."""
    return belum_qc or 0


def _sudah_qc(sudah_qc):
    """The row count a finished tiket was checked over — the work done on it."""
    return sudah_qc or 0


# The column groups of the summary table, in the order it renders them. Read
# across a PIC's line they are that person's whole load in time order once the
# last two are folded back to the front: the year and the quarter behind them,
# the work in their hands now, and the two queues still upstream that will reach
# them — which is what makes the table worth reading as a row rather than as
# five separate figures.
#
# Every group is one column, the rows behind its tikets, and every group is
# split the same way by jenis tabel — down the table into a line per kind rather
# than across it into columns, which is what lets all of them carry the split
# instead of only the first.
#
# `key` is the payload section, and the template renders the labels from this
# same list, so the header and the figures under it cannot drift apart.
#
# `lines` is the label as the header sets it: with one column under each group,
# the label is what decides how wide that column has to be, and the two finished
# queues are named at a length no column of figures needs. Broken where the name
# itself breaks — which queue, then how far back it reaches — they set two short
# lines instead of one long one and the columns come out even. `label` is the
# same words in one line, for everywhere the name is read rather than headed.
SUMMARY_SECTIONS = tuple(
    dict(section, label=' '.join(section['lines']))
    for section in (
        {'key': 'qc', 'lines': ('Proses QC',), 'variant': 'own'},
        {'key': 'p3de', 'lines': ('Masih di P3DE',), 'variant': 'upstream'},
        {'key': 'pide', 'lines': ('Masih di PIDE',), 'variant': 'upstream-alt'},
        {'key': 'selesai', 'lines': ('Selesai QC', '90 Hari Terakhir'),
         'variant': 'done'},
        {'key': 'selesai_tahun', 'lines': ('Selesai QC', '1 Tahun Terakhir'),
         'variant': 'done-alt'},
    )
)

# How many hues the jenis tabel lines cycle through before repeating one; see
# the .sq-kind-* rules in seksi_queue/list.html, which define exactly this many.
SUMMARY_KIND_HUES = 5

# What the table is ordered by when the page opens: the weighted load below,
# heaviest first. The first question a reader of this page has is who is
# carrying the most work, which alphabetical order answers for nobody.
SUMMARY_DEFAULT_SORT = 'beban'


# ---------------------------------------------------------------------------
# Indeks Beban — how heavy a PIC's load is, rather than how large
# ---------------------------------------------------------------------------
#
# The tiket count is deliberately absent from every term below. Quality control
# is done row by row, so one tiket of a million rows is a thousand tikets of a
# thousand, and every factor here multiplies baris data instead.
#
# What the factors say, in the order they are applied:
#
#   * jenis tabel — data that is identified is checked field by field, where
#     the rest is checked as a whole, so it weighs about twice as much;
#   * kategori wilayah — a regional ILAP is checked back against the unit that
#     sent it, which the wider ones are not;
#   * prioritas — data that was prioritas when it arrived is worked to a
#     tighter standard, so it counts half as much again;
#   * jatuh tempo — rows falling due within ten days press hardest, and the
#     press eases in the same bands the filter panel offers;
#   * which queue it sits in — see SECTION_WEIGHTS.
#
# These are ratios rather than measurements: they say a regional tiket is worth
# about one and a half international ones, which is a claim about the work that
# the seksi can argue with. They are gathered here to be argued with and edited,
# and nothing else in the page depends on their particular values.
JENIS_TABEL_WEIGHTS = {
    'Diidentifikasi': 1.0,
    'Tidak Diidentifikasi': 0.5,
    'Tidak Terstruktur': 0.5,
}

KATEGORI_WILAYAH_WEIGHTS = {
    'Regional': 1.0,
    'Nasional': 0.65,
    'Internasional': 0.65,
}

# A queue's weight is how much of a PIC's attention it has. What is in front of
# them now is the load they are actually carrying; what is at PIDE will reach
# them soon and what is at P3DE later still, so each is discounted by how far
# off it is. Finished work is behind them and counts least — it is in the score
# because a PIC who has just cleared a heavy quarter has been carrying that
# load, not because it is still theirs to do.
#
# The two finished queues overlap by construction, the quarter being part of the
# year, so work closed last week is counted under both weights and work closed
# ten months ago under the year's alone. That is the point of the pair rather
# than a fault in it: recent work counts for 0.15 + 0.05 and old work for 0.05,
# which is the score fading with age instead of dropping off a cliff at ninety
# days.
SECTION_WEIGHTS = {
    'qc': 1.0,
    'pide': 0.45,
    'p3de': 0.25,
    'selesai': 0.15,
    'selesai_tahun': 0.05,
}

# What a value none of the maps above names is worth — a reference row added
# since, or a tiket with none set. Half, so an unnamed kind is treated as the
# lighter sort of work rather than silently becoming the heaviest.
DEFAULT_ENTRY_WEIGHT = 0.5

PRIORITAS_WEIGHT = 1.5

# How much harder a deadline presses as it approaches. The bands are the filter
# panel's own thresholds — see JATUH_TEMPO_LIMITS — so the page asks one question
# about urgency and answers it the same way twice: what the dropdown will narrow
# to is what the score has already weighed.
#
# Read in order as `(hari, bobot)`: a tiket takes the first band its jatuh tempo
# falls under, and anything past the last threshold takes the default of 1. An
# overdue tiket's jatuh tempo is negative, so it falls under every band and takes
# the first — which is the dropdown's reading of "< 10 hari" too.
#
# This term applies to the QC queue alone. Only work a seksi is actually holding
# has a deadline of its own: an upstream tiket has not started its count, and a
# finished one is long past it. See SUMMARY_DEADLINES.
JATUH_TEMPO_WEIGHTS = tuple(zip(sq.JATUH_TEMPO_LIMITS, (2.0, 1.5, 1.2)))


def jatuh_tempo_bands():
    """The bands as the page names them, the last one being the default.

    Named from the thresholds rather than written out, so a threshold changed in
    JATUH_TEMPO_LIMITS renames the band it belongs to.
    """
    bands = []
    previous = None
    for days, weight in JATUH_TEMPO_WEIGHTS:
        label = f'Kurang dari {days} hari' if previous is None else f'{previous}–{days} hari'
        bands.append({'nama': label, 'bobot': weight})
        previous = days
    bands.append({'nama': f'Lebih dari {previous} hari', 'bobot': 1.0})
    return bands

# The queues whose rows carry a deadline this seksi is counted against. The rest
# are scored without the jatuh tempo term rather than with a guess at it.
SUMMARY_DEADLINES = {'qc': DEADLINE}


def summary_splits():
    """The dimensions a PIC's figures are broken into detail lines along.

    Two questions get asked of a load, and each is the same tikets counted a
    different way: what kind of table the data is, and how far the ILAP behind
    it reaches. They are listed one under the other rather than crossed with
    each other — a line per pairing would be the two of them multiplied, and
    nobody reads a load that way.
    """
    return [sq.jenis_tabel_split(), sq.kategori_wilayah_split()]


def _beban_info(splits):
    """The weights as the page explains them, read off the weights themselves.

    The panel behind the Indeks Beban column is built from this rather than
    written out in the template, so editing a weight above changes what the page
    says about itself. Entries no weight names are listed at the default, since
    that is what they are actually scored at.
    """
    named = {
        'jenis_tabel': JENIS_TABEL_WEIGHTS,
        'kategori_wilayah': KATEGORI_WILAYAH_WEIGHTS,
    }
    return {
        'faktor': [
            {
                'label': split.label,
                'bobot': [
                    {'nama': name,
                     'bobot': named.get(split.key, {}).get(name, DEFAULT_ENTRY_WEIGHT)}
                    for _entry_id, name in split.entries
                ],
            }
            for split in splits
        ],
        'antrean': [
            {'label': section['label'], 'bobot': SECTION_WEIGHTS[section['key']]}
            for section in SUMMARY_SECTIONS
        ],
        'jatuh_tempo': jatuh_tempo_bands(),
        'jatuh_tempo_antrean': ', '.join(
            section['label'] for section in SUMMARY_SECTIONS
            if section['key'] in SUMMARY_DEADLINES
        ),
        'prioritas': PRIORITAS_WEIGHT,
        'selesai_hari': SELESAI_WINDOW_DAYS,
        'selesai_tahun_hari': SELESAI_TAHUN_WINDOW_DAYS,
    }


def _entry_weights(splits):
    """The weight of every entry of every split, keyed the way a row reads them.

    The maps above are written by name, because that is what a reader arguing
    about them sees; the scoring reads ids, because that is what a row carries.
    This turns the one into the other, once per request.
    """
    by_split = {
        'jenis_tabel': JENIS_TABEL_WEIGHTS,
        'kategori_wilayah': KATEGORI_WILAYAH_WEIGHTS,
    }
    return [
        {
            entry_id: by_split.get(split.key, {}).get(name, DEFAULT_ENTRY_WEIGHT)
            for entry_id, name in split.entries
        }
        for split in splits
    ]


def _summary_sections(user, selected):
    """The queue behind each column group: what to read, how to count it, and
    how heavily its rows weigh.

    Jatuh tempo is dropped from every group but the QC queue itself: it counts
    from a transfer date that upstream work does not have yet and that finished
    work is long past, so keeping it would empty those groups rather than narrow
    them.

    The prioritas windows are read once here and shared by all four weightings,
    which is what keeps the score off the per-row query path.
    """
    outside_queue = sq.upstream_selected(selected)
    splits = summary_splits()
    weights = _entry_weights(splits)
    windows = sq.prioritas_windows()

    def weighting(key):
        return sq.Weighting(
            SECTION_WEIGHTS[key], weights, DEFAULT_ENTRY_WEIGHT,
            PRIORITAS_WEIGHT, windows,
            deadline=SUMMARY_DEADLINES.get(key),
            jatuh_tempo_weights=JATUH_TEMPO_WEIGHTS,
        )

    def upstream(key, statuses):
        return (
            sq.apply_filters(
                _upstream_queryset(user, statuses), outside_queue, FILTER_APPLIERS,
            ),
            splits,
            sq.BARIS_DATA_FIELDS,
            sq.baris_data,
            weighting(key),
        )

    # The two finished columns are one queue read over two windows, the narrower
    # one inside the wider, so they differ in nothing but how far back they
    # reach.
    def finished(key, days):
        return (
            sq.apply_filters(
                _selesai_queryset(user, days), outside_queue, FILTER_APPLIERS,
            ),
            splits,
            ('sudah_qc',),
            _sudah_qc,
            weighting(key),
        )

    return {
        'qc': (
            sq.apply_filters(_scoped_queryset(user), selected, FILTER_APPLIERS),
            splits,
            ('belum_qc',),
            _belum_qc,
            weighting('qc'),
        ),
        'p3de': upstream('p3de', STATUSES_DI_P3DE),
        'pide': upstream('pide', STATUSES_DI_PIDE),
        'selesai': finished('selesai', SELESAI_WINDOW_DAYS),
        'selesai_tahun': finished('selesai_tahun', SELESAI_TAHUN_WINDOW_DAYS),
    }


def _summary(user, selected):
    """The summary table above the chart, over the same filters the chart uses.

    One line per PIC PMDE — whoever the filter panel has left in the sections,
    rather than the whole seksi — carrying every queue side by side, so a
    reader sees at once how much of each is that person's. The totals come back
    under the section keys they have always used, which is the line under the
    table.
    """
    rows, totals = sq.pic_summary(
        _summary_sections(user, selected), TiketPIC.Role.PMDE,
        pic_profil_visibility(user), no_pic_label='Tanpa PIC PMDE',
    )
    return dict(totals, rows=rows)


def _chart_data(scoped, selected):
    """Jml Progress — the rows left to check — per jatuh tempo, per PIC PMDE."""
    return sq.chart_data(
        scoped, selected, FILTER_APPLIERS, DEADLINE, TiketPIC.Role.PMDE,
        no_pic_label='Tanpa PIC PMDE',
        progress_fields=('belum_qc',), progress_of=_belum_qc,
    )


@login_required
@user_passes_test(_is_pmde_user)
@require_http_methods(["POST", "GET"])
@csrf_protect
def quality_control_data(request):
    """DataTables server-side endpoint for Quality Control page.

    With ``get_filter_options=1`` it returns the option lists for the filter
    panel, with ``get_summary=1`` the figures for the tiles above the chart, and
    with ``get_chart_data=1`` the series behind the chart itself; every other
    request returns a page of rows. All of them read the same filter parameters,
    so the panel scopes the tiles, the chart and the table together.
    """
    params = request.POST if request.method == 'POST' else request.GET

    scoped = _scoped_queryset(request.user)
    selected = sq.selected_filters(params, FILTER_APPLIERS)

    if params.get('get_filter_options'):
        return JsonResponse({
            'filter_options': sq.filter_options(scoped, selected, FILTER_APPLIERS),
        })

    if params.get('get_summary'):
        return JsonResponse(_summary(request.user, selected))

    if params.get('get_chart_data'):
        return JsonResponse(_chart_data(scoped, selected))

    draw = int(params.get('draw', '1'))
    start = int(params.get('start', '0'))
    length = int(params.get('length', '10'))

    records_total = scoped.count()

    tikets = DEADLINE.annotate_durasi(
        sq.apply_filters(scoped, selected, FILTER_APPLIERS).select_related(
            f'{sq.ILAP}',
            f'{sq.SUB}__id_jenis_tabel',
        ).prefetch_related(
            Prefetch('tiketpic_set', queryset=TiketPIC.objects.select_related('id_user')),
        ).annotate(
            tgl_transfer_date=Cast('tgl_transfer', DateField()),
            tgl_rematch_date=Cast('tgl_rematch', DateField()),
        )
    ).annotate(
        is_prioritas=sq.prioritas_exists(),
        # The deadline itself, so the column can be sorted in SQL rather than
        # recomputed per page.
        deadline_date=DEADLINE.deadline_date_expr(),
    )

    records_filtered = tikets.count()

    # ---- Server-side sorting ----
    # Columns 2, 3 and 4 each stack two values in one cell — nomor tiket over
    # sub jenis data, nama ILAP over jenis tabel, tgl transfer over tgl rematch.
    # Each sorts by the line the cell leads with, which is also the one the
    # header names first, then falls back to its second line so the sort is not
    # left as a coarse grouping. Nomor tiket is unique, so it needs no fallback.
    order_map = {
        0: (f'{sq.SUB}__nama_tabel_I',),
        1: ('id',),
        2: ('nomor_tiket',),
        3: (f'{sq.ILAP}__nama_ilap', f'{sq.SUB}__id_jenis_tabel__deskripsi'),
        4: ('tgl_transfer_date', 'tgl_rematch_date'),
        5: ('deadline_date',),
        # Jatuh tempo is the deadline counted from today, so it sorts the same way.
        6: ('deadline_date',),
        7: ('is_prioritas',),
        8: ('baris_i',),
        9: ('sudah_qc',),
        10: ('belum_qc',),
    }

    # Read sort column and direction from DataTables params
    order_col_index = params.get('order[0][column]')
    order_dir = params.get('order[0][dir]', 'asc')

    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            cols = order_map.get(idx, ('id',))
            if order_dir == 'desc':
                cols = tuple('-' + col for col in cols)
            tikets = tikets.order_by(*cols)
        except (ValueError, TypeError):
            tikets = tikets.order_by('-id')
    else:
        tikets = tikets.order_by('-id')

    page = list(tikets[start:start + length])

    # Resolved once for the whole page: whether a PIC name is a link depends on
    # who is reading, and the rule costs a query to work out.
    can_view = pic_profil_visibility(request.user)

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
            # Linked to the Profil PIC page, like every other name in the app:
            # the reader of a QC queue often wants the rest of that person's
            # load, not just the row in front of them.
            pic_pmde_name = pic_profil_link(pic_pmde.id_user, can_view)

        row = {
            'nama_tabel': sub_jenis_data.nama_tabel_I or '',
            'pic_pmde': pic_pmde_name,
            'nomor_tiket': tiket.nomor_tiket,
            'nama_ilap': ilap.nama_ilap if ilap else '',
            'sub_jenis_data': sub_jenis_data.nama_sub_jenis_data or '',
            'jenis_tabel': jenis_tabel.deskripsi if jenis_tabel else '',
            'tgl_transfer': {
                'display': tiket.tgl_transfer.strftime('%d/%m/%Y') if tiket.tgl_transfer else '-',
                'sort': tiket.tgl_transfer.strftime('%Y-%m-%d') if tiket.tgl_transfer else '',
            },
            'tgl_rematch': {
                'display': tiket.tgl_rematch.strftime('%d/%m/%Y') if tiket.tgl_rematch else '-',
                'sort': tiket.tgl_rematch.strftime('%Y-%m-%d') if tiket.tgl_rematch else '',
            },
            'prioritas': 'Ya' if tiket.is_prioritas else 'Tidak',
            'jml_baris_i': tiket.baris_i or 0,
            'jml_selesai': tiket.sudah_qc or 0,
            'jml_progress': tiket.belum_qc or 0,
            'action': f'<a href="{reverse("tiket_detail", args=[tiket.id])}" class="btn btn-sm btn-primary" title="Lihat Detail"><i class="feather-eye"></i></a>',
        }
        # Deadline, jatuh tempo and the sisa_hari the frontend colours the row
        # by, all counted from the durasi annotated above.
        row.update(DEADLINE.cells(tiket))
        data.append(row)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data
    })
