from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.kpp import KPP
from ..forms.kpp import KPPForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin


class KPPListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `KPP` entries."""
    template_name = 'kpp/list.html'

    def get(self, request, *args, **kwargs):
        """Handle GET request for the KPP list page.

        Renders the list template and optionally displays a success message
        when the user is redirected here after deleting a KPP entry.

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            HttpResponse: The rendered list template response.
        """
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'KPP "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class KPPCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `KPP`."""
    model = KPP
    form_class = KPPForm
    template_name = 'kpp/form.html'
    success_url = reverse_lazy('kpp_list')
    success_message = 'KPP "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        """Populate the template context for the KPP create form.

        Adds the form action URL pointing to the create endpoint so the
        form can be submitted via both AJAX and full-page POST requests.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary including the form action URL.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kpp_create')
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the KPP create view.

        Instantiates an empty KPP form and renders it. Supports both AJAX
        requests (returning a JSON response with the rendered form HTML) and
        standard full-page requests (returning the complete template).

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            HttpResponse: The form rendered as a JSON response for AJAX
                requests, or as a full template response otherwise.
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class KPPUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `KPP` entries."""
    model = KPP
    form_class = KPPForm
    template_name = 'kpp/form.html'
    success_url = reverse_lazy('kpp_list')
    success_message = 'KPP "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        """Populate the template context for the KPP update form.

        Adds the form action URL pointing to the update endpoint for the
        specific KPP instance being edited.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary including the form action URL.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kpp_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the KPP update view.

        Retrieves the existing KPP instance, binds it to the form, and
        renders the edit form. Supports both AJAX requests (returning a JSON
        response with the rendered form HTML) and standard full-page requests.

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            HttpResponse: The form rendered as a JSON response for AJAX
                requests, or as a full template response otherwise.
        """
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)


class KPPDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `KPP` entries."""
    model = KPP
    template_name = 'kpp/confirm_delete.html'
    success_url = reverse_lazy('kpp_list')

    def get_context_data(self, **kwargs):
        """Populate the template context for the KPP delete confirmation page.

        Adds the form action URL pointing to the delete endpoint for the
        specific KPP instance being deleted.

        Args:
            **kwargs: Additional keyword arguments passed to the parent
                      context builder.

        Returns:
            dict: The template context dictionary including the form action URL.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('kpp_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request for the KPP delete confirmation view.

        Retrieves the KPP instance to be deleted and renders the
        confirmation template. If the request includes an ``ajax`` query
        parameter, returns the rendered HTML as a JSON response for
        in-page modal display.

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            HttpResponse: The confirmation template rendered either as a JSON
                response (for AJAX requests) or as a full page.
        """
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Perform the deletion of the KPP instance.

        Removes the KPP entry from the database. For AJAX (XMLHttpRequest)
        requests, returns a JSON response with a success message. For
        standard requests, sets a Django messages framework success message
        and returns a JSON redirect response.

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            JsonResponse: A JSON object containing:
                - ``success`` (bool): Always ``True`` on successful deletion.
                - ``message`` (str, optional): A human-readable success
                  message (only for AJAX requests).
                - ``redirect`` (str, optional): The URL to redirect to after
                  deletion (only for non-AJAX requests).
        """
        self.object = self.get_object()
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'KPP "{name}" berhasil dihapus.'
            })
        messages.success(request, f'KPP "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        """Handle POST request for the KPP delete view.

        Delegates to the ``delete`` method to perform the actual KPP
        removal. This is the standard entry point for form-based POST
        submissions from the delete confirmation page.

        Args:
            request (HttpRequest): The incoming HTTP request object.
            *args: Additional positional arguments passed to the parent handler.
            **kwargs: Additional keyword arguments passed to the parent handler.

        Returns:
            JsonResponse: The response from the ``delete`` method.
        """
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def kpp_data(request):
    """Serve server-side processed data for the KPP DataTable.

    Handles pagination, column-specific search filtering, and sorting
    for the KPP list DataTable. Only accessible to authenticated users
    belonging to the ``admin`` or ``admin_p3de`` groups.

    The endpoint expects the following GET parameters as sent by
    DataTables' server-side processing mode:
        - ``draw``: Draw counter to ensure response matches request.
        - ``start``: Offset for paginated results.
        - ``length``: Number of records per page.
        - ``columns_search[]``: Per-column search values (index 0 = Kode KPP,
          1 = Nama KPP, 2 = Kode Kanwil, 3 = Nama Kanwil).
        - ``order[0][column]``: Index of the column to sort by.
        - ``order[0][dir]``: Sort direction (``asc`` or ``desc``).

    Args:
        request (HttpRequest): The incoming HTTP GET request containing
            DataTables server-side parameters.

    Returns:
        JsonResponse: A JSON payload with the following keys:
            - ``draw`` (int): The echo-back draw counter.
            - ``recordsTotal`` (int): Total number of KPP records.
            - ``recordsFiltered`` (int): Number of records after filtering.
            - ``data`` (list[dict]): The page of KPP records, each with
              ``kode_kpp``, ``nama_kpp``, ``kode_kanwil``, ``nama_kanwil``,
              and ``actions`` (HTML).
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = KPP.objects.select_related('id_kanwil').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Kode KPP
            qs = qs.filter(kode_kpp__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama KPP
            qs = qs.filter(nama_kpp__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Kode Kanwil
            qs = qs.filter(id_kanwil__kode_kanwil__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Nama Kanwil
            qs = qs.filter(id_kanwil__nama_kanwil__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['kode_kpp', 'nama_kpp', 'id_kanwil__kode_kanwil', 'id_kanwil__nama_kanwil']
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
            'kode_kpp': obj.kode_kpp,
            'nama_kpp': obj.nama_kpp,
            'kode_kanwil': obj.id_kanwil.kode_kanwil if obj.id_kanwil else '-',
            'nama_kanwil': obj.id_kanwil.nama_kanwil if obj.id_kanwil else '-',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('kpp_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('kpp_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
