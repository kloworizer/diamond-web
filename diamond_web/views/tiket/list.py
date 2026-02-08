"""Tiket list view - shared across all workflow steps."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse
from django.urls import reverse

from ...models.tiket import Tiket
from ..mixins import can_access_tiket_list
from ...constants.tiket_status import STATUS_LABELS


class TiketListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display list of all tikets with DataTables integration."""
    template_name = 'tiket/list.html'

    def test_func(self):
        return can_access_tiket_list(self.request.user)


@login_required
@user_passes_test(lambda u: can_access_tiket_list(u))
@require_GET
def tiket_data(request):
    """Server-side processing for DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = Tiket.objects.select_related('id_periode_data__id_sub_jenis_data_ilap').all()
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        qs = qs.filter(
            tiketpic__id_user=request.user
        ).distinct()
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
    for obj in qs_page:
        # Get nama_ilap and nama_sub_jenis_data from related models
        nama_ilap = '-'
        nama_sub_jenis_data = '-'
        if obj.id_periode_data and obj.id_periode_data.id_sub_jenis_data_ilap:
            jenis_data_ilap = obj.id_periode_data.id_sub_jenis_data_ilap
            if jenis_data_ilap.id_ilap:
                nama_ilap = jenis_data_ilap.id_ilap.nama_ilap
            nama_sub_jenis_data = jenis_data_ilap.nama_sub_jenis_data

        # Format periode (e.g. Januari 2026, Semester 1 2026)
        periode_formatted = '-'
        if obj.id_periode_data and obj.id_periode_data.id_periode_pengiriman:
            periode_desc = obj.id_periode_data.id_periode_pengiriman.deskripsi
            tahun = str(obj.tahun) if obj.tahun else '-'
            if periode_desc.lower() == 'bulanan' and obj.periode:
                # Map periode number to month name
                bulan_map = {
                    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
                    7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
                }
                bulan = bulan_map.get(obj.periode, f'Bulan {obj.periode}')
                periode_formatted = f"{bulan} {tahun}"
            elif 'semester' in periode_desc.lower() and obj.periode:
                periode_formatted = f"Semester {obj.periode} {tahun}"
            elif 'triwulan' in periode_desc.lower() and obj.periode:
                periode_formatted = f"Triwulan {obj.periode} {tahun}"
            elif 'mingguan' in periode_desc.lower() and obj.periode:
                periode_formatted = f"Minggu {obj.periode} {tahun}"
            else:
                periode_formatted = f"{periode_desc} {tahun}"

        data.append({
            'id': obj.id,
            'nomor_tiket': obj.nomor_tiket or '-',
            'nama_ilap': nama_ilap,
            'nama_sub_jenis_data': nama_sub_jenis_data,
            'periode_formatted': periode_formatted,
            'status': STATUS_LABELS.get(obj.status, '-'),
            'actions': f"<a href='{reverse('tiket_detail', args=[obj.pk])}' class='btn btn-sm btn-info' title='View'><i class='ri-eye-line'></i></a>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
