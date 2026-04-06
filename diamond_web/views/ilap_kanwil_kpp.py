from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.ilap_kanwil_kpp import ILAPKanwilKPP
from ..forms.ilap_kanwil_kpp import ILAPKanwilKPPForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin


class ILAPKanwilKPPListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `ILAPKanwilKPP` entries."""
    template_name = 'ilap_kanwil_kpp/list.html'

    def get(self, request, *args, **kwargs):
        """Render the list template and surface optional delete message."""
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'ILAP Kanwil KPP "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class ILAPKanwilKPPCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `ILAPKanwilKPP`."""
    model = ILAPKanwilKPP
    form_class = ILAPKanwilKPPForm
    template_name = 'ilap_kanwil_kpp/form.html'
    success_url = reverse_lazy('ilap_kanwil_kpp_list')
    success_message = 'ILAP Kanwil KPP "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_kanwil_kpp_create')
        return context

    def get(self, request, *args, **kwargs):
        """Return the create form rendered for AJAX or full-page requests."""
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class ILAPKanwilKPPUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `ILAPKanwilKPP` entries."""
    model = ILAPKanwilKPP
    form_class = ILAPKanwilKPPForm
    template_name = 'ilap_kanwil_kpp/form.html'
    success_url = reverse_lazy('ilap_kanwil_kpp_list')
    success_message = 'ILAP Kanwil KPP "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_kanwil_kpp_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Return the edit form for the requested instance."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)


class ILAPKanwilKPPDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `ILAPKanwilKPP` entries."""
    model = ILAPKanwilKPP
    template_name = 'ilap_kanwil_kpp/confirm_delete.html'
    success_url = reverse_lazy('ilap_kanwil_kpp_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('ilap_kanwil_kpp_delete', args=[self.object.pk])
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
                'message': f'ILAP Kanwil KPP "{name}" berhasil dihapus.'
            })
        messages.success(request, f'ILAP Kanwil KPP "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def ilap_kanwil_kpp_data(request):
    """Server-side DataTables endpoint for `ILAPKanwilKPP`."""
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = ILAPKanwilKPP.objects.select_related('id_ilap', 'id_kpp').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID
            qs = qs.filter(id__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # ILAP
            qs = qs.filter(id_ilap__id__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Kanwil
            qs = qs.filter(id_kpp__id_kanwil__nama_kanwil__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # KPP
            qs = qs.filter(id_kpp__nama_kpp__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'id_ilap', 'id_kpp__id_kanwil', 'id_kpp']
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
            'id_ilap': str(obj.id_ilap),
            'id_kanwil': obj.id_kpp.id_kanwil.nama_kanwil,
            'id_kpp': obj.id_kpp.nama_kpp,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('ilap_kanwil_kpp_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('ilap_kanwil_kpp_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
