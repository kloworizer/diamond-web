from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.backup_data import BackupData
from ..models.tiket import Tiket
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..forms.backup_data import BackupDataForm
from ..constants.tiket_action_types import BackupActionType
from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE
from .mixins import AjaxFormMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin


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

class BackupDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for BackupData.

    Renders the `backup_data/list.html` template. Access restricted to
    authenticated users in `user_p3de` (or admin) via `UserP3DERequiredMixin`.
    """
    template_name = 'backup_data/list.html'

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


class BackupDataDeleteView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, DeleteView):
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
            tiket.save(update_fields=["backup"])
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

    qs = BackupData.objects.select_related('id_user', 'id_tiket')
    
    # Filter by user role (non-admin/superuser only see their own records)
    if not request.user.is_superuser and not request.user.groups.filter(name='admin').exists():
        qs = qs.filter(
            id_tiket__tiketpic__id_user=request.user,
            id_tiket__tiketpic__role=TiketPIC.Role.P3DE
        ).distinct()
    
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # No Tiket
            qs = qs.filter(id_tiket__nomor_tiket__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Lokasi Backup
            qs = qs.filter(lokasi_backup__icontains=columns_search[1])

    records_filtered = qs.count()

    # Ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['id', 'id_tiket__nomor_tiket', 'lokasi_backup']

    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-id')
    else:
        qs = qs.order_by('-id')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        user_name = obj.id_user.username if obj.id_user else '-'
        actions = ''
        # Check if user is active PIC for this tiket
        is_active_pic = False
        if obj.id_tiket:
            is_active_pic = TiketPIC.objects.filter(
                id_tiket=obj.id_tiket,
                id_user=request.user,
                active=True
            ).exists()
        
        if obj.id_tiket and obj.id_tiket.status is not None and obj.id_tiket.status < STATUS_DIKIRIM_KE_PIDE and is_active_pic:
            actions = (
                f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse('backup_data_update', args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse('backup_data_delete', args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
            )
        data.append({
            'id': obj.pk,
            'no_tiket': obj.id_tiket.nomor_tiket if obj.id_tiket else '-',
            'lokasi_backup': obj.lokasi_backup,
            'user': user_name,
            'actions': actions
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })