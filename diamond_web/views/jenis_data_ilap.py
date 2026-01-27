from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.jenis_data_ilap import JenisDataILAP
from ..forms.jenis_data_ilap import JenisDataILAPForm
from .mixins import AjaxFormMixin

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()

class JenisDataILAPListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'jenis_data_ilap/list.html'

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Jenis Data "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class JenisDataILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, CreateView):
    model = JenisDataILAP
    form_class = JenisDataILAPForm
    template_name = 'jenis_data_ilap/form.html'
    success_url = reverse_lazy('jenis_data_ilap_list')
    success_message = 'Jenis Data "{object}" created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class JenisDataILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, UpdateView):
    model = JenisDataILAP
    form_class = JenisDataILAPForm
    template_name = 'jenis_data_ilap/form.html'
    success_url = reverse_lazy('jenis_data_ilap_list')
    success_message = 'Jenis Data "{object}" updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class JenisDataILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = JenisDataILAP
    template_name = 'jenis_data_ilap/confirm_delete.html'
    success_url = reverse_lazy('jenis_data_ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('jenis_data_ilap_delete', args=[self.object.pk])
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
                'message': f'Jenis Data "{name}" deleted successfully.'
            })
        messages.success(request, f'Jenis Data "{name}" deleted successfully.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def jenis_data_ilap_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = JenisDataILAP.objects.select_related(
        'id_kategori_ilap',
        'id_ilap',        'id_jenis_tabel',
        'id_kategori_wilayah',
        'id_klasifikasi_tabel'
    ).all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID Jenis Data
            qs = qs.filter(id_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Nama Jenis Data
            qs = qs.filter(nama_jenis_data__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Nama Sub Jenis Data
            qs = qs.filter(nama_sub_jenis_data__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Nama Tabel I
            qs = qs.filter(nama_tabel_I__icontains=columns_search[4])
        if len(columns_search) > 5 and columns_search[5]:  # Nama Tabel U
            qs = qs.filter(nama_tabel_U__icontains=columns_search[5])
        if len(columns_search) > 6 and columns_search[6]:  # Kategori ILAP
            qs = qs.filter(id_kategori_ilap__nama_kategori__icontains=columns_search[6])
        if len(columns_search) > 7 and columns_search[7]:  # ILAP
            qs = qs.filter(id_ilap__nama_ilap__icontains=columns_search[7])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_jenis_data', 'id_sub_jenis_data', 'nama_jenis_data', 'nama_sub_jenis_data', 
               'nama_tabel_I', 'nama_tabel_U', 'id_kategori_ilap__nama_kategori', 'id_ilap__nama_ilap']
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
            'id_jenis_data': obj.id_jenis_data,
            'id_sub_jenis_data': obj.id_sub_jenis_data,
            'nama_jenis_data': obj.nama_jenis_data,
            'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            'nama_tabel_I': obj.nama_tabel_I,
            'nama_tabel_U': obj.nama_tabel_U,
            'kategori_ilap': str(obj.id_kategori_ilap),
            'ilap': str(obj.id_ilap),
            'jenis_tabel': str(obj.id_jenis_tabel),
            'kategori_wilayah': str(obj.id_kategori_wilayah),
            'klasifikasi_tabel': str(obj.id_klasifikasi_tabel),
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('jenis_data_ilap_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('jenis_data_ilap_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
