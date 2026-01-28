from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.kategori_wilayah import KategoriWilayah
from ..forms.kategori_wilayah import KategoriWilayahForm
from .mixins import AjaxFormMixin

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()

class KategoriWilayahListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'kategori_wilayah/list.html'

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Kategori "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class KategoriWilayahCreateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, CreateView):
    model = KategoriWilayah
    form_class = KategoriWilayahForm
    template_name = 'kategori_wilayah/form.html'
    success_url = reverse_lazy('kategori_wilayah_list')
    success_message = 'Kategori "{object}" created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_wilayah_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class KategoriWilayahUpdateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, UpdateView):
    model = KategoriWilayah
    form_class = KategoriWilayahForm
    template_name = 'kategori_wilayah/form.html'
    success_url = reverse_lazy('kategori_wilayah_list')
    success_message = 'Kategori "{object}" updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_wilayah_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class KategoriWilayahDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = KategoriWilayah
    template_name = 'kategori_wilayah/confirm_delete.html'
    success_url = reverse_lazy('kategori_wilayah_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_wilayah_delete', args=[self.object.pk])
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
                'message': f'Kategori "{name}" deleted successfully.'
            })
        messages.success(request, f'Kategori "{name}" deleted successfully.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def kategori_wilayah_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = KategoriWilayah.objects.all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID
            qs = qs.filter(id__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Deskripsi
            qs = qs.filter(deskripsi__icontains=columns_search[1])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'deskripsi']
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
            'id': obj.id,
            'deskripsi': obj.deskripsi,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('kategori_wilayah_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('kategori_wilayah_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
