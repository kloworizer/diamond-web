from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.kategori_ilap import KategoriILAP
from ..forms.kategori_ilap import KategoriILAPForm

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.groups.filter(name='Admin').exists()

class KategoriILAPListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'kategori_ilap/list.html'

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

class KategoriILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_ilap_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(form=form), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Kategori "{self.object}" created successfully.'
            })
        messages.success(self.request, f'Kategori "{self.object}" created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(form=form), self.request)
            return JsonResponse({'success': False, 'html': html})
        return super().form_invalid(form)

class KategoriILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = KategoriILAP
    form_class = KategoriILAPForm
    template_name = 'kategori_ilap/form.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_ilap_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(form=form), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Kategori "{self.object}" updated successfully.'
            })
        messages.success(self.request, f'Kategori "{self.object}" updated successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(form=form), self.request)
            return JsonResponse({'success': False, 'html': html})
        return super().form_invalid(form)

class KategoriILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = KategoriILAP
    template_name = 'kategori_ilap/confirm_delete.html'
    success_url = reverse_lazy('kategori_ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kategori_ilap_delete', args=[self.object.pk])
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
@user_passes_test(lambda u: u.groups.filter(name='Admin').exists())
@require_GET
def kategori_ilap_data(request):
    """Server-side processing for DataTables.

    Accepts DataTables parameters: draw, start, length, search[value], order[0][column], order[0][dir]
    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = KategoriILAP.objects.all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID Kategori
            qs = qs.filter(id_kategori__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Kategori
            qs = qs.filter(nama_kategori__icontains=columns_search[1])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_kategori', 'nama_kategori']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id_kategori'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('id_kategori')
    else:
        qs = qs.order_by('id_kategori')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        data.append({
            'id_kategori': obj.id_kategori,
            'nama_kategori': obj.nama_kategori,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('kategori_ilap_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('kategori_ilap_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })