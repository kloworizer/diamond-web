from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.status_penelitian import StatusPenelitian
from ..forms.status_penelitian import StatusPenelitianForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin

class StatusPenelitianListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `StatusPenelitian` entries."""
    template_name = 'status_penelitian/list.html'

    def get(self, request, *args, **kwargs):
        """Render list template and surface optional delete message."""
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Status Penelitian "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class StatusPenelitianCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `StatusPenelitian`."""
    model = StatusPenelitian
    form_class = StatusPenelitianForm
    template_name = 'status_penelitian/form.html'
    success_url = reverse_lazy('status_penelitian_list')
    success_message = 'Status Penelitian "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('status_penelitian_create')
        return context

class StatusPenelitianUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `StatusPenelitian`."""
    model = StatusPenelitian
    form_class = StatusPenelitianForm
    template_name = 'status_penelitian/form.html'
    success_url = reverse_lazy('status_penelitian_list')
    success_message = 'Status Penelitian "{object}" berhasil diubah.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('status_penelitian_update', args=[self.object.pk])
        return context

class StatusPenelitianDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, SafeDeleteMixin, DeleteView):
    """Delete view for `StatusPenelitian`."""
    model = StatusPenelitian
    template_name = 'status_penelitian/confirm_delete.html'
    success_url = reverse_lazy('status_penelitian_list')

    def get_success_url(self):
        """Redirect with success message containing deleted object name."""
        return f"{reverse_lazy('status_penelitian_list')}?deleted=true&name={quote_plus(self.object.deskripsi)}"

@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def status_penelitian_data(request):
    """Server-side DataTable endpoint for StatusPenelitian list view.
    
    Handles:
    - Pagination (start, length)
    - Sorting (order column and direction)
    - Global search (across all columns)
    - Column-specific filtering
    
    Returns JSON with:
    - draw: Echo request draw counter
    - recordsTotal: Total records before filtering
    - recordsFiltered: Total records after filtering
    - data: Array of StatusPenelitian records with actions
    """
    draw = request.GET.get('draw', 1)
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')

    qs = StatusPenelitian.objects.all()
    
    # Global search
    if search_value:
        qs = qs.filter(deskripsi__icontains=search_value)
    
    records_total = StatusPenelitian.objects.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID
            qs = qs.filter(id__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Deskripsi
            qs = qs.filter(deskripsi__icontains=columns_search[1])

    records_filtered = qs.count()

    # Ordering
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
        actions = (
            f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('status_penelitian_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
            f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('status_penelitian_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        )
        data.append({
            'id': obj.pk,
            'deskripsi': obj.deskripsi,
            'actions': actions
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data
    })
