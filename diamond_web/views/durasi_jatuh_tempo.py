from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.tiket import Tiket
from ..forms.durasi_jatuh_tempo import DurasiJatuhTempoForm
from .mixins import AjaxFormMixin, AdminPIDERequiredMixin, AdminPMDERequiredMixin, SafeDeleteMixin
from datetime import date as _date

# Durasi Jatuh Tempo PMDE auto-generation rules
GENERATE_PMDE_START_YEAR = 2019
GENERATE_PMDE_DURASI_PRIORITAS = 45
GENERATE_PMDE_DURASI_NON_PRIORITAS = 85

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

class DurasiJatuhTempoPIDEDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminPIDERequiredMixin, DeleteView):
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
    - columns_search[]: column-specific search values (id_sub_jenis_data, nama_sub_jenis_data, durasi, start_date, end_date).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Filters queryset to `seksi__name='user_pide'` and uses
        `select_related('id_sub_jenis_data', 'seksi')` for efficiency.
    - Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    - Each data row contains: `id_sub_jenis_data`, `nama_sub_jenis_data`, `durasi`, `start_date`, `end_date`, and `actions`.

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
        if columns_search[0]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__id_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Durasi
            qs = qs.filter(durasi__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[4])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__id_sub_jenis_data', 'id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
            'id_sub_jenis_data': obj.id_sub_jenis_data.id_sub_jenis_data,
            'nama_sub_jenis_data': obj.id_sub_jenis_data.nama_sub_jenis_data,
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pide_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pide_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ========== PMDE Section ==========

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

class DurasiJatuhTempoPMDEDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminPMDERequiredMixin, DeleteView):
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
    - columns_search[]: column-specific search values (id_sub_jenis_data, nama_sub_jenis_data, durasi, start_date, end_date).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Filters queryset to `seksi__name='user_pmde'` and uses
        `select_related('id_sub_jenis_data', 'seksi')` for efficiency.
    - Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    - Each data row contains: `id_sub_jenis_data`, `nama_sub_jenis_data`, `durasi`, `start_date`, `end_date`, and `actions`.

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
        if columns_search[0]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__id_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__nama_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Durasi
            qs = qs.filter(durasi__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[4])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data__id_sub_jenis_data', 'id_sub_jenis_data__nama_sub_jenis_data', 'durasi', 'start_date', 'end_date']
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
            'id_sub_jenis_data': obj.id_sub_jenis_data.id_sub_jenis_data,
            'nama_sub_jenis_data': obj.id_sub_jenis_data.nama_sub_jenis_data,
            'durasi': obj.durasi,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('durasi_jatuh_tempo_pmde_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('durasi_jatuh_tempo_pmde_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


def _build_pmde_generate_plan(pmde_group):
    """Work out which PMDE `DurasiJatuhTempo` rows are missing.

    Rules applied:
    - Every `JenisDataILAP` row is considered, so a Sub Jenis Data that already
      has PMDE entries still gets the years none of them cover.
    - `durasi` is 45 when the Sub Jenis Data appears in `JenisPrioritasData`,
      otherwise 85.
    - One range per year from `GENERATE_PMDE_START_YEAR` up to and including the
      current year, each covering 01-01 until 31-12 of that year.

    A year is skipped when its range would duplicate or overlap an existing PMDE
    row for the same Sub Jenis Data, so the non-overlapping invariant holds and
    nothing already configured by hand is touched.

    Returns a tuple ``(years, plan, skipped)`` where `plan` is a list of
    ``{'jenis_data', 'durasi', 'is_prioritas', 'ranges'}`` dicts, and `skipped`
    counts the ranges dropped as overlapping. Read-only — nothing is saved.
    """
    current_year = timezone.now().date().year
    years = list(range(GENERATE_PMDE_START_YEAR, current_year + 1))

    candidates = list(JenisDataILAP.objects.order_by('id_sub_jenis_data'))

    if not candidates:
        return years, [], 0

    prioritas_ids = set(
        JenisPrioritasData.objects.values_list('id_sub_jenis_data_ilap_id', flat=True)
    )

    # Existing PMDE ranges per Sub Jenis Data, used to guarantee no duplicate or
    # overlapping range is planned.
    existing_ranges = {}
    for sub_id, start_date, end_date in DurasiJatuhTempo.objects.filter(
        seksi=pmde_group
    ).values_list('id_sub_jenis_data_id', 'start_date', 'end_date'):
        existing_ranges.setdefault(sub_id, []).append((start_date, end_date or _date.max))

    plan = []
    skipped = 0
    for obj in candidates:
        is_prioritas = obj.pk in prioritas_ids
        durasi = (
            GENERATE_PMDE_DURASI_PRIORITAS if is_prioritas
            else GENERATE_PMDE_DURASI_NON_PRIORITAS
        )
        ranges = existing_ranges.setdefault(obj.pk, [])
        planned_ranges = []
        for year in years:
            start_date = _date(year, 1, 1)
            end_date = _date(year, 12, 31)
            if any(not (e1 < start_date or end_date < s1) for s1, e1 in ranges):
                skipped += 1
                continue
            ranges.append((start_date, end_date))
            planned_ranges.append((start_date, end_date))
        if planned_ranges:
            plan.append({
                'jenis_data': obj,
                'durasi': durasi,
                'is_prioritas': is_prioritas,
                'ranges': planned_ranges,
            })

    return years, plan, skipped


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_generate_preview(request):
    """Summarise the PMDE `DurasiJatuhTempo` rows that `generate` would create.

    Used to confirm the operation before anything is written. Applies exactly the
    same rules as `durasi_jatuh_tempo_pmde_generate` — see
    `_build_pmde_generate_plan` — but saves nothing.

    Returns JSON with `success`, `tahun_awal`/`tahun_akhir`, `total_rows`,
    `total_jenis_data`, `prioritas`/`non_prioritas` (Sub Jenis Data per durasi),
    `skipped`, and `items`: one entry per affected Sub Jenis Data with its kode,
    nama, durasi, and the periode ranges to be inserted.

    Side effects: None — read-only endpoint.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    years, plan, skipped = _build_pmde_generate_plan(pmde_group)

    items = [
        {
            'id_sub_jenis_data': entry['jenis_data'].id_sub_jenis_data,
            'nama_sub_jenis_data': entry['jenis_data'].nama_sub_jenis_data,
            'durasi': entry['durasi'],
            'is_prioritas': entry['is_prioritas'],
            'jumlah_baris': len(entry['ranges']),
            'periode': [
                f"{start.strftime('%d-%m-%Y')} s.d. {end.strftime('%d-%m-%Y')}"
                for start, end in entry['ranges']
            ],
        }
        for entry in plan
    ]

    return JsonResponse({
        'success': True,
        'tahun_awal': years[0] if years else None,
        'tahun_akhir': years[-1] if years else None,
        'total_rows': sum(item['jumlah_baris'] for item in items),
        'total_jenis_data': len(items),
        'prioritas': sum(1 for item in items if item['is_prioritas']),
        'non_prioritas': sum(1 for item in items if not item['is_prioritas']),
        'durasi_prioritas': GENERATE_PMDE_DURASI_PRIORITAS,
        'durasi_non_prioritas': GENERATE_PMDE_DURASI_NON_PRIORITAS,
        'skipped': skipped,
        'items': items,
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_generate(request):
    """Bulk-create the missing PMDE `DurasiJatuhTempo` rows.

    Applies the rules described in `_build_pmde_generate_plan`; the client shows
    `durasi_jatuh_tempo_pmde_generate_preview` first so the user can confirm what
    will be inserted.

    Side effects: creates `DurasiJatuhTempo` rows (stamped with audit fields)
    inside a single transaction.

    Returns JSON with `success`, `created` (rows written), `jenis_data`
    (Sub Jenis Data touched), `skipped` (ranges skipped as overlapping) and a
    ready-to-display `message`.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    years, plan, skipped = _build_pmde_generate_plan(pmde_group)

    if not plan:
        return JsonResponse({
            'success': True,
            'created': 0,
            'jenis_data': 0,
            'skipped': skipped,
            'message': 'Tidak ada Jenis Data yang perlu ditambahkan. Semua tahun sudah punya Durasi Jatuh Tempo PMDE.',
        })

    today = timezone.now().date()
    username = (getattr(request.user, 'username', '') or '')[:9]

    new_rows = [
        DurasiJatuhTempo(
            id_sub_jenis_data=entry['jenis_data'],
            seksi=pmde_group,
            durasi=entry['durasi'],
            start_date=start_date,
            end_date=end_date,
            create_date=today,
            create_by=username,
            update_date=today,
            update_by=username,
        )
        for entry in plan
        for start_date, end_date in entry['ranges']
    ]

    with transaction.atomic():
        DurasiJatuhTempo.objects.bulk_create(new_rows, batch_size=500)

    return JsonResponse({
        'success': True,
        'created': len(new_rows),
        'jenis_data': len(plan),
        'skipped': skipped,
        'message': (
            f'{len(new_rows)} baris Durasi Jatuh Tempo PMDE berhasil dibuat untuk '
            f'{len(plan)} Sub Jenis Data (tahun {years[0]}-{years[-1]}).'
        ),
    })


def _build_pmde_prioritas_sync_plan(pmde_group):
    """Find the generated PMDE rows whose durasi no longer matches their prioritas.

    A Sub Jenis Data can be added to or removed from `JenisPrioritasData` long
    after its `DurasiJatuhTempo` rows were generated, which leaves those rows on
    the wrong side of the 45/85 rule. This collects the rows that need flipping —
    85 to 45 when the Sub Jenis Data became prioritas, 45 to 85 when it stopped
    being one.

    Only rows that still carry one of the two generated values are considered, so
    a durasi somebody set by hand (say 30) is never overwritten.

    Returns a dict with `updates` (list of ``(durasi_row_id, durasi_baru)``
    pairs), `items` (one entry per Sub Jenis Data, for the confirmation screen)
    and the `menjadi_prioritas`/`menjadi_non_prioritas` Sub Jenis Data counts.
    Read-only — nothing is saved.
    """
    is_prioritas = Exists(
        JenisPrioritasData.objects.filter(id_sub_jenis_data_ilap=OuterRef('id_sub_jenis_data_id'))
    )
    stale = DurasiJatuhTempo.objects.filter(
        seksi=pmde_group,
        durasi__in=(GENERATE_PMDE_DURASI_PRIORITAS, GENERATE_PMDE_DURASI_NON_PRIORITAS),
    ).annotate(prioritas=is_prioritas).filter(
        Q(prioritas=True, durasi=GENERATE_PMDE_DURASI_NON_PRIORITAS)
        | Q(prioritas=False, durasi=GENERATE_PMDE_DURASI_PRIORITAS)
    ).order_by('id_sub_jenis_data__id_sub_jenis_data', 'start_date')

    updates = []
    items = {}
    for row_id, sub_id, kode, nama, durasi, prioritas, start_date, end_date in stale.values_list(
        'id', 'id_sub_jenis_data_id',
        'id_sub_jenis_data__id_sub_jenis_data', 'id_sub_jenis_data__nama_sub_jenis_data',
        'durasi', 'prioritas', 'start_date', 'end_date',
    ).iterator(chunk_size=2000):
        durasi_baru = (
            GENERATE_PMDE_DURASI_PRIORITAS if prioritas
            else GENERATE_PMDE_DURASI_NON_PRIORITAS
        )
        updates.append((row_id, durasi_baru))
        item = items.setdefault(sub_id, {
            'id_sub_jenis_data': kode,
            'nama_sub_jenis_data': nama,
            'is_prioritas': bool(prioritas),
            'durasi_lama': durasi,
            'durasi_baru': durasi_baru,
            'jumlah_baris': 0,
            'periode': [],
        })
        item['jumlah_baris'] += 1
        item['periode'].append(
            f"{start_date.strftime('%d-%m-%Y')} s.d. "
            f"{end_date.strftime('%d-%m-%Y') if end_date else 'seterusnya'}"
        )

    items = list(items.values())
    return {
        'updates': updates,
        'items': items,
        'menjadi_prioritas': sum(1 for item in items if item['is_prioritas']),
        'menjadi_non_prioritas': sum(1 for item in items if not item['is_prioritas']),
    }


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_prioritas_sync_preview(request):
    """Summarise the durasi values that the prioritas sync step would change.

    Applies exactly the same rules as `durasi_jatuh_tempo_pmde_prioritas_sync` —
    see `_build_pmde_prioritas_sync_plan` — but saves nothing.

    Returns JSON with `success`, `total_rows`, `total_jenis_data`,
    `menjadi_prioritas`/`menjadi_non_prioritas`, the two durasi constants, and
    `items`: one entry per affected Sub Jenis Data with its kode, nama, old and
    new durasi, and the periode of every row that changes.

    Side effects: None — read-only endpoint.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    plan = _build_pmde_prioritas_sync_plan(pmde_group)

    return JsonResponse({
        'success': True,
        'total_rows': len(plan['updates']),
        'total_jenis_data': len(plan['items']),
        'menjadi_prioritas': plan['menjadi_prioritas'],
        'menjadi_non_prioritas': plan['menjadi_non_prioritas'],
        'durasi_prioritas': GENERATE_PMDE_DURASI_PRIORITAS,
        'durasi_non_prioritas': GENERATE_PMDE_DURASI_NON_PRIORITAS,
        'items': plan['items'],
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_prioritas_sync(request):
    """Re-apply the 45/85 rule to PMDE rows whose prioritas has since changed.

    Applies the rules described in `_build_pmde_prioritas_sync_plan`; the client
    shows `durasi_jatuh_tempo_pmde_prioritas_sync_preview` first so the user can
    confirm what will change.

    Side effects: updates `durasi` (and the audit fields) on the affected
    `DurasiJatuhTempo` rows inside a single transaction. The rows themselves are
    kept, so tikets already pointing at them keep their reference and simply pick
    up the new durasi.

    Returns JSON with `success`, `updated` (rows changed), `jenis_data`
    (Sub Jenis Data touched) and a ready-to-display `message`.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    plan = _build_pmde_prioritas_sync_plan(pmde_group)
    updates = plan['updates']

    if not updates:
        return JsonResponse({
            'success': True,
            'updated': 0,
            'jenis_data': 0,
            'message': 'Tidak ada durasi yang perlu disesuaikan. Semua sudah sesuai status prioritasnya.',
        })

    today = timezone.now().date()
    username = (getattr(request.user, 'username', '') or '')[:9]

    with transaction.atomic():
        DurasiJatuhTempo.objects.bulk_update(
            [
                DurasiJatuhTempo(
                    id=row_id, durasi=durasi_baru, update_date=today, update_by=username
                )
                for row_id, durasi_baru in updates
            ],
            ['durasi', 'update_date', 'update_by'],
            batch_size=500,
        )

    return JsonResponse({
        'success': True,
        'updated': len(updates),
        'jenis_data': len(plan['items']),
        'message': (
            f'{len(updates)} baris Durasi Jatuh Tempo PMDE disesuaikan untuk '
            f'{len(plan["items"])} Sub Jenis Data ('
            f'{plan["menjadi_prioritas"]} menjadi prioritas, '
            f'{plan["menjadi_non_prioritas"]} menjadi non-prioritas).'
        ),
    })


def _build_pmde_tiket_backfill_plan(pmde_group):
    """Match every Tiket that still has no `id_durasi_jatuh_tempo_pmde` to a row.

    The match follows the model relation: a tiket points at a `PeriodeJenisData`,
    which names the `JenisDataILAP`, which owns the `DurasiJatuhTempo` rows — of
    those, the PMDE one whose range covers the tiket's base date is the answer.

    The base date is `tgl_rematch` when the tiket has been rematched and
    `tgl_transfer` otherwise, the same date `quality_control` counts the PMDE
    deadline from. Tikets that never reached PMDE therefore have no base date and
    are left untouched, and so is a tiket whose base date falls outside every
    range configured for its Sub Jenis Data.

    Returns a dict with `matches` (list of ``(tiket_id, durasi_id)`` pairs),
    `per_year` (matched tikets grouped by the year of their base date),
    `unmatched` and `tanpa_tanggal`. Read-only — nothing is saved.
    """
    # PMDE ranges per Sub Jenis Data, latest start first so the most recently
    # configured range wins when two of them cover the same date.
    ranges = {}
    for durasi_id, sub_id, start_date, end_date in DurasiJatuhTempo.objects.filter(
        seksi=pmde_group
    ).values_list('id', 'id_sub_jenis_data_id', 'start_date', 'end_date'):
        ranges.setdefault(sub_id, []).append((start_date, end_date or _date.max, durasi_id))
    for entries in ranges.values():
        entries.sort(key=lambda entry: entry[0], reverse=True)

    empty = Tiket.objects.filter(id_durasi_jatuh_tempo_pmde__isnull=True)
    tanpa_tanggal = empty.filter(tgl_transfer__isnull=True, tgl_rematch__isnull=True).count()

    matches = []
    per_year = {}
    unmatched = 0
    for tiket_id, sub_id, tgl_transfer, tgl_rematch in empty.exclude(
        tgl_transfer__isnull=True, tgl_rematch__isnull=True
    ).values_list(
        'id', 'id_periode_data__id_sub_jenis_data_ilap_id', 'tgl_transfer', 'tgl_rematch'
    ).iterator(chunk_size=2000):
        base = tgl_rematch or tgl_transfer
        base_date = base.date() if hasattr(base, 'date') else base
        for start_date, end_date, durasi_id in ranges.get(sub_id, ()):
            if start_date <= base_date <= end_date:
                matches.append((tiket_id, durasi_id))
                per_year[base_date.year] = per_year.get(base_date.year, 0) + 1
                break
        else:
            unmatched += 1

    return {
        'matches': matches,
        'per_year': [{'tahun': year, 'jumlah': per_year[year]} for year in sorted(per_year)],
        'unmatched': unmatched,
        'tanpa_tanggal': tanpa_tanggal,
    }


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_tiket_backfill_preview(request):
    """Summarise the tikets that the backfill step would fill in.

    Second step of Generate Otomatis: once the PMDE `DurasiJatuhTempo` rows exist,
    the tikets that were imported without one can be pointed at them. Applies
    exactly the same matching as `durasi_jatuh_tempo_pmde_tiket_backfill` — see
    `_build_pmde_tiket_backfill_plan` — but saves nothing.

    Returns JSON with `success`, `total_tiket` (rows that would be updated),
    `per_year` (breakdown by year of the base date), `unmatched` (tikets whose
    base date no range covers) and `tanpa_tanggal` (tikets that never reached
    PMDE, so they have no base date to match on).

    Side effects: None — read-only endpoint.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    plan = _build_pmde_tiket_backfill_plan(pmde_group)

    return JsonResponse({
        'success': True,
        'total_tiket': len(plan['matches']),
        'per_year': plan['per_year'],
        'unmatched': plan['unmatched'],
        'tanpa_tanggal': plan['tanpa_tanggal'],
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_tiket_backfill(request):
    """Fill the empty `Tiket.id_durasi_jatuh_tempo_pmde` columns.

    Applies the matching described in `_build_pmde_tiket_backfill_plan`; the
    client shows `durasi_jatuh_tempo_pmde_tiket_backfill_preview` first so the
    user can confirm how many tikets will be touched.

    Side effects: updates `id_durasi_jatuh_tempo_pmde` on the matched tikets
    inside a single transaction. Only rows that are currently NULL are considered,
    so a value already recorded is never overwritten and re-running is a no-op.

    Returns JSON with `success`, `updated`, `unmatched`, `tanpa_tanggal` and a
    ready-to-display `message`.
    """
    pmde_group = Group.objects.filter(name='user_pmde').first()
    if pmde_group is None:
        return JsonResponse(
            {'success': False, 'message': 'Grup seksi "user_pmde" belum tersedia.'},
            status=400,
        )

    plan = _build_pmde_tiket_backfill_plan(pmde_group)
    matches = plan['matches']

    if not matches:
        return JsonResponse({
            'success': True,
            'updated': 0,
            'unmatched': plan['unmatched'],
            'tanpa_tanggal': plan['tanpa_tanggal'],
            'message': 'Tidak ada Tiket yang perlu diisi Durasi Jatuh Tempo PMDE-nya.',
        })

    with transaction.atomic():
        Tiket.objects.bulk_update(
            [
                Tiket(id=tiket_id, id_durasi_jatuh_tempo_pmde_id=durasi_id)
                for tiket_id, durasi_id in matches
            ],
            ['id_durasi_jatuh_tempo_pmde'],
            batch_size=500,
        )

    message = f'{len(matches)} Tiket berhasil diisi Durasi Jatuh Tempo PMDE-nya.'
    if plan['unmatched']:
        message += (
            f' {plan["unmatched"]} Tiket dilewati karena tidak ada durasi yang '
            'berlaku pada tanggal transfer/rematch-nya.'
        )

    return JsonResponse({
        'success': True,
        'updated': len(matches),
        'unmatched': plan['unmatched'],
        'tanpa_tanggal': plan['tanpa_tanggal'],
        'message': message,
    })
