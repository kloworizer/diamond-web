from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.cara_penyampaian import CaraPenyampaian
from ..forms.cara_penyampaian import CaraPenyampaianForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, SafeDeleteMixin

class CaraPenyampaianListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `CaraPenyampaian` entries."""
    template_name = 'cara_penyampaian/list.html'

    def get(self, request, *args, **kwargs):
        """Render list template and surface optional delete message."""
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Cara Penyampaian "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class CaraPenyampaianCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `CaraPenyampaian`."""
    model = CaraPenyampaian
    form_class = CaraPenyampaianForm
    template_name = 'cara_penyampaian/form.html'
    success_url = reverse_lazy('cara_penyampaian_list')
    success_message = 'Cara Penyampaian "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('cara_penyampaian_create')
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request to display the empty creation form.

        Sets ``self.object`` to ``None`` (no existing object) and
        instantiates the form so the user can fill in a new
        ``CaraPenyampaian`` record.

        Returns:
            HttpResponse: The rendered form response (either HTML or
            AJAX-fragment depending on the request).
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class CaraPenyampaianUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `CaraPenyampaian` entries."""
    model = CaraPenyampaian
    form_class = CaraPenyampaianForm
    template_name = 'cara_penyampaian/form.html'
    success_url = reverse_lazy('cara_penyampaian_list')
    success_message = 'Cara Penyampaian "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('cara_penyampaian_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request to display the update form for an existing record.

        Loads the existing ``CaraPenyampaian`` instance identified by the
        URL keyword arguments and binds it to the form so the user can
        modify its fields.

        Returns:
            HttpResponse: The rendered form response (either HTML or
            AJAX-fragment depending on the request).
        """
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class CaraPenyampaianDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `CaraPenyampaian` entries."""
    model = CaraPenyampaian
    template_name = 'cara_penyampaian/confirm_delete.html'
    success_url = reverse_lazy('cara_penyampaian_list')

    def get_context_data(self, **kwargs):
        """Extend template context with the delete confirmation form action URL.

        Adds an extra ``form_action`` entry pointing to the delete
        endpoint for the current object so the confirmation template
        knows where to submit the ``POST`` request.

        Returns:
            dict: The augmented template context dictionary.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('cara_penyampaian_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request to display the delete confirmation page.

        Loads the existing ``CaraPenyampaian`` instance and renders the
        confirmation template. If the request includes an ``?ajax=1``
        parameter, the response is returned as a JSON fragment suitable
        for in-page a modal.

        Returns:
            JsonResponse: An AJAX response with the rendered HTML when
            ``?ajax=1`` is present.
            HttpResponse: The standard confirmation page otherwise.
        """
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Delete the ``CaraPenyampaian`` instance and return a JSON response.

        Removes the object from the database. For AJAX requests
        (``X-Requested-With: XMLHttpRequest``) a success message is
        embedded in the JSON payload; otherwise a Django ``messages``
        success notification is stored before redirecting.

        Returns:
            JsonResponse: A JSON object with ``success``, an optional
            ``message``, and the ``redirect`` URL.
        """
        self.object = self.get_object()
        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Cara Penyampaian "{name}" berhasil dihapus.',
                'redirect': str(self.success_url)
            })
        messages.success(request, f'Cara Penyampaian "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': str(self.success_url)})

    def post(self, request, *args, **kwargs):
        """Handle POST request by delegating to the delete logic.

        A standard HTML form submission uses ``POST`` rather than
        ``DELETE``; this method forwards the request to ``delete()``
        so the same code path handles both verbs.

        Returns:
            JsonResponse: The same JSON response produced by
            ``delete()``.
        """
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def cara_penyampaian_data(request):
    """Return paginated, searchable, orderable JSON data for DataTables.

    This view powers the server-side processing of the
    ``CaraPenyampaian`` DataTable.  It accepts standard DataTables
    parameters (``draw``, ``start``, ``length``, ``order[0][column]``,
    ``order[0][dir]``) together with custom column-level search filters
    (``columns_search[]``) and returns a ``JsonResponse`` that conforms
    to the DataTables protocol.

    The response includes:
        - ``draw`` — the draw counter sent by DataTables.
        - ``recordsTotal`` — total number of records in the database.
        - ``recordsFiltered`` — number of records after applying filters.
        - ``data`` — the array of row data for the current page.

    Returns:
        JsonResponse: A DataTables-compatible JSON payload on success.
        JsonResponse: A 500 response with ``error`` and ``traceback``
        keys when an unexpected exception occurs.
    """
    try:
        draw = int(request.GET.get('draw', '1'))
        start = int(request.GET.get('start', '0'))
        length = int(request.GET.get('length', '10'))

        qs = CaraPenyampaian.objects.all()
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
                'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('cara_penyampaian_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                           f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('cara_penyampaian_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
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
