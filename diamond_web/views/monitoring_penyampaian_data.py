from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from datetime import datetime, timedelta
import calendar
from urllib.parse import urlencode

from ..models.jenis_data_ilap import JenisDataILAP
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.tiket import Tiket
from ..models.detil_tanda_terima import DetilTandaTerima
from ..models.tiket_pic import TiketPIC
from ..models.pic import PIC
from ..models.kanwil import Kanwil
from ..models.kpp import KPP
from ..models.kategori_wilayah import KategoriWilayah
from ..models.kategori_ilap import KategoriILAP
from ..models.ilap import ILAP
from ..models.jenis_tabel import JenisTabel
from ..models.dasar_hukum import DasarHukum
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..models.periode_pengiriman import PeriodePengiriman
from ..utils import format_periode
from .mixins import UserP3DERequiredMixin, get_active_p3de_jenis_data_ilap_ids


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
    # Check if requesting filter options
    if request.GET.get('get_filter_options'):
        from django.db.models import Min, Max
        
        # Determine if user is admin or regular user
        is_admin = request.user.is_superuser or request.user.groups.filter(name='admin').exists()
        
        # Get active JenisDataILAP IDs for current user (used for filtering all dropdowns for non-admin users)
        active_jenis_data_ilap_ids = get_active_p3de_jenis_data_ilap_ids(request.user) if not is_admin else None
        
        # Build filter querysets based on user role
        if is_admin:
            # Admin: show all data
            kanwil_list = Kanwil.objects.all().values('id', 'kode_kanwil', 'nama_kanwil').order_by('kode_kanwil')
            kpp_list = KPP.objects.all().values('id', 'kode_kpp', 'nama_kpp').order_by('kode_kpp')
            kategori_wilayah_list = KategoriWilayah.objects.all().values('id', 'deskripsi').order_by('id')
            kategori_ilap_list = KategoriILAP.objects.all().values('id', 'id_kategori', 'nama_kategori').order_by('nama_kategori')
            ilap_list = ILAP.objects.all().values('id', 'id_ilap', 'nama_ilap').order_by('id_ilap')
            jenis_data_list = JenisDataILAP.objects.values('id_jenis_data', 'nama_jenis_data').distinct().order_by('id_jenis_data')
            sub_jenis_data_list = JenisDataILAP.objects.values('id_sub_jenis_data', 'nama_sub_jenis_data').distinct().order_by('id_sub_jenis_data')
            jenis_tabel_list = JenisTabel.objects.all().values('id', 'deskripsi').order_by('id')
            dasar_hukum_list = DasarHukum.objects.all().values('id', 'deskripsi').order_by('id')
            periode_pengiriman_list = PeriodePengiriman.objects.all().values('id', 'periode_penyampaian').order_by('id')
        else:
            # Regular user: filter all data based on active P3DE PIC assignment
            if active_jenis_data_ilap_ids:
                active_jenis_data_qs = JenisDataILAP.objects.filter(
                    id__in=active_jenis_data_ilap_ids
                ).select_related(
                    'id_ilap',
                    'id_ilap__id_kpp',
                    'id_ilap__id_kpp__id_kanwil',
                    'id_ilap__id_kategori',
                    'id_ilap__id_kategori_wilayah',
                    'id_jenis_tabel',
                )

                active_jenis_data = list(active_jenis_data_qs)
                active_ilap_ids = {j.id_ilap_id for j in active_jenis_data if j.id_ilap_id}
                ilap_qs = ILAP.objects.filter(id__in=active_ilap_ids).select_related(
                    'id_kpp__id_kanwil',
                    'id_kategori',
                    'id_kategori_wilayah',
                )
                ilap_list = ilap_qs.values('id', 'id_ilap', 'nama_ilap').order_by('id_ilap')

                # Get kanwil/kpp from related ILAPs
                kanwil_set = set()
                kpp_set = set()
                for ilap in ilap_qs:
                    if ilap.id_kpp:
                        kpp_set.add(ilap.id_kpp.id)
                        if ilap.id_kpp.id_kanwil:
                            kanwil_set.add(ilap.id_kpp.id_kanwil.id)
                
                kanwil_list = Kanwil.objects.filter(id__in=kanwil_set).values('id', 'kode_kanwil', 'nama_kanwil').order_by('kode_kanwil')
                kpp_list = KPP.objects.filter(id__in=kpp_set).values('id', 'kode_kpp', 'nama_kpp').order_by('kode_kpp')
                
                # Get kategori_wilayah from related ILAPs
                kategori_wilayah_set = {
                    ilap.id_kategori_wilayah.id
                    for ilap in ilap_qs
                    if ilap.id_kategori_wilayah
                }
                
                kategori_wilayah_list = KategoriWilayah.objects.filter(id__in=kategori_wilayah_set).values('id', 'deskripsi').order_by('id')
                
                # Get kategori_ilap from related ILAPs
                kategori_ilap_set = {
                    ilap.id_kategori.id
                    for ilap in ilap_qs
                    if ilap.id_kategori
                }
                
                kategori_ilap_list = KategoriILAP.objects.filter(id__in=kategori_ilap_set).values('id', 'id_kategori', 'nama_kategori').order_by('nama_kategori')
                
                # Get jenis_data and sub_jenis_data from active assignment scope
                jenis_data_list = active_jenis_data_qs.values('id_jenis_data', 'nama_jenis_data').distinct().order_by('id_jenis_data')
                sub_jenis_data_list = active_jenis_data_qs.values('id_sub_jenis_data', 'nama_sub_jenis_data').distinct().order_by('id_sub_jenis_data')
                
                # Get jenis_tabel and dasar_hukum from active ILAPs' sub jenis data
                jenis_tabel_set = {
                    jdd.id_jenis_tabel.id
                    for jdd in active_jenis_data
                    if jdd.id_jenis_tabel
                }
                
                jenis_tabel_list = JenisTabel.objects.filter(id__in=jenis_tabel_set).values('id', 'deskripsi').order_by('id')
                
                # Get dasar_hukum from active sub jenis data
                dasar_hukum_set = set()
                for kj in KlasifikasiJenisData.objects.filter(id_sub_jenis_data_id__in=active_jenis_data_ilap_ids):
                    if kj.id_klasifikasi_tabel:
                        dasar_hukum_set.add(kj.id_klasifikasi_tabel.id)
                
                dasar_hukum_list = DasarHukum.objects.filter(id__in=dasar_hukum_set).values('id', 'deskripsi').order_by('id')
                
                # Get periode_pengiriman from active sub jenis data
                periode_pengiriman_set = set()
                for pjd in PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap_id__in=active_jenis_data_ilap_ids):
                    if pjd.id_periode_pengiriman:
                        periode_pengiriman_set.add(pjd.id_periode_pengiriman.id)
                
                periode_pengiriman_list = PeriodePengiriman.objects.filter(id__in=periode_pengiriman_set).values('id', 'periode_penyampaian').order_by('id')
            else:
                # No active assignments, return empty lists
                kanwil_list = []
                kpp_list = []
                kategori_wilayah_list = []
                kategori_ilap_list = []
                ilap_list = []
                jenis_data_list = []
                sub_jenis_data_list = []
                jenis_tabel_list = []
                dasar_hukum_list = []
                periode_pengiriman_list = []
        
        # Get unique tahun from periode_jenis_data and generate range up to current year
        tahun_range = PeriodeJenisData.objects.aggregate(
            min_year=Min('start_date__year'),
            max_year=Max('start_date__year')
        )
        min_year = tahun_range.get('min_year') or datetime.now().year
        max_year = max(tahun_range.get('max_year') or datetime.now().year, datetime.now().year)
        tahun_options = [{'id': str(year), 'name': str(year)} for year in range(min_year, max_year + 1)]
        
        # Get PIC P3DE list based on user role
        if is_admin:
            # Admin: show all P3DE users
            pic_p3de_list = PIC.objects.filter(
                tipe=PIC.TipePIC.P3DE,
                end_date__isnull=True
            ).values('id_user__id', 'id_user__username', 'id_user__first_name', 'id_user__last_name').distinct().order_by('id_user__first_name', 'id_user__last_name', 'id_user__username')
            pic_p3de_options = [
                {
                    'id': str(pic['id_user__id']),
                    'name': f"{pic['id_user__username']} - {pic['id_user__first_name']} {pic['id_user__last_name']}".strip()
                }
                for pic in pic_p3de_list
            ]
        else:
            # Regular User P3DE: show only their own name if they have active P3DE PIC
            if active_jenis_data_ilap_ids:
                pic_p3de_options = [
                    {
                        'id': str(request.user.id),
                        'name': f"{request.user.username} - {request.user.first_name} {request.user.last_name}".strip()
                    }
                ]
            else:
                pic_p3de_options = []
        
        return JsonResponse({
            'filter_options': {
                'tahun': tahun_options,
                'pic_p3de': pic_p3de_options,
                'kanwil': [{'id': str(k['id']), 'name': f"{k['kode_kanwil']} - {k['nama_kanwil']}"} for k in kanwil_list],
                'kpp': [{'id': str(k['id']), 'name': f"{k['kode_kpp']} - {k['nama_kpp']}"} for k in kpp_list],
                'kategori_wilayah': [{'id': str(k['id']), 'name': k['deskripsi']} for k in kategori_wilayah_list],
                'kategori_ilap': [{'id': str(k['id']), 'name': f"{k['id_kategori']} - {k['nama_kategori']}"} for k in kategori_ilap_list],
                'ilap': [{'id': str(k['id']), 'name': f"{k['id_ilap']} - {k['nama_ilap']}"} for k in ilap_list],
                'jenis_data': [{'id': k['id_jenis_data'], 'name': f"{k['id_jenis_data']} - {k['nama_jenis_data']}"} for k in jenis_data_list],
                'sub_jenis_data': [{'id': k['id_sub_jenis_data'], 'name': f"{k['id_sub_jenis_data']} - {k['nama_sub_jenis_data']}"} for k in sub_jenis_data_list],
                'jenis_tabel': [{'id': str(k['id']), 'name': k['deskripsi']} for k in jenis_tabel_list],
                'dasar_hukum': [{'id': str(k['id']), 'name': k['deskripsi']} for k in dasar_hukum_list],
                'periode_pengiriman': [{'id': str(k['id']), 'name': k['periode_penyampaian']} for k in periode_pengiriman_list],
                'periode': [
                    {'id': 'Januari', 'name': 'Januari'},
                    {'id': 'Februari', 'name': 'Februari'},
                    {'id': 'Maret', 'name': 'Maret'},
                    {'id': 'April', 'name': 'April'},
                    {'id': 'Mei', 'name': 'Mei'},
                    {'id': 'Juni', 'name': 'Juni'},
                    {'id': 'Juli', 'name': 'Juli'},
                    {'id': 'Agustus', 'name': 'Agustus'},
                    {'id': 'September', 'name': 'September'},
                    {'id': 'Oktober', 'name': 'Oktober'},
                    {'id': 'November', 'name': 'November'},
                    {'id': 'Desember', 'name': 'Desember'},
                    {'id': 'Triwulan I', 'name': 'Triwulan I'},
                    {'id': 'Triwulan II', 'name': 'Triwulan II'},
                    {'id': 'Triwulan III', 'name': 'Triwulan III'},
                    {'id': 'Triwulan IV', 'name': 'Triwulan IV'},
                    {'id': 'Semester I', 'name': 'Semester I'},
                    {'id': 'Semester II', 'name': 'Semester II'},
                    {'id': 'Tahunan', 'name': 'Tahunan'},
                ],
            }
        })
    
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    today = datetime.now().date()
    records = []

    is_admin = request.user.is_superuser or request.user.groups.filter(
        name__in=['admin', 'admin_p3de', 'admin_pide', 'admin_pmde']
    ).exists()

    # Read all filter params early so they can be applied at DB level
    tahun_filter = request.GET.get('tahun', '')
    pic_p3de_filter = request.GET.get('pic_p3de', '')
    kanwil_id = request.GET.get('kanwil', '')
    kpp_id = request.GET.get('kpp', '')
    kategori_wilayah_id = request.GET.get('kategori_wilayah', '')
    kategori_ilap_id = request.GET.get('kategori_ilap', '')
    ilap_id = request.GET.get('ilap', '')
    jenis_data_id = request.GET.get('jenis_data', '')
    sub_jenis_data_id = request.GET.get('sub_jenis_data', '')
    status_penyampaian_filter = request.GET.get('status_penyampaian', '')
    terlambat_filter = request.GET.get('terlambat', '')
    jenis_tabel_filter = request.GET.get('jenis_tabel', '')
    dasar_hukum_filter = request.GET.get('dasar_hukum', '')
    periode_pengiriman_filter = request.GET.get('periode_pengiriman', '')
    periode_filter = request.GET.get('periode', '')

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
        'id_sub_jenis_data_ilap__id_ilap__id_kpp',
        'id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil',
        'id_sub_jenis_data_ilap__id_jenis_tabel',
        'id_sub_jenis_data_ilap__id_status_data',
    )
    if allowed_jenis_data_ids is not None:
        periode_data_qs = periode_data_qs.filter(id_sub_jenis_data_ilap_id__in=allowed_jenis_data_ids)

    # Push dimension filters to DB level to drastically reduce rows processed in Python
    if kanwil_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil_id=kanwil_id
        )
    if kpp_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_ilap__id_kpp_id=kpp_id
        )
    if kategori_wilayah_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah_id=kategori_wilayah_id
        )
    if kategori_ilap_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_ilap__id_kategori_id=kategori_ilap_id
        )
    if ilap_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_ilap_id=ilap_id
        )
    if sub_jenis_data_id:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_sub_jenis_data=sub_jenis_data_id
        )
    if jenis_tabel_filter:
        periode_data_qs = periode_data_qs.filter(
            id_sub_jenis_data_ilap__id_jenis_tabel_id=jenis_tabel_filter
        )
    if periode_pengiriman_filter:
        periode_data_qs = periode_data_qs.filter(
            id_periode_pengiriman_id=periode_pengiriman_filter
        )

    # If tahun_filter is set, only load periode_data whose range overlaps the requested year
    tahun_int = int(tahun_filter) if tahun_filter else None
    if tahun_int:
        year_start = datetime(tahun_int, 1, 1).date()
        year_end = datetime(tahun_int, 12, 31).date()
        periode_data_qs = periode_data_qs.filter(
            start_date__lte=year_end
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=year_start)
        )

    periode_data_list = list(periode_data_qs)
    if not periode_data_list:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
        })

    jenis_data_ids = {pd.id_sub_jenis_data_ilap_id for pd in periode_data_list}
    periode_data_ids = {pd.id for pd in periode_data_list}

    # Build a map of jenis_data_ilap_id -> set of dasar_hukum ids
    dasar_hukum_map = {}
    for kj in KlasifikasiJenisData.objects.filter(id_sub_jenis_data_id__in=jenis_data_ids).values(
        'id_sub_jenis_data_id',
        'id_klasifikasi_tabel_id',
    ):
        dasar_hukum_map.setdefault(kj['id_sub_jenis_data_id'], set()).add(kj['id_klasifikasi_tabel_id'])

    # Build active PIC map once (jenis_data_id -> user_id)
    pic_p3de_map: dict[int, int] = {}
    for pic in PIC.objects.filter(
        id_sub_jenis_data_ilap_id__in=jenis_data_ids,
        tipe=PIC.TipePIC.P3DE,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).order_by('id').values('id_sub_jenis_data_ilap_id', 'id_user_id'):
        pic_p3de_map.setdefault(pic['id_sub_jenis_data_ilap_id'], pic['id_user_id'])

    # Build tiket lookup once ((periode_data_id, periode, tahun) -> tiket)
    tiket_map: dict[tuple[int, int, int], Tiket] = {}
    for tiket in Tiket.objects.filter(
        id_periode_data_id__in=periode_data_ids,
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

        # Restrict period generation range to tahun_filter to avoid generating all history
        if tahun_int:
            year_start = datetime(tahun_int, 1, 1).date()
            year_end = datetime(tahun_int, 12, 31).date()
            start_date = max(start_date, year_start)
            end_date_for_periods = min(end_date_for_periods, year_end)
            if start_date > end_date_for_periods:
                continue

        # Generate all periods from start_date until end_date_for_periods using effective periode_penerimaan
        periods = get_periods_for_range(start_date, end_date_for_periods, periode_type_penerimaan)

        # Compute per-jenis_data values once outside the inner period loop
        pic_p3de_id = pic_p3de_map.get(jenis_data.id)
        kategori_wilayah_desc = (
            (jenis_data.id_ilap.id_kategori_wilayah.deskripsi or '').lower()
            if jenis_data.id_ilap and jenis_data.id_ilap.id_kategori_wilayah
            else ''
        )
        is_regional_ilap = 'regional' in kategori_wilayah_desc
        jenis_data_kanwil_id = (jenis_data.id_ilap.id_kpp.id_kanwil_id if jenis_data.id_ilap.id_kpp else '')
        jenis_data_kpp_id = (jenis_data.id_ilap.id_kpp.id if jenis_data.id_ilap.id_kpp else '')
        jenis_data_kategori_wilayah_id = jenis_data.id_ilap.id_kategori_wilayah.id if jenis_data.id_ilap.id_kategori_wilayah else ''
        jenis_data_kategori_ilap_id = jenis_data.id_ilap.id_kategori.id if jenis_data.id_ilap.id_kategori else ''
        jenis_data_dasar_hukum_ids = dasar_hukum_map.get(jenis_data.id, set())
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
                'tiket_id': tiket.id if tiket_exists else None,
                'is_late': is_late,
                'days_diff': days_diff,
                'pic_p3de_id': pic_p3de_id,
                'kanwil_id': jenis_data_kanwil_id,
                'kpp_id': jenis_data_kpp_id,
                'kategori_wilayah_id': jenis_data_kategori_wilayah_id,
                'kategori_ilap_id': jenis_data_kategori_ilap_id,
                'jenis_tabel_id': jenis_data.id_jenis_tabel_id,
                'periode_pengiriman_id': periode_data.id_periode_pengiriman_id,
                'dasar_hukum_ids': jenis_data_dasar_hukum_ids,
            })

    records_total = len(records)

    # Apply remaining Python-side filters in a single pass
    # (DB-level filters for kanwil/kpp/ilap/etc. already applied above)
    def record_matches_filters(r):
        if tahun_filter and str(r.get('tahun', '')) != tahun_filter:
            return False
        if pic_p3de_filter and (not r.get('pic_p3de_id') or str(r.get('pic_p3de_id')) != pic_p3de_filter):
            return False
        if status_penyampaian_filter and r.get('status_penyampaian', '') != status_penyampaian_filter:
            return False
        if terlambat_filter and r.get('status_terlambat', '') != terlambat_filter:
            return False
        if jenis_data_id and r.get('jenis_data', '') != jenis_data_id:
            return False
        if dasar_hukum_filter and int(dasar_hukum_filter) not in r.get('dasar_hukum_ids', set()):
            return False
        if periode_filter and str(r.get('periode_display_name', '')) != periode_filter:
            return False
        return True

    filtered_records = records if not any([
        tahun_filter, pic_p3de_filter, status_penyampaian_filter,
        terlambat_filter, jenis_data_id, dasar_hukum_filter,
        periode_filter,
    ]) else [r for r in records if record_matches_filters(r)]

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
        if record["tiket_id"]:
            tiket_detail_url = f'/tiket/{record["tiket_id"]}/'
        else:
            tiket_detail_url = f'/tiket/?{tiket_query}'
        
        lihat_tiket_btn = ""
        if record["status_penyampaian"] != "Belum Menyampaikan":
            lihat_tiket_btn = (
                f'<a href="{tiket_detail_url}" '
                f'class="btn btn-primary btn-sm" title="Lihat Tiket">'
                f'<i class="feather-eye"></i>'
                f'</a>'
            )

        actions = (
            f'<div class="btn-group btn-group-sm">'
            f'{lihat_tiket_btn}'
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


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def monitoring_penyampaian_data_filter_relations(request):
    """Return relationship data for client-side cascading filters.

    Returns JSON describing how filter dimensions relate to each other so the
    frontend can narrow down combobox options based on the current selection
    (e.g. selecting a Tahun restricts which Kategori ILAP / ILAP / Jenis Data
    are shown).

    **Permissions:** same as ``monitoring_penyampaian_data_data``.

    **Read-only:** queries existing models only, does not modify data.
    """
    from django.db.models import Min, Max

    is_admin = request.user.is_superuser or request.user.groups.filter(
        name__in=['admin', 'admin_p3de', 'admin_pide', 'admin_pmde']
    ).exists()
    allowed_jenis_data_ids = None
    if not is_admin:
        allowed_jenis_data_ids = set(get_active_p3de_jenis_data_ilap_ids(request.user))

    # --- ILAP -> kategori, jenis_data_ids, tahuns ---
    ilap_qs = ILAP.objects.select_related('id_kategori')
    jenis_qs = JenisDataILAP.objects.all()
    if allowed_jenis_data_ids is not None:
        jenis_qs = jenis_qs.filter(id__in=allowed_jenis_data_ids)
        active_ilap_ids = set(jenis_qs.values_list('id_ilap_id', flat=True))
        ilap_qs = ilap_qs.filter(id__in=active_ilap_ids)

    jenis_list = list(jenis_qs.values('id', 'id_ilap_id', 'id_jenis_data', 'nama_jenis_data'))
    ilap_list = list(ilap_qs.values('id', 'id_ilap', 'nama_ilap', 'id_kategori_id'))

    # Map ilap_id (pk) -> {kategori_id, jenis_data list}
    ilap_data = {}
    ilap_by_kategori = {}
    for il in ilap_list:
        pk = str(il['id'])
        kat_id = str(il['id_kategori_id']) if il['id_kategori_id'] else ''
        ilap_data[pk] = {
            'id': pk,
            'name': f"{il['id_ilap']} - {il['nama_ilap']}",
            'kategori_id': kat_id,
            'jenis_data': [],
            'tahuns': [],
        }
        ilap_by_kategori.setdefault(kat_id, []).append({
            'id': pk, 'name': ilap_data[pk]['name']
        })

    # Attach jenis_data to each ilap
    jenis_data_by_ilap = {}
    for j in jenis_list:
        ilap_pk = str(j['id_ilap_id']) if j['id_ilap_id'] else ''
        jd_id = j['id_jenis_data']
        jd_obj = {
            'id': jd_id,
            'name': f"{jd_id} - {j['nama_jenis_data']}",
        }
        if ilap_pk in ilap_data:
            ilap_data[ilap_pk]['jenis_data'].append(jd_obj)
        jenis_data_by_ilap.setdefault(ilap_pk, []).append(jd_obj)

    # --- tahun relations via PeriodeJenisData ---
    periode_qs = PeriodeJenisData.objects.all()
    if allowed_jenis_data_ids is not None:
        periode_qs = periode_qs.filter(id_sub_jenis_data_ilap_id__in=allowed_jenis_data_ids)

    # For each ilap, which years appear in its periode data?
    # Group by ilap through the sub jenis data path.
    periode_rows = list(
        periode_qs.values(
            'id_sub_jenis_data_ilap__id_ilap_id',
            'id_sub_jenis_data_ilap__id_ilap__id_kategori_id',
        ).annotate(
            min_year=Min('start_date__year'),
            max_year=Max('start_date__year'),
        )
    )
    tahun_global = periode_qs.aggregate(
        min_year=Min('start_date__year'),
        max_year=Max('start_date__year'),
    )
    g_min = tahun_global.get('min_year') or datetime.now().year
    g_max = max(tahun_global.get('max_year') or datetime.now().year, datetime.now().year)
    all_tahuns = list(range(g_min, g_max + 1))

    # Build kategori_by_tahun and ilap tahuns
    kategori_by_tahun = {}
    for row in periode_rows:
        ilap_pk = row.get('id_sub_jenis_data_ilap__id_ilap_id')
        kat_id = row.get('id_sub_jenis_data_ilap__id_ilap__id_kategori_id')
        if not ilap_pk:
            continue
        ilap_pk = str(ilap_pk)
        kat_id_str = str(kat_id) if kat_id else ''
        if row.get('min_year') and row.get('max_year'):
            years = list(range(row['min_year'], row['max_year'] + 1))
            if ilap_pk in ilap_data:
                ilap_data[ilap_pk]['tahuns'] = years
            for y in years:
                kobj = {'id': kat_id_str}
                lst = kategori_by_tahun.setdefault(str(y), [])
                # de-dupe kategori per tahun
                if not any(k['id'] == kat_id_str for k in lst):
                    lst.append(kobj)

    # Resolve kategori names
    kat_ids = {il['kategori_id'] for il in ilap_data.values() if il['kategori_id']}
    kat_map = {}
    if kat_ids:
        for k in KategoriILAP.objects.filter(id__in=kat_ids).values('id', 'id_kategori', 'nama_kategori'):
            kat_map[str(k['id'])] = f"{k['id_kategori']} - {k['nama_kategori']}"
    # Enrich kategori_by_tahun with names
    for y, lst in kategori_by_tahun.items():
        for k in lst:
            k['name'] = kat_map.get(k['id'], k['id'])

    return JsonResponse({
        'all_tahuns': all_tahuns,
        'kategori_by_tahun': kategori_by_tahun,
        'ilap_by_kategori': ilap_by_kategori,
        'jenis_data_by_ilap': jenis_data_by_ilap,
        'ilap_data': ilap_data,
        'kategori_map': kat_map,
    })

