from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Max

from ..models.ilap import ILAP
from ..forms.ilap import ILAPForm
from .mixins import AjaxFormMixin, AdminRequiredMixin


class ILAPListView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    template_name = 'ilap/list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'ILAP "{name}" deleted successfully.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name='admin').exists())
@require_GET
def get_next_ilap_id(request):
    """Get next id_ilap for a given category."""
    kategori_id = request.GET.get('kategori_id')
    if not kategori_id:
        return JsonResponse({'error': 'kategori_id is required'}, status=400)
    
    # Get the last id_ilap for this category
    last_ilap = ILAP.objects.filter(id_ilap__startswith=kategori_id).order_by('-id_ilap').first()
    
    if last_ilap:
        # Extract the numeric part and increment
        last_number = int(last_ilap.id_ilap[len(kategori_id):])
        next_number = last_number + 1
    else:
        # First entry for this category
        next_number = 1
    
    # Format with 3 digits
    next_id = f"{kategori_id}{next_number:03d}"
    
    return JsonResponse({'next_id': next_id})


@login_required
@user_passes_test(lambda u: u.groups.filter(name='admin').exists())
@require_GET
def ilap_data(request):
    """Server-side processing for ILAP DataTables."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = ILAP.objects.select_related('id_kategori', 'id_kategori_wilayah').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Kategori Wilayah
            qs = qs.filter(id_kategori_wilayah__deskripsi__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # ID ILAP
            qs = qs.filter(id_ilap__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # ID Kategori
            qs = qs.filter(id_kategori__id_kategori__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Nama ILAP
            qs = qs.filter(nama_ilap__icontains=columns_search[3])

    records_filtered = qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_kategori_wilayah__deskripsi', 'id_ilap', 'id_kategori__nama_kategori', 'nama_ilap']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id_ilap'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('id_ilap')
    else:
        qs = qs.order_by('id_ilap')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        data.append({
            'kategori_wilayah': str(obj.id_kategori_wilayah),
            'id_ilap': obj.id_ilap,
            'id_kategori': str(obj.id_kategori),
            'nama_ilap': obj.nama_ilap,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('ilap_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('ilap_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


class ILAPCreateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, CreateView):
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')
    success_message = 'ILAP "{object}" created successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        # Manually set id_ilap since it's disabled
        if not form.instance.pk:
            id_ilap = self.request.POST.get('id_ilap')
            if id_ilap:
                form.instance.id_ilap = id_ilap
        return super().form_valid(form)


class ILAPUpdateView(LoginRequiredMixin, AdminRequiredMixin, AjaxFormMixin, UpdateView):
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')
    success_message = 'ILAP "{object}" updated successfully.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_update', args=[self.object.pk])
        context['original_id_ilap'] = self.object.id_ilap
        context['original_id_kategori'] = self.object.id_kategori.id_kategori
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)


class ILAPDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = ILAP
    template_name = 'ilap/confirm_delete.html'
    success_url = reverse_lazy('ilap_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_delete', args=[self.object.pk])
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
                'message': f'ILAP "{name}" deleted successfully.'
            })
        messages.success(request, f'ILAP "{name}" deleted successfully.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
