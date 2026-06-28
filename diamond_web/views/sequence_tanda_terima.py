"""Views for Sequence Tanda Terima management."""

from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET
from django.db import models

from ..models.sequence_tanda_terima import SequenceTandaTerima
from ..models.tanda_terima_data import TandaTerimaData
from ..forms.sequence_tanda_terima import SequenceTandaTerimaForm
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin


class SequenceTandaTerimaListView(LoginRequiredMixin, AdminP3DERequiredMixin, TemplateView):
    """List view for `SequenceTandaTerima` entries.

    Renders `sequence_tanda_terima/list.html`. When the view is redirected
    from a delete operation it reads `deleted` and `name` query parameters
    (URL-encoded) and registers a Django `messages.success` notification.
    """
    template_name = 'sequence_tanda_terima/list.html'

    def get(self, request, *args, **kwargs):
        """Handle GET request and display success message after delete redirect.

        Checks for `deleted` and `name` query parameters (URL-encoded) passed
        from the delete view redirect. If present, decodes the name and
        registers a success notification via Django messages framework.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The rendered template response.
        """
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Data sequence tahun "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def sequence_tanda_terima_data(request):
    """DataTables server-side endpoint for `SequenceTandaTerima`.

    GET parameters (DataTables): `draw`, `start`, `length`,
    `columns_search[]`, `search[value]`, `order[0][column]`, `order[0][dir]`.

    Permissions: wrapped by decorators to allow only users in `admin` or
    `admin_p3de` groups.

    Returns: JSON with `draw`, `recordsTotal`, `recordsFiltered`, and
    `data` rows. Each row includes `tahun`, `nomor_terakhir`,
    `nomor_berikutnya`, `can_edit`, and `actions` HTML.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = SequenceTandaTerima.objects.all()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Tahun
            qs = qs.filter(tahun__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nomor Terakhir
            qs = qs.filter(nomor_terakhir__icontains=columns_search[1])

    records_total = SequenceTandaTerima.objects.count()
    records_filtered = qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['tahun', 'nomor_terakhir']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'tahun'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-tahun')
    else:
        qs = qs.order_by('-tahun')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        # Determine if editing is allowed - not allowed if there are TandaTerimaData for this year
        has_records = TandaTerimaData.objects.filter(tahun_terima=obj.tahun).exists()
        can_edit = not has_records
        can_delete = not has_records

        edit_url = reverse('sequence_tanda_terima_update', args=[obj.pk])
        delete_url = reverse('sequence_tanda_terima_delete', args=[obj.pk])

        status_badge = ''
        if has_records:
            status_badge = '<span class="badge bg-warning">Terkunci</span>'
        else:
            status_badge = '<span class="badge bg-success">Dapat Diubah</span>'

        actions_html = ''
        if can_edit:
            actions_html += f"<button class='btn btn-sm btn-primary' data-action='edit' data-url='{edit_url}' title='Edit'><i class='feather-edit-2'></i></button> "
        else:
            actions_html += f"<button class='btn btn-sm btn-secondary' disabled title='Tidak dapat diedit karena sudah ada Tanda Terima di tahun ini'><i class='feather-edit-2'></i></button> "
        if can_delete:
            actions_html += f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{delete_url}' title='Hapus'><i class='feather-trash-2'></i></button>"
        else:
            actions_html += f"<button class='btn btn-sm btn-secondary' disabled title='Tidak dapat dihapus karena sudah ada Tanda Terima di tahun ini'><i class='feather-trash-2'></i></button>"

        data.append({
            'tahun': obj.tahun,
            'nomor_terakhir': obj.nomor_terakhir,
            'nomor_berikutnya': obj.nomor_berikutnya,
            'status': status_badge,
            'actions': actions_html,
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


class SequenceTandaTerimaCreateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `SequenceTandaTerima` with AJAX support."""
    model = SequenceTandaTerima
    form_class = SequenceTandaTerimaForm
    template_name = 'sequence_tanda_terima/form.html'
    success_url = reverse_lazy('sequence_tanda_terima_list')
    success_message = 'Data sequence tahun {object} berhasil dibuat.'

    def get_context_data(self, **kwargs):
        """Add form action URL to the template context.

        Args:
            **kwargs: Additional keyword arguments passed to the parent.

        Returns:
            dict: Template context dictionary with 'form_action' key.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('sequence_tanda_terima_create')
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request and render the creation form.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            HttpResponse: The rendered form response.
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)


class SequenceTandaTerimaUpdateView(LoginRequiredMixin, AdminP3DERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `SequenceTandaTerima` with AJAX support.

    Prevents editing if there are already TandaTerimaData records for
    the year. Uses the form validation to enforce this rule.
    """
    model = SequenceTandaTerima
    form_class = SequenceTandaTerimaForm
    template_name = 'sequence_tanda_terima/form.html'
    success_url = reverse_lazy('sequence_tanda_terima_list')
    success_message = 'Data sequence tahun {object} berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        """Add form action URL to the template context.

        Args:
            **kwargs: Additional keyword arguments passed to the parent.

        Returns:
            dict: Template context dictionary with 'form_action' key.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('sequence_tanda_terima_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request and render the edit form.

        Checks if editing is allowed (no TandaTerimaData for this year).
        If not allowed, returns an error JSON response.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            JsonResponse or HttpResponse: Error response or rendered form.
        """
        self.object = self.get_object()
        # Double-check: prevent edit if there are TandaTerimaData records
        if TandaTerimaData.objects.filter(tahun_terima=self.object.tahun).exists():
            return JsonResponse({
                'success': False,
                'message': f'Tidak dapat mengubah data untuk tahun {self.object.tahun} karena sudah ada Tanda Terima Data yang tercatat.',
                'html': '<div class="alert alert-warning">Tidak dapat mengubah data karena sudah ada Tanda Terima Data untuk tahun ini.</div>'
            })
        form = self.get_form()
        return self.render_form_response(form)


class SequenceTandaTerimaDeleteView(LoginRequiredMixin, AdminP3DERequiredMixin, DeleteView):
    """Delete view for `SequenceTandaTerima`.

    Prevents deletion if there are already TandaTerimaData records for
    the year.
    """
    model = SequenceTandaTerima
    template_name = 'sequence_tanda_terima/confirm_delete.html'
    success_url = reverse_lazy('sequence_tanda_terima_list')

    def get_context_data(self, **kwargs):
        """Add delete form action URL to the template context.

        Args:
            **kwargs: Additional keyword arguments passed to the parent.

        Returns:
            dict: Template context with ``form_action`` key.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('sequence_tanda_terima_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Handle GET request and render the delete confirmation dialog.

        Supports AJAX requests by rendering the template to an HTML string
        and returning it as a JSON response. Also checks if deletion is
        allowed.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            JsonResponse or HttpResponse: AJAX HTML string or full page response.
        """
        self.object = self.get_object()
        if TandaTerimaData.objects.filter(tahun_terima=self.object.tahun).exists():
            if request.GET.get('ajax'):
                return JsonResponse({
                    'success': False,
                    'html': '<div class="alert alert-warning">Data tidak dapat dihapus karena sudah ada Tanda Terima Data untuk tahun ini.</div>'
                })
            messages.error(request, f'Data tidak dapat dihapus karena sudah ada Tanda Terima Data untuk tahun {self.object.tahun}.')
            return self.render_to_response(self.get_context_data())

        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Perform deletion of the sequence record with integrity check.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            JsonResponse or HttpResponseRedirect: Result of deletion.
        """
        self.object = self.get_object()

        if TandaTerimaData.objects.filter(tahun_terima=self.object.tahun).exists():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Tidak dapat menghapus data untuk tahun {self.object.tahun} karena sudah ada Tanda Terima Data.'
                })
            messages.error(request, f'Tidak dapat menghapus data untuk tahun {self.object.tahun} karena sudah ada Tanda Terima Data.')
            return self.render_to_response(self.get_context_data())

        name = str(self.object)
        self.object.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Data sequence tahun "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Data sequence tahun "{name}" berhasil dihapus.')
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.success_url)

    def post(self, request, *args, **kwargs):
        """Handle POST request by delegating to the delete method.

        Args:
            request: The incoming HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            JsonResponse or HttpResponseRedirect: Result from delete method.
        """
        return self.delete(request, *args, **kwargs)
