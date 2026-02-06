"""Tiket list view - shared across all workflow steps."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse

from ...models.tiket import Tiket
from ..mixins import UserP3DERequiredMixin


class TiketListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """Display list of all tikets with DataTables integration."""
    template_name = 'tiket/list.html'


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def tiket_data(request):
    """Server-side processing for DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = Tiket.objects.select_related('id_periode_data__id_sub_jenis_data_ilap').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Nomor Tiket
            qs = qs.filter(nomor_tiket__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Periode Jenis Data
            qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Periode
            qs = qs.filter(periode__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Tahun
            qs = qs.filter(tahun__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Status
            qs = qs.filter(status__icontains=columns_search[4])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'nomor_tiket', 'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data', 'periode', 'tahun', 'status']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('id')
    else:
        qs = qs.order_by('id')

    qs_page = qs[start:start + length]

    data = []
    status_labels = {
        1: 'Direkam',
        2: 'Backup direkam',
        3: 'Tanda Terima dibuat',
        4: 'Diteliti',
        5: 'Dikembalikan',
        6: 'Dikirim ke PIDE',
        7: 'Identifikasi',
        8: 'Pengendalian Mutu',
        9: 'Dibatalkan',
        10: 'Selesai'
    }
    
    for obj in qs_page:
        data.append({
            'id': obj.id,
            'nomor_tiket': obj.nomor_tiket or '-',
            'periode_jenis_data': str(obj.id_periode_data) if obj.id_periode_data else '-',
            'periode': str(obj.periode) if obj.periode else '-',
            'tahun': str(obj.tahun) if obj.tahun else '-',
            'status': status_labels.get(obj.status, '-'),
            'actions': f"<a href='{reverse('tiket_detail', args=[obj.pk])}' class='btn btn-sm btn-info' title='View'><i class='ri-eye-line'></i></a>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
