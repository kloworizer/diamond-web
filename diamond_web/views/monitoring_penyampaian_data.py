from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from datetime import datetime, timedelta

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
from .mixins import UserP3DERequiredMixin


class MonitoringPenyampaianDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for monitoring data submissions (monitoring penyampaian data).

    Renders `monitoring_penyampaian_data/list.html`. Shows monitoring for each sub jenis data
    with periodic rows from start_date until current date, checking submission status for each period.
    """
    template_name = 'monitoring_penyampaian_data/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


def get_period_display_name(periode_type, periode_num, start_date):
    """Generate period display name based on type and number."""
    months_indo = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
                   'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    
    periode_type_lower = periode_type.lower()
    
    if periode_type_lower == 'harian':
        return start_date.strftime('%d-%m-%Y')
    elif periode_type_lower == 'mingguan':
        return f"Minggu {periode_num}"
    elif periode_type_lower == '2 mingguan':
        return f"2 Minggu {periode_num}"
    elif periode_type_lower == 'bulanan':
        month_idx = (start_date.month - 1 + (periode_num - 1)) % 12
        return months_indo[month_idx]
    elif periode_type_lower == 'triwulanan':
        return f"Triwulan {periode_num}"
    elif periode_type_lower == 'kuartal':
        return f"Kuartal {periode_num}"
    elif periode_type_lower == 'semester':
        return f"Semester {periode_num}"
    elif periode_type_lower == 'tahunan':
        return "-"
    else:
        return str(periode_num)


def get_periods_for_range(start_date, end_date, periode_type):
    """Generate period dates based on periode type from start_date to end_date.
    
    Periode count resets to 1 at the beginning of each calendar year.
    """
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
            # Add 1 month
            if current.month == 12:
                next_date = current.replace(year=current.year + 1, month=1)
            else:
                next_date = current.replace(month=current.month + 1)
        elif periode_type.lower() == 'triwulanan':
            # Add 3 months
            month = current.month + 3
            year = current.year
            while month > 12:
                month -= 12
                year += 1
            next_date = current.replace(year=year, month=month)
        elif periode_type.lower() == 'kuartal':
            # Add 3 months
            month = current.month + 3
            year = current.year
            while month > 12:
                month -= 12
                year += 1
            next_date = current.replace(year=year, month=month)
        elif periode_type.lower() == 'semester':
            # Add 6 months
            month = current.month + 6
            year = current.year
            while month > 12:
                month -= 12
                year += 1
            next_date = current.replace(year=year, month=month)
        elif periode_type.lower() == 'tahunan':
            # Add 1 year
            next_date = current.replace(year=current.year + 1)
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
    
    Generates monitoring rows for each sub jenis data from start_date to current date,
    checking if tiket exists for each period and calculating if late.
    
    Permissions: wrapped by decorators to allow only users in `admin` or
    `user_p3de` groups. Non-admin users are further restricted to
    monitoring records for sub jenis data where they are an active P3DE PIC.
    
    Query parameters for filter options: get_filter_options=1 to get available filter values
    Query parameters for filtering: kanwil, kpp, kategori_wilayah, kategori_ilap, ilap, 
                                     jenis_data, sub_jenis_data, status_penyampaian, terlambat
    """
    # Check if requesting filter options
    if request.GET.get('get_filter_options'):
        kanwil_list = Kanwil.objects.all().values('id', 'nama_kanwil').order_by('nama_kanwil')
        kpp_list = KPP.objects.all().values('id', 'nama_kpp').order_by('nama_kpp')
        kategori_wilayah_list = KategoriWilayah.objects.all().values('id', 'deskripsi').order_by('deskripsi')
        kategori_ilap_list = KategoriILAP.objects.all().values('id', 'id_kategori', 'nama_kategori').order_by('nama_kategori')
        ilap_list = ILAP.objects.all().values('id', 'id_ilap', 'nama_ilap').order_by('id_ilap')
        jenis_data_list = JenisDataILAP.objects.values('nama_jenis_data').distinct().order_by('nama_jenis_data')
        sub_jenis_data_list = JenisDataILAP.objects.values('id_sub_jenis_data', 'nama_sub_jenis_data').distinct().order_by('id_sub_jenis_data')
        
        return JsonResponse({
            'filter_options': {
                'kanwil': [{'id': str(k['id']), 'name': k['nama_kanwil']} for k in kanwil_list],
                'kpp': [{'id': str(k['id']), 'name': k['nama_kpp']} for k in kpp_list],
                'kategori_wilayah': [{'id': str(k['id']), 'name': k['deskripsi']} for k in kategori_wilayah_list],
                'kategori_ilap': [{'id': str(k['id']), 'name': f"{k['id_kategori']} - {k['nama_kategori']}"} for k in kategori_ilap_list],
                'ilap': [{'id': str(k['id']), 'name': f"{k['id_ilap']} - {k['nama_ilap']}"} for k in ilap_list],
                'jenis_data': [{'id': k['nama_jenis_data'], 'name': k['nama_jenis_data']} for k in jenis_data_list],
                'sub_jenis_data': [{'id': k['id_sub_jenis_data'], 'name': f"{k['id_sub_jenis_data']} - {k['nama_sub_jenis_data']}"} for k in sub_jenis_data_list],
            }
        })
    
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    today = datetime.now().date()
    records = []

    # Get all jenis_data_ilap with related data
    jenis_data_ilap_list = JenisDataILAP.objects.select_related(
        'id_ilap',
        'id_ilap__id_kategori',
        'id_ilap__id_kategori_wilayah',
        'id_ilap__id_kpp',
        'id_ilap__id_kpp__id_kanwil',
        'id_jenis_tabel',
        'id_status_data'
    ).all()

    # For each jenis_data_ilap, generate monitoring records for each period
    for jenis_data in jenis_data_ilap_list:
        # Get all periode_jenis_data for this jenis_data_ilap
        periode_data_list = PeriodeJenisData.objects.filter(
            id_sub_jenis_data_ilap=jenis_data
        ).select_related('id_periode_pengiriman').all()

        for periode_data in periode_data_list:
            if not periode_data.id_periode_pengiriman:
                continue
                
            # Get start date and generate periods until today
            start_date = periode_data.start_date
            akhir_penyampaian = periode_data.akhir_penyampaian  # days to submit after period end
            periode_type_penyampaian = periode_data.id_periode_pengiriman.periode_penyampaian
            periode_type_penerimaan = periode_data.id_periode_pengiriman.periode_penerimaan  # Use this for row generation
            
            # Generate all periods from start_date until today using periode_penerimaan
            periods = get_periods_for_range(start_date, today, periode_type_penerimaan)
            
            for period in periods:
                deadline_date = period['end_date'] + timedelta(days=akhir_penyampaian)
                period_display_name = get_period_display_name(periode_type_penerimaan, period['periode_num'], start_date)
                
                # Check if tiket exists for this period
                tiket_exists = Tiket.objects.filter(
                    id_periode_data=periode_data,
                    periode=period['periode_num']
                ).exists()
                
                # Determine status
                if tiket_exists:
                    # Check if tanda_terima exists (data submitted)
                    tanda_terima_exists = DetilTandaTerima.objects.filter(
                        id_tiket__id_periode_data=periode_data,
                        id_tiket__periode=period['periode_num']
                    ).exists()
                    
                    if tanda_terima_exists:
                        status_penyampaian = "Sudah Menyampaikan"
                        status_penyampaian_class = "bg-success"
                        is_late = False
                        status_terlambat = "Tidak"
                        status_terlambat_class = "bg-light"
                    else:
                        # Tiket exists but no tanda_terima
                        is_late = today > deadline_date
                        status_penyampaian = "Belum Menyampaikan"
                        status_penyampaian_class = "bg-warning"
                        if is_late:
                            status_terlambat = "Ya"
                            status_terlambat_class = "bg-danger"
                        else:
                            status_terlambat = "Tidak"
                            status_terlambat_class = "bg-light"
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
                    'ilap_name': jenis_data.id_ilap.nama_ilap,
                    'ilap_id': jenis_data.id_ilap.id_ilap,
                    'ilap_jenis_data_id': jenis_data.id_ilap.id,
                    'jenis_data': jenis_data.nama_jenis_data,
                    'jenis_data_id': jenis_data.id,
                    'sub_jenis_data': jenis_data.nama_sub_jenis_data,
                    'periode_penyampaian': periode_type_penyampaian,
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
                    'kanwil_id': (jenis_data.id_ilap.id_kpp.id_kanwil_id if jenis_data.id_ilap.id_kpp else ''),
                    'kpp_id': (jenis_data.id_ilap.id_kpp.id if jenis_data.id_ilap.id_kpp else ''),
                    'kategori_wilayah_id': jenis_data.id_ilap.id_kategori_wilayah.id if jenis_data.id_ilap.id_kategori_wilayah else '',
                    'kategori_ilap_id': jenis_data.id_ilap.id_kategori.id if jenis_data.id_ilap.id_kategori else '',
                })

    records_total = len(records)

    # Apply RBAC filtering
    # Admin users see all records
    # Non-admin P3DE users see only records for sub jenis data where they are an active P3DE PIC
    if not request.user.is_superuser and not request.user.groups.filter(name='admin').exists():
        # Get jenis_data_ilap IDs where user is active P3DE PIC (end_date is None means active)
        user_jenis_data_ids = set(
            PIC.objects.filter(
                id_user=request.user,
                tipe=PIC.TipePIC.P3DE,
                end_date__isnull=True
            ).values_list('id_sub_jenis_data_ilap_id', flat=True)
        )
        records = [r for r in records if r['id_jenis_data'] in user_jenis_data_ids]

    records_total = len(records)

    # Apply filter form parameters
    kanwil_id = request.GET.get('kanwil', '')
    kpp_id = request.GET.get('kpp', '')
    kategori_wilayah_id = request.GET.get('kategori_wilayah', '')
    kategori_ilap_id = request.GET.get('kategori_ilap', '')
    ilap_id = request.GET.get('ilap', '')
    jenis_data_id = request.GET.get('jenis_data', '')
    sub_jenis_data_id = request.GET.get('sub_jenis_data', '')
    status_penyampaian_filter = request.GET.get('status_penyampaian', '')
    terlambat_filter = request.GET.get('terlambat', '')
    
    filtered_records = records
    
    if kanwil_id:
        filtered_records = [r for r in filtered_records if str(r.get('kanwil_id', '')) == kanwil_id]
    if kpp_id:
        filtered_records = [r for r in filtered_records if str(r.get('kpp_id', '')) == kpp_id]
    if kategori_wilayah_id:
        filtered_records = [r for r in filtered_records if str(r.get('kategori_wilayah_id', '')) == kategori_wilayah_id]
    if kategori_ilap_id:
        filtered_records = [r for r in filtered_records if str(r.get('kategori_ilap_id', '')) == kategori_ilap_id]
    if ilap_id:
        filtered_records = [r for r in filtered_records if str(r.get('ilap_jenis_data_id', '')) == ilap_id]
    if jenis_data_id:
        filtered_records = [r for r in filtered_records if r.get('jenis_data', '') == jenis_data_id]
    if sub_jenis_data_id:
        filtered_records = [r for r in filtered_records if r.get('id_sub_jenis_data', '') == sub_jenis_data_id]
    if status_penyampaian_filter:
        filtered_records = [r for r in filtered_records if r.get('status_penyampaian', '') == status_penyampaian_filter]
    if terlambat_filter:
        filtered_records = [r for r in filtered_records if r.get('status_terlambat', '') == terlambat_filter]

    records_total = len(records)

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    
    if columns_search:
        if columns_search[0]:  # ILAP
            search_term = columns_search[0].lower()
            filtered_records = [r for r in filtered_records if search_term in r['ilap_name'].lower() or search_term in r['ilap_id'].lower()]
        if len(columns_search) > 1 and columns_search[1]:  # Jenis Data - only search jenis data fields, not ilap
            search_term = columns_search[1].lower()
            filtered_records = [r for r in filtered_records if (
                search_term in r['id_sub_jenis_data'].lower() or 
                search_term in r['sub_jenis_data'].lower() or 
                search_term in r['jenis_data'].lower()
            ) and search_term not in r['ilap_name'].lower()]
        if len(columns_search) > 2 and columns_search[2]:  # Periode Penyampaian
            filtered_records = [r for r in filtered_records if columns_search[2].lower() in r['periode_penyampaian'].lower()]
        if len(columns_search) > 3 and columns_search[3]:  # Periode
            try:
                periode_val = int(columns_search[3])
                filtered_records = [r for r in filtered_records if r['periode'] == periode_val]
            except:
                pass
        if len(columns_search) > 4 and columns_search[4]:  # Tahun
            try:
                tahun_val = int(columns_search[4])
                filtered_records = [r for r in filtered_records if r['tahun'] == tahun_val]
            except:
                pass
        if len(columns_search) > 5 and columns_search[5]:  # Status Penyampaian
            status_filter = columns_search[5].lower().strip()
            filtered_records = [r for r in filtered_records if status_filter in r['status_penyampaian'].lower()]
        if len(columns_search) > 6 and columns_search[6]:  # Status Terlambat
            status_filter = columns_search[6].lower().strip()
            filtered_records = [r for r in filtered_records if status_filter in r['status_terlambat'].lower()]

    records_filtered = len(filtered_records)

    # Sorting
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['ilap_name', 'jenis_data', 'periode_penyampaian', 'periode', 'tahun', 'status_penyampaian', 'status_terlambat', 'days_diff']
    
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
        actions = (
            f'<div class="btn-group btn-group-sm">'
            f'<a href="/tiket/?jenis_data={record["id_jenis_data"]}&periode={record["periode_num"]}" '
            f'class="btn btn-primary btn-sm" title="Lihat Detail">'
            f'<i class="ri-eye-line"></i>'
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
            'periode_penyampaian': record['periode_penyampaian'],
            'periode': record['periode_display_name'],
            'tahun': record['tahun'],
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

