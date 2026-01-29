from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.jenis_data_ilap import JenisDataILAP
from ..forms.nama_tabel import NamaTabelForm
from .mixins import AjaxFormMixin, AdminRequiredMixin

class NamaTabelListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'nama_tabel/list.html'

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class NamaTabelCreateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, CreateView):
    model = JenisDataILAP
    form_class = NamaTabelForm
    template_name = 'nama_tabel/form.html'
    success_url = reverse_lazy('nama_tabel_list')
    success_message = 'Nama Tabel "{object}" created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class NamaTabelUpdateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, UpdateView):
    model = JenisDataILAP
    form_class = NamaTabelForm
    template_name = 'nama_tabel/form.html'
    success_url = reverse_lazy('nama_tabel_list')
    success_message = 'Nama Tabel "{object}" updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class NamaTabelDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = JenisDataILAP
    template_name = 'nama_tabel/confirm_delete.html'
    success_url = reverse_lazy('nama_tabel_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_delete', args=[self.object.pk])
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
        # Clear only the nama_tabel_I and nama_tabel_U fields instead of deleting the row
        self.object.nama_tabel_I = ''
        self.object.nama_tabel_U = ''
        self.object.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Nama Tabel "{name}" cleared successfully.'
            })
        messages.success(request, f'Nama Tabel "{name}" cleared successfully.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def nama_tabel_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = JenisDataILAP.objects.select_related(
        'id_ilap',
        'id_ilap__id_kategori',
        'id_jenis_tabel'
    ).all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Jenis Data
            qs = qs.filter(nama_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Nama Sub Jenis Data
            qs = qs.filter(nama_sub_jenis_data__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Nama Tabel I
            qs = qs.filter(nama_tabel_I__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Nama Tabel U
            qs = qs.filter(nama_tabel_U__icontains=columns_search[4])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data', 'nama_jenis_data', 'nama_sub_jenis_data', 'nama_tabel_I', 'nama_tabel_U']
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
            'id_sub_jenis_data': obj.id_sub_jenis_data,
            'nama_jenis_data': obj.nama_jenis_data,
            'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            'nama_tabel_I': obj.nama_tabel_I,
            'nama_tabel_U': obj.nama_tabel_U,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('nama_tabel_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('nama_tabel_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
