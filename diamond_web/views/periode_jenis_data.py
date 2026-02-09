from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.periode_jenis_data import PeriodeJenisData
from ..forms.periode_jenis_data import PeriodeJenisDataForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin
from datetime import date as _date

class PeriodeJenisDataListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    template_name = 'periode_jenis_data/list.html'

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Periode Jenis Data "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class PeriodeJenisDataCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    model = PeriodeJenisData
    form_class = PeriodeJenisDataForm
    template_name = 'periode_jenis_data/form.html'
    success_url = reverse_lazy('periode_jenis_data_list')
    success_message = 'Periode Jenis Data "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('periode_jenis_data_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data_ilap') or form.instance.id_sub_jenis_data_ilap
        qs = PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap=id_sub)
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class PeriodeJenisDataUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    model = PeriodeJenisData
    form_class = PeriodeJenisDataForm
    template_name = 'periode_jenis_data/form.html'
    success_url = reverse_lazy('periode_jenis_data_list')
    success_message = 'Periode Jenis Data "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('periode_jenis_data_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data_ilap') or form.instance.id_sub_jenis_data_ilap
        qs = PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap=id_sub).exclude(pk=form.instance.pk)
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class PeriodeJenisDataDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    model = PeriodeJenisData
    template_name = 'periode_jenis_data/confirm_delete.html'
    success_url = reverse_lazy('periode_jenis_data_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('periode_jenis_data_delete', args=[self.object.pk])
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
                'message': f'Periode Jenis Data "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Periode Jenis Data "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def periode_jenis_data_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = PeriodeJenisData.objects.select_related('id_sub_jenis_data_ilap', 'id_periode_pengiriman').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Sub Jenis Data ILAP
            qs = qs.filter(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Periode Pengiriman
            qs = qs.filter(id_periode_pengiriman__deskripsi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data_ilap__nama_sub_jenis_data', 'id_periode_pengiriman__deskripsi', 'start_date', 'end_date']
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
            'sub_jenis_data_ilap': str(obj.id_sub_jenis_data_ilap),
            'periode_pengiriman': str(obj.id_periode_pengiriman),
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('periode_jenis_data_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('periode_jenis_data_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
