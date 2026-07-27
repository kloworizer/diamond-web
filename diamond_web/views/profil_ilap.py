from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.http import Http404, JsonResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.dateformat import format as date_format
from django.utils.html import escape
from datetime import datetime

from ..constants.tiket_status import STATUS_BADGE_CLASSES, STATUS_LABELS
from ..models.ilap import ILAP
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.pic import PIC
from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..utils import format_periode
from .mixins import UserP3DERequiredMixin, is_admin_p3de, is_kasi

__all__ = [
    'ProfilILAPListView',
    'ProfilILAPDetailView',
    'JenisDataILAPProfilView',
    'jenis_data_ilap_tiket_data',
    'navbar_search',
]


# Number of reporting periods contained in a single year, keyed by the
# `periode_penerimaan` label of the related PeriodePengiriman row.
PERIODE_PENERIMAAN_PER_YEAR = {
    'bulanan': 12,
    'triwulanan': 4,
    'triwulan': 4,
    'semesteran': 2,
    'semester': 2,
    'tahunan': 1,
}
DEFAULT_PERIODE_PER_YEAR = 12


def get_periode_per_year(periode_penerimaan):
    """Return how many periods a year holds for a `periode_penerimaan` label.

    Args:
        periode_penerimaan (str): Reception period label, e.g. ``Bulanan``.

    Returns:
        int: Number of periods in one year (12 for monthly, 4 for quarterly,
        2 for semesterly, 1 for yearly). Unknown labels fall back to 12.
    """
    return PERIODE_PENERIMAAN_PER_YEAR.get(
        (periode_penerimaan or '').strip().lower(), DEFAULT_PERIODE_PER_YEAR
    )


def get_periode_for_year(periode_list, year):
    """Pick the PeriodeJenisData row that applies to a given year.

    Args:
        periode_list (list): PeriodeJenisData rows ordered by ``start_date``.
        year (int): The calendar year to resolve.

    Returns:
        PeriodeJenisData: The row whose active range covers `year`, the latest
        row that started on or before `year` otherwise, or the first row when
        `year` predates every row.
    """
    covering = [
        p for p in periode_list
        if p.start_date.year <= year and (p.end_date is None or p.end_date.year >= year)
    ]
    if covering:
        return covering[-1]
    started = [p for p in periode_list if p.start_date.year <= year]
    return started[-1] if started else periode_list[0]


def build_jenis_data_year_summary(jenis_data, current_year):
    """Summarise a JenisDataILAP row for the profil ILAP year matrix.

    The displayed years span from the earliest ``start_date`` in
    `periode_jenis_data` up to the latest ``end_date`` year, or the current
    year when the period is still open. Each year cell reports how many
    tikets were recorded against the expected number of periods for that
    year (e.g. ``7/12`` for a monthly reception period).

    Args:
        jenis_data (JenisDataILAP): The sub jenis data row to summarise.
        current_year (int): Year used as the upper bound for open periods.

    Returns:
        dict: Summary with ``jenis_data``, ``dasar_hukum``, ``periode_label``,
        ``periode_list``, ``years`` and ``year_data`` keys, or ``None`` when the
        sub jenis data has no periode_jenis_data rows.
    """
    periode_list = list(
        PeriodeJenisData.objects
        .filter(id_sub_jenis_data_ilap=jenis_data)
        .select_related('id_periode_pengiriman')
        .order_by('start_date')
    )
    if not periode_list:
        return None

    start_year = min(p.start_date.year for p in periode_list)
    end_year = max(p.end_date.year if p.end_date else current_year for p in periode_list)
    years = list(range(start_year, max(start_year, end_year) + 1))

    dasar_hukum = ', '.join(
        k.id_klasifikasi_tabel.deskripsi
        for k in KlasifikasiJenisData.objects
        .filter(id_sub_jenis_data=jenis_data)
        .select_related('id_klasifikasi_tabel')
    )

    # De-duplicate while preserving order: a sub jenis data can change its
    # periode pengiriman over time but often repeats the same combination.
    periode_label = ' / '.join(dict.fromkeys(
        f'{p.id_periode_pengiriman.periode_penyampaian} - {p.id_periode_pengiriman.periode_penerimaan}'
        for p in periode_list
    ))

    year_data = {}
    for year in years:
        periode = get_periode_for_year(periode_list, year)
        total = get_periode_per_year(periode.id_periode_pengiriman.periode_penerimaan)
        count = Tiket.objects.filter(id_periode_data=periode, tahun=year).count()
        year_data[year] = {
            'count': count,
            'total': total,
            'label': f'{count}/{total}',
            'complete': count >= total,
        }

    return {
        'jenis_data': jenis_data,
        'dasar_hukum': dasar_hukum,
        'periode_label': periode_label,
        'periode_list': periode_list,
        'years': years,
        'year_data': year_data,
    }


class ProfilILAPListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for ILAP profiles with basic information."""
    template_name = 'profil_ilap/list.html'

    def get_context_data(self, **kwargs):
        """Add additional context data for the ILAP list view.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
                context data.

        Returns:
            dict: Template context data including any additional variables
                for rendering the page.
        """
        context = super().get_context_data(**kwargs)
        return context

    def render_to_response(self, context, **response_kwargs):
        """Render the response, returning JSON for AJAX requests or HTML otherwise.

        If the request is an AJAX request (``XMLHttpRequest``) or the
        ``format`` parameter is ``json``, returns a JSON response for
        DataTables integration. Otherwise delegates to the parent class.

        Args:
            context (dict): The template context data.
            **response_kwargs: Additional keyword arguments for the response.

        Returns:
            JsonResponse: If the request expects JSON data.
            django.http.HttpResponse: The rendered HTML template otherwise.
        """
        # Check if request wants JSON data (for DataTables)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or self.request.GET.get('format') == 'json':
            return self.get_data_json()
        return super().render_to_response(context, **response_kwargs)

    def get_data_json(self):
        """Build and return a JSON response for DataTables server-side processing.

        Handles pagination, global search, per-column filtering, ordering,
        and record counts required by the DataTables jQuery plugin.

        Returns:
            JsonResponse: A JSON object containing:
                - draw (int): Echoes the draw parameter from the request.
                - recordsTotal (int): Total records before filtering.
                - recordsFiltered (int): Total records after filtering.
                - data (list): Paginated list of ILAP row dictionaries.
        """
        draw = int(self.request.GET.get('draw', 1))
        start = int(self.request.GET.get('start', 0))
        length = int(self.request.GET.get('length', 10))
        search_value = self.request.GET.get('search[value]', '').strip()

        # Column order mapping
        order_columns = {
            0: 'id_ilap',
            1: 'id_kategori__nama_kategori',
            2: 'nama_ilap',
            3: 'id_kategori_wilayah__deskripsi',
        }

        # Base queryset
        base_qs = ILAP.objects.all().select_related(
            'id_kategori',
            'id_kategori_wilayah',
        ).prefetch_related(
            'ilap_kpp_relations__id_kpp',
        )

        # Total records (without filtering)
        records_total = base_qs.count()

        # Apply global search
        if search_value:
            global_filter = Q(id_ilap__icontains=search_value) | \
                            Q(nama_ilap__icontains=search_value) | \
                            Q(id_kategori__nama_kategori__icontains=search_value) | \
                            Q(id_kategori_wilayah__deskripsi__icontains=search_value)
            base_qs = base_qs.filter(global_filter)

        # Apply individual column searches (sent via custom parameters)
        for i in range(4):  # columns 0-3
            col_search = self.request.GET.get(f'columns[{i}][search][value]', '').strip()
            if col_search:
                col_map = {
                    0: Q(id_ilap__icontains=col_search),
                    1: Q(id_kategori__nama_kategori__icontains=col_search),
                    2: Q(nama_ilap__icontains=col_search),
                    3: Q(id_kategori_wilayah__deskripsi__icontains=col_search),
                }
                base_qs = base_qs.filter(col_map.get(i, Q()))

        # Records after filtering
        records_filtered = base_qs.count()

        # Apply ordering
        order_column_idx = self.request.GET.get('order[0][column]')
        order_dir = self.request.GET.get('order[0][dir]', 'asc')
        if order_column_idx is not None:
            order_col = order_columns.get(int(order_column_idx))
            if order_col:
                if order_dir == 'desc':
                    order_col = f'-{order_col}'
                base_qs = base_qs.order_by(order_col)
        else:
            base_qs = base_qs.order_by('id_ilap')

        # Apply pagination
        ilaps = base_qs[start:start + length]

        # Build data rows
        data = []
        for ilap in ilaps:
            data.append({
                'id_ilap': ilap.id_ilap,
                'kategori': ilap.id_kategori.nama_kategori if ilap.id_kategori else '---',
                'nama': ilap.nama_ilap,
                'wilayah': ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else '---',
                'actions': f'<a href="/profil-ilap/{ilap.id_ilap}/" class="btn btn-sm btn-primary"><i class="feather-eye me-1"></i>Detail</a>'
            })

        return JsonResponse({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
        })


class ProfilILAPDetailView(LoginRequiredMixin, UserP3DERequiredMixin, DetailView):
    """Detail view for ILAP profile, keyed by the business `id_ilap` code."""
    model = ILAP
    template_name = 'profil_ilap/detail.html'
    context_object_name = 'ilap'

    def get_queryset(self):
        """Return the ILAP queryset with the relations used by the template."""
        return ILAP.objects.select_related(
            'id_kategori', 'id_kategori_wilayah'
        ).prefetch_related('ilap_kpp_relations__id_kpp')

    def get_object(self, queryset=None):
        """Look the ILAP up by its `id_ilap` code instead of its primary key.

        Args:
            queryset (QuerySet, optional): Base queryset to search in.

        Returns:
            ILAP: The matching ILAP instance.

        Raises:
            Http404: When no ILAP carries the requested `id_ilap` code.
        """
        queryset = self.get_queryset() if queryset is None else queryset
        ilap = queryset.filter(id_ilap=self.kwargs['id_ilap']).first()
        if ilap is None:
            raise Http404(f"ILAP dengan ID {self.kwargs['id_ilap']} tidak ditemukan.")
        return ilap

    def get_context_data(self, **kwargs):
        """Add the Jenis Data ILAP matrix for this ILAP.

        Each row covers one sub jenis data and reports, per year, the number
        of recorded tikets against the expected number of periods for that
        year. Years run from the earliest `periode_jenis_data` start date up
        to the end date year, or the current year while the period is open.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
                context data.

        Returns:
            dict: Template context containing:
                - ilap (ILAP): The current ILAP object.
                - jenis_data_details (list): One summary dict per sub jenis data.
                - years (list): Union of every row's years, used as the header.
        """
        context = super().get_context_data(**kwargs)
        current_year = datetime.now().year

        jenis_data_list = JenisDataILAP.objects.filter(
            id_ilap=self.object
        ).select_related('id_jenis_tabel', 'id_status_data').order_by('id_sub_jenis_data')

        jenis_data_details = []
        years = set()
        for jenis_data in jenis_data_list:
            detail = build_jenis_data_year_summary(jenis_data, current_year)
            if detail is None:
                continue
            years.update(detail['years'])
            jenis_data_details.append(detail)

        context['jenis_data_details'] = jenis_data_details
        context['years'] = sorted(years)

        return context


class JenisDataILAPProfilView(LoginRequiredMixin, UserP3DERequiredMixin, DetailView):
    """Profile page for a single sub jenis data, keyed by `id_sub_jenis_data`."""
    model = JenisDataILAP
    template_name = 'profil_ilap/jenis_data_detail.html'
    context_object_name = 'jenis_data'

    def get_queryset(self):
        """Return the JenisDataILAP queryset with the relations the page needs."""
        return JenisDataILAP.objects.select_related(
            'id_ilap', 'id_ilap__id_kategori', 'id_jenis_tabel', 'id_status_data'
        )

    def get_object(self, queryset=None):
        """Look the sub jenis data up by its `id_sub_jenis_data` code.

        Args:
            queryset (QuerySet, optional): Base queryset to search in.

        Returns:
            JenisDataILAP: The matching sub jenis data instance.

        Raises:
            Http404: When no row carries the requested `id_sub_jenis_data`.
        """
        queryset = self.get_queryset() if queryset is None else queryset
        jenis_data = queryset.filter(
            id_sub_jenis_data=self.kwargs['id_sub_jenis_data']
        ).first()
        if jenis_data is None:
            raise Http404(
                f"Sub Jenis Data {self.kwargs['id_sub_jenis_data']} tidak ditemukan."
            )
        return jenis_data

    def get_context_data(self, **kwargs):
        """Add periods, legal bases, PIC assignments and tikets for this sub jenis data.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
                context data.

        Returns:
            dict: Template context containing:
                - jenis_data (JenisDataILAP): The current sub jenis data.
                - summary (dict|None): Year matrix from
                  :func:`build_jenis_data_year_summary`.
                - years (list): Years covered by the summary.
                - dasar_hukum_list (list): Related DasarHukum rows.
                - periode_list (list): Related PeriodeJenisData rows.
                - pic_groups (list): PIC assignments grouped by tipe.
                - tiket_total (int): Number of tikets recorded for this sub
                  jenis data. The rows themselves are loaded server-side by
                  :func:`jenis_data_ilap_tiket_data`.
        """
        context = super().get_context_data(**kwargs)
        jenis_data = self.object
        current_year = datetime.now().year

        summary = build_jenis_data_year_summary(jenis_data, current_year)
        context['summary'] = summary
        context['years'] = summary['years'] if summary else []
        context['periode_list'] = summary['periode_list'] if summary else []

        context['dasar_hukum_list'] = [
            k.id_klasifikasi_tabel
            for k in KlasifikasiJenisData.objects
            .filter(id_sub_jenis_data=jenis_data)
            .select_related('id_klasifikasi_tabel')
        ]

        pics = PIC.objects.filter(
            id_sub_jenis_data_ilap=jenis_data
        ).select_related('id_user').order_by('tipe', '-start_date')
        context['pic_groups'] = [
            {'tipe': tipe, 'label': label, 'pics': [p for p in pics if p.tipe == tipe]}
            for tipe, label in PIC.TipePIC.choices
        ]

        context['tiket_total'] = Tiket.objects.filter(
            id_periode_data__id_sub_jenis_data_ilap=jenis_data
        ).count()

        return context


def _can_view_profil_ilap(user):
    """Return True when `user` may read profil ILAP pages and their data."""
    return user.groups.filter(name__in=['admin', 'admin_p3de', 'user_p3de']).exists()


def _can_open_tiket(user, tiket):
    """Return True when `user` may open `tiket`'s detail page.

    Mirrors the rule enforced by `TiketDetailView.get_object`: admins (global
    and P3DE) and kasi may open any tiket, everyone else needs a TiketPIC
    assignment on it.
    """
    if is_admin_p3de(user) or is_kasi(user):
        return True
    return TiketPIC.objects.filter(id_tiket=tiket, id_user=user).exists()


@login_required
def navbar_search(request):
    """Resolve a header search term to an ILAP, sub jenis data or tiket page.

    Used by the navbar search box before it falls back to looking the term up
    as a nomor tiket through the tiket list endpoint. Matching is exact but
    case-insensitive, so ``BI001`` resolves to the ILAP profile, ``BI0010101``
    to the sub jenis data page and a full nomor tiket to the tiket detail page.
    Users without access to the profil ILAP pages get no ILAP/jenis data match,
    which leaves them on the nomor tiket path.

    The nomor tiket branch exists for Admin P3DE: they may correct the isian of
    any tiket but the tiket list endpoint only ever shows them the tikets they
    are a PIC for, so an exact nomor tiket is their way in. It is scoped to the
    tikets the user may actually open, so it never widens anyone else's reach —
    for other roles it simply short-circuits the lookup they would otherwise do
    against the tiket list endpoint.

    Args:
        request (HttpRequest): The current request; the term is read from the
            ``q`` query parameter.

    Returns:
        JsonResponse: ``{'match': None}`` when nothing matched, otherwise
        ``{'match': 'ilap'|'jenis_data'|'tiket', 'url': str, 'label': str}``.
    """
    term = request.GET.get('q', '').strip()
    if not term:
        return JsonResponse({'match': None})

    if _can_view_profil_ilap(request.user):
        # Sub jenis data codes are the more specific of the two, so check them
        # first even though the ID lengths make a collision unlikely.
        jenis_data = JenisDataILAP.objects.filter(id_sub_jenis_data__iexact=term).first()
        if jenis_data is not None:
            return JsonResponse({
                'match': 'jenis_data',
                'url': reverse('jenis_data_ilap_profil', args=[jenis_data.id_sub_jenis_data]),
                'label': f'{jenis_data.id_sub_jenis_data} - {jenis_data.nama_sub_jenis_data}',
            })

        ilap = ILAP.objects.filter(id_ilap__iexact=term).first()
        if ilap is not None:
            return JsonResponse({
                'match': 'ilap',
                'url': reverse('profil_ilap_detail', args=[ilap.id_ilap]),
                'label': f'{ilap.id_ilap} - {ilap.nama_ilap}',
            })

    # nomor_tiket is unique, so an exact match identifies a single tiket.
    tiket = Tiket.objects.filter(nomor_tiket__iexact=term).first()
    if tiket is not None and _can_open_tiket(request.user, tiket):
        return JsonResponse({
            'match': 'tiket',
            'url': reverse('tiket_detail', args=[tiket.pk]),
            'label': tiket.nomor_tiket,
        })

    return JsonResponse({'match': None})


@login_required
@user_passes_test(_can_view_profil_ilap)
def jenis_data_ilap_tiket_data(request, id_sub_jenis_data):
    """Server-side DataTables endpoint for a sub jenis data's tiket list.

    Args:
        request (HttpRequest): The current request, carrying the DataTables
            ``draw``, ``start``, ``length``, ``search[value]`` and ``order``
            parameters.
        id_sub_jenis_data (str): The sub jenis data code the tikets belong to.

    Returns:
        JsonResponse: A JSON object with ``draw``, ``recordsTotal``,
        ``recordsFiltered`` and ``data`` (one dict per tiket row).
    """
    jenis_data = get_object_or_404(JenisDataILAP, id_sub_jenis_data=id_sub_jenis_data)

    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()

    base_qs = Tiket.objects.filter(
        id_periode_data__id_sub_jenis_data_ilap=jenis_data
    ).select_related('id_periode_data__id_periode_pengiriman')

    records_total = base_qs.count()

    if search_value:
        # The status column stores an integer, so match the search term
        # against the human-readable labels and filter by the matching codes.
        status_codes = [
            code for code, label in STATUS_LABELS.items()
            if search_value.lower() in label.lower()
        ]
        search_filter = Q(nomor_tiket__icontains=search_value)
        if search_value.isdigit():
            search_filter |= Q(tahun=int(search_value)) | Q(periode=int(search_value))
        if status_codes:
            search_filter |= Q(status_tiket__in=status_codes)
        base_qs = base_qs.filter(search_filter)

    records_filtered = base_qs.count()

    order_columns = {
        0: 'nomor_tiket',
        1: 'periode',
        2: 'tahun',
        3: 'status_tiket',
        4: 'tgl_terima_dip',
    }
    order_column_idx = request.GET.get('order[0][column]')
    order_col = order_columns.get(int(order_column_idx)) if order_column_idx else None
    if order_col:
        if request.GET.get('order[0][dir]', 'asc') == 'desc':
            order_col = f'-{order_col}'
        base_qs = base_qs.order_by(order_col)
    else:
        base_qs = base_qs.order_by('nomor_tiket')

    data = []
    for tiket in base_qs[start:start + length]:
        periode_penerimaan = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
        status_label = STATUS_LABELS.get(tiket.status_tiket, '---')
        badge_class = STATUS_BADGE_CLASSES.get(tiket.status_tiket, 'bg-secondary')
        detail_url = reverse('tiket_detail', args=[tiket.pk])
        data.append({
            'nomor_tiket': escape(tiket.nomor_tiket),
            'periode': escape(format_periode(
                periode_penerimaan, tiket.periode, tiket.tahun, include_year=False
            )),
            'tahun': tiket.tahun,
            'status': f'<span class="badge {badge_class}">{escape(status_label)}</span>',
            'tgl_terima_dip': (
                date_format(tiket.tgl_terima_dip, 'd M Y H:i')
                if tiket.tgl_terima_dip else '---'
            ),
            'actions': (
                f'<a href="{detail_url}" class="btn btn-sm btn-primary" title="Detail Tiket">'
                f'<i class="feather-eye me-1"></i>Detail</a>'
            ),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
