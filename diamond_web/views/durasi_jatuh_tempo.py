from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..forms.durasi_jatuh_tempo import DurasiJatuhTempoForm
from .mixins import AjaxFormMixin, AdminPIDERequiredMixin, AdminPMDERequiredMixin
from datetime import date as _date

# ========== PIDE Section ==========

class DurasiJatuhTempoPIDEListView(LoginRequiredMixin, AdminPIDERequiredMixin, TemplateView):
    """List view for `DurasiJatuhTempo` entries scoped to PIDE (`user_pide`).

    Renders `durasi_jatuh_tempo/pide_list.html`. When redirected after a
    successful deletion, query parameters `deleted` and `name` are used to
    generate a Django success message for UI to render a toast.
    """
    template_name = 'durasi_jatuh_tempo/pide_list.html'

    def get(self, request, *args, **kwargs):
        """Render the PIDE list template and surface delete success messages.

        Query params considered: `deleted` and `name`. When redirecting after a
        deletion, the `name` value is URL-encoded; this method will decode it and
        show a Django `messages.success` toast.
        """
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class DurasiJatuhTempoPIDECreateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `DurasiJatuhTempo` entries for PIDE.

    Usage: Presents a modal/form to create a new duration rule scoped to PIDE
    (`seksi__name='user_pide'`). Enforces non-overlapping date ranges for the
    same `id_sub_jenis_data`. Supports AJAX via `AjaxFormMixin`.

    Side effects on successful save:
    - Persists a `DurasiJatuhTempo` row with `seksi='user_pide'`.
    - No additional model side-effects beyond saving the instance.
    """
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_form_kwargs(self):
        """Pass `group_name='user_pide'` to the form so widget choices/validation can scope to PIDE."""
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pide'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        """Validate that the date range does not overlap an existing entry.

        This view enforces that for the same `id_sub_jenis_data` within the PIDE
        seksi, the `start_date`/`end_date` ranges do not overlap with other
        `DurasiJatuhTempo` rows. If overlap is detected, an error is added to
        `start_date` and the form is invalidated.
        """
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data') or form.instance.id_sub_jenis_data
        qs = DurasiJatuhTempo.objects.filter(id_sub_jenis_data=id_sub, seksi__name='user_pide')
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class DurasiJatuhTempoPIDEUpdateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `DurasiJatuhTempo` entries (PIDE scope).

    Ensures the updated date range does not overlap other entries for the same
    `id_sub_jenis_data` within the PIDE seksi. Supports AJAX form flows.
    """
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pide'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data') or form.instance.id_sub_jenis_data
        qs = DurasiJatuhTempo.objects.filter(id_sub_jenis_data=id_sub, seksi__name='user_pide').exclude(pk=form.instance.pk)
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class DurasiJatuhTempoPIDEDeleteView(LoginRequiredMixin, AdminPIDERequiredMixin, DeleteView):
    """Delete view for `DurasiJatuhTempo` entries in PIDE scope.

    For AJAX `GET` requests the confirmation fragment is returned as JSON with
    the `html` key. On deletion, sets a Django success message and returns a
    JSON object containing a `redirect` URL so clients can navigate and render
    toasts uniformly.
    """
    model = DurasiJatuhTempo
    template_name = 'durasi_jatuh_tempo/confirm_delete.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pide_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pide_delete', args=[self.object.pk])
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
        # For AJAX, set server-side message and return redirect so that the
        # client can navigate to the list view and let the base template
        # render the toast from Django messages.
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
            return JsonResponse({'success': True, 'redirect': self.success_url})
        messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def durasi_jatuh_tempo_pide_data(request):
    """Server-side DataTables endpoint for PIDE `DurasiJatuhTempo`.

    GET parameters:
    - draw: DataTables draw counter.
    - start, length: paging offset and page size.
    - columns_search[]: column-specific search values (sub_jenis_data, durasi, start_date, end_date).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Filters queryset to `seksi__name='user_pide'` and uses
        `select_related('id_sub_jenis_data', 'seksi')` for efficiency.
    - Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    - Each data row contains: `sub_jenis_data`, `durasi`, `start_date`, `end_date`, and `actions`.

    Side effects: None — read-only endpoint.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = DurasiJatuhTempo.objects.select_related('id_sub_jenis_data', 'seksi').filter(seksi__name='user_pide')
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(durasi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(end_date__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
            'sub_jenis_data': str(obj.id_sub_jenis_data),
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ========== PMDE Section ==========

class AdminPMDERequiredMixin(UserPassesTestMixin):
    """Ensure view access is limited to `admin` or `admin_pmde` group members.

    Use this mixin on class-based views that should be visible only to PMDE
    administrators. It implements `test_func` returning True when the
    requesting user is a member of `admin` or `admin_pmde` groups.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde']).exists()

class DurasiJatuhTempoPMDEListView(LoginRequiredMixin, AdminPMDERequiredMixin, TemplateView):
    """List view for `DurasiJatuhTempo` entries scoped to PMDE (`user_pmde`).

    Renders `durasi_jatuh_tempo/pmde_list.html`. When redirected after a
    successful deletion, query parameters `deleted` and `name` are used to
    generate a Django success message for UI to render a toast.
    """
    template_name = 'durasi_jatuh_tempo/pmde_list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)

class DurasiJatuhTempoPMDECreateView(LoginRequiredMixin, AdminPMDERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `DurasiJatuhTempo` entries for PMDE.

    Usage: Presents a modal/form to create a new duration rule scoped to PMDE
    (`seksi__name='user_pmde'`). Enforces non-overlapping date ranges for the
    same `id_sub_jenis_data`. Supports AJAX via `AjaxFormMixin`.

    Side effects on successful save:
    - Persists a `DurasiJatuhTempo` row with `seksi='user_pmde'`.
    """
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil dibuat.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pmde'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_create')
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data') or form.instance.id_sub_jenis_data
        qs = DurasiJatuhTempo.objects.filter(id_sub_jenis_data=id_sub, seksi__name='user_pmde')
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class DurasiJatuhTempoPMDEUpdateView(LoginRequiredMixin, AdminPMDERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for existing `DurasiJatuhTempo` entries (PMDE scope).

    Ensures the updated date range does not overlap other entries for the same
    `id_sub_jenis_data` within the PMDE seksi. Supports AJAX form flows.
    """
    model = DurasiJatuhTempo
    form_class = DurasiJatuhTempoForm
    template_name = 'durasi_jatuh_tempo/form.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')
    success_message = 'Durasi Jatuh Tempo "{object}" berhasil diperbarui.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['group_name'] = 'user_pmde'
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        s2 = form.cleaned_data.get('start_date')
        if not s2:
            return super().form_valid(form)
        e2 = form.cleaned_data.get('end_date') or _date.max
        id_sub = form.cleaned_data.get('id_sub_jenis_data') or form.instance.id_sub_jenis_data
        qs = DurasiJatuhTempo.objects.filter(id_sub_jenis_data=id_sub, seksi__name='user_pmde').exclude(pk=form.instance.pk)
        for other in qs:
            s1 = other.start_date
            e1 = other.end_date or _date.max
            if not (e1 < s2 or e2 < s1):
                form.add_error('start_date', 'Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini.')
                return self.form_invalid(form)
        return super().form_valid(form)

class DurasiJatuhTempoPMDEDeleteView(LoginRequiredMixin, AdminPMDERequiredMixin, DeleteView):
    """Delete view for `DurasiJatuhTempo` entries in PMDE scope.

    Behaves like the PIDE delete view: returns a confirmation fragment for
    AJAX `GET` and returns JSON with `redirect` on successful deletion. Also
    sets a Django `messages.success` to allow the base template to render
    toasts after navigation.
    """
    model = DurasiJatuhTempo
    template_name = 'durasi_jatuh_tempo/confirm_delete.html'
    success_url = reverse_lazy('durasi_jatuh_tempo_pmde_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('durasi_jatuh_tempo_pmde_delete', args=[self.object.pk])
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
                'message': f'Durasi Jatuh Tempo "{name}" berhasil dihapus.'
            })
        messages.success(request, f'Durasi Jatuh Tempo "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_data(request):
    """Server-side DataTables endpoint for PMDE `DurasiJatuhTempo`.

    GET parameters:
    - draw: DataTables draw counter.
    - start, length: paging offset and page size.
    - columns_search[]: column-specific search values (sub_jenis_data, durasi, start_date, end_date).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Filters queryset to `seksi__name='user_pmde'` and uses
        `select_related('id_sub_jenis_data', 'seksi')` for efficiency.
    - Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    - Each data row contains: `sub_jenis_data`, `durasi`, `start_date`, `end_date`, and `actions`.

    Side effects: None — read-only endpoint.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = DurasiJatuhTempo.objects.select_related('id_sub_jenis_data', 'seksi').filter(seksi__name='user_pmde')
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(durasi__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(end_date__icontains=columns_search[3])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
            'sub_jenis_data': str(obj.id_sub_jenis_data),
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
