from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET
from django.db.models import Count, Q
from django.db.models.functions import ExtractYear
from io import BytesIO
from openpyxl import Workbook

from ..utils import format_periode

from ..models.backup_data import BackupData
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..models.media_backup import MediaBackup
from ..forms.backup_data import BackupDataForm
from ..constants.tiket_action_types import BackupActionType
from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE, STATUS_DIREKAM
from .mixins import AjaxFormMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, SafeDeleteMixin


def create_tiket_action(tiket, user, catatan, action_type):
    """Create an audit trail TiketAction for a tiket.

    Usage: called whenever a backup-related change occurs to record who
    performed the action and when.

    Args:
        tiket: Tiket model instance (related tiket for the action).
        user: User model instance who performed the action.
        catatan: Human-readable note describing the action.
        action_type: Action type constant from `tiket_action_types`.

    Side effects:
        Persists a `TiketAction` row with `timestamp=datetime.now()`.
    """
    if not tiket:
        return
    TiketAction.objects.create(
        id_tiket=tiket,
        id_user=user,
        timestamp=datetime.now(),
        action=action_type,
        catatan=catatan
    )


def _get_backup_data_base_queryset(request):
    """Return base queryset with role-based access restriction.

    Non-admin/non-superuser users see only BackupData records where they
    are an active P3DE PIC for the related tiket.

    Args:
        request: The HTTP request instance used to determine user permissions.

    Returns:
        QuerySet of BackupData with select_related optimizations, filtered
        by user's P3DE PIC role if the user is not an admin or superuser.
    """
    qs = BackupData.objects.select_related(
        'id_user',
        'id_media_backup',
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori',
        'id_tiket__id_periode_data__id_periode_pengiriman',
    )

    if not request.user.is_superuser and not request.user.groups.filter(name='admin').exists():
        qs = qs.filter(
            id_tiket__tiketpic__id_user=request.user,
            id_tiket__tiketpic__role=TiketPIC.Role.P3DE,
            id_tiket__tiketpic__active=True,
        ).distinct()
    return qs


def _apply_backup_data_filters(qs, params):
    """Apply filter parameters to a BackupData queryset.

    Iterates over known filter keys (tahun, id_ilap, id_jenis_data, etc.)
    and narrows the queryset accordingly. Unknown or empty parameters are
    silently ignored.

    Args:
        qs: Base QuerySet of BackupData to filter.
        params: dict-like object (e.g., request.GET) containing potential
            filter keys with string values.

    Returns:
        QuerySet of BackupData filtered by the provided parameters, with
        distinct() applied.
    """
    tahun = (params.get('tahun') or '').strip()
    if tahun:
        try:
            qs = qs.filter(id_tiket__tgl_terima_dip__year=int(tahun))
        except (ValueError, TypeError):
            pass

    id_ilap = (params.get('id_ilap') or '').strip()
    if id_ilap:
        qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=id_ilap)

    id_jenis_data = (params.get('id_jenis_data') or '').strip()
    if id_jenis_data:
        qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap_id=id_jenis_data)

    id_sub_jenis_data_ilap = (params.get('id_sub_jenis_data_ilap') or '').strip()
    if id_sub_jenis_data_ilap:
        qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap_id=id_sub_jenis_data_ilap)

    id_kategori_ilap = (params.get('id_kategori_ilap') or '').strip()
    if id_kategori_ilap:
        qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_id=id_kategori_ilap)

    id_periode_data = (params.get('id_periode_data') or '').strip()
    if id_periode_data:
        qs = qs.filter(id_tiket__id_periode_data_id=id_periode_data)

    id_periode_pengiriman = (params.get('id_periode_pengiriman') or '').strip()
    if id_periode_pengiriman:
        qs = qs.filter(id_tiket__id_periode_data__id_periode_pengiriman_id=id_periode_pengiriman)

    id_media_backup = (params.get('id_media_backup') or '').strip()
    if id_media_backup:
        qs = qs.filter(id_media_backup_id=id_media_backup)

    id_pic_p3de = (params.get('id_pic_p3de') or '').strip()
    if id_pic_p3de:
        qs = qs.filter(
            id_tiket__tiketpic__id_user_id=id_pic_p3de,
            id_tiket__tiketpic__role=TiketPIC.Role.P3DE,
            id_tiket__tiketpic__active=True,
        )

    return qs.distinct()


def _format_backup_periode_data(tiket_obj):
    """Return a human-readable formatted periode data label.

    Builds a label from the tiket's related periode_pengiriman descriptor,
    periode number, and year. Falls back to a simple "periode/tahun" string
    when the related objects cannot be resolved.

    Args:
        tiket_obj: A Tiket model instance (or any object with ``.periode``,
            ``.tahun``, and ``.id_periode_data`` relation chain).

    Returns:
        str: Formatted periode label, e.g. "Januari 2026", or "-" if the
        input is ``None``.
    """
    try:
        periode_desc = tiket_obj.id_periode_data.id_periode_pengiriman.periode_penerimaan
        return format_periode(periode_desc, tiket_obj.periode, tiket_obj.tahun)
    except Exception:
        return f"{tiket_obj.periode}/{tiket_obj.tahun}" if tiket_obj else '-'


def _build_backup_data_row(obj, request=None, include_actions=False):
    """Serialize a BackupData instance into a dict for DataTables or export.

    Resolves related models (kategori, ilap, sub-jenis, PIC names) and
    optionally builds action button HTML if the user has edit permission.

    Args:
        obj: BackupData model instance to serialize.
        request: Optional HttpRequest; required when ``include_actions`` is
            ``True`` to check user permissions.
        include_actions: bool. If ``True``, generates edit/delete button HTML
            for users with active PIC access on tikets with status below
            ``STATUS_DIKIRIM_KE_PIDE``.

    Returns:
        dict: A dictionary with keys suitable for DataTables or export
        (``kategori_ilap``, ``nama_ilap``, ``jenis_data``, ``subjenis_data``,
        ``periode_data``, ``nomor_tiket``, ``media_backup``,
        ``lokasi_penyimpanan``, ``pic_p3de``, ``jumlah_data``, ``actions``).
    """
    tiket = obj.id_tiket
    subjenis = tiket.id_periode_data.id_sub_jenis_data_ilap if tiket and tiket.id_periode_data else None
    ilap = subjenis.id_ilap if subjenis else None
    kategori = ilap.id_kategori if ilap else None

    pic_names = []
    if tiket:
        for p in TiketPIC.objects.select_related('id_user').filter(
            id_tiket=tiket,
            role=TiketPIC.Role.P3DE,
            active=True,
        ):
            if not p.id_user:
                continue
            full_name = f"{(p.id_user.first_name or '').strip()} {(p.id_user.last_name or '').strip()}".strip()
            pic_names.append(full_name or p.id_user.username)
    pic_label = ', '.join(sorted(set([n for n in pic_names if n]))) if pic_names else '-'

    actions = ''
    if include_actions and request and tiket:
        is_active_pic = TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=request.user,
            active=True,
        ).exists()
        if tiket.status_tiket is not None and tiket.status_tiket < STATUS_DIKIRIM_KE_PIDE and is_active_pic:
            actions = (
                f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('backup_data_update', args=[obj.pk])}' title='Edit'><i class='feather-edit-2'></i></button>"
                f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('backup_data_delete', args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
            )

    return {
        'id': obj.pk,
        'kategori_ilap': kategori.nama_kategori if kategori else '-',
        'nama_ilap': ilap.nama_ilap if ilap else '-',
        'jenis_data': subjenis.nama_jenis_data if subjenis else '-',
        'subjenis_data': subjenis.nama_sub_jenis_data if subjenis else '-',
        'periode_data': _format_backup_periode_data(tiket),
        'nomor_tiket': tiket.nomor_tiket if tiket else '-',
        'media_backup': obj.id_media_backup.deskripsi if obj.id_media_backup else '-',
        'lokasi_penyimpanan': obj.lokasi_backup or '-',
        'pic_p3de': pic_label,
        'jumlah_data': tiket.baris_diterima if tiket and tiket.baris_diterima is not None else '-',
        'actions': actions,
    }


def _get_backup_media_counts(qs):
    """Return media backup counts from a filtered BackupData queryset.

    Aggregates the number of BackupData records per MediaBackup and returns
    a complete list of all MediaBackup objects with their counts (zero for
    media with no matching backups).

    Args:
        qs: QuerySet of BackupData to aggregate counts from.

    Returns:
        list[dict]: Each entry contains ``{'id': int, 'deskripsi': str,
        'count': int}`` for every MediaBackup, ordered by description.
    """
    agg = (
        qs.values('id_media_backup_id', 'id_media_backup__deskripsi')
        .annotate(count=Count('id'))
        .order_by('id_media_backup__deskripsi')
    )
    counts = {
        row['id_media_backup_id']: row['count']
        for row in agg if row['id_media_backup_id']
    }

    result = []
    for media in MediaBackup.objects.all().order_by('deskripsi'):
        result.append({
            'id': media.id,
            'deskripsi': media.deskripsi,
            'count': counts.get(media.id, 0),
        })
    return result


def _pdf_escape(value):
    """Escape special characters for PDF string content.

    Escapes backslashes and parentheses so the value can be safely embedded
    in PDF text operators. Also ensures the result is Latin-1 encodable by
    replacing unsupported characters.

    Args:
        value: Any value to escape (will be converted to string).

    Returns:
        str: Latin-1-safe string with escaped PDF special characters.
    """
    text = str(value or '')
    text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _build_simple_table_pdf(title, headers, rows):
    """Generate a lightweight PDF as bytes without external PDF libraries.

    Builds a minimal PDF document manually by constructing PDF objects,
    streams, and the cross-reference table. Each row is prefixed with its
    number. Pagination is handled automatically.

    Args:
        title: str. The document title displayed at the top of each page.
        headers: list of str. Column header labels.
        rows: list of list of str. Table data rows (each inner list is a row
            of cell values).

    Returns:
        bytes: The raw PDF content, ready to be served as an HTTP response.
    """
    page_width = 595
    page_height = 842
    margin = 36
    line_height = 13
    top = page_height - margin
    bottom = margin

    lines = [' | '.join(headers)]
    for idx, row in enumerate(rows, start=1):
        lines.append(f"{idx}. " + ' | '.join(str(c) for c in row))

    max_lines_per_page = max(1, int((top - bottom - 2 * line_height) // line_height))
    pages = []
    for i in range(0, len(lines), max_lines_per_page):
        pages.append(lines[i:i + max_lines_per_page])
    if not pages:
        pages = [[]]

    objects = []

    def _add_obj(content):
        objects.append(content)
        return len(objects)

    catalog_id = _add_obj('')
    pages_id = _add_obj('')
    font_id = _add_obj('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    page_ids = []
    for page_no, page_lines in enumerate(pages, start=1):
        cmds = []
        cmds.append(f"BT /F1 11 Tf {margin} {top} Td ({_pdf_escape(title)} - Halaman {page_no}) Tj ET")
        y = top - (line_height * 2)
        for line in page_lines:
            cmds.append(f"BT /F1 9 Tf {margin} {y} Td ({_pdf_escape(line)}) Tj ET")
            y -= line_height
        stream_data = '\n'.join(cmds).encode('latin-1', errors='replace')
        content_id = _add_obj(
            f"<< /Length {len(stream_data)} >>\nstream\n".encode('latin-1') + stream_data + b"\nendstream"
        )
        page_id = _add_obj(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
    kids = ' '.join([f"{pid} 0 R" for pid in page_ids])
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>"

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(pdf.tell())
        pdf.write(f"{i} 0 obj\n".encode('latin-1'))
        if isinstance(obj, bytes):
            pdf.write(obj)
        else:
            pdf.write(str(obj).encode('latin-1', errors='replace'))
        pdf.write(b"\nendobj\n")

    xref_pos = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode('latin-1'))
    pdf.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.write(f"{off:010d} 00000 n \n".encode('latin-1'))
    pdf.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode('latin-1')
    )
    return pdf.getvalue()

class BackupDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for BackupData.

    Renders the `backup_data/list.html` template. Access restricted to
    authenticated users in `user_p3de` (or admin) via `UserP3DERequiredMixin`.
    
    Context data includes:
    - tahun_list: Distinct tahun values from accessible tikets
    - media_backup_list: MediaBackup objects with backup counts
    - filter_options: ILAP, Jenis Data, Subjenis Data, Kategori ILAP options
    """
    template_name = 'backup_data/list.html'

    def get_accessible_tikets(self):
        """Get tikets accessible by current user (user's P3DE tikets or all if admin)."""
        if self.request.user.is_superuser or self.request.user.groups.filter(name='admin').exists():
            return Tiket.objects.all()
        else:
            # Only tikets where user is active P3DE PIC
            return Tiket.objects.filter(
                tiketpic__id_user=self.request.user,
                tiketpic__role=TiketPIC.Role.P3DE,
                tiketpic__active=True
            ).distinct()

    def get_context_data(self, **kwargs):
        """Provide filter data for the template."""
        context = super().get_context_data(**kwargs)
        accessible_tikets = self.get_accessible_tikets()

        tahun_values = list(
            accessible_tikets
            .exclude(tgl_terima_dip__isnull=True)
            .annotate(tahun_terima=ExtractYear('tgl_terima_dip'))
            .values_list('tahun_terima', flat=True)
            .distinct()
            .order_by('-tahun_terima')
        )
        default_tahun = 2026
        if default_tahun not in tahun_values:
            tahun_values.insert(0, default_tahun)

        ilap_options = []
        ilap_ids = set(
            accessible_tikets.values_list('id_periode_data__id_sub_jenis_data_ilap__id_ilap_id', flat=True)
        )
        ilap_ids = {x for x in ilap_ids if x}
        if ilap_ids:
            from ..models.ilap import ILAP
            ilap_options = list(
                ILAP.objects.filter(id__in=ilap_ids)
                .values('id', 'nama_ilap')
                .order_by('nama_ilap')
            )
            for ilap in ilap_options:
                ilap['deskripsi'] = ilap.pop('nama_ilap')

        base_qs = _get_backup_data_base_queryset(self.request)
        media_backup_list = _get_backup_media_counts(base_qs.filter(id_tiket__tgl_terima_dip__year=default_tahun))

        context.update({
            'default_tahun': default_tahun,
            'tahun_list': tahun_values,
            'media_backup_list': media_backup_list,
            'filter_options': {
                'ilap': ilap_options,
                'jenis_data': [],
                'subjenis_data': [],
                'kategori_ilap': [],
                'periode_data': [],
                'periode_pengiriman': [],
                'media_backup': [],
                'pic_p3de': [],
            }
        })
        return context

class BackupDataCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `BackupData`.

    Usage: Presents a modal/form to record a backup entry associated with a
    `Tiket`. Access restricted to users in `user_p3de` (or admin) via
    `UserP3DERequiredMixin`.

    Side effects on successful save:
    - sets `BackupData.id_user` to `request.user`
    - marks the related `Tiket.backup = True`
    - creates a `TiketAction` audit row of type `BackupActionType.DIREKAM`

    The view supports both normal (HTML) and AJAX (JSON) flows via
    `AjaxFormMixin`.
    """
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_url = reverse_lazy('backup_data_list')
    success_message = 'Data Backup berhasil direkam.'


    def get_form_kwargs(self):
        """Pass the current request `user` into the form kwargs.

        Many `BackupDataForm` implementations expect a `user` kwarg to
        restrict selectable tiket choices or to default fields.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        """Render the create form.

        For AJAX requests the HTML fragment is returned by
        `AjaxFormMixin.render_form_response`.
        """
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def get_context_data(self, **kwargs):
        """Provide template context for the create form.

        Adds `form_action` (URL for form POST) and `page_title` used by the
        shared modal/form template.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_create')
        context['page_title'] = 'Rekam Backup Data'
        return context

    def form_valid(self, form):
        """Handle a successful BackupData form submission.

        Side effects:
        - Associates the backup record with the current user.
        - Marks the related `Tiket.backup=True` and persists it.
        - Creates a `TiketAction` audit record of type `BackupActionType.DIREKAM`.

        Returns the parent `form_valid` response (redirect or JSON for AJAX).
        """
        form.instance.id_user = self.request.user
        response = super().form_valid(form)
        tiket = self.object.id_tiket
        # Set tiket backup flag to True
        if not tiket.backup:
            tiket.backup = True
            tiket.save(update_fields=["backup"])
        # Add TiketAction for backup
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=datetime.now(),
            action=BackupActionType.DIREKAM,
            catatan="backup data direkam"
        )
        return response


class BackupDataFromTiketCreateView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, AjaxFormMixin, CreateView):
    """Create a `BackupData` row for a specific `Tiket`.

    Usage: When the user is adding backup data from a tiket detail view
    (URL contains `tiket_pk`). Access is restricted by
    `ActiveTiketP3DERequiredForEditMixin` which ensures the request user
    is an active P3DE PIC for the targeted tiket.

    Side effects on success:
    - sets `BackupData.id_user` to `request.user`
    - sets `BackupData.id_tiket` from `tiket_pk`
    - marks the tiket `backup=True`
    - creates a `TiketAction` audit row (type `BackupActionType.DIREKAM`)
    """
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_message = 'Data Backup berhasil direkam.'

    def get_success_url(self):
        """Return the tiket detail URL for the tiket referenced by `tiket_pk`.

        Used after successful creation to redirect back to the tiket.
        """
        return reverse('tiket_detail', kwargs={'pk': self.kwargs['tiket_pk']})
    
    # Authentication/authorization handled by ActiveTiketP3DERequiredForEditMixin

    def get_form_kwargs(self):
        """Pass `tiket_pk` into the form kwargs so the form can validate
        and bind the related `Tiket` instance when necessary.
        """
        kwargs = super().get_form_kwargs()
        kwargs['tiket_pk'] = self.kwargs.get('tiket_pk')
        return kwargs

    def get_context_data(self, **kwargs):
        """Provide template context including resolved tiket and form action.

        Adds `form_action`, `page_title`, and the `tiket` instance (resolved
        using `tiket_pk`) so the form template can display tiket info.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': self.kwargs['tiket_pk']})
        context['page_title'] = f'Rekam Backup Data'
        context['tiket'] = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        return context

    def form_valid(self, form):
        """Finalize creation: bind user and tiket, persist, and log action.

        Steps performed:
        1. Set `id_user` to `request.user`.
        2. Resolve `Tiket` from `tiket_pk` and assign it to `id_tiket`.
        3. Save the `BackupData` instance.
        4. Mark the tiket `backup=True` and persist that change.
        5. Create a `TiketAction` row of type `BackupActionType.DIREKAM`.

        Returns an AJAX-friendly response via `AjaxFormMixin.form_valid`.
        """
        form.instance.id_user = self.request.user
        # Set the tiket from the tiket_pk
        tiket = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        form.instance.id_tiket = tiket
        self.object = form.save()
        
        # Set tiket backup flag to True
        tiket.backup = True
        tiket.save(update_fields=["backup"])
        
        # Record tiket_action for audit trail
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=datetime.now(),
            action=BackupActionType.DIREKAM,
            catatan="backup data direkam"
        )
        
        return AjaxFormMixin.form_valid(self, form)

class BackupDataUpdateView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, AjaxFormMixin, UpdateView):
    """Update view for `BackupData` entries.

    Usage: Edit an existing backup record. Access restricted to active P3DE
    PICs for the related tiket or admins via
    `ActiveTiketP3DERequiredForEditMixin`.

    On successful update an audit `TiketAction` is recorded.
    """
    model = BackupData
    form_class = BackupDataForm
    template_name = 'backup_data/form.html'
    success_url = reverse_lazy('backup_data_list')
    success_message = 'Data Backup berhasil diperbarui.'
    
    # Authentication/authorization handled by ActiveTiketP3DERequiredForEditMixin

    def get_context_data(self, **kwargs):
        """Add `form_action` and `page_title` for the edit template context."""
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_update', args=[self.object.pk])
        context['page_title'] = 'Edit Data Backup'
        return context

    def form_valid(self, form):
        """Persist the update and append a `TiketAction` audit entry."""
        response = super().form_valid(form)
        create_tiket_action(self.object.id_tiket, self.request.user, "backup data diperbarui", BackupActionType.DIREKAM)
        return response

    def get(self, request, *args, **kwargs):
        """Render the edit form for the requested `BackupData` instance."""
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)

    def post(self, request, *args, **kwargs):
        """Handle POST submissions, ensuring disabled `id_tiket` inputs are
        preserved for validation by re-inserting them into `request.POST`.
        """
        self.object = self.get_object()
        # If id_tiket is disabled, add its value back to POST data before form validation
        if self.object and 'id_tiket' not in request.POST:
            data = request.POST.copy()
            data['id_tiket'] = str(self.object.id_tiket_id)
            request.POST = data
        return super().post(request, *args, **kwargs)


class BackupDataDeleteView(SafeDeleteMixin, LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, DeleteView):
    """Delete (remove) a `BackupData` record and log the action.

    Notes:
    - Deleting a `BackupData` will remove the row. If the related tiket has no
      remaining backups, the tiket's `backup` flag is cleared.
    - A `TiketAction` entry with `BackupActionType.DIHAPUS` is created to
      record who deleted the backup and when.
    - For AJAX `GET` requests (confirmation), the HTML fragment is returned
      as JSON with the key `html`. For AJAX `DELETE`, a JSON success message
      is returned. Non-AJAX flows set a Django message and return JSON with a
      `redirect` URL (so the client can navigate and display toasts uniformly).
    """
    model = BackupData
    template_name = 'backup_data/confirm_delete.html'
    success_url = reverse_lazy('backup_data_list')
    
    # Authentication/authorization handled by ActiveTiketP3DERequiredForEditMixin

    def get_context_data(self, **kwargs):
        """Provide `form_action` used by the confirmation template."""
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('backup_data_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        """Return confirmation UI; for AJAX clients return rendered fragment.

        The template used is `backup_data/confirm_delete.html` and context is
        populated via `get_context_data`.
        """
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Perform the deletion and related tiket cleanup and logging.

        Returns JSON for both AJAX and non-AJAX flows, and sets a Django
        `messages.success` on non-AJAX for UI to display a toast.
        """
        self.object = self.get_object()
        tiket = self.object.id_tiket
        user = request.user
        # Delete the backup data
        self.object.delete()
        # Set tiket backup flag to False if no other backups exist
        if not tiket.backups.exists():
            tiket.backup = False
            tiket.status_tiket = STATUS_DIREKAM
            tiket.save(update_fields=["backup", "status_tiket"])
        # Audit trail: add TiketAction
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=user,
            timestamp=datetime.now(),
            action=BackupActionType.DIHAPUS,
            catatan="backup data dihapus"
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Data Backup berhasil dihapus.'
            })
        messages.success(request, 'Data Backup berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        """Proxy POST to the `delete` handler to support form POST confirm."""
        return self.delete(request, *args, **kwargs)

@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_data(request):
    """Server-side DataTables endpoint for BackupData.

    GET parameters:
    - draw: DataTables draw counter.
    - start, length: paging offset and page size.
    - tahun: filter by tahun
    - id_ilap: filter by ILAP
    - id_jenis_data: filter by Jenis Data
    - id_sub_jenis_data_ilap: filter by Subjenis Data
    - id_kategori_ilap: filter by Kategori ILAP
    - id_media_backup: filter by Media Backup
    - columns_search[]: column-specific search values (nomor_tiket, lokasi_backup).
    - order[0][column], order[0][dir]: ordering index and direction.

    Behavior:
    - Uses `select_related('id_user', 'id_tiket')` for query efficiency.
    - Non-admin/superuser users only see backups for tikets where they are an
        active P3DE PIC (`TiketPIC` with `role=TiketPIC.Role.P3DE`).
    - The `actions` HTML is enabled only when the related tiket exists,
        `tiket.status < STATUS_DIKIRIM_KE_PIDE`, and the requester is an
        active PIC for that tiket.

    Returns:
    JSON object with `draw`, `recordsTotal`, `recordsFiltered`, and `data`.
    Each row in `data` contains: `id`, `no_tiket`, `lokasi_backup`, `user`, and `actions`.

    Side effects: None — read-only endpoint.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = _get_backup_data_base_queryset(request)
    records_total = qs.count()

    qs = _apply_backup_data_filters(qs, request.GET)

    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if len(columns_search) > 0 and columns_search[0]:
            qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:
            qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:
            qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            qs = qs.filter(id_tiket__id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:
            text = columns_search[4].strip()
            q_obj = Q(id_tiket__id_periode_data__id_periode_pengiriman__periode_penerimaan__icontains=text)
            if text.isdigit():
                q_obj |= Q(id_tiket__periode=int(text))
                q_obj |= Q(id_tiket__tgl_terima_dip__year=int(text))
            qs = qs.filter(q_obj)
        if len(columns_search) > 5 and columns_search[5]:
            qs = qs.filter(id_tiket__nomor_tiket__icontains=columns_search[5])
        if len(columns_search) > 6 and columns_search[6]:
            qs = qs.filter(id_media_backup__deskripsi__icontains=columns_search[6])
        if len(columns_search) > 7 and columns_search[7]:
            qs = qs.filter(lokasi_backup__icontains=columns_search[7])
        if len(columns_search) > 8 and columns_search[8]:
            qs = qs.filter(
                Q(id_tiket__tiketpic__id_user__first_name__icontains=columns_search[8]) |
                Q(id_tiket__tiketpic__id_user__last_name__icontains=columns_search[8]) |
                Q(id_tiket__tiketpic__id_user__username__icontains=columns_search[8])
            )
        if len(columns_search) > 9 and columns_search[9]:
            text = columns_search[9].strip()
            if text.isdigit():
                qs = qs.filter(id_tiket__baris_diterima=int(text))

    records_filtered = qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = [
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori',
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap',
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data',
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
        'id_tiket__tahun',
        'id_tiket__nomor_tiket',
        'id_media_backup__deskripsi',
        'lokasi_backup',
        'id_tiket__baris_diterima',
        'id',
    ]

    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if 0 <= idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-id')
    else:
        qs = qs.order_by('-id')

    qs_page = qs[start:start + length]
    data = [_build_backup_data_row(obj, request=request, include_actions=True) for obj in qs_page]

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_filter_options(request):
    """Return dynamic filter options based on selected filters."""
    backup_qs = _get_backup_data_base_queryset(request)

    tiket_qs = Tiket.objects.select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori',
        'id_periode_data__id_periode_pengiriman',
    )
    if not request.user.is_superuser and not request.user.groups.filter(name='admin').exists():
        tiket_qs = tiket_qs.filter(
            tiketpic__id_user=request.user,
            tiketpic__role=TiketPIC.Role.P3DE,
            tiketpic__active=True,
        ).distinct()

    # Media summary is driven by selected year only.
    tahun_param = {'tahun': (request.GET.get('tahun') or '').strip()}
    media_counts = _get_backup_media_counts(_apply_backup_data_filters(backup_qs, tahun_param))

    id_ilap = (request.GET.get('id_ilap') or '').strip()
    if not id_ilap:
        return JsonResponse({
            'filter_options': {
                'jenis_data': [],
                'subjenis_data': [],
                'kategori_ilap': [],
                'periode_data': [],
                'periode_pengiriman': [],
                'media_backup': [],
                'pic_p3de': [],
            },
            'media_backup_list': media_counts,
        })

    # Build filtered tiket queryset based on current filter selection.
    tiket_qs = tiket_qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=id_ilap)

    tahun = (request.GET.get('tahun') or '').strip()
    if tahun:
        try:
            tiket_qs = tiket_qs.filter(tgl_terima_dip__year=int(tahun))
        except (ValueError, TypeError):
            pass

    id_jenis_data = (request.GET.get('id_jenis_data') or '').strip()
    if id_jenis_data:
        tiket_qs = tiket_qs.filter(id_periode_data__id_sub_jenis_data_ilap_id=id_jenis_data)

    id_sub_jenis_data_ilap = (request.GET.get('id_sub_jenis_data_ilap') or '').strip()
    if id_sub_jenis_data_ilap:
        tiket_qs = tiket_qs.filter(id_periode_data__id_sub_jenis_data_ilap_id=id_sub_jenis_data_ilap)

    id_kategori_ilap = (request.GET.get('id_kategori_ilap') or '').strip()
    if id_kategori_ilap:
        tiket_qs = tiket_qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_id=id_kategori_ilap)

    id_periode_data = (request.GET.get('id_periode_data') or '').strip()
    if id_periode_data:
        tiket_qs = tiket_qs.filter(id_periode_data_id=id_periode_data)

    id_periode_pengiriman = (request.GET.get('id_periode_pengiriman') or '').strip()
    if id_periode_pengiriman:
        tiket_qs = tiket_qs.filter(id_periode_data__id_periode_pengiriman_id=id_periode_pengiriman)

    id_pic_p3de = (request.GET.get('id_pic_p3de') or '').strip()
    if id_pic_p3de:
        tiket_qs = tiket_qs.filter(
            tiketpic__id_user_id=id_pic_p3de,
            tiketpic__role=TiketPIC.Role.P3DE,
            tiketpic__active=True,
        )

    tiket_qs = tiket_qs.distinct()

    # Jenis/Subjenis from JenisDataILAP
    jenis_rows = list(
        tiket_qs.values(
            'id_periode_data__id_sub_jenis_data_ilap_id',
            'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
            'id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data',
        )
        .distinct()
        .order_by('id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    )

    # Deduplicate by the sub-jenis id while preserving order
    seen_ids = set()
    jenis_data = []
    subjenis_data = []
    for r in jenis_rows:
        sid = r.get('id_periode_data__id_sub_jenis_data_ilap_id')
        if not sid or sid in seen_ids:
            continue
        seen_ids.add(sid)
        jenis_name = r.get('id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data') or r.get('id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data') or '-'
        subjenis_name = r.get('id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data') or '-'
        jenis_data.append({'id': sid, 'name': jenis_name})
        subjenis_data.append({'id': sid, 'name': subjenis_name})

    kategori_rows = list(
        tiket_qs.values(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori',
        )
        .distinct()
        .order_by('id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori')
    )
    seen_kats = set()
    kategori_ilap = []
    for r in kategori_rows:
        kid = r.get('id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_id')
        if not kid or kid in seen_kats:
            continue
        seen_kats.add(kid)
        kategori_ilap.append({
            'id': kid,
            'name': r.get('id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori') or '-',
        })

    periode_data_rows = list(
        tiket_qs.values(
            'id_periode_data_id',
            'periode',
            'tahun',
            'id_periode_data__id_periode_pengiriman__periode_penerimaan',
        )
        .distinct()
        .order_by('tahun', 'periode')
    )
    seen_periods = set()
    periode_data = []
    for r in periode_data_rows:
        pid = r.get('id_periode_data_id')
        if not pid or pid in seen_periods:
            continue
        seen_periods.add(pid)
        periode_data.append({
            'id': pid,
            'name': format_periode(
                r.get('id_periode_data__id_periode_pengiriman__periode_penerimaan') or 'Bulanan',
                r.get('periode') or 0,
                r.get('tahun') or 0,
            ),
        })

    periode_pengiriman_rows = list(
        tiket_qs.values(
            'id_periode_data__id_periode_pengiriman_id',
            'id_periode_data__id_periode_pengiriman__periode_penyampaian',
        )
        .distinct()
        .order_by('id_periode_data__id_periode_pengiriman__periode_penyampaian')
    )
    seen_peng = set()
    periode_pengiriman = []
    for r in periode_pengiriman_rows:
        pid = r.get('id_periode_data__id_periode_pengiriman_id')
        if not pid or pid in seen_peng:
            continue
        seen_peng.add(pid)
        periode_pengiriman.append({
            'id': pid,
            'name': r.get('id_periode_data__id_periode_pengiriman__periode_penyampaian') or '-',
        })

    # Media backup options from available backup records for filtered tiket scope.
    filtered_tiket_ids = tiket_qs.values_list('id', flat=True)
    media_backup_rows = (
        backup_qs.filter(id_tiket_id__in=filtered_tiket_ids)
        .values('id_media_backup_id', 'id_media_backup__deskripsi')
        .distinct()
        .order_by('id_media_backup__deskripsi')
    )
    media_backup = [
        {'id': r['id_media_backup_id'], 'name': r['id_media_backup__deskripsi'] or '-'}
        for r in media_backup_rows if r['id_media_backup_id']
    ]

    from django.contrib.auth.models import User
    pic_user_ids = tiket_qs.filter(
        tiketpic__role=TiketPIC.Role.P3DE,
        tiketpic__active=True,
    ).values_list('tiketpic__id_user_id', flat=True).distinct()
    pic_p3de = []
    for u in User.objects.filter(id__in=pic_user_ids).order_by('first_name', 'last_name', 'username'):
        full_name = f"{(u.first_name or '').strip()} {(u.last_name or '').strip()}".strip()
        pic_p3de.append({'id': u.id, 'name': full_name or u.username})

    return JsonResponse({
        'filter_options': {
            'jenis_data': jenis_data,
            'subjenis_data': subjenis_data,
            'kategori_ilap': kategori_ilap,
            'periode_data': periode_data,
            'periode_pengiriman': periode_pengiriman,
            'media_backup': media_backup,
            'pic_p3de': pic_p3de,
        },
        'media_backup_list': media_counts,
    })


def _get_export_rows(request):
    """Build a sorted list of serialized BackupData rows for export.

    Applies current GET filters, orders by year/tiket number/id, and returns
    serialized dicts without action buttons.

    Args:
        request: The HTTP request (used for both base queryset and filters).

    Returns:
        list[dict]: Serialized BackupData rows suitable for Excel/PDF export.
    """
    qs = _apply_backup_data_filters(_get_backup_data_base_queryset(request), request.GET)
    qs = qs.order_by('id_tiket__tahun', 'id_tiket__nomor_tiket', 'id')
    return [_build_backup_data_row(obj, request=request, include_actions=False) for obj in qs]


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_export_excel(request):
    """Export filtered backup data to XLSX."""
    rows = _get_export_rows(request)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Backup Data'

    headers = [
        'Kategori ILAP',
        'Nama ILAP',
        'Jenis Data',
        'Subjenis Data',
        'Periode Data',
        'Nomor Tiket',
        'Media Backup',
        'Lokasi Penyimpanan',
        'PIC P3DE',
        'Jumlah Data',
    ]
    ws.append(headers)
    for row in rows:
        ws.append([
            row['kategori_ilap'],
            row['nama_ilap'],
            row['jenis_data'],
            row['subjenis_data'],
            row['periode_data'],
            row['nomor_tiket'],
            row['media_backup'],
            row['lokasi_penyimpanan'],
            row['pic_p3de'],
            row['jumlah_data'],
        ])

    output = BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="backup_data.xlsx"'
    return response


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_export_pdf(request):
    """Export filtered backup data to PDF."""
    rows = _get_export_rows(request)
    headers = [
        'Kategori ILAP',
        'Nama ILAP',
        'Jenis Data',
        'Subjenis Data',
        'Periode Data',
        'Nomor Tiket',
        'Media Backup',
        'Lokasi',
        'PIC P3DE',
        'Jumlah Data',
    ]
    table_rows = [
        [
            row['kategori_ilap'],
            row['nama_ilap'],
            row['jenis_data'],
            row['subjenis_data'],
            row['periode_data'],
            row['nomor_tiket'],
            row['media_backup'],
            row['lokasi_penyimpanan'],
            row['pic_p3de'],
            row['jumlah_data'],
        ]
        for row in rows
    ]
    pdf_bytes = _build_simple_table_pdf('Laporan Backup Data', headers, table_rows)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="backup_data.pdf"'
    return response


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def backup_data_tiket_info(request, tiket_pk):
    """Retrieve details for a specific ticket to display on the backup form."""
    try:
        tiket = Tiket.objects.select_related(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap'
        ).get(pk=tiket_pk)
        
        subjenis = tiket.id_periode_data.id_sub_jenis_data_ilap if tiket.id_periode_data else None
        ilap = subjenis.id_ilap if subjenis else None
        
        # Get period text
        periode_text = '-'
        if tiket.id_periode_data and tiket.id_periode_data.id_periode_pengiriman:
            periode_text = f"{tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan} {tiket.periode}"
        else:
            periode_text = f"{tiket.periode}"
            
        return JsonResponse({
            'success': True,
            'ilap': ilap.nama_ilap if ilap else '-',
            'jenis_data': subjenis.nama_jenis_data if subjenis else '-',
            'periode': periode_text,
            'jumlah_data': f"{tiket.baris_diterima:,}" if tiket.baris_diterima is not None else '0'
        })
    except Tiket.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Tiket tidak ditemukan'}, status=404)