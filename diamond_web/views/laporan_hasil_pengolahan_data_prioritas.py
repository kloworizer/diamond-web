"""Laporan Hasil Pengolahan Data Prioritas view."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_GET, require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from datetime import datetime, timedelta
from django.db.models import Q
from io import BytesIO
from openpyxl import Workbook

from ..models.tiket import Tiket
from ..constants.tiket_status import STATUS_LABELS
from ..constants.jenis_tabel import JENIS_TABEL_DIIDENTIFIKASI, JENIS_TABEL_TIDAK_DIIDENTIFIKASI
from ..forms.laporan_hasil_pengolahan_data_prioritas import LaporanHasilPengolahanDataPrioritasFilterForm, LaporanHasilPengolahanDataPrioritasExportResource
from ..utils import format_periode


def _is_pmde_user(user):
    """Check if user is PMDE user or admin."""
    return user.is_superuser or user.is_staff or user.groups.filter(name__in=['user_pmde', 'admin', 'admin_pmde']).exists()


class LaporanHasilPengolahanDataPrioritasView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display Laporan Hasil Pengolahan Data Prioritas with filtering by periode and year.
    
    This view renders a template with filter form and DataTables table that displays
    tikets. Access control is enforced via test_func() to verify user is PMDE user or admin.
    
    Template: laporan_hasil_pengolahan_data_prioritas/list.html
    """
    template_name = 'laporan_hasil_pengolahan_data_prioritas/list.html'
    
    def test_func(self):
        """Verify user is PMDE user or admin."""
        return _is_pmde_user(self.request.user)
    
    def get_context_data(self, **kwargs):
        """Add years list and form to context for filter dropdown."""
        context = super().get_context_data(**kwargs)
        # Get unique years from tiket data
        tikets = Tiket.objects.all()
        years = sorted(set(t.tahun for t in tikets), reverse=True)
        
        # Always include current year
        current_year = datetime.now().year
        if current_year not in years:
            years = [current_year] + list(years)
        
        context['years'] = years
        # Initialize form with years
        context['form'] = LaporanHasilPengolahanDataPrioritasFilterForm(years=years)
        return context


@login_required
@user_passes_test(_is_pmde_user)
@require_http_methods(["GET", "POST"])
@csrf_protect
def laporan_hasil_pengolahan_data_prioritas_data(request):
    """DataTables server-side endpoint for Laporan Hasil Pengolahan Data Prioritas.
    
    Filters tikets by:
    - tgl_transfer within specified periode (month/quarter/semester/year) and tahun (year)
    - Periode types:
      - bulanan (monthly): Filter by specific month (1-12)
      - triwulanan (quarterly): Filter by quarter (1-4)
      - semester (semiannual): Filter by semester (1-2)
      - tahunan (yearly): Filter by entire year
    
    GET Parameters:
    - periode_type: Type of period (bulanan, triwulanan, semester, tahunan), required
    - periode: Period value based on type, required
    - tahun: Year, required
    - draw: DataTables draw counter
    - start: Record offset for pagination
    - length: Number of records per page
    
    Returns JSON with tiket data.
    """
    params = request.POST if request.method == 'POST' else request.GET
    periode_type = params.get('periode_type')
    periode = params.get('periode')
    tahun = params.get('tahun')

    try:
        draw = int(params.get('draw', 1))
    except (ValueError, TypeError):
        draw = 1

    try:
        start = int(params.get('start', 0))
    except (ValueError, TypeError):
        start = 0

    try:
        length = int(params.get('length', 10))
    except (ValueError, TypeError):
        length = 10
    
    # Validate inputs
    if not periode_type or not periode or not tahun:
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        })
    
    try:
        tahun_int = int(tahun)
    except (ValueError, TypeError):
        return JsonResponse({
            'draw': draw,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': []
        })
    
    # Calculate date range based on periode type
    start_date = None
    end_date = None
    
    if periode_type == 'bulanan':
        try:
            bulan = int(periode)
            if bulan < 1 or bulan > 12:
                return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
            start_date = datetime(tahun_int, bulan, 1).date()
            if bulan == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, bulan + 1, 1).date() - timedelta(days=1)
        except (ValueError, TypeError):
            return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
    
    elif periode_type == 'triwulanan':
        quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
        try:
            triwulan = int(periode)
            if triwulan not in quarter_months:
                return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
            start_month, end_month = quarter_months[triwulan]
            start_date = datetime(tahun_int, start_month, 1).date()
            if end_month == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, end_month + 1, 1).date() - timedelta(days=1)
        except (ValueError, TypeError):
            return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
    
    elif periode_type == 'semester':
        semester_months = {1: (1, 6), 2: (7, 12)}
        try:
            semester = int(periode)
            if semester not in semester_months:
                return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
            start_month, end_month = semester_months[semester]
            start_date = datetime(tahun_int, start_month, 1).date()
            if end_month == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, end_month + 1, 1).date() - timedelta(days=1)
        except (ValueError, TypeError):
            return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
    
    elif periode_type == 'tahunan':
        start_date = datetime(tahun_int, 1, 1).date()
        end_date = datetime(tahun_int, 12, 31).date()
    
    else:
        return JsonResponse({'draw': draw, 'recordsTotal': 0, 'recordsFiltered': 0, 'data': []})
    
    # Query tikets with tgl_transfer in the specified period
    # Using tgl_kirim_pide as the relevant date for "pengolahan data"
    tikets = Tiket.objects.filter(
        tgl_kirim_pide__isnull=False,
        tgl_kirim_pide__date__gte=start_date,
        tgl_kirim_pide__date__lte=end_date
    ).select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel',
        'id_periode_data__id_periode_pengiriman'
    ).order_by('-tgl_kirim_pide')
    
    records_total = Tiket.objects.count() # Total records in the system
    records_filtered = tikets.count() # Records after applying date filter
    
    # Pagination
    tikets_paginated = tikets[start:start + length]
    
    # Build response data
    data = []
    for tiket in tikets_paginated:
        pd = tiket.id_periode_data
        sub_jenis_data = pd.id_sub_jenis_data_ilap if pd else None
        ilap = sub_jenis_data.id_ilap if sub_jenis_data else None
        jenis_tabel = sub_jenis_data.id_jenis_tabel if sub_jenis_data else None
        periode_pengiriman = pd.id_periode_pengiriman if pd else None

        # Replicate dehydrate logic from LaporanHasilPengolahanDataPrioritasExportResource
        baris_diterima = tiket.baris_diterima or 0
        baris_i = tiket.baris_i or 0
        baris_u = tiket.baris_u or 0
        baris_lengkap = tiket.baris_lengkap or 0
        baris_tidak_lengkap = tiket.baris_tidak_lengkap or 0

        data_direkam = baris_i + baris_u
        
        data_teridentifikasi = 0
        if sub_jenis_data and jenis_tabel and jenis_tabel.id == JENIS_TABEL_DIIDENTIFIKASI:
            data_teridentifikasi = baris_i

        data_tidak_diidentifikasi = 0
        if sub_jenis_data and jenis_tabel and jenis_tabel.id == JENIS_TABEL_TIDAK_DIIDENTIFIKASI:
            data_tidak_diidentifikasi = baris_i

        data_belum_diidentifikasi = 0
        if sub_jenis_data and jenis_tabel and jenis_tabel.id == JENIS_TABEL_DIIDENTIFIKASI:
            data_belum_diidentifikasi = max(0, baris_diterima - data_direkam)

        periode_tiket_formatted = "-"
        if periode_pengiriman:
            periode_tiket_formatted = format_periode(
                periode_pengiriman.periode_penerimaan,
                tiket.periode,
                tiket.tahun
            )

        row = {
            'no': '', # Will be filled by DataTables counter
            'nama_ilap': ilap.nama_ilap if ilap else '',
            'nama_jenis_data': sub_jenis_data.nama_sub_jenis_data if sub_jenis_data else '',
            'nama_tabel_kpde': sub_jenis_data.nama_tabel_I if sub_jenis_data else '',
            'nama_tabel_bankdata': sub_jenis_data.nama_tabel_I if sub_jenis_data else '',
            'nama_tabel_bankdata_u': sub_jenis_data.nama_tabel_U if sub_jenis_data else '',
            'periode_data': periode_pengiriman.periode_penyampaian if periode_pengiriman else '',
            'id_tiket': tiket.nomor_tiket if tiket.nomor_tiket else '',
            'periode_tiket': periode_tiket_formatted,
            'data_diterima': baris_diterima,
            'data_lengkap': baris_lengkap,
            'data_klarifikasi': baris_tidak_lengkap,
            'data_diterima_v2': baris_diterima, # Repeated as per request
            'data_direkam': data_direkam,
            'data_teridentifikasi': data_teridentifikasi,
            'data_tidak_teridentifikasi': baris_u,
            'data_belum_diidentifikasi': data_belum_diidentifikasi,
            'data_tidak_diidentifikasi': data_tidak_diidentifikasi,
            'data_diterima_tabel_i': data_teridentifikasi, # Alias for data_teridentifikasi
            'data_lolos_qc': tiket.lolos_qc or 0,
            'data_tidak_lolos_qc': tiket.tidak_lolos_qc or 0,
            'data_belum_qc': tiket.qc_c or 0,
            'keterangan': '',
        }
        data.append(row)
    
    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data
    })


@login_required
@user_passes_test(_is_pmde_user)
@require_GET
@csrf_protect
def laporan_hasil_pengolahan_data_prioritas_export(request):
    """Export Laporan Hasil Pengolahan Data Prioritas to XLSX file.
    
    GET Parameters:
    - periode_type: Type of period (bulanan, triwulanan, semester, tahunan)
    - periode: Period value
    - tahun: Year
    
    Returns: XLSX file download
    """
    periode_type = request.GET.get('periode_type')
    periode = request.GET.get('periode')
    tahun = request.GET.get('tahun')
    
    # Validate inputs
    if not periode_type or not periode or not tahun:
        return HttpResponse('Invalid parameters', status=400)
    
    try:
        tahun_int = int(tahun)
    except (ValueError, TypeError):
        return HttpResponse('Invalid year', status=400)
    
    # Calculate date range based on periode type
    start_date = None
    end_date = None
    periode_label = ''
    
    if periode_type == 'bulanan':
        try:
            bulan = int(periode)
            if bulan < 1 or bulan > 12:
                return HttpResponse('Invalid month', status=400)
            start_date = datetime(tahun_int, bulan, 1).date()
            if bulan == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, bulan + 1, 1).date() - timedelta(days=1)
            
            bulan_names = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                          'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
            periode_label = f'{bulan_names[bulan]} {tahun_int}'
        except (ValueError, TypeError):
            return HttpResponse('Invalid month', status=400)
    
    elif periode_type == 'triwulanan':
        quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
        try:
            triwulan = int(periode)
            if triwulan not in quarter_months:
                return HttpResponse('Invalid quarter', status=400)
            start_month, end_month = quarter_months[triwulan]
            start_date = datetime(tahun_int, start_month, 1).date()
            if end_month == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, end_month + 1, 1).date() - timedelta(days=1)
            periode_label = f'Triwulan {triwulan} {tahun_int}'
        except (ValueError, TypeError):
            return HttpResponse('Invalid quarter', status=400)
    
    elif periode_type == 'semester':
        semester_months = {1: (1, 6), 2: (7, 12)}
        try:
            semester = int(periode)
            if semester not in semester_months:
                return HttpResponse('Invalid semester', status=400)
            start_month, end_month = semester_months[semester]
            start_date = datetime(tahun_int, start_month, 1).date()
            if end_month == 12:
                end_date = datetime(tahun_int + 1, 1, 1).date() - timedelta(days=1)
            else:
                end_date = datetime(tahun_int, end_month + 1, 1).date() - timedelta(days=1)
            periode_label = f'Semester {semester} {tahun_int}'
        except (ValueError, TypeError):
            return HttpResponse('Invalid semester', status=400)
    
    elif periode_type == 'tahunan':
        start_date = datetime(tahun_int, 1, 1).date()
        end_date = datetime(tahun_int, 12, 31).date()
        periode_label = f'{tahun_int}'
    
    else:
        return HttpResponse('Invalid periode type', status=400)
    
    
    # Query tikets
    tikets = Tiket.objects.filter(
        tgl_kirim_pide__isnull=False,
        tgl_kirim_pide__date__gte=start_date,
        tgl_kirim_pide__date__lte=end_date
    ).select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel',
        'id_periode_data__id_periode_pengiriman'
    ).order_by('-tgl_kirim_pide')
    
    # Use django-import-export to generate XLSX
    resource = LaporanHasilPengolahanDataPrioritasExportResource()
    dataset = resource.export(tikets)
    
    # tablib (dataset) handles XLSX generation safely and handles character escaping
    excel_data = dataset.xlsx
    
    # Create HTTP response
    response = HttpResponse(
        excel_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Ensure filename is clean for browsers
    clean_filename = f"Laporan_Hasil_Pengolahan_Data_Prioritas_{periode_label.replace(' ', '_')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{clean_filename}"'
    return response