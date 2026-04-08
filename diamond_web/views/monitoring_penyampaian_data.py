from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from datetime import datetime, timedelta
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
        return months_indo[start_date.month - 1]
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
        
        # Get unique tahun from periode_jenis_data and generate range up to current year
        from django.db.models import Min, Max
        tahun_range = PeriodeJenisData.objects.aggregate(
            min_year=Min('start_date__year'),
            max_year=Max('start_date__year')
        )
        min_year = tahun_range.get('min_year') or datetime.now().year
        max_year = max(tahun_range.get('max_year') or datetime.now().year, datetime.now().year)
        tahun_options = [{'id': str(year), 'name': str(year)} for year in range(min_year, max_year + 1)]
        
        # Get PIC P3DE list based on user role
        if request.user.is_superuser or request.user.groups.filter(name='admin').exists():
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
            # User P3DE: show only their own name
            user_pic = PIC.objects.filter(
                id_user=request.user,
                tipe=PIC.TipePIC.P3DE,
                end_date__isnull=True
            ).first()
            if user_pic:
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
            }
        })
    
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    today = datetime.now().date()
    records = []

    # Build a map of jenis_data_ilap_id -> set of dasar_hukum ids (many-to-many via KlasifikasiJenisData)
    dasar_hukum_map = {}
    for kj in KlasifikasiJenisData.objects.values('id_jenis_data_ilap_id', 'id_klasifikasi_tabel_id'):
        dasar_hukum_map.setdefault(kj['id_jenis_data_ilap_id'], set()).add(kj['id_klasifikasi_tabel_id'])

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
            periode_type_penerimaan = periode_data.id_periode_pengiriman.periode_penerimaan

            # Rule: sub-monthly penyampaian (harian, mingguan, 2 mingguan) is always
            # received/grouped monthly — override penerimaan to bulanan regardless of DB value
            if periode_type_penyampaian.lower() in ('harian', 'mingguan', '2 mingguan'):
                periode_type_penerimaan = 'Bulanan'

            # Determine the end date for period generation
            # If periode_data has an end_date, use it; otherwise use today
            end_date_for_periods = periode_data.end_date if periode_data.end_date else today

            # Generate all periods from start_date until end_date_for_periods using effective periode_penerimaan
            periods = get_periods_for_range(start_date, end_date_for_periods, periode_type_penerimaan)
            
            for period in periods:
                deadline_date = period['end_date'] + timedelta(days=akhir_penyampaian)
                period_display_name = get_period_display_name(periode_type_penerimaan, period['periode_num'], period['start_date'])
                
                # Get pic_p3de from PIC model (active P3DE PIC for this jenis_data_ilap)
                pic_p3de = PIC.objects.filter(
                    id_sub_jenis_data_ilap=jenis_data,
                    tipe=PIC.TipePIC.P3DE,
                    end_date__isnull=True
                ).first()
                pic_p3de_id = pic_p3de.id_user_id if pic_p3de else None
                
                # Check if tiket exists for this period
                tiket = Tiket.objects.filter(
                    id_periode_data=periode_data,
                    periode=period['periode_num'],
                    tahun=period['start_date'].year
                ).first()
                
                tiket_exists = tiket is not None
                
                # Determine status
                if tiket_exists:
                    # Tiket exists means data has been submitted (sudah menyampaikan)
                    status_penyampaian = "Sudah Menyampaikan"
                    status_penyampaian_class = "bg-success"
                    is_late = False
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
                    'pic_p3de_id': pic_p3de_id,
                    'kanwil_id': (jenis_data.id_ilap.id_kpp.id_kanwil_id if jenis_data.id_ilap.id_kpp else ''),
                    'kpp_id': (jenis_data.id_ilap.id_kpp.id if jenis_data.id_ilap.id_kpp else ''),
                    'kategori_wilayah_id': jenis_data.id_ilap.id_kategori_wilayah.id if jenis_data.id_ilap.id_kategori_wilayah else '',
                    'kategori_ilap_id': jenis_data.id_ilap.id_kategori.id if jenis_data.id_ilap.id_kategori else '',
                    'jenis_tabel_id': jenis_data.id_jenis_tabel_id,
                    'periode_pengiriman_id': periode_data.id_periode_pengiriman_id,
                    'dasar_hukum_ids': dasar_hukum_map.get(jenis_data.id, set()),
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
    
    filtered_records = records
    
    if tahun_filter:
        filtered_records = [r for r in filtered_records if str(r.get('tahun', '')) == tahun_filter]
    if pic_p3de_filter:
        filtered_records = [r for r in filtered_records if r.get('pic_p3de_id') and str(r.get('pic_p3de_id')) == pic_p3de_filter]
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

    jenis_tabel_filter = request.GET.get('jenis_tabel', '')
    dasar_hukum_filter = request.GET.get('dasar_hukum', '')
    periode_pengiriman_filter = request.GET.get('periode_pengiriman', '')

    if jenis_tabel_filter:
        filtered_records = [r for r in filtered_records if str(r.get('jenis_tabel_id', '')) == jenis_tabel_filter]
    if dasar_hukum_filter:
        filtered_records = [r for r in filtered_records if int(dasar_hukum_filter) in r.get('dasar_hukum_ids', set())]
    if periode_pengiriman_filter:
        filtered_records = [r for r in filtered_records if str(r.get('periode_pengiriman_id', '')) == periode_pengiriman_filter]

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
            f'<i class="ri-eye-line"></i>'
            f'</a>'
            f'<a href="/tiket/rekam/create/?{tiket_rekam_query}" '
            f'class="btn btn-success btn-sm" title="Rekam Penerimaan Data">'
            f'<i class="ri-file-add-line"></i>'
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

