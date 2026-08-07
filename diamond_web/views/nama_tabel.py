from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.dateformat import format as date_format
from django.utils.html import escape
from django.views.decorators.http import require_GET

from ..constants.tiket_status import STATUS_BADGE_CLASSES, STATUS_LABELS
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.tiket import Tiket
from ..forms.nama_tabel import NamaTabelForm
from ..utils import format_periode
from .mixins import AjaxFormMixin, AdminPIDERequiredMixin, SafeDeleteMixin

class NamaTabelListView(LoginRequiredMixin, AdminPIDERequiredMixin, TemplateView):
    """List view for `JenisDataILAP` (Nama Tabel) entries.

    Renders `nama_tabel/list.html`. This view is protected by
    `AdminPIDERequiredMixin` and `LoginRequiredMixin` so only authorized
    admin users can access the listing UI.
    """
    template_name = 'nama_tabel/list.html'

    def get(self, request, *args, **kwargs):
        """Render the list template.

        Presentational method — no extra context is required beyond the
        template's client-side DataTables initialization.
        """
        return super().get(request, *args, **kwargs)

class NamaTabelCreateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `JenisDataILAP` entries representing table names.

    Uses `AjaxFormMixin` to support modal forms; on success it returns a JSON
    redirect for AJAX clients or sets a Django success message for full-page
    flows. The `form_action` context key is set to the create URL.
    """
    model = JenisDataILAP
    form_class = NamaTabelForm
    template_name = 'nama_tabel/form.html'
    success_url = reverse_lazy('nama_tabel_list')
    success_message = 'Nama Tabel "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_create')
        return context

    def get(self, request, *args, **kwargs):
        """Return the create form rendered for AJAX or full-page requests."""
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

class NamaTabelUpdateView(LoginRequiredMixin, AdminPIDERequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `JenisDataILAP` (Nama Tabel).

    Provides the same AJAX/modal behaviour as the create view and sets
    `form_action` to the update URL for the instance being edited.
    """
    model = JenisDataILAP
    form_class = NamaTabelForm
    template_name = 'nama_tabel/form.html'
    success_url = reverse_lazy('nama_tabel_list')
    success_message = 'Nama Tabel "{object}" berhasil diperbarui.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_update', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Return the edit form for the requested instance."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

class NamaTabelDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminPIDERequiredMixin, DeleteView):
    """Delete/clear action for `JenisDataILAP` table-name fields.

    Instead of removing the database row, this view clears the
    `nama_tabel_I` and `nama_tabel_U` fields and persists the instance.
    Supports AJAX confirmation fragment (`GET?ajax=1`) and returns JSON
    responses for AJAX form submissions. On non-AJAX flows a success
    message is registered and a JSON redirect is returned for consistency.
    """
    model = JenisDataILAP
    template_name = 'nama_tabel/confirm_delete.html'
    success_url = reverse_lazy('nama_tabel_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('nama_tabel_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Return confirmation HTML when requested via AJAX, else render page."""
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Clear the two table-name fields and persist the instance.

        Returns JSON indicating success and a `redirect` URL for clients to
        follow when needed. Also sets a Django success message for non-AJAX
        workflows.
        """
        self.object = self.get_object()
        name = str(self.object)
        # Clear only the nama_tabel_I and nama_tabel_U fields instead of deleting the row
        self.object.nama_tabel_I = ''
        self.object.nama_tabel_U = ''
        self.object.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Nama Tabel "{name}" berhasil dikosongkan.'
            })
        messages.success(request, f'Nama Tabel "{name}" berhasil dikosongkan.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def nama_tabel_data(request):
    """Server-side DataTables endpoint for `JenisDataILAP` (Nama Tabel).

    GET parameters:
    - draw: DataTables draw counter.
    - start, length: paging offset and page size.
    - columns_search[]: column-specific search values (id_sub_jenis_data, nama_jenis_data, nama_sub_jenis_data, nama_tabel_I, nama_tabel_U).
    - order[0][column], order[0][dir]: ordering index and direction.

    Returns JSON with `draw`, `recordsTotal`, `recordsFiltered`, and `data` rows.
    Each row contains: `id_sub_jenis_data`, `nama_jenis_data`, `nama_sub_jenis_data`, `nama_tabel_I`, `nama_tabel_U`, and `actions` HTML.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = JenisDataILAP.objects.select_related(
        'id_ilap',
        'id_ilap__id_kategori',
        'id_jenis_tabel'
    ).all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Nama Jenis Data
            qs = qs.filter(nama_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Nama Sub Jenis Data
            qs = qs.filter(nama_sub_jenis_data__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Nama Tabel I
            qs = qs.filter(nama_tabel_I__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Nama Tabel U
            qs = qs.filter(nama_tabel_U__icontains=columns_search[4])

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id_sub_jenis_data', 'nama_jenis_data', 'nama_sub_jenis_data', 'nama_tabel_I', 'nama_tabel_U']
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
            'id_sub_jenis_data': obj.id_sub_jenis_data,
            'nama_jenis_data': obj.nama_jenis_data,
            'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            'nama_tabel_I': obj.nama_tabel_I,
            'nama_tabel_U': obj.nama_tabel_U,
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('nama_tabel_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('nama_tabel_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


# ---------------------------------------------------------------------------
# Nama Tabel detail: one bank data table, and every tiket landing in it
# ---------------------------------------------------------------------------
#
# A nama tabel is not a row of its own — it is a field repeated across the sub
# jenis data that feed the same bank data table, and one table routinely
# collects dozens of them. The pages above edit that field per sub jenis data;
# the page below reads it the other way round, from the table towards the
# tikets, which is what the navbar search sends a reader to when they type a
# table name.


def _nama_tabel_jenis_data(nama_tabel):
    """The sub jenis data feeding `nama_tabel`, or 404 when none do.

    Args:
        nama_tabel (str): The nama tabel I to look up, matched case-insensitively
            because it arrives from a URL a user may have typed or copied.

    Returns:
        QuerySet: The matching JenisDataILAP rows, ILAP preloaded.

    Raises:
        Http404: When no sub jenis data carries that table name.
    """
    rows = JenisDataILAP.objects.filter(
        nama_tabel_I__iexact=nama_tabel
    ).select_related('id_ilap').order_by('id_sub_jenis_data')
    if not rows.exists():
        raise Http404(f'Nama Tabel "{nama_tabel}" tidak ditemukan.')
    return rows


def _distinct_by_nama(rows):
    """Collapse `rows` to one entry per distinct nama sub jenis data.

    The same name is routinely recorded against many sub jenis data of a table —
    one per ILAP, per region, per year of the arrangement — so listing every row
    would repeat one name dozens of times. Each entry keeps the first row it saw
    so the chip still links somewhere, and counts how many it stands for, which
    is what stops the collapsed list from reading as the whole story.

    Args:
        rows (iterable): JenisDataILAP rows sharing a nama tabel.

    Returns:
        list: Dicts of ``{'nama', 'jenis_data', 'count'}``, sorted by name.
    """
    entries = {}
    for row in rows:
        nama = row.nama_sub_jenis_data or '---'
        entry = entries.get(nama)
        if entry is None:
            entries[nama] = {'nama': nama, 'jenis_data': row, 'count': 1}
        else:
            entry['count'] += 1
    return sorted(entries.values(), key=lambda entry: entry['nama'].lower())


class NamaTabelDetailView(LoginRequiredMixin, TemplateView):
    """One bank data table, with the sub jenis data and tikets that fill it.

    Open to every logged in user, like the ILAP and jenis data profil pages it
    sits alongside: the catalogue is not secret, and opening a tiket from the
    list still goes through `TiketDetailView`, which enforces the PIC rules.

    Template: nama_tabel/detail.html
    """
    template_name = 'nama_tabel/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nama_tabel = self.kwargs['nama_tabel']
        rows = _nama_tabel_jenis_data(nama_tabel)

        context['nama_tabel'] = rows[0].nama_tabel_I  # as recorded, not as typed
        context['jenis_data_list'] = _distinct_by_nama(rows)
        context['jenis_data_total'] = len(context['jenis_data_list'])
        # Distinct ILAPs, in the order the sub jenis data list introduces them.
        ilaps = {}
        for row in rows:
            if row.id_ilap and row.id_ilap.id_ilap not in ilaps:
                ilaps[row.id_ilap.id_ilap] = row.id_ilap
        context['ilap_list'] = list(ilaps.values())
        context['tiket_total'] = Tiket.objects.filter(
            id_periode_data__id_sub_jenis_data_ilap__in=rows
        ).count()
        return context


@login_required
@require_GET
def nama_tabel_tiket_data(request, nama_tabel):
    """Server-side DataTables endpoint for a nama tabel's tiket list.

    Every tiket whose sub jenis data lands in this table, across all the sub
    jenis data that share it — which is the whole point of the page, since a
    single table is routinely fed by dozens of them.

    Args:
        request (HttpRequest): The current request, carrying the DataTables
            ``draw``, ``start``, ``length``, ``search[value]`` and ``order``
            parameters.
        nama_tabel (str): The nama tabel I the tikets land in.

    Returns:
        JsonResponse: A JSON object with ``draw``, ``recordsTotal``,
        ``recordsFiltered`` and ``data`` (one dict per tiket row).
    """
    rows = _nama_tabel_jenis_data(nama_tabel)

    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))
    search_value = request.GET.get('search[value]', '').strip()

    base_qs = Tiket.objects.filter(
        id_periode_data__id_sub_jenis_data_ilap__in=rows
    ).select_related(
        'id_periode_data__id_periode_pengiriman',
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
    )

    records_total = base_qs.count()

    if search_value:
        # status_tiket stores an integer, so the term is matched against the
        # labels first and the resulting codes are what the filter looks for.
        status_codes = [
            code for code, label in STATUS_LABELS.items()
            if search_value.lower() in label.lower()
        ]
        search_filter = (
            Q(nomor_tiket__icontains=search_value)
            | Q(id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=search_value)
            | Q(id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=search_value)
        )
        if search_value.isdigit():
            search_filter |= Q(tahun=int(search_value)) | Q(periode=int(search_value))
        if status_codes:
            search_filter |= Q(status_tiket__in=status_codes)
        base_qs = base_qs.filter(search_filter)

    records_filtered = base_qs.count()

    order_columns = {
        0: 'nomor_tiket',
        1: 'id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap',
        2: 'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
        3: 'periode',
        4: 'tahun',
        5: 'status_tiket',
        6: 'tgl_terima_dip',
    }
    order_col_index = request.GET.get('order[0][column]')
    order_col = None
    if order_col_index is not None:
        try:
            order_col = order_columns.get(int(order_col_index))
        except (TypeError, ValueError):
            order_col = None
    if order_col:
        if request.GET.get('order[0][dir]', 'asc') == 'desc':
            order_col = f'-{order_col}'
        base_qs = base_qs.order_by(order_col)
    else:
        base_qs = base_qs.order_by('nomor_tiket')

    data = []
    for tiket in base_qs[start:start + length]:
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        ilap = sub_jenis_data.id_ilap
        periode_penerimaan = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
        status_label = STATUS_LABELS.get(tiket.status_tiket, '---')
        badge_class = STATUS_BADGE_CLASSES.get(tiket.status_tiket, 'bg-secondary')
        jenis_data_url = reverse(
            'jenis_data_ilap_profil', args=[sub_jenis_data.id_sub_jenis_data]
        )
        detail_url = reverse('tiket_detail', args=[tiket.pk])
        data.append({
            'nomor_tiket': escape(tiket.nomor_tiket),
            'nama_ilap': (
                f'<span class="text-muted small">{escape(ilap.id_ilap)}</span><br>'
                f'{escape(ilap.nama_ilap)}'
            ) if ilap else '---',
            'sub_jenis_data': (
                f'<a href="{jenis_data_url}" class="text-primary text-decoration-none">'
                f'<span class="text-muted small">{escape(sub_jenis_data.id_sub_jenis_data)}</span>'
                f'<br>{escape(sub_jenis_data.nama_sub_jenis_data)}</a>'
            ),
            'periode': escape(format_periode(
                periode_penerimaan, tiket.periode, tiket.tahun, include_year=False
            )),
            'tahun': tiket.tahun,
            'status': f'<span class="badge {badge_class}">{escape(status_label)}</span>',
            'tgl_terima_dip': (
                date_format(tiket.tgl_terima_dip, 'd M Y')
                if tiket.tgl_terima_dip else '---'
            ),
            'actions': (
                f'<a href="{detail_url}" class="btn btn-sm btn-primary" title="Detail Tiket">'
                f'<i class="feather-eye me-1"></i>Detail</a>'
            ),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
