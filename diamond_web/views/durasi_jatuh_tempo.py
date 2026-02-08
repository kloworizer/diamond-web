from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..forms.durasi_jatuh_tempo import DurasiJatuhTempoForm
from .mixins import AjaxFormMixin

# ========== PIDE Section ==========

class AdminPIDERequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide']).exists()

class DurasiJatuhTempoPIDEListView(LoginRequiredMixin, AdminPIDERequiredMixin, TemplateView):
    template_name = 'durasi_jatuh_tempo/pide_list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class DurasiJatuhTempoPIDECreateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, CreateView):
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pide'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class DurasiJatuhTempoPIDEUpdateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, UpdateView):
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pide'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class DurasiJatuhTempoPIDEDeleteView(LoginRequiredMixin, AdminPIDERequiredMixin, DeleteView):
    model = DurasiJatuhTempo
    template_name = 'durasi_jatuh_tempo/confirm_delete.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_delete', args=[self.object.pk])
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
                'message': f'Durasi Jatuh Tempo "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def durasi_jatuh_tempo_pide_data(request):
    """Server-side processing for DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = DurasiJatuhTempo.objects.select_related('id_sub_jenis_data', 'seksi').filter(seksi__name='user_pide')
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(durasi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(end_date__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
        data.append({
            'sub_jenis_data': str(obj.id_sub_jenis_data),
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ========== PMDE Section ==========

class AdminPMDERequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde']).exists()

class DurasiJatuhTempoPMDEListView(LoginRequiredMixin, AdminPMDERequiredMixin, TemplateView):
    template_name = 'durasi_jatuh_tempo/pmde_list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class DurasiJatuhTempoPMDECreateView(LoginRequiredMixin, AdminPMDERequiredMixin, AjaxFormMixin, CreateView):
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pmde'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class DurasiJatuhTempoPMDEUpdateView(LoginRequiredMixin, AdminPMDERequiredMixin, AjaxFormMixin, UpdateView):
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pmde'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class DurasiJatuhTempoPMDEDeleteView(LoginRequiredMixin, AdminPMDERequiredMixin, DeleteView):
    model = DurasiJatuhTempo
    template_name = 'durasi_jatuh_tempo/confirm_delete.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_delete', args=[self.object.pk])
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
                'message': f'Durasi Jatuh Tempo "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_data(request):
    """Server-side processing for DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = DurasiJatuhTempo.objects.select_related('id_sub_jenis_data', 'seksi').filter(seksi__name='user_pmde')
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(durasi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(end_date__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
        data.append({
            'sub_jenis_data': str(obj.id_sub_jenis_data),
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
