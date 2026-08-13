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

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.db.models import DateField, Prefetch
from django.db.models.functions import Cast

from . import seksi_queue as sq
from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..constants.tiket_status import (
    STATUS_PENGENDALIAN_MUTU,
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
        """Add the header of the summary table.

        Its sub columns are the jenis tabel of the reference table, which the
        page cannot spell out in its markup — a jenis tabel added there has to
        appear as a column here, exactly as it appears in every breakdown the
        endpoint sends back. The endpoint reads the same list in the same order,
        so a line of figures lands under the heading it belongs to.
        """
        context = super().get_context_data(**kwargs)
        kinds = [
            # `hue` is the palette slot the column is drawn in, assigned by
            # position and wrapping after the palette runs out — see the
            # .sq-kind-* rules. Decided here rather than in the template because
            # the template language has no modulo.
            {'name': deskripsi, 'hue': index % SUMMARY_KIND_HUES}
            for index, (_kind_id, deskripsi) in enumerate(sq.jenis_tabel_kinds())
        ]
        context.update({
            'summary_sections': SUMMARY_SECTIONS,
            'summary_kinds': kinds,
            # Tiket and Baris Data, then one column per jenis tabel.
            'summary_colspan': len(kinds) + 2,
            'summary_section_keys': ','.join(
                section['key'] for section in SUMMARY_SECTIONS
            ),
            'summary_section_variants': ','.join(
                section['variant'] for section in SUMMARY_SECTIONS
            ),
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


def _belum_qc(belum_qc):
    """The row count a tiket in quality control still has left to check."""
    return belum_qc or 0


# The three column groups of the summary table, in the order it renders them:
# the QC queue this page lists, then the two queues upstream of it, kept apart
# because they are different work — P3DE still holds one count of a tiket's
# data, while PIDE has begun splitting it.
#
# Only this page's own queue is split by jenis tabel. That split says how a
# tiket's data is handled, which is the question a reader has about work that is
# in front of them now; for the two upstream queues the question is only how
# much is coming, so they are the tiket and row totals and nothing more — three
# groups of five columns each would bury the queue that is actually theirs.
#
# `key` is the payload section, and the template renders the labels and the
# column widths from this same list, so the header and the figures under it
# cannot drift apart.
SUMMARY_SECTIONS = (
    {'key': 'qc', 'label': 'Pengendalian Mutu', 'variant': 'own', 'kinds': True},
    {'key': 'p3de', 'label': 'Masih di P3DE', 'variant': 'upstream', 'kinds': False},
    {'key': 'pide', 'label': 'Masih di PIDE', 'variant': 'upstream-alt', 'kinds': False},
)

# How many hues the jenis tabel columns cycle through before repeating one; see
# the .sq-kind-* rules in seksi_queue/list.html, which define exactly this many.
SUMMARY_KIND_HUES = 5


def _summary_sections(user, selected):
    """The queue behind each column group: what to read, and how to count it."""
    upstream_selected = sq.upstream_selected(selected)

    def upstream(statuses):
        return (
            sq.apply_filters(
                _upstream_queryset(user, statuses), upstream_selected, FILTER_APPLIERS,
            ),
            # No jenis tabel columns, so nothing to split by.
            (),
            sq.BARIS_DATA_FIELDS,
            sq.baris_data,
        )

    return {
        'qc': (
            sq.apply_filters(_scoped_queryset(user), selected, FILTER_APPLIERS),
            sq.jenis_tabel_kinds(),
            ('belum_qc',),
            _belum_qc,
        ),
        'p3de': upstream(STATUSES_DI_P3DE),
        'pide': upstream(STATUSES_DI_PIDE),
    }


def _summary(user, selected):
    """The summary table above the chart, over the same filters the chart uses.

    One line per PIC PMDE — whoever the filter panel has left in the sections,
    rather than the whole seksi — carrying all three queues side by side, so a
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
