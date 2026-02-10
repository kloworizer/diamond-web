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
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin


class ILAPListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `ILAP` entries.

    Renders the `ilap/list.html` template and surfaces deletion success
    messages when redirected from delete operations. The view is restricted to
    users in the `admin` or `admin_p3de` groups via
    `AdminP3DERequiredMixin`.
    """
    template_name = 'ilap/list.html'

    def get(self, request, *args, **kwargs):
        """Render list template and decode optional `name` query param.

        Query params: `deleted` and `name`. When redirected after a deletion,
        `name` is URL-encoded; this method decodes it and registers a Django
        `messages.success` toast for the UI.
        """
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'ILAP "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def get_next_ilap_id(request):
    """Return the next `id_ilap` string for a given `kategori_id`.

    GET parameters:
    - kategori_id: prefix used for ILAP identifiers (required).

    Behavior:
    - Finds the last `ILAP.id_ilap` starting with `kategori_id`, extracts the
        numeric suffix, increments it, and returns the next identifier formatted
        with three digits (e.g., `CAT001`).

    Returns JSON `{'next_id': '<kategori><NNN>'}` or a 400 error when
    `kategori_id` is missing.
    """
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
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def ilap_data(request):
    """Server-side DataTables endpoint for `ILAP`.

    GET parameters:
    - draw: DataTables draw counter.
    - start, length: paging offset and page size.
    - columns_search[]: column-specific search values (kategori_wilayah, id_ilap, id_kategori, nama_ilap).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Uses `select_related('id_kategori', 'id_kategori_wilayah')` for efficiency.
    - Filters and orders queryset according to DataTables parameters.

    Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    Each `data` row contains: `kategori_wilayah`, `id_ilap`, `id_kategori`, `nama_ilap`, and `actions` HTML.
    """
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


class ILAPCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `ILAP` entries.

    Usage: Presents a modal/form to create an `ILAP`. The form commonly
    renders a disabled `id_ilap` input (auto-generated by client-side JS), so
    on submit the view will manually bind `id_ilap` from `POST` when the
    instance is new.

    Side effects on successful save:
    - Persists the `ILAP` instance.
    """
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')
    success_message = 'ILAP "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        """Bind `id_ilap` from POST when the field is disabled in the form."""
        if not form.instance.pk:
            id_ilap = self.request.POST.get('id_ilap')
            if id_ilap:
                form.instance.id_ilap = id_ilap
        return super().form_valid(form)


class ILAPUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `ILAP` entries.

    Ensures the form context includes `original_id_ilap` and
    `original_id_kategori` to allow templates to keep track of disabled/readonly
    identifiers during editing.
    """
    model = ILAP
    form_class = ILAPForm
    template_name = 'ilap/form.html'
    success_url = reverse_lazy('ilap_list')
    success_message = 'ILAP "{object}" berhasil diperbarui.'

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


class ILAPDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `ILAP` entries.

    For AJAX `GET` requests returns the confirmation fragment as JSON under
    the `html` key. On deletion, returns JSON with `redirect` and sets a
    Django success message so the base template can render a toast after
    navigation.
    """
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
                'message': f'ILAP "{name}" berhasil dihapus.'
            })
        messages.success(request, f'ILAP "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
