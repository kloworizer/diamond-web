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
from django.utils import timezone

from ..models.aturan_durasi_jatuh_tempo import AturanDurasiJatuhTempo
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.tiket import Tiket
from ..forms.durasi_jatuh_tempo import DurasiJatuhTempoForm
from .mixins import AjaxFormMixin, AdminPIDERequiredMixin, AdminPMDERequiredMixin, SafeDeleteMixin
from datetime import date as _date

# Grup seksi pemilik tiap menu Durasi Jatuh Tempo.
SEKSI_PIDE = 'user_pide'
SEKSI_PMDE = 'user_pmde'

# Durasi Generate Otomatis dulu berupa konstanta di sini (prioritas 45, non
# prioritas 85, PMDE saja). Angkanya sekarang data: satu baris
# AturanDurasiJatuhTempo per seksi per tahun, dengan pengecualian opsional per
# ILAP atau per sub jenis data. Lihat models/aturan_durasi_jatuh_tempo.py.

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


def _overlaps(start_a, end_a, start_b, end_b):
    """True when the two closed date ranges share at least one day."""
    return not (end_a < start_b or end_b < start_a)


def _seksi_group(nama):
    """Grup seksi, atau None bila belum ada di database."""
    return Group.objects.filter(name=nama).first()


def _seksi_missing_response(nama):
    return JsonResponse(
        {'success': False, 'message': f'Grup seksi "{nama}" belum tersedia.'},
        status=400,
    )


def _prioritas_ranges():
    """The periods each Sub Jenis Data is prioritas, keyed by Sub Jenis Data id.

    Prioritas is not a property of the Sub Jenis Data but of a period of it: a
    `JenisPrioritasData` row carries the `start_date`/`end_date` the ND assigned
    it for, so a Sub Jenis Data can be prioritas in one year and not the next.
    An open-ended row (no `end_date`) runs indefinitely.
    """
    ranges = {}
    for sub_id, start_date, end_date in JenisPrioritasData.objects.values_list(
        'id_sub_jenis_data_ilap_id', 'start_date', 'end_date'
    ):
        ranges.setdefault(sub_id, []).append((start_date, end_date or _date.max))
    return ranges


def _is_prioritas_periode(prioritas_ranges, sub_id, start_date, end_date):
    """Whether the period `start_date`..`end_date` of `sub_id` counts as prioritas.

    A period is prioritas when any of the Sub Jenis Data's prioritas ranges
    overlaps it. Generated ranges are whole years and the prioritas ND covers a
    whole year too, so in practice this is a year-for-year comparison; a prioritas
    range that only covers part of a period still makes that whole period
    prioritas, since the durasi is a single number per row.
    """
    return any(
        _overlaps(start_date, end_date, p_start, p_end)
        for p_start, p_end in prioritas_ranges.get(sub_id, ())
    )


def _build_generate_plan(seksi):
    """Work out which `DurasiJatuhTempo` rows are missing for `seksi`.

    Rules applied:
    - Every `JenisDataILAP` row is considered, so a Sub Jenis Data that already
      has entries still gets the years none of them cover.
    - One range per year that `seksi` has an `AturanDurasiJatuhTempo` for, each
      covering 01-01 until 31-12 of that year. A year with no rule is not
      generated at all — the durasi would be a guess, so it is reported instead.
    - `durasi` comes from the rule that best fits the Sub Jenis Data: its own
      rule, else its ILAP's, else the seksi's general rule for that year. Whether
      the prioritas or the non-prioritas number applies is decided per year, from
      the `JenisPrioritasData` periods — so one Sub Jenis Data can take the
      prioritas durasi in some years and the non-prioritas one in the rest.

    A year is skipped when its range would duplicate or overlap an existing row
    for the same Sub Jenis Data, so the non-overlapping invariant holds and
    nothing already configured by hand is touched.

    Returns ``(years, plan, skipped)`` where `plan` is a list of
    ``{'jenis_data', 'ranges'}`` dicts whose `ranges` are
    ``(start_date, end_date, durasi, is_prioritas)`` tuples, and `skipped` counts
    the ranges dropped as overlapping. Read-only — nothing is saved.
    """
    years = AturanDurasiJatuhTempo.tahun_tersedia(seksi)
    if not years:
        return [], [], 0

    aturan = AturanDurasiJatuhTempo.index_for(seksi)
    candidates = list(
        JenisDataILAP.objects.order_by('id_sub_jenis_data').only('id', 'id_ilap')
    )
    if not candidates:
        return years, [], 0

    prioritas_ranges = _prioritas_ranges()

    # Existing ranges per Sub Jenis Data, used to guarantee no duplicate or
    # overlapping range is planned.
    existing_ranges = {}
    for sub_id, start_date, end_date in DurasiJatuhTempo.objects.filter(
        seksi=seksi
    ).values_list('id_sub_jenis_data_id', 'start_date', 'end_date'):
        existing_ranges.setdefault(sub_id, []).append((start_date, end_date or _date.max))

    plan = []
    skipped = 0
    for obj in candidates:
        ranges = existing_ranges.setdefault(obj.pk, [])
        planned_ranges = []
        for year in years:
            start_date = _date(year, 1, 1)
            end_date = _date(year, 12, 31)
            if any(_overlaps(start_date, end_date, s1, e1) for s1, e1 in ranges):
                skipped += 1
                continue
            is_prioritas = _is_prioritas_periode(prioritas_ranges, obj.pk, start_date, end_date)
            durasi = AturanDurasiJatuhTempo.resolve(
                aturan, obj.pk, obj.id_ilap_id, year, is_prioritas
            )
            if durasi is None:
                continue
            ranges.append((start_date, end_date))
            planned_ranges.append((start_date, end_date, durasi, is_prioritas))
        if planned_ranges:
            plan.append({'jenis_data': obj, 'ranges': planned_ranges})

    return years, plan, skipped


def _build_prioritas_sync_plan(seksi):
    """Find the rows of `seksi` whose durasi no longer matches their prioritas.

    A prioritas period can be added or deleted long after the `DurasiJatuhTempo`
    rows were generated, which leaves rows on the wrong side of the rule. Each
    row is judged against its own periode — the same test
    :func:`_build_generate_plan` applies when it creates one — so only the years
    a `JenisPrioritasData` period actually overlaps take the prioritas durasi,
    and a year that lost its prioritas goes back to the non-prioritas one while
    the Sub Jenis Data's other years stay put.

    **Only rows that still hold one of the two numbers their own rule allows are
    touched.** A durasi somebody set by hand (say 30) is never overwritten — and
    neither is one governed by a per-ILAP or per-sub-jenis-data exception, since
    the comparison is made against that Sub Jenis Data's own resolved rule rather
    than against one global pair of numbers.

    Returns a dict with `updates` (list of ``(durasi_row_id, durasi_baru)``
    pairs), `items` (one entry per Sub Jenis Data, each listing the rows that
    change, for the confirmation screen) and the `baris_ke_prioritas` /
    `baris_ke_non_prioritas` row counts. Read-only — nothing is saved.
    """
    prioritas_ranges = _prioritas_ranges()
    aturan = AturanDurasiJatuhTempo.index_for(seksi)

    candidates = DurasiJatuhTempo.objects.filter(
        seksi=seksi
    ).order_by('id_sub_jenis_data__id_sub_jenis_data', 'start_date')

    updates = []
    items = {}
    ke_prioritas = 0
    ke_non_prioritas = 0
    # Angka yang aturan izinkan pada baris-baris yang diperiksa — itulah yang
    # membedakan "sesuai aturan" dari "disetel tangan", dan bisa lebih dari satu
    # karena ada pengecualian per ILAP/Sub Jenis Data.
    nilai_prioritas = set()
    nilai_non_prioritas = set()
    for (
        row_id, sub_id, ilap_id, kode, nama, durasi, start_date, end_date
    ) in candidates.values_list(
        'id', 'id_sub_jenis_data_id', 'id_sub_jenis_data__id_ilap_id',
        'id_sub_jenis_data__id_sub_jenis_data', 'id_sub_jenis_data__nama_sub_jenis_data',
        'durasi', 'start_date', 'end_date',
    ).iterator(chunk_size=2000):
        tahun = start_date.year
        durasi_prioritas = AturanDurasiJatuhTempo.resolve(
            aturan, sub_id, ilap_id, tahun, True
        )
        durasi_non_prioritas = AturanDurasiJatuhTempo.resolve(
            aturan, sub_id, ilap_id, tahun, False
        )
        if durasi_prioritas is None or durasi_non_prioritas is None:
            # Tahun ini belum punya aturan — tidak ada dasar untuk mengubahnya.
            continue
        nilai_prioritas.add(durasi_prioritas)
        nilai_non_prioritas.add(durasi_non_prioritas)
        if durasi not in (durasi_prioritas, durasi_non_prioritas):
            # Diatur di luar aturan (mis. disetel tangan). Jangan disentuh.
            continue

        is_prioritas = _is_prioritas_periode(
            prioritas_ranges, sub_id, start_date, end_date or _date.max
        )
        durasi_baru = durasi_prioritas if is_prioritas else durasi_non_prioritas
        if durasi == durasi_baru:
            continue

        updates.append((row_id, durasi_baru))
        if is_prioritas:
            ke_prioritas += 1
        else:
            ke_non_prioritas += 1

        item = items.setdefault(sub_id, {
            'id_sub_jenis_data': kode,
            'nama_sub_jenis_data': nama,
            'jumlah_baris': 0,
            'baris': [],
        })
        item['jumlah_baris'] += 1
        item['baris'].append({
            'periode': (
                f"{start_date.strftime('%d-%m-%Y')} s.d. "
                f"{end_date.strftime('%d-%m-%Y') if end_date else 'seterusnya'}"
            ),
            'durasi_lama': durasi,
            'durasi_baru': durasi_baru,
            'is_prioritas': is_prioritas,
        })

    return {
        'updates': updates,
        'items': list(items.values()),
        'baris_ke_prioritas': ke_prioritas,
        'baris_ke_non_prioritas': ke_non_prioritas,
        'durasi_prioritas': sorted(nilai_prioritas),
        'durasi_non_prioritas': sorted(nilai_non_prioritas),
    }


def _generate_preview_payload(seksi):
    """JSON body ringkasan baris yang akan dibuat Generate Otomatis.

    Dipakai kedua seksi lewat endpoint masing-masing, supaya PIDE dan PMDE tidak
    bisa perlahan berbeda aturan.
    """
    years, plan, skipped = _build_generate_plan(seksi)

    items = [
        {
            'id_sub_jenis_data': entry['jenis_data'].id_sub_jenis_data,
            'nama_sub_jenis_data': entry['jenis_data'].nama_sub_jenis_data,
            'jumlah_baris': len(entry['ranges']),
            'baris': [
                {
                    'periode': f"{start.strftime('%d-%m-%Y')} s.d. {end.strftime('%d-%m-%Y')}",
                    'durasi': durasi,
                    'is_prioritas': is_prioritas,
                }
                for start, end, durasi, is_prioritas in entry['ranges']
            ],
        }
        for entry in plan
    ]

    all_rows = [row for item in items for row in item['baris']]

    # Angka yang benar-benar akan ditulis, bukan satu pasang tetap: sejak durasi
    # datang dari AturanDurasiJatuhTempo, satu seksi bisa memakai beberapa angka
    # sekaligus — aturan umumnya plus pengecualian per ILAP/Sub Jenis Data.
    return {
        'success': True,
        'tahun_awal': years[0] if years else None,
        'tahun_akhir': years[-1] if years else None,
        'tahun_tersedia': years,
        'total_rows': len(all_rows),
        'total_jenis_data': len(items),
        'baris_prioritas': sum(1 for row in all_rows if row['is_prioritas']),
        'baris_non_prioritas': sum(1 for row in all_rows if not row['is_prioritas']),
        'durasi_prioritas': sorted({r['durasi'] for r in all_rows if r['is_prioritas']}),
        'durasi_non_prioritas': sorted({r['durasi'] for r in all_rows if not r['is_prioritas']}),
        'skipped': skipped,
        'items': items,
        'message_kosong': (
            'Belum ada Aturan Durasi Jatuh Tempo untuk seksi ini. Isi dulu di menu '
            'Aturan Durasi Jatuh Tempo — tanpa aturan, durasi tidak bisa ditentukan.'
        ) if not years else '',
    }


def _generate_apply(request, seksi, label):
    """Tulis baris yang direncanakan Generate Otomatis untuk `seksi`."""
    years, plan, skipped = _build_generate_plan(seksi)

    if not years:
        return JsonResponse({
            'success': False,
            'message': (
                'Belum ada Aturan Durasi Jatuh Tempo untuk seksi ini. Isi dulu di '
                'menu Aturan Durasi Jatuh Tempo.'
            ),
        }, status=400)

    if not plan:
        return JsonResponse({
            'success': True,
            'created': 0,
            'jenis_data': 0,
            'skipped': skipped,
            'message': (
                f'Tidak ada Jenis Data yang perlu ditambahkan. Semua tahun sudah '
                f'punya Durasi Jatuh Tempo {label}.'
            ),
        })

    today = timezone.now().date()
    username = (getattr(request.user, 'username', '') or '')[:9]

    new_rows = [
        DurasiJatuhTempo(
            id_sub_jenis_data=entry['jenis_data'],
            seksi=seksi,
            durasi=durasi,
            start_date=start_date,
            end_date=end_date,
            create_date=today,
            create_by=username,
            update_date=today,
            update_by=username,
        )
        for entry in plan
        for start_date, end_date, durasi, _is_prioritas in entry['ranges']
    ]

    with transaction.atomic():
        DurasiJatuhTempo.objects.bulk_create(new_rows, batch_size=500)

    return JsonResponse({
        'success': True,
        'created': len(new_rows),
        'jenis_data': len(plan),
        'skipped': skipped,
        'message': (
            f'{len(new_rows)} baris Durasi Jatuh Tempo {label} berhasil dibuat untuk '
            f'{len(plan)} Sub Jenis Data (tahun {years[0]}-{years[-1]}).'
        ),
    })


def _prioritas_sync_preview_payload(seksi):
    plan = _build_prioritas_sync_plan(seksi)
    return {
        'success': True,
        'total_rows': len(plan['updates']),
        'total_jenis_data': len(plan['items']),
        'baris_ke_prioritas': plan['baris_ke_prioritas'],
        'baris_ke_non_prioritas': plan['baris_ke_non_prioritas'],
        'durasi_prioritas': plan['durasi_prioritas'],
        'durasi_non_prioritas': plan['durasi_non_prioritas'],
        'items': plan['items'],
    }


def _prioritas_sync_apply(request, seksi, label):
    plan = _build_prioritas_sync_plan(seksi)
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
            f'{len(updates)} baris Durasi Jatuh Tempo {label} disesuaikan untuk '
            f'{len(plan["items"])} Sub Jenis Data.'
        ),
    })


# ---------------------------------------------------------------------------
# Endpoint PMDE
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_generate_preview(request):
    """Summarise the PMDE `DurasiJatuhTempo` rows that `generate` would create.

    Used to confirm the operation before anything is written. Applies exactly the
    same rules as `durasi_jatuh_tempo_pmde_generate` — see `_build_generate_plan`
    — but saves nothing. Side effects: None.
    """
    seksi = _seksi_group(SEKSI_PMDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return JsonResponse(_generate_preview_payload(seksi))


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_generate(request):
    """Bulk-create the missing PMDE `DurasiJatuhTempo` rows.

    Applies the rules described in `_build_generate_plan`; the client shows
    `durasi_jatuh_tempo_pmde_generate_preview` first so the user can confirm what
    will be inserted. Side effects: creates rows inside a single transaction.
    """
    seksi = _seksi_group(SEKSI_PMDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return _generate_apply(request, seksi, 'PMDE')


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_prioritas_sync_preview(request):
    """Summarise the durasi values that the PMDE prioritas sync would change.

    Same rules as `durasi_jatuh_tempo_pmde_prioritas_sync` — see
    `_build_prioritas_sync_plan` — but saves nothing. Side effects: None.
    """
    seksi = _seksi_group(SEKSI_PMDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return JsonResponse(_prioritas_sync_preview_payload(seksi))


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_prioritas_sync(request):
    """Re-apply each row's own rule to PMDE rows whose prioritas has changed.

    Side effects: updates `durasi` (and the audit fields) on the affected rows
    inside a single transaction. The rows themselves are kept, so tikets already
    pointing at them keep their reference and simply pick up the new durasi.
    """
    seksi = _seksi_group(SEKSI_PMDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return _prioritas_sync_apply(request, seksi, 'PMDE')


# ---------------------------------------------------------------------------
# Endpoint PIDE — mesin yang sama, grup seksi dan hak akses berbeda
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def durasi_jatuh_tempo_pide_generate_preview(request):
    """Summarise the PIDE `DurasiJatuhTempo` rows that `generate` would create."""
    seksi = _seksi_group(SEKSI_PIDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return JsonResponse(_generate_preview_payload(seksi))


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_POST
def durasi_jatuh_tempo_pide_generate(request):
    """Bulk-create the missing PIDE `DurasiJatuhTempo` rows."""
    seksi = _seksi_group(SEKSI_PIDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return _generate_apply(request, seksi, 'PIDE')


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def durasi_jatuh_tempo_pide_prioritas_sync_preview(request):
    """Summarise the durasi values that the PIDE prioritas sync would change."""
    seksi = _seksi_group(SEKSI_PIDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return JsonResponse(_prioritas_sync_preview_payload(seksi))


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_POST
def durasi_jatuh_tempo_pide_prioritas_sync(request):
    """Re-apply each row's own rule to PIDE rows whose prioritas has changed."""
    seksi = _seksi_group(SEKSI_PIDE)
    if seksi is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return _prioritas_sync_apply(request, seksi, 'PIDE')


# Which Tiket column each seksi's backfill fills, and the tiket dates it matches
# on — in priority order, the first one that is set wins.
#
# PMDE counts from tgl_transfer and starts again from tgl_rematch, matching the
# Deadline in quality_control. PIDE counts from tgl_kirim_pide alone: the tiket
# is handed to PIDE on that date, and that is the date the durasi is meant to be
# read at, so a later tgl_rekam_pide does not move which row applies.
TIKET_BACKFILL = {
    SEKSI_PMDE: ('id_durasi_jatuh_tempo_pmde', ('tgl_rematch', 'tgl_transfer')),
    SEKSI_PIDE: ('id_durasi_jatuh_tempo_pide', ('tgl_kirim_pide',)),
}


def _build_tiket_backfill_plan(seksi, kolom, tanggal_fields):
    """Match every Tiket that still has no durasi for `seksi` to a row.

    The match follows the model relation: a tiket points at a `PeriodeJenisData`,
    which names the `JenisDataILAP`, which owns the `DurasiJatuhTempo` rows — of
    those, the one for this seksi whose range covers the tiket's base date is the
    answer.

    The base date is the first of `tanggal_fields` that is set — see
    `TIKET_BACKFILL` for what each seksi counts from and why. A tiket that never
    reached the seksi therefore has no base date and is left untouched, and so is
    a tiket whose base date falls outside every range configured for its Sub Jenis
    Data.

    Returns a dict with `matches` (list of ``(tiket_id, durasi_id)`` pairs),
    `per_year` (matched tikets grouped by the year of their base date),
    `unmatched` and `tanpa_tanggal`. Read-only — nothing is saved.
    """
    # Ranges per Sub Jenis Data, latest start first so the most recently
    # configured range wins when two of them cover the same date.
    ranges = {}
    for durasi_id, sub_id, start_date, end_date in DurasiJatuhTempo.objects.filter(
        seksi=seksi
    ).values_list('id', 'id_sub_jenis_data_id', 'start_date', 'end_date'):
        ranges.setdefault(sub_id, []).append((start_date, end_date or _date.max, durasi_id))
    for entries in ranges.values():
        entries.sort(key=lambda entry: entry[0], reverse=True)

    empty = Tiket.objects.filter(**{f'{kolom}__isnull': True})
    # Passing every date field to one filter() ANDs them, so this counts the
    # tikets with none of them set — and exclude() of the same lookup keeps the
    # tikets with at least one.
    tanpa_semua_tanggal = {f'{field}__isnull': True for field in tanggal_fields}
    tanpa_tanggal = empty.filter(**tanpa_semua_tanggal).count()

    matches = []
    per_year = {}
    unmatched = 0
    for row in empty.exclude(**tanpa_semua_tanggal).values_list(
        'id', 'id_periode_data__id_sub_jenis_data_ilap_id', *tanggal_fields
    ).iterator(chunk_size=2000):
        tiket_id, sub_id = row[0], row[1]
        base = next((value for value in row[2:] if value), None)
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


def _tiket_backfill_preview_payload(seksi_name):
    """Read-only summary of what `_tiket_backfill_apply` would fill in."""
    seksi = _seksi_group(seksi_name)
    if seksi is None:
        return None

    kolom, tanggal_fields = TIKET_BACKFILL[seksi_name]
    plan = _build_tiket_backfill_plan(seksi, kolom, tanggal_fields)

    return {
        'success': True,
        'total_tiket': len(plan['matches']),
        'per_year': plan['per_year'],
        'unmatched': plan['unmatched'],
        'tanpa_tanggal': plan['tanpa_tanggal'],
    }


def _tiket_backfill_apply(seksi_name, label, tanggal_label):
    """Fill the empty durasi column on the matched tikets.

    Only rows that are currently NULL are considered, so a value already recorded
    is never overwritten and re-running is a no-op.
    """
    seksi = _seksi_group(seksi_name)
    if seksi is None:
        return None

    kolom, tanggal_fields = TIKET_BACKFILL[seksi_name]
    plan = _build_tiket_backfill_plan(seksi, kolom, tanggal_fields)
    matches = plan['matches']

    if not matches:
        return {
            'success': True,
            'updated': 0,
            'unmatched': plan['unmatched'],
            'tanpa_tanggal': plan['tanpa_tanggal'],
            'message': f'Tidak ada Tiket yang perlu diisi Durasi Jatuh Tempo {label}-nya.',
        }

    with transaction.atomic():
        Tiket.objects.bulk_update(
            [Tiket(id=tiket_id, **{f'{kolom}_id': durasi_id}) for tiket_id, durasi_id in matches],
            [kolom],
            batch_size=500,
        )

    message = f'{len(matches)} Tiket berhasil diisi Durasi Jatuh Tempo {label}-nya.'
    if plan['unmatched']:
        message += (
            f' {plan["unmatched"]} Tiket dilewati karena tidak ada durasi yang '
            f'berlaku pada {tanggal_label}-nya.'
        )

    return {
        'success': True,
        'updated': len(matches),
        'unmatched': plan['unmatched'],
        'tanpa_tanggal': plan['tanpa_tanggal'],
        'message': message,
    }


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def durasi_jatuh_tempo_pmde_tiket_backfill_preview(request):
    """Summarise the tikets that the backfill step would fill in.

    Third step of Generate Otomatis: once the PMDE `DurasiJatuhTempo` rows exist,
    the tikets that were imported without one can be pointed at them. Applies
    exactly the same matching as `durasi_jatuh_tempo_pmde_tiket_backfill` — see
    `_build_tiket_backfill_plan` — but saves nothing.

    Returns JSON with `success`, `total_tiket` (rows that would be updated),
    `per_year` (breakdown by year of the base date), `unmatched` (tikets whose
    base date no range covers) and `tanpa_tanggal` (tikets that never reached
    PMDE, so they have no base date to match on).

    Side effects: None — read-only endpoint.
    """
    payload = _tiket_backfill_preview_payload(SEKSI_PMDE)
    if payload is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return JsonResponse(payload)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_POST
def durasi_jatuh_tempo_pmde_tiket_backfill(request):
    """Fill the empty `Tiket.id_durasi_jatuh_tempo_pmde` columns.

    Applies the matching described in `_build_tiket_backfill_plan`; the client
    shows `durasi_jatuh_tempo_pmde_tiket_backfill_preview` first so the user can
    confirm how many tikets will be touched.

    Side effects: updates `id_durasi_jatuh_tempo_pmde` on the matched tikets
    inside a single transaction. Only rows that are currently NULL are considered,
    so a value already recorded is never overwritten and re-running is a no-op.

    Returns JSON with `success`, `updated`, `unmatched`, `tanpa_tanggal` and a
    ready-to-display `message`.
    """
    payload = _tiket_backfill_apply(SEKSI_PMDE, 'PMDE', 'tanggal transfer/rematch')
    if payload is None:
        return _seksi_missing_response(SEKSI_PMDE)
    return JsonResponse(payload)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def durasi_jatuh_tempo_pide_tiket_backfill_preview(request):
    """Summarise the tikets that the PIDE backfill step would fill in.

    Same shape as the PMDE endpoint, matching on `tgl_kirim_pide` instead — see
    `TIKET_BACKFILL`. Read-only.
    """
    payload = _tiket_backfill_preview_payload(SEKSI_PIDE)
    if payload is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return JsonResponse(payload)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_POST
def durasi_jatuh_tempo_pide_tiket_backfill(request):
    """Fill the empty `Tiket.id_durasi_jatuh_tempo_pide` columns.

    Side effects: updates `id_durasi_jatuh_tempo_pide` on the matched tikets
    inside a single transaction. Only rows that are currently NULL are considered,
    so a value already recorded is never overwritten and re-running is a no-op.
    """
    payload = _tiket_backfill_apply(SEKSI_PIDE, 'PIDE', 'tanggal kirim ke PIDE')
    if payload is None:
        return _seksi_missing_response(SEKSI_PIDE)
    return JsonResponse(payload)
