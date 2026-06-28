from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.kanwil import Kanwil
from ..forms.kanwil import KanwilForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin


class KanwilListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `Kanwil` entries."""
    template_name = 'kanwil/list.html'

    def get(self, request, *args, **kwargs):
        """Handle GET request for the Kanwil list page.

        Extracts optional query parameters for a deletion notification,
        decodes the Kanwil name, and surfaces a success message to the user
        before rendering the template.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            django.http.HttpResponse: The rendered list template response.
        """
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Kanwil "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class KanwilCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `Kanwil`."""
    model = Kanwil
    form_class = KanwilForm
    template_name = 'kanwil/form.html'
    success_url = reverse_lazy('kanwil_list')
    success_message = 'Kanwil "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        """Add extra context for the create form template.

        Inserts the URL endpoint used as the form action so the template
        knows where to submit the new Kanwil entry.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary with the added `form_action`.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kanwil_create')
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the Kanwil creation page.

        Prepares an unbound form instance and renders it either as an AJAX
        response or a full-page HTML form depending on the request type.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            django.http.HttpResponse: The rendered form response.
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class KanwilUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `Kanwil` entries."""
    model = Kanwil
    form_class = KanwilForm
    template_name = 'kanwil/form.html'
    success_url = reverse_lazy('kanwil_list')
    success_message = 'Kanwil "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        """Add extra context for the update form template.

        Inserts the URL endpoint used as the form action, including the
        primary key of the Kanwil being edited, so the form submits to the
        correct update URL.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary with the added `form_action`.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kanwil_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the Kanwil edit page.

        Retrieves the existing Kanwil instance, binds an unbound form with
        its current data, and renders the form either as an AJAX response
        or a full-page HTML template.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            django.http.HttpResponse: The rendered form response.
        """
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)


class KanwilDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `Kanwil` entries."""
    model = Kanwil
    template_name = 'kanwil/confirm_delete.html'
    success_url = reverse_lazy('kanwil_list')

    def get_context_data(self, **kwargs):
        """Add extra context for the delete confirmation template.

        Inserts the URL endpoint used as the form action for deleting
        a specific Kanwil entry.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary with the added `form_action`.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kanwil_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the Kanwil delete confirmation page.

        Fetches the Kanwil instance to be deleted. If the request is AJAX,
        returns the confirmation dialog HTML as JSON; otherwise renders
        the full-page confirmation template.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            django.http.JsonResponse | django.http.HttpResponse:
                A JSON response with the rendered HTML for AJAX requests,
                or a full template response for standard requests.
        """
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Delete the specified Kanwil instance.

        Performs the actual deletion of the Kanwil object. For AJAX requests
        returns a JSON response with the success message. For standard
        requests a success message is flashed and the user is redirected.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            django.http.JsonResponse:
                A JSON object containing `success`, an optional `message`,
                and a `redirect` URL for non-AJAX submissions.
        """
        self.object = self.get_object()
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Kanwil "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Kanwil "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        """Handle POST request as a deletion action.

        Delegates directly to the `delete()` method so the same logic
        applies regardless of whether the HTTP verb is DELETE or POST.

        Args:
            request: The incoming HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            django.http.JsonResponse:
                The response from the `delete()` method.
        """
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def kanwil_data(request):
    """Return paginated, searchable, and ordered Kanwil data for DataTables.

    Handles server-side processing for a DataTable, including column-specific
    filtering, multi-column sorting, and pagination. Returns a JSON payload
    conforming to the DataTables server-side protocol.

    The function supports filtering on the following columns:
        - ID
        - Kode Kanwil
        - Nama Kanwil

    Args:
        request: The incoming HTTP GET request containing DataTables
            parameters (`draw`, `start`, `length`, `columns_search[]`,
            `order[0][column]`, `order[0][dir]`).

    Returns:
        django.http.JsonResponse:
            A JSON object with `draw`, `recordsTotal`, `recordsFiltered`,
            and `data` keys as required by the DataTables protocol.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = Kanwil.objects.all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Kode Kanwil (column 0)
            qs = qs.filter(kode_kanwil__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Kanwil (column 1)
            qs = qs.filter(nama_kanwil__icontains=columns_search[1])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'kode_kanwil', 'nama_kanwil']
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
            'kode_kanwil': obj.kode_kanwil,
            'nama_kanwil': obj.nama_kanwil,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('kanwil_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('kanwil_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
