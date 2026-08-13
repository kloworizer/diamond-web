"""Identifikasi page - PIDE User identification queue.

This module provides a page for PIDE users to view and monitor tickets that are
in the identification process (status = Identifikasi). It is the Quality Control
page read by the other seksi: the same filter panel, summary sections, chart and
table, built by `seksi_queue`.

What is decided here is that the queue is PIDE's, that its deadline counts from
the day the tiket reached PIDE — or from the day identification started, once
that date is set — and that the work left on a row is the rows of its data that
identification has not split yet.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.db.models import DateField, F, Prefetch, Value
from django.db.models.functions import Cast, Coalesce, Greatest

from . import seksi_queue as sq
from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUSES_DI_P3DE,
)
from ..utils.pic_profil import pic_profil_link, pic_profil_visibility
from .mixins import is_kasi_pide

__all__ = ['IdentifikasiView', 'identifikasi_data']


# A tiket enters PIDE's queue when P3DE sends it (tgl_kirim_pide) and its count
# starts again when identification is opened on it (tgl_rekam_pide), so the
# later date wins whenever it is set — the same shape PMDE's transfer and
# rematch have.
DEADLINE = sq.Deadline(
    seksi='user_pide', start_field='tgl_kirim_pide', restart_field='tgl_rekam_pide',
)

FILTER_APPLIERS = sq.build_filter_appliers(DEADLINE)


def jatuh_tempo_ids(qs, limit):
    """Ids of the tikets in `qs` falling due within `limit` days, PIDE's count."""
    return DEADLINE.jatuh_tempo_ids(qs, limit)


def _is_pide_user(user):
    """Check if user is PIDE user, admin or the PIDE supervisor (kasi)."""
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pide', 'admin', 'admin_pide', 'kasi_pide']
    ).exists()


class IdentifikasiView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display the Identifikasi page for PIDE users.

    Shows a DataTable of the tikets the current PIDE user is identifying
    (status = Identifikasi), with the deadline PIDE has for each of them.

    Template: identifikasi/list.html
    """
    template_name = 'identifikasi/list.html'

    def test_func(self):
        """Verify user is PIDE user or admin."""
        return _is_pide_user(self.request.user)


def _pide_scope(tikets, user):
    """Narrow `tikets` to what `user` is allowed to see as PIDE."""
    return sq.pic_scope(tikets, user, TiketPIC.Role.PIDE, is_kasi_pide)


def _scoped_queryset(user):
    """Tikets being identified that `user` is allowed to see."""
    return _pide_scope(Tiket.objects.filter(status_tiket=STATUS_IDENTIFIKASI), user)


def _upstream_queryset(user, statuses):
    """Tikets in `statuses` that `user` is allowed to see, for the two upstream
    sections of the summary.

    The same scope as the page's own queue, over the statuses upstream of
    identification instead. A PIDE PIC is assigned when a tiket is recorded
    rather than when it is sent on (see rekam_tiket), so a pelaksana already has
    assignments among these: they are the work heading towards them, which is
    what makes them worth a section on this page.
    """
    return _pide_scope(Tiket.objects.filter(status_tiket__in=statuses), user)


def _belum_identifikasi(baris_lengkap, baris_i, baris_u, baris_cde, baris_res):
    """The rows of a tiket's data that identification has not split yet.

    Identification takes the one count P3DE recorded — baris lengkap — and
    splits it into I, U, CDE and Res, so what is left to identify is the part of
    that count the split has not reached. The figure is floored at zero: a split
    that already exceeds baris lengkap means the counts disagree, which is not
    negative work left.

    The table's own rows take this figure from the `baris_belum` annotation,
    which is this same rule in SQL so the column can be sorted before paging;
    the summary and the chart, which read whole queues, use it from here.
    """
    identified = (baris_i or 0) + (baris_u or 0) + (baris_cde or 0) + (baris_res or 0)
    return max((baris_lengkap or 0) - identified, 0)


# The columns `_belum_identifikasi` reads, in the order it takes them.
_BELUM_IDENTIFIKASI_FIELDS = (
    'baris_lengkap', 'baris_i', 'baris_u', 'baris_cde', 'baris_res',
)


def _summary(user, selected):
    """The three sections above the chart, over the same filters the chart uses.

    The first is the identification queue this page lists, counting the rows it
    has left to split. The other two are the queues upstream of it: the tikets
    PIDE has received but not opened yet, and the ones P3DE is still holding.
    All three read the same shape — a tiket total, a row total and a
    per-jenis-tabel breakdown — so they can be read against each other down the
    row.
    """
    upstream_selected = sq.upstream_selected(selected)
    kinds = sq.jenis_tabel_kinds()

    def upstream(statuses):
        return sq.queue_breakdown(
            sq.apply_filters(
                _upstream_queryset(user, statuses), upstream_selected, FILTER_APPLIERS,
            ),
            kinds, sq.BARIS_DATA_FIELDS, sq.baris_data,
        )

    return {
        'identifikasi': sq.queue_breakdown(
            sq.apply_filters(_scoped_queryset(user), selected, FILTER_APPLIERS),
            kinds, _BELUM_IDENTIFIKASI_FIELDS, _belum_identifikasi,
        ),
        'dikirim_ke_pide': upstream((STATUS_DIKIRIM_KE_PIDE,)),
        'p3de': upstream(STATUSES_DI_P3DE),
    }


def _chart_data(scoped, selected):
    """Jml Progress — the rows left to identify — per jatuh tempo, per PIC PIDE."""
    return sq.chart_data(
        scoped, selected, FILTER_APPLIERS, DEADLINE, TiketPIC.Role.PIDE,
        no_pic_label='Tanpa PIC PIDE',
        progress_fields=_BELUM_IDENTIFIKASI_FIELDS, progress_of=_belum_identifikasi,
    )


@login_required
@user_passes_test(_is_pide_user)
@require_http_methods(["POST", "GET"])
@csrf_protect
def identifikasi_data(request):
    """DataTables server-side endpoint for the Identifikasi page.

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
            tgl_kirim_pide_date=Cast('tgl_kirim_pide', DateField()),
            tgl_rekam_pide_date=Cast('tgl_rekam_pide', DateField()),
        )
    ).annotate(
        is_prioritas=sq.prioritas_exists(),
        # The deadline itself, so the column can be sorted in SQL rather than
        # recomputed per page.
        deadline_date=DEADLINE.deadline_date_expr(),
        # The last two columns are derived rather than stored, so they get the
        # same rule `_belum_identifikasi` applies, written once more in SQL —
        # sorting a page of rows by a figure computed after paging would sort
        # the wrong rows.
        baris_belum=Greatest(
            Coalesce('baris_lengkap', Value(0)) - (
                Coalesce('baris_i', Value(0)) + Coalesce('baris_u', Value(0))
                + Coalesce('baris_cde', Value(0)) + Coalesce('baris_res', Value(0))
            ),
            Value(0),
        ),
    ).annotate(
        baris_selesai=Coalesce('baris_lengkap', Value(0)) - F('baris_belum'),
    )

    records_filtered = tikets.count()

    # ---- Server-side sorting ----
    # Columns 2, 3 and 4 each stack two values in one cell — nomor tiket over
    # sub jenis data, nama ILAP over jenis tabel, tgl kirim over tgl rekam. Each
    # sorts by the line the cell leads with, which is also the one the header
    # names first, then falls back to its second line so the sort is not left as
    # a coarse grouping. Nomor tiket is unique, so it needs no fallback.
    order_map = {
        0: (f'{sq.SUB}__nama_tabel_I',),
        1: ('id',),
        2: ('nomor_tiket',),
        3: (f'{sq.ILAP}__nama_ilap', f'{sq.SUB}__id_jenis_tabel__deskripsi'),
        4: ('tgl_kirim_pide_date', 'tgl_rekam_pide_date'),
        5: ('deadline_date',),
        # Jatuh tempo is the deadline counted from today, so it sorts the same way.
        6: ('deadline_date',),
        7: ('is_prioritas',),
        8: ('baris_lengkap',),
        9: ('baris_selesai',),
        10: ('baris_belum',),
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

        # Get PIC PIDE name from the prefetched assignments
        pic_pide = next(
            (pic for pic in tiket.tiketpic_set.all()
             if pic.role == TiketPIC.Role.PIDE and pic.active and pic.id_user),
            None,
        )
        pic_pide_name = ''
        if pic_pide:
            # Linked to the Profil PIC page, like every other name in the app:
            # the reader of this queue often wants the rest of that person's
            # load, not just the row in front of them.
            pic_pide_name = pic_profil_link(pic_pide.id_user, can_view)

        row = {
            'nama_tabel': sub_jenis_data.nama_tabel_I or '',
            'pic_pide': pic_pide_name,
            'nomor_tiket': tiket.nomor_tiket,
            'nama_ilap': ilap.nama_ilap if ilap else '',
            'sub_jenis_data': sub_jenis_data.nama_sub_jenis_data or '',
            'jenis_tabel': jenis_tabel.deskripsi if jenis_tabel else '',
            'tgl_kirim_pide': {
                'display': tiket.tgl_kirim_pide.strftime('%d/%m/%Y') if tiket.tgl_kirim_pide else '-',
                'sort': tiket.tgl_kirim_pide.strftime('%Y-%m-%d') if tiket.tgl_kirim_pide else '',
            },
            'tgl_rekam_pide': {
                'display': tiket.tgl_rekam_pide.strftime('%d/%m/%Y') if tiket.tgl_rekam_pide else '-',
                'sort': tiket.tgl_rekam_pide.strftime('%Y-%m-%d') if tiket.tgl_rekam_pide else '',
            },
            'prioritas': 'Ya' if tiket.is_prioritas else 'Tidak',
            'jml_baris_lengkap': tiket.baris_lengkap or 0,
            # Read off the annotations rather than recomputed here, so the
            # figure shown is the one the column was sorted by.
            'jml_selesai': tiket.baris_selesai,
            'jml_progress': tiket.baris_belum,
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
