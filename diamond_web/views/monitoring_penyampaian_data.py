from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Min, Max
from datetime import datetime, timedelta
import calendar
from urllib.parse import urlencode

from ..models.periode_jenis_data import PeriodeJenisData
from ..models.tiket import Tiket
from ..models.detil_tanda_terima import DetilTandaTerima
from ..models.tiket_pic import TiketPIC
from ..models.pic import PIC
from ..utils import format_periode
from ..utils.wilayah import ilap_in_kanwil_q, kanwil_value_paths
from .mixins import UserP3DERequiredMixin, get_active_p3de_jenis_data_ilap_ids


# Query-path fragments leading from PeriodeJenisData — the row this page
# monitors — to each dimension the filters slice by.
JD_PATH = 'id_sub_jenis_data_ilap'
ILAP_PATH = f'{JD_PATH}__id_ilap'
ILAP_REL_PATH = f'{ILAP_PATH}__ilap_kpp_relations'

# Filters whose value is computed while generating the monitoring rows rather
# than stored on a column, so they can only be applied after generation and
# cannot narrow the other dropdowns.
COMPUTED_FILTER_KEYS = ('status_penyampaian', 'terlambat')

# Every filter the page exposes, in dropdown order.
FILTER_KEYS = (
    'tahun',
    'pic_p3de',
    'kategori_ilap',
    'ilap',
    'jenis_data',
    'sub_jenis_data',
    'kanwil',
    'kpp',
    'kategori_wilayah',
    'jenis_tabel',
    'dasar_hukum',
    'periode_pengiriman',
) + COMPUTED_FILTER_KEYS

STATUS_PENYAMPAIAN_OPTIONS = [
    {'id': 'Sudah Menyampaikan', 'name': 'Sudah Menyampaikan'},
    {'id': 'Belum Menyampaikan', 'name': 'Belum Menyampaikan'},
]

TERLAMBAT_OPTIONS = [
    {'id': 'Ya', 'name': 'Ya'},
    {'id': 'Tidak', 'name': 'Tidak'},
]


class MonitoringPenyampaianDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for monitoring data submissions (monitoring penyampaian data).

    Renders `monitoring_penyampaian_data/list.html`. Shows monitoring for each sub jenis data
    with periodic rows from start_date until current date, checking submission status for each period.
    """
    template_name = 'monitoring_penyampaian_data/list.html'

    def get_context_data(self, **kwargs):
        """Prepare template context for the monitoring penyampaian data list view.

        Returns:
            dict: Template context dictionary.
        """
        context = super().get_context_data(**kwargs)
        return context


def get_periods_for_range(start_date, end_date, periode_type):
    """Generate a list of period date ranges based on the given periode type.

    Periods are generated sequentially from *start_date* to *end_date*. The
    periode count resets to 1 at the beginning of each calendar year.

    Args:
        start_date (datetime.date): The start date for period generation.
        end_date (datetime.date): The end date for period generation.
        periode_type (str): The type of period duration. Supported values:
            ``'harian'``, ``'mingguan'``, ``'2 mingguan'``, ``'bulanan'``,
            ``'triwulanan'``, ``'kuartal'``, ``'semester'``, ``'tahunan'``.

    Returns:
        list[dict]: A list of dictionaries, each containing:

            - **periode_num** (*int*): Sequential period number (resets yearly).
            - **start_date** (*datetime.date*): Start date of the period.
            - **end_date** (*datetime.date*): End date of the period.
    """
    def _add_months_safe(dt, months):
        """Add a given number of months to a date, handling month-end overflow safely.

        Args:
            dt (datetime.date): The base date.
            months (int): Number of months to add (can be negative).

        Returns:
            datetime.date: The resulting date with the month adjusted, and the
                day clamped to the last day of the target month if necessary.
        """
        month = dt.month - 1 + months
        year = dt.year + month // 12
        month = month % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    periods = []
    current = start_date
    periode_count = 1
    current_year = start_date.year
    
    while current <= end_date:
        # Check if year has changed, reset periode_count
        if current.year != current_year:
            current_year = current.year
            periode_count = 1
        
        if periode_type.lower() == 'harian':
            next_date = current + timedelta(days=1)
        elif periode_type.lower() == 'mingguan':
            next_date = current + timedelta(weeks=1)
        elif periode_type.lower() == '2 mingguan':
            next_date = current + timedelta(weeks=2)
        elif periode_type.lower() == 'bulanan':
            # Add 1 month safely (handles 29/30/31)
            next_date = _add_months_safe(current, 1)
        elif periode_type.lower() == 'triwulanan':
            # Add 3 months safely
            next_date = _add_months_safe(current, 3)
        elif periode_type.lower() == 'kuartal':
            # Add 3 months safely
            next_date = _add_months_safe(current, 3)
        elif periode_type.lower() == 'semester':
            # Add 6 months safely
            next_date = _add_months_safe(current, 6)
        elif periode_type.lower() == 'tahunan':
            # Add 12 months safely (handles leap day)
            next_date = _add_months_safe(current, 12)
        else:
            next_date = current + timedelta(days=1)
        
        periods.append({
            'periode_num': periode_count,
            'start_date': current,
            'end_date': next_date - timedelta(days=1),
        })
        
        current = next_date
        periode_count += 1

    return periods


def split_filter_values(raw):
    """Split a comma-separated multi-select value into a clean list.

    Args:
        raw (str): Raw query-string value, e.g. ``"1,2,3"``.

    Returns:
        list[str]: Non-empty, stripped values.
    """
    if not raw:
        return []
    return [value.strip() for value in raw.split(',') if value.strip()]


def read_filters(request):
    """Read every filter parameter off the request as a list of values.

    Args:
        request (HttpRequest): The incoming request.

    Returns:
        dict[str, list[str]]: Selected values keyed by filter name; a filter
            the user left on "-- Semua --" maps to an empty list.
    """
    return {key: split_filter_values(request.GET.get(key, '')) for key in FILTER_KEYS}


def year_overlap_q(years):
    """Q matching PeriodeJenisData whose active range touches any of *years*.

    Args:
        years (list[int]): Calendar years to match.

    Returns:
        Q: Combined overlap condition (empty Q when *years* is empty).
    """
    condition = Q()
    for year in years:
        condition |= (
            Q(start_date__lte=datetime(year, 12, 31).date())
            & (Q(end_date__isnull=True) | Q(end_date__gte=datetime(year, 1, 1).date()))
        )
    return condition


def dimension_q(key, values, today):
    """Build the PeriodeJenisData condition for one filter dimension.

    Args:
        key (str): Filter name, one of :data:`FILTER_KEYS`.
        values (list[str]): Selected values for that filter.
        today (datetime.date): Reference date used to decide PIC activeness.

    Returns:
        Q | None: The condition, or ``None`` when the filter selects nothing
            or cannot be expressed as a query (the computed filters).
    """
    if not values:
        return None

    if key == 'tahun':
        years = [int(v) for v in values if v.isdigit()]
        return year_overlap_q(years) if years else None

    if key == 'pic_p3de':
        # All conditions live in one Q so they resolve against the same PIC row.
        return Q(**{
            f'{JD_PATH}__pic__tipe': PIC.TipePIC.P3DE,
            f'{JD_PATH}__pic__id_user_id__in': values,
            f'{JD_PATH}__pic__start_date__lte': today,
        }) & (
            Q(**{f'{JD_PATH}__pic__end_date__isnull': True})
            | Q(**{f'{JD_PATH}__pic__end_date__gte': today})
        )

    if key == 'kanwil':
        # Regional ILAP reach a Kanwil either directly or through a KPP.
        return ilap_in_kanwil_q(values, prefix=ILAP_REL_PATH)

    lookup = {
        'kpp': f'{ILAP_REL_PATH}__id_kpp__id__in',
        'kategori_wilayah': f'{ILAP_PATH}__id_kategori_wilayah__id__in',
        'kategori_ilap': f'{ILAP_PATH}__id_kategori__id__in',
        'ilap': f'{ILAP_PATH}__id__in',
        'jenis_data': f'{JD_PATH}__id_jenis_data__in',
        'sub_jenis_data': f'{JD_PATH}__id_sub_jenis_data__in',
        'jenis_tabel': f'{JD_PATH}__id_jenis_tabel__id__in',
        'dasar_hukum': f'{JD_PATH}__klasifikasijenisdata__id_klasifikasi_tabel__id__in',
        'periode_pengiriman': 'id_periode_pengiriman__id__in',
    }.get(key)

    return Q(**{lookup: values}) if lookup else None


def apply_filters(queryset, filters, today, exclude=None):
    """Narrow a PeriodeJenisData queryset by the selected filters.

    Args:
        queryset (QuerySet): PeriodeJenisData queryset to narrow.
        filters (dict[str, list[str]]): Output of :func:`read_filters`.
        today (datetime.date): Reference date for PIC activeness.
        exclude (str | None): Filter to skip. Pass a dropdown's own name when
            building its options, so selecting a value there does not collapse
            that dropdown down to the single value already chosen.

    Returns:
        QuerySet: The narrowed queryset, de-duplicated because several of the
            conditions join across multi-valued relations.
    """
    for key, values in filters.items():
        if key == exclude:
            continue
        condition = dimension_q(key, values, today)
        if condition is not None:
            queryset = queryset.filter(condition)
    return queryset.distinct()


def collect_options(queryset, paths, label):
    """Pull distinct dropdown options straight off a queryset.

    Args:
        queryset (QuerySet): Queryset to read values from.
        paths (list[str]): Field paths; the first one supplies the option id.
        label (callable): Receives the values of *paths* and returns the label.

    Returns:
        list[dict]: ``{'id', 'name'}`` options, sorted by label.
    """
    options = []
    seen = set()
    for row in queryset.values_list(*paths).distinct():
        if row[0] is None:
            continue
        option_id = str(row[0])
        if option_id in seen:
            continue
        seen.add(option_id)
        options.append({'id': option_id, 'name': label(*row)})
    return sorted(options, key=lambda option: option['name'])


def build_filter_options(base_queryset, filters, today, is_admin, user):
    """Build every dropdown's options from the currently selected filters.

    Each dropdown is populated from the queryset narrowed by all *other*
    selections, so picking a value in one filter prunes the remaining ones to
    what is still reachable.

    Args:
        base_queryset (QuerySet): PeriodeJenisData scoped to what the user may see.
        filters (dict[str, list[str]]): Output of :func:`read_filters`.
        today (datetime.date): Reference date for PIC activeness and open ranges.
        is_admin (bool): Whether the requesting user has the admin role.
        user (User): The requesting user, used for the non-admin PIC list.

    Returns:
        dict[str, list[dict]]: Option lists keyed by filter name.
    """
    def scoped(key):
        """Queryset narrowed by every filter except *key*."""
        return apply_filters(base_queryset, filters, today, exclude=key)

    specs = {
        'kpp': (
            [
                f'{ILAP_REL_PATH}__id_kpp__id',
                f'{ILAP_REL_PATH}__id_kpp__kode_kpp',
                f'{ILAP_REL_PATH}__id_kpp__nama_kpp',
            ],
            lambda _id, kode, nama: f'{kode} - {nama}',
        ),
        'kategori_wilayah': (
            [
                f'{ILAP_PATH}__id_kategori_wilayah__id',
                f'{ILAP_PATH}__id_kategori_wilayah__deskripsi',
            ],
            lambda _id, deskripsi: deskripsi,
        ),
        'kategori_ilap': (
            [
                f'{ILAP_PATH}__id_kategori__id',
                f'{ILAP_PATH}__id_kategori__id_kategori',
                f'{ILAP_PATH}__id_kategori__nama_kategori',
            ],
            lambda _id, kode, nama: f'{kode} - {nama}',
        ),
        'ilap': (
            [f'{ILAP_PATH}__id', f'{ILAP_PATH}__id_ilap', f'{ILAP_PATH}__nama_ilap'],
            lambda _id, kode, nama: f'{kode} - {nama}',
        ),
        'jenis_data': (
            [f'{JD_PATH}__id_jenis_data', f'{JD_PATH}__nama_jenis_data'],
            lambda kode, nama: f'{kode} - {nama}',
        ),
        'sub_jenis_data': (
            [f'{JD_PATH}__id_sub_jenis_data', f'{JD_PATH}__nama_sub_jenis_data'],
            lambda kode, nama: f'{kode} - {nama}',
        ),
        'jenis_tabel': (
            [f'{JD_PATH}__id_jenis_tabel__id', f'{JD_PATH}__id_jenis_tabel__deskripsi'],
            lambda _id, deskripsi: deskripsi,
        ),
        'dasar_hukum': (
            [
                f'{JD_PATH}__klasifikasijenisdata__id_klasifikasi_tabel__id',
                f'{JD_PATH}__klasifikasijenisdata__id_klasifikasi_tabel__deskripsi',
            ],
            lambda _id, deskripsi: deskripsi,
        ),
        'periode_pengiriman': (
            ['id_periode_pengiriman__id', 'id_periode_pengiriman__periode_penyampaian'],
            lambda _id, deskripsi: deskripsi,
        ),
    }

    options = {
        key: collect_options(scoped(key), paths, label)
        for key, (paths, label) in specs.items()
    }

    # Kanwil is reachable by two different shapes, so both paths are collected
    # and merged into one option list.
    kanwil_queryset = scoped('kanwil')
    kanwil_options = []
    kanwil_seen = set()
    for paths in kanwil_value_paths(prefix=ILAP_REL_PATH):
        for option in collect_options(
            kanwil_queryset, list(paths), lambda _id, kode, nama: f'{kode} - {nama}'
        ):
            if option['id'] not in kanwil_seen:
                kanwil_seen.add(option['id'])
                kanwil_options.append(option)
    options['kanwil'] = sorted(kanwil_options, key=lambda option: option['name'])

    options['tahun'] = build_tahun_options(scoped('tahun'), today)

    if is_admin:
        options['pic_p3de'] = build_pic_p3de_options(scoped('pic_p3de'), today)
    else:
        # A non-admin only ever monitors their own assignments, so the list
        # stays limited to themselves rather than exposing co-assigned PICs.
        options['pic_p3de'] = (
            [{
                'id': str(user.id),
                'name': f"{user.username} - {user.first_name} {user.last_name}".strip(),
            }]
            if base_queryset.exists() else []
        )

    options['status_penyampaian'] = list(STATUS_PENYAMPAIAN_OPTIONS)
    options['terlambat'] = list(TERLAMBAT_OPTIONS)
    return options


def build_tahun_options(queryset, today):
    """Years covered by the periode data still reachable under the filters.

    Args:
        queryset (QuerySet): PeriodeJenisData narrowed by the other filters.
        today (datetime.date): Upper bound for rows with no end date.

    Returns:
        list[dict]: One ``{'id', 'name'}`` per year, oldest first.
    """
    bounds = queryset.aggregate(
        min_year=Min('start_date__year'),
        max_start_year=Max('start_date__year'),
        max_end_year=Max('end_date__year'),
    )
    min_year = bounds.get('min_year')
    if min_year is None:
        return []

    # A row with no end date is still running, so it reaches the current year.
    if queryset.filter(end_date__isnull=True).exists():
        max_year = today.year
    else:
        max_year = max(
            bounds.get('max_end_year') or 0,
            bounds.get('max_start_year') or 0,
        )
    max_year = max(max_year, min_year)

    return [{'id': str(year), 'name': str(year)} for year in range(min_year, max_year + 1)]


def build_pic_p3de_options(queryset, today):
    """Active P3DE PICs on the sub jenis data still reachable under the filters.

    Args:
        queryset (QuerySet): PeriodeJenisData narrowed by the other filters.
        today (datetime.date): Reference date for PIC activeness.

    Returns:
        list[dict]: One ``{'id', 'name'}`` per user, sorted by label.
    """
    jenis_data_ids = queryset.values_list(f'{JD_PATH}__id', flat=True).distinct()
    pics = PIC.objects.filter(
        tipe=PIC.TipePIC.P3DE,
        id_sub_jenis_data_ilap_id__in=jenis_data_ids,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related('id_user')

    options = []
    seen = set()
    for pic in pics:
        user = pic.id_user
        if not user or user.id in seen:
            continue
        seen.add(user.id)
        full_name = f"{user.first_name} {user.last_name}".strip()
        options.append({
            'id': str(user.id),
            'name': f"{user.username} - {full_name}" if full_name else user.username,
        })
    return sorted(options, key=lambda option: option['name'])


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def monitoring_penyampaian_data_data(request):
    """DataTables server-side endpoint for Monitoring Penyampaian Data.

    Generates monitoring rows for each sub jenis data from *start_date* to the
    current date, checking if a tiket exists for each period and calculating
    whether the submission is late.

    **Permissions:** wrapped by decorators to allow only users in ``admin`` or
    ``user_p3de`` groups. Non-admin users are further restricted to monitoring
    records for sub jenis data where they are an active P3DE PIC.

    **Query parameters for filter options:**
        ``get_filter_options=1`` — returns available filter values instead of data.

    **Query parameters for filtering:**
        ``kanwil``, ``kpp``, ``kategori_wilayah``, ``kategori_ilap``, ``ilap``,
        ``jenis_data``, ``sub_jenis_data``, ``jenis_tabel``, ``dasar_hukum``,
        ``periode_pengiriman``, ``status_penyampaian``, ``terlambat``, ``tahun``,
        ``pic_p3de``.

    Args:
        request (HttpRequest): The incoming HTTP request with GET parameters
            for DataTables pagination, sorting, and filtering.

    Returns:
        JsonResponse: A JSON response compatible with DataTables server-side
            processing, containing the ``draw``, ``recordsTotal``,
            ``recordsFiltered``, and ``data`` keys. If ``get_filter_options=1``
            is present, returns a dictionary with available filter option lists.
    """
    # Dropdown options are rebuilt on every filter change so that each one
    # only offers values still reachable under the other selections.
    if request.GET.get('get_filter_options'):
        options_today = datetime.now().date()
        is_admin = request.user.is_superuser or request.user.groups.filter(name='admin').exists()

        # Options come from the same periode data the list draws from, so a
        # non-admin never sees a value outside their active P3DE assignments.
        base_queryset = PeriodeJenisData.objects.all()
        if not is_admin:
            base_queryset = base_queryset.filter(
                id_sub_jenis_data_ilap_id__in=get_active_p3de_jenis_data_ilap_ids(request.user)
            )

        return JsonResponse({
            'filter_options': build_filter_options(
                base_queryset,
                read_filters(request),
                options_today,
                is_admin,
                request.user,
            )
        })

    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    today = datetime.now().date()
    records = []

    is_admin = request.user.is_superuser or request.user.groups.filter(
        name__in=['admin', 'admin_p3de', 'admin_pide', 'admin_pmde']
    ).exists()

    # Read every filter up front so they can be pushed down to the queryset
    filters = read_filters(request)
    selected_years = sorted(int(year) for year in filters['tahun'] if year.isdigit())

    # Apply RBAC at query level to avoid building records that will be discarded
    allowed_jenis_data_ids = None
    if not is_admin:
        allowed_jenis_data_ids = set(get_active_p3de_jenis_data_ilap_ids(request.user))
        if not allowed_jenis_data_ids:
            return JsonResponse({
                'draw': draw,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': [],
            })

    periode_data_qs = PeriodeJenisData.objects.select_related(
        'id_periode_pengiriman',
        'id_sub_jenis_data_ilap',
        'id_sub_jenis_data_ilap__id_ilap',
        'id_sub_jenis_data_ilap__id_ilap__id_kategori',
        'id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah',
        'id_sub_jenis_data_ilap__id_jenis_tabel',
        'id_sub_jenis_data_ilap__id_status_data',
    ).prefetch_related(
        'id_sub_jenis_data_ilap__id_ilap__ilap_kpp_relations__id_kpp__id_kanwil',
    )
    if allowed_jenis_data_ids is not None:
        periode_data_qs = periode_data_qs.filter(id_sub_jenis_data_ilap_id__in=allowed_jenis_data_ids)

    # Push every filter that maps to a column down to the DB, which drastically
    # reduces the rows expanded into monitoring periods in Python.
    periode_data_qs = apply_filters(periode_data_qs, filters, today)

    periode_data_list = list(periode_data_qs)
    if not periode_data_list:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
        })

    periode_data_ids = {pd.id for pd in periode_data_list}

    # Build tiket lookup once ((periode_data_id, periode, tahun) -> tiket)
    tiket_map: dict[tuple[int, int, int], Tiket] = {}
    for tiket in Tiket.objects.filter(
        id_periode_data_id__in=periode_data_ids,
        penyampaian=1,
    ).only(
        'id',
        'id_periode_data_id',
        'periode',
        'tahun',
        'tgl_terima_vertikal',
        'tgl_terima_dip',
    ).order_by('-id'):
        key = (tiket.id_periode_data_id, tiket.periode, tiket.tahun)
        if key not in tiket_map:
            tiket_map[key] = tiket

    # Generate monitoring records from preloaded data
    for periode_data in periode_data_list:
        jenis_data = periode_data.id_sub_jenis_data_ilap

        if not periode_data.id_periode_pengiriman:
            continue

        # Get start date and generate periods until today
        start_date = periode_data.start_date
        akhir_penyampaian = periode_data.akhir_penyampaian  # days to submit after period end
        periode_type_penyampaian = periode_data.id_periode_pengiriman.periode_penyampaian
        periode_type_penerimaan = periode_data.id_periode_pengiriman.periode_penerimaan

        # Rule: sub-monthly penyampaian (harian, mingguan, 2 mingguan) is always
        # received/grouped monthly — override penerimaan to bulanan regardless of DB value
        if periode_type_penyampaian.lower() in ('harian', 'mingguan', '2 mingguan'):
            periode_type_penerimaan = 'Bulanan'

        # Determine the end date for period generation
        # If periode_data has an end_date, use it; otherwise use today
        end_date_for_periods = periode_data.end_date if periode_data.end_date else today

        # Restrict period generation to the selected years so history outside
        # them is never generated just to be filtered away afterwards.
        if selected_years:
            start_date = max(start_date, datetime(min(selected_years), 1, 1).date())
            end_date_for_periods = min(
                end_date_for_periods, datetime(max(selected_years), 12, 31).date()
            )
            if start_date > end_date_for_periods:
                continue

        # Generate all periods from start_date until end_date_for_periods using effective periode_penerimaan
        periods = get_periods_for_range(start_date, end_date_for_periods, periode_type_penerimaan)

        # Compute per-jenis_data values once outside the inner period loop
        kategori_wilayah_desc = (
            (jenis_data.id_ilap.id_kategori_wilayah.deskripsi or '').lower()
            if jenis_data.id_ilap and jenis_data.id_ilap.id_kategori_wilayah
            else ''
        )
        is_regional_ilap = 'regional' in kategori_wilayah_desc
        # Get first wilayah relation if any (for backward compatibility with
        # single-KPP setups). PV ILAPs resolve to a Kanwil without a KPP.
        first_kpp_rel = jenis_data.id_ilap.ilap_kpp_relations.first() if jenis_data.id_ilap else None
        first_rel_kanwil = first_kpp_rel.kanwil if first_kpp_rel else None
        jenis_data_kanwil_id = (first_rel_kanwil.id if first_rel_kanwil else '')
        jenis_data_kpp_id = (first_kpp_rel.id_kpp.id if first_kpp_rel and first_kpp_rel.id_kpp else '')
        jenis_data_kategori_wilayah_id = jenis_data.id_ilap.id_kategori_wilayah.id if jenis_data.id_ilap.id_kategori_wilayah else ''
        jenis_data_kategori_ilap_id = jenis_data.id_ilap.id_kategori.id if jenis_data.id_ilap.id_kategori else ''
        jenis_data_ilap_name = jenis_data.id_ilap.nama_ilap
        jenis_data_ilap_id = jenis_data.id_ilap.id_ilap
        jenis_data_ilap_pk = jenis_data.id_ilap.id

        for period in periods:
            deadline_date = period['end_date'] + timedelta(days=akhir_penyampaian)
            period_display_name = format_periode(periode_type_penerimaan, period['periode_num'], period['start_date'].year, include_year=False)

            # Check if tiket exists for this period
            tiket = tiket_map.get((
                periode_data.id,
                period['periode_num'],
                period['start_date'].year,
            ))

            tiket_exists = tiket is not None

            # Determine status
            if tiket_exists:
                # Tiket exists means data has been submitted (sudah menyampaikan)
                status_penyampaian = "Sudah Menyampaikan"
                status_penyampaian_class = "bg-success"

                receive_dt = tiket.tgl_terima_vertikal if is_regional_ilap else tiket.tgl_terima_dip
                receive_date = receive_dt.date() if receive_dt else None
                is_late = bool(receive_date and receive_date > deadline_date)
                status_terlambat = "Ya" if is_late else "Tidak"
                status_terlambat_class = "bg-danger" if is_late else "bg-light"
            else:
                # No tiket created
                is_late = today > deadline_date
                status_penyampaian = "Belum Menyampaikan"
                status_penyampaian_class = "bg-warning"
                if is_late:
                    status_terlambat = "Ya"
                    status_terlambat_class = "bg-danger"
                else:
                    status_terlambat = "Tidak"
                    status_terlambat_class = "bg-light"

            # Calculate days from today to deadline
            days_diff = (deadline_date - today).days

            records.append({
                'id_periode_data': periode_data.id,
                'id_jenis_data': jenis_data.id,
                'id_sub_jenis_data': jenis_data.id_sub_jenis_data,
                'periode_num': period['periode_num'],
                'ilap_name': jenis_data_ilap_name,
                'ilap_id': jenis_data_ilap_id,
                'ilap_jenis_data_id': jenis_data_ilap_pk,
                'jenis_data': jenis_data.nama_jenis_data,
                'jenis_data_id': jenis_data.id,
                'sub_jenis_data': jenis_data.nama_sub_jenis_data,
                'periode_penyampaian': periode_type_penyampaian,
                'periode_penerimaan': periode_type_penerimaan,
                'periode': period['periode_num'],
                'periode_display_name': period_display_name,
                'tahun': period['start_date'].year,
                'start_date': period['start_date'],
                'end_date': period['end_date'],
                'deadline_date': deadline_date,
                'status_penyampaian': status_penyampaian,
                'status_penyampaian_class': status_penyampaian_class,
                'status_terlambat': status_terlambat,
                'status_terlambat_class': status_terlambat_class,
                'tiket_exists': tiket_exists,
                'is_late': is_late,
                'days_diff': days_diff,
                'kanwil_id': jenis_data_kanwil_id,
                'kpp_id': jenis_data_kpp_id,
                'kategori_wilayah_id': jenis_data_kategori_wilayah_id,
                'kategori_ilap_id': jenis_data_kategori_ilap_id,
                'jenis_tabel_id': jenis_data.id_jenis_tabel_id,
                'periode_pengiriman_id': periode_data.id_periode_pengiriman_id,
            })

    records_total = len(records)

    # Status penyampaian, terlambat and tahun are properties of a generated
    # period rather than of a periode data row, so they are the only filters
    # left to apply once the rows exist.
    tahun_filter = set(filters['tahun'])
    status_penyampaian_filter = set(filters['status_penyampaian'])
    terlambat_filter = set(filters['terlambat'])

    def record_matches_filters(record):
        """Whether a generated monitoring row survives the remaining filters."""
        if tahun_filter and str(record['tahun']) not in tahun_filter:
            return False
        if status_penyampaian_filter and record['status_penyampaian'] not in status_penyampaian_filter:
            return False
        if terlambat_filter and record['status_terlambat'] not in terlambat_filter:
            return False
        return True

    filtered_records = (
        [r for r in records if record_matches_filters(r)]
        if (tahun_filter or status_penyampaian_filter or terlambat_filter)
        else records
    )

    records_filtered = len(filtered_records)

    # Sorting
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['ilap_name', 'jenis_data', 'periode', 'tahun', 'deadline_date', 'status_penyampaian', 'status_terlambat', 'days_diff']
    
    if order_col_index is not None:
        try:
            col_index = int(order_col_index)
            if col_index < len(columns):
                col = columns[col_index]
                reverse = (order_dir == 'desc')
                
                # Handle numeric fields
                if col in ['periode', 'tahun']:
                    filtered_records = sorted(
                        filtered_records,
                        key=lambda x: x[col] if x[col] else 0,
                        reverse=reverse
                    )
                else:
                    filtered_records = sorted(
                        filtered_records,
                        key=lambda x: str(x[col]).lower(),
                        reverse=reverse
                    )
        except (ValueError, IndexError):
            pass

    # Pagination
    paginated_records = filtered_records[start:start + length]

    # Build response data
    data = []
    for record in paginated_records:
        tiket_query = urlencode({
            'ilap': record['ilap_jenis_data_id'],
            'sub_jenis_data': record['id_sub_jenis_data'],
            'periode': record['periode_num'],
            'tahun': record['tahun'],
            'periode_penerimaan': record.get('periode_penerimaan', ''),
        })
        tiket_rekam_query = urlencode({
            'ilap_id': record['ilap_jenis_data_id'],
            'periode_data_id': record['id_periode_data'],
            'periode': record['periode_num'],
            'tahun': record['tahun'],
        })
        actions = (
            f'<div class="btn-group btn-group-sm">'
            f'<a href="/tiket/?{tiket_query}" '
            f'class="btn btn-primary btn-sm" title="Lihat Tiket">'
            f'<i class="feather-eye"></i>'
            f'</a>'
            f'<a href="/tiket/rekam/?{tiket_rekam_query}" '
            f'class="btn btn-success btn-sm" title="Rekam Penerimaan Data">'
            f'<i class="feather-file-plus"></i>'
            f'</a>'
            f'</div>'
        )
        
        status_penyampaian_html = (
            f'<span class="badge {record["status_penyampaian_class"]}">'
            f'{record["status_penyampaian"]}'
            f'</span>'
        )
        
        status_terlambat_class = "bg-danger" if record["status_terlambat"] == "Ya" else "bg-secondary"
        status_terlambat_html = (
            f'<span class="badge {status_terlambat_class}">'
            f'{record["status_terlambat"]}'
            f'</span>'
        )
        
        data.append({
            'ilap': f"{record['ilap_id']} - {record['ilap_name']}",
            'jenis_data': f"{record['id_sub_jenis_data']} - {record['sub_jenis_data']}",
            'periode': record['periode_display_name'],
            'tahun': record['tahun'],
            'deadline': record['deadline_date'].strftime('%d-%m-%Y'),
            'status_penyampaian': status_penyampaian_html,
            'status_terlambat': status_terlambat_html,
            'hari': record['days_diff'],
            'actions': actions,
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })

