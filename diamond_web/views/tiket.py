from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET
from django.utils import timezone
from django.db import transaction
from datetime import datetime

from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..models.periode_jenis_data import PeriodeJenisData
from ..forms.tiket import TiketForm
from .mixins import AjaxFormMixin

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()

class TiketListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'tiket/list.html'

class TiketCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Tiket
    form_class = TiketForm
    template_name = 'tiket/form.html'
    success_url = reverse_lazy('tiket_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tiket_create')
        context['page_title'] = 'Rekam Penerimaan Data'
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Get the periode_jenis_data to extract id_sub_jenis_data
                periode_jenis_data = form.cleaned_data['id_periode_data']
                id_sub_jenis_data = periode_jenis_data.id_sub_jenis_data_ilap.id_sub_jenis_data
                
                # Generate nomor_tiket: id_sub_jenis_data (9 digit) + yymmdd + 2 digit sequence
                today = timezone.now().date()
                yymmdd = today.strftime('%y%m%d')
                
                # Get the count of tickets for this id_sub_jenis_data and date
                nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
                count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
                sequence = str(count + 1).zfill(3)
                
                nomor_tiket = f"{nomor_tiket_prefix}{sequence}"
                
                # Save the tiket with status = 1
                self.object = form.save(commit=False)
                self.object.nomor_tiket = nomor_tiket
                self.object.status = 1
                self.object.save()
                
                # Create tiket_action entry
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=timezone.now(),
                    action=1,
                    catatan="tiket direkam"
                )
                
                # Create tiket_pic entry
                TiketPIC.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=timezone.now(),
                    role=1
                )
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Tiket "{nomor_tiket}" created successfully.',
                        'redirect': self.success_url
                    })
                    
                messages.success(self.request, f'Tiket "{nomor_tiket}" created successfully.')
                return super().form_valid(form)
                
        except Exception as e:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [str(e)]}
                })
            messages.error(self.request, f'Error creating tiket: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
        return super().form_invalid(form)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def tiket_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
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
    columns = ['nomor_tiket', 'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data', 'periode', 'tahun', 'status']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-id')
    else:
        qs = qs.order_by('-id')

    qs_page = qs[start:start + length]

    data = []
    status_labels = {
        1: 'Direkam',
        2: 'Diteliti',
        3: 'Dikirim ke PIDE',
        4: 'Dibatalkan',
        5: 'Dikembalikan'
    }
    
    for obj in qs_page:
        data.append({
            'nomor_tiket': obj.nomor_tiket or '-',
            'periode_jenis_data': str(obj.id_periode_data) if obj.id_periode_data else '-',
            'periode': str(obj.periode) if obj.periode else '-',
            'tahun': str(obj.tahun) if obj.tahun else '-',
            'status': status_labels.get(obj.status, '-'),
            'tgl_terima_vertikal': obj.tgl_terima_vertikal.strftime('%Y-%m-%d %H:%M') if obj.tgl_terima_vertikal else '-',
            'tgl_terima_dip': obj.tgl_terima_dip.strftime('%Y-%m-%d %H:%M') if obj.tgl_terima_dip else '-',
            'actions': f"<button class='btn btn-sm btn-info' data-action='view' data-id='{obj.pk}' title='View'><i class='ri-eye-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
