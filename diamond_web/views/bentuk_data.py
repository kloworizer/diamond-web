from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.bentuk_data import BentukData
from ..forms.bentuk_data import BentukDataForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin

class BentukDataListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `BentukData` entries."""
    template_name = 'bentuk_data/list.html'

    def get(self, request, *args, **kwargs):
        """Render list template and surface optional delete message."""
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Bentuk Data "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class BentukDataCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `BentukData`."""
    model = BentukData
    form_class = BentukDataForm
    template_name = 'bentuk_data/form.html'
    success_url = reverse_lazy('bentuk_data_list')
    success_message = 'Bentuk Data "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('bentuk_data_create')
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request.

        Instantiate an empty form and render it for user input.

        Args:
            request: The incoming HTTP request.

        Returns:
            HttpResponse: The rendered form response (optionally wrapped for
                AJAX requests via AjaxFormMixin).
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class BentukDataUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `BentukData` entries."""
    model = BentukData
    form_class = BentukDataForm
    template_name = 'bentuk_data/form.html'
    success_url = reverse_lazy('bentuk_data_list')
    success_message = 'Bentuk Data "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('bentuk_data_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request.

        Retrieve the existing object and populate the form with its current
        data for editing.

        Args:
            request: The incoming HTTP request.

        Returns:
            HttpResponse: The rendered form response (optionally wrapped for
                AJAX requests via AjaxFormMixin).
        """
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class BentukDataDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `BentukData` entries."""
    model = BentukData
    template_name = 'bentuk_data/confirm_delete.html'
    success_url = reverse_lazy('bentuk_data_list')

    def get_context_data(self, **kwargs):
        """Add deletion form action URL to the template context.

        Returns:
            dict: Template context with an extra ``form_action`` key pointing
                to the delete endpoint for the current object.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('bentuk_data_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request.

        Retrieve the object to be deleted and render the confirmation page.
        When the ``ajax`` query parameter is present the response is returned
        as JSON containing the rendered HTML snippet.

        Args:
            request: The incoming HTTP request.

        Returns:
            JsonResponse | HttpResponse: An AJAX JSON response with the
                rendered HTML, or a full confirmation-page response.
        """
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Handle object deletion.

        Performs the actual delete and returns a JSON response indicating
        success. A flash success message is stored for non-AJAX flows; AJAX
        callers receive the message inline.

        Args:
            request: The incoming HTTP request.

        Returns:
            JsonResponse: Always returns JSON with ``success`` and
                ``redirect`` keys, and optionally an inline ``message``.
        """
        self.object = self.get_object()
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Bentuk Data "{name}" berhasil dihapus.',
                'redirect': str(self.success_url)
            })
        messages.success(request, f'Bentuk Data "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': str(self.success_url)})

    def post(self, request, *args, **kwargs):
        """Handle POST request by delegating to the delete handler.

        Allows HTML forms (which can only issue GET/POST) to trigger the
        deletion logic.

        Args:
            request: The incoming HTTP request.

        Returns:
            JsonResponse: The same response as :meth:`delete`.
        """
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def bentuk_data_data(request):
    """Return JSON data for server-side DataTables processing.

    Handles pagination, per-column filtering, and single-column sorting
    for the ``BentukData`` model.  Designed to be consumed by a jQuery
    DataTable initialised with ``serverSide: true``.

    Args:
        request: The incoming HTTP GET request.  Expected query parameters:

            - ``draw`` (int): Draw counter for DataTables.
            - ``start`` (int): Offset for pagination.
            - ``length`` (int): Number of records per page.
            - ``columns_search[]`` (list of str, optional): Column-specific
              search values (index 0 = *id*, index 1 = *deskripsi*).
            - ``order[0][column]`` (int, optional): Index of the column to
              sort by.
            - ``order[0][dir]`` (str, optional): Sort direction -- ``asc``
              or ``desc`` (default ``asc``).

    Returns:
        JsonResponse: A JSON object with the DataTables contract keys
        (``draw``, ``recordsTotal``, ``recordsFiltered``, ``data``).  On
        failure a 500 response with ``error`` and ``traceback`` is returned.
    """
    try:
        draw = int(request.GET.get('draw', '1'))
        start = int(request.GET.get('start', '0'))
        length = int(request.GET.get('length', '10'))

        qs = BentukData.objects.all()
        records_total = qs.count()

        # Column-specific filtering
        columns_search = request.GET.getlist('columns_search[]')
        if columns_search:
            if columns_search[0]:  # ID
                try:
                    id_value = int(columns_search[0])
                    qs = qs.filter(id=id_value)
                except ValueError:
                    pass
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
                'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('bentuk_data_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                           f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('bentuk_data_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
            })

        return JsonResponse({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
        })
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return JsonResponse({
            'error': str(e),
            'traceback': error_details
        }, status=500)
