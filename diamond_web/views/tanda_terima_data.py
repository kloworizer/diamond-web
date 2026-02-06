from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from ..models.tanda_terima_data import TandaTerimaData
from ..models.detil_tanda_terima import DetilTandaTerima
from ..models.tiket_action import TiketAction
from ..forms.tanda_terima_data import TandaTerimaDataForm
from .mixins import AjaxFormMixin, UserP3DERequiredMixin


class TandaTerimaDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    template_name = 'tanda_terima_data/list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Tanda Terima Data "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def tanda_terima_data_data(request):
    """Server-side processing for Tanda Terima Data DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = TandaTerimaData.objects.select_related('id_ilap', 'id_perekam').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Nomor Tanda Terima
            qs = qs.filter(nomor_tanda_terima__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Tanggal
            qs = qs.filter(tanggal_tanda_terima__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # ILAP
            qs = qs.filter(id_ilap__nama_ilap__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Deskripsi
            qs = qs.filter(deskripsi__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Perekam
            qs = qs.filter(id_perekam__username__icontains=columns_search[4])

    records_filtered = qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['nomor_tanda_terima', 'tanggal_tanda_terima', 'id_ilap__nama_ilap', 'deskripsi', 'id_perekam__username']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'nomor_tanda_terima'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-tanggal_tanda_terima')
    else:
        qs = qs.order_by('-tanggal_tanda_terima')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        data.append({
            'nomor_tanda_terima': obj.nomor_tanda_terima,
            'tanggal_tanda_terima': obj.tanggal_tanda_terima.strftime('%Y-%m-%d %H:%M'),
            'id_ilap': str(obj.id_ilap),
            'deskripsi': obj.deskripsi,
            'id_perekam': obj.id_perekam.username,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('tanda_terima_data_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('tanda_terima_data_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
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
def tanda_terima_next_number(request):
    """Return next nomor_tanda_terima based on selected tanggal_tanda_terima year."""
    tanggal_param = request.GET.get('tanggal')
    tanggal = parse_datetime(tanggal_param) if tanggal_param else None
    if tanggal is None and tanggal_param:
        tanggal = parse_date(tanggal_param)

    tahun = (tanggal or timezone.now()).year
    suffix = f"/{tahun}"

    existing_numbers = TandaTerimaData.objects.filter(
        nomor_tanda_terima__endswith=suffix
    ).values_list('nomor_tanda_terima', flat=True)

    max_seq = 0
    for nomor in existing_numbers:
        try:
            seq_part = nomor.split('/')[0]
            max_seq = max(max_seq, int(seq_part))
        except Exception:
            continue

    next_seq = max_seq + 1
    nomor_tanda_terima = f"{str(next_seq).zfill(5)}/{tahun}"

    return JsonResponse({
        'success': True,
        'nomor_tanda_terima': nomor_tanda_terima
    })


class TandaTerimaDataCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_url = reverse_lazy('tanda_terima_data_list')
    success_message = 'Tanda Terima Data "{object}" created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        # Set the logged-in user as id_perekam
        form.instance.id_perekam = self.request.user
        response = super().form_valid(form)
        
        # Save selected tikets to DetilTandaTerima
        tiket_ids = form.cleaned_data.get('tiket_ids', [])
        for tiket in tiket_ids:
            DetilTandaTerima.objects.create(
                id_tanda_terima=self.object,
                id_tiket=tiket
            )
        
        return response


class TandaTerimaDataFromTiketCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create Tanda Terima Data from a specific Tiket."""
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_message = 'Tanda Terima Data "{object}" created successfully.'

    def get_success_url(self):
        return reverse('tiket_detail', kwargs={'pk': self.kwargs['tiket_pk']})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tiket_pk'] = self.kwargs.get('tiket_pk')
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_from_tiket_create', args=[self.kwargs['tiket_pk']])
        from ..models.tiket import Tiket
        context['tiket'] = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        from ..models.tiket import Tiket
        
        # Set the logged-in user as id_perekam
        form.instance.id_perekam = self.request.user
        # Ensure ILAP is set from tiket for single-tiket flow
        tiket = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        if tiket.id_periode_data:
            form.instance.id_ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        
        # Save the form (this sets self.object)
        self.object = form.save()
        
        # Create DetilTandaTerima for the specific tiket
        DetilTandaTerima.objects.create(
            id_tanda_terima=self.object,
            id_tiket=tiket
        )

        # Update tiket status and record action
        tiket.status = 3
        tiket.save()
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=timezone.now(),
            action=3,
            catatan='Tanda terima dibuat'
        )
        
        # Now handle the response (AJAX or redirect)
        message = self.get_success_message(form)
        if self.is_ajax():
            payload = {"success": True}
            if message:
                payload["message"] = message
            return JsonResponse(payload)
        if message:
            messages.success(self.request, message)
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())


class TandaTerimaDataUpdateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, UpdateView):
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_url = reverse_lazy('tanda_terima_data_list')
    success_message = 'Tanda Terima Data "{object}" updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Update tiket selections
        tiket_ids = form.cleaned_data.get('tiket_ids', [])
        
        # Delete existing detil items
        DetilTandaTerima.objects.filter(id_tanda_terima=self.object).delete()
        
        # Create new detil items
        for tiket in tiket_ids:
            DetilTandaTerima.objects.create(
                id_tanda_terima=self.object,
                id_tiket=tiket
            )

            # Record tiket_action for audit trail
            TiketAction.objects.create(
                id_tiket=tiket,
                id_user=self.request.user,
                timestamp=timezone.now(),
                action=3,
                catatan='Tanda terima diubah'
            )
        
        return response


class TandaTerimaDataDeleteView(LoginRequiredMixin, UserP3DERequiredMixin, DeleteView):
    model = TandaTerimaData
    template_name = 'tanda_terima_data/confirm_delete.html'
    success_url = reverse_lazy('tanda_terima_data_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Tanda Terima Data "{name}" deleted successfully.'
            })
        messages.success(request, f'Tanda Terima Data "{name}" deleted successfully.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
