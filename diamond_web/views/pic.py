from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET

from ..models.pic import PIC
from ..forms.pic import PICForm
from ..constants.tiket_action_types import PICActionType
from ..constants.tiket_status import STATUS_DIBATALKAN
from .mixins import AjaxFormMixin, AdminP3DERequiredMixin, AdminPIDERequiredMixin, AdminPMDERequiredMixin


class PICListView(LoginRequiredMixin, TemplateView):
    """List view for `PIC` entries of a specific `tipe`.

    Subclasses must set the `tipe` attribute to one of `PIC.TipePIC` values
    (e.g. `PIC.TipePIC.P3DE`). Renders `pic/list.html` by default and
    provides the following context variables for templates:

    - ``tipe``: raw stored `tipe` value
    - ``tipe_display``: human-readable label for the `tipe`

    Behavior:
    - When redirected after a delete operation the view reads `deleted` and
        `name` query parameters (URL-encoded) and registers a Django
        `messages.success` notification so the frontend can display a toast.
    """
    template_name = 'pic/list.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        return context

    def get(self, request, *args, **kwargs):
        # If redirected after delete, show success message from query params
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'{self.get_tipe_display()} "{name}" berhasil dihapus.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


class PICCreateView(LoginRequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `PIC` assignments.

    Presents a form to create a `PIC` record. On successful save this view
    also propagates the assignment to active `Tiket` objects that reference
    the same `id_sub_jenis_data_ilap`. For each matching `Tiket` the view
    will either create a new `TiketPIC` record or reactivate/update an
    existing one, and will append a `TiketAction` log entry. This side-effect
    is intentional to keep ticket assignments in sync with PIC definitions.

    Notes:
    - The view supports AJAX via `AjaxFormMixin`: AJAX clients receive a
        JSON redirect payload; non-AJAX clients receive a standard redirect
        and a Django success message.
    - The form receives a ``tipe`` kwarg to restrict form choices where
        applicable.
    """
    model = PIC
    form_class = PICForm
    template_name = 'pic/form.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))
    
    @property
    def success_message(self):
        return f'{self.get_tipe_display()} "{{object}}" berhasil dibuat.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tipe'] = self.tipe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_create_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_create',
            PIC.TipePIC.PIDE: 'pic_pide_create',
            PIC.TipePIC.PMDE: 'pic_pmde_create',
        }
        context['form_action'] = reverse(tipe_create_url_map.get(self.tipe, 'home'))
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)
    
        def form_valid(self, form):
                """Handle successful form submission and propagate PIC to active tikets.

                Side effects:
                - Queries `Tiket` for entries matching `id_sub_jenis_data_ilap` and
                    with `status` less than `STATUS_DIBATALKAN`.
                - Creates or updates `TiketPIC` records and creates `TiketAction`
                    records for each affected ticket.
                """
        from ..models.tiket import Tiket
        from ..models.tiket_pic import TiketPIC
        from ..models.tiket_action import TiketAction
        from django.utils import timezone
        from django.db.models import Q
        
        response = super().form_valid(form)
        
        # Get the newly created PIC object
        pic = self.object
        
        # Map PIC tipe to TiketPIC role
        tipe_to_role = {
            PIC.TipePIC.P3DE: TiketPIC.Role.P3DE,
            PIC.TipePIC.PIDE: TiketPIC.Role.PIDE,
            PIC.TipePIC.PMDE: TiketPIC.Role.PMDE,
        }
        role = tipe_to_role.get(pic.tipe)
        current_time = timezone.now()
        tipe_label = dict(PIC.TipePIC.choices).get(pic.tipe, pic.tipe)
        action_logged = False
        
        if role:
            # Find all tikets using this sub_jenis_data with status < 7 (not dibatalkan or selesai)
            # AND with tgl_terima_dip >= pic.start_date
            active_tikets = Tiket.objects.filter(
                id_periode_data__id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap,
                status__lt=STATUS_DIBATALKAN  # status < STATUS_DIBATALKAN (not dibatalkan or selesai)
            ).filter(
                Q(tgl_terima_dip__gte=pic.start_date) | Q(tgl_terima_dip__isnull=True)
            )
            
            # Create or update TiketPIC records for this user
            for tiket in active_tikets:
                # Check if user already has a PIC record for this tiket and role
                existing_pic = TiketPIC.objects.filter(
                    id_tiket=tiket,
                    id_user=pic.id_user,
                    role=role
                ).first()
                
                if existing_pic:
                    # Check if this is a reactivation (was inactive)
                    was_inactive = not existing_pic.active
                    update_fields = []
                    
                    # Reactivate if inactive
                    if not existing_pic.active:
                        existing_pic.active = True
                        update_fields.append('active')
                    
                    # Fill timestamp if null
                    if existing_pic.timestamp is None:
                        existing_pic.timestamp = current_time
                        update_fields.append('timestamp')
                    
                    if update_fields:
                        existing_pic.save(update_fields=update_fields)
                        
                        # Log with appropriate message
                        if was_inactive:
                            action_type = PICActionType.DIAKTIFKAN_KEMBALI
                            message = f'{tipe_label} {pic.id_user.username} diaktifkan kembali'
                        else:
                            action_type = PICActionType.DITAMBAHKAN
                            message = f'{tipe_label} {pic.id_user.username} ditambahkan'
                        
                        TiketAction.objects.create(
                            id_tiket=tiket,
                            id_user=self.request.user,
                            timestamp=current_time,
                            action=action_type,
                            catatan=message
                        )
                        action_logged = True
                else:
                    # Create new TiketPIC with timestamp
                    TiketPIC.objects.create(
                        id_tiket=tiket,
                        id_user=pic.id_user,
                        role=role,
                        active=True,
                        timestamp=current_time
                    )
                    
                    # Add log to TiketAction
                    TiketAction.objects.create(
                        id_tiket=tiket,
                        id_user=self.request.user,
                        timestamp=current_time,
                        action=PICActionType.DITAMBAHKAN,
                        catatan=f'{tipe_label} {pic.id_user.username} ditambahkan'
                    )
                    action_logged = True
            
            # Only log to tikets where changes were actually made
        
        return response


class PICUpdateView(LoginRequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `PIC` entries.

    When the `end_date` field is set on a `PIC` (transition from None ->
    date) this view will deactivate related `TiketPIC` records (for
    tickets referencing the same `id_sub_jenis_data_ilap`) and create
    `TiketAction` logs. When `end_date` is cleared (date -> None) it will
    attempt to reactivate or create `TiketPIC` records for relevant active
    tickets and log the actions.

    The view preserves standard AJAX behavior through `AjaxFormMixin`.
    """
    model = PIC
    form_class = PICForm
    template_name = 'pic/form.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))
    
    @property
    def success_message(self):
        return f'{self.get_tipe_display()} "{{object}}" berhasil diperbarui.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tipe'] = self.tipe
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_update_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_update',
            PIC.TipePIC.PIDE: 'pic_pide_update',
            PIC.TipePIC.PMDE: 'pic_pmde_update',
        }
        context['form_action'] = reverse(tipe_update_url_map.get(self.tipe, 'home'), args=[self.object.pk])
        return context

        def form_valid(self, form):
                """Process `end_date` changes and update `TiketPIC` / `TiketAction`.

                Behavior:
                - If `end_date` is newly set, deactivate matching active `TiketPIC`
                    records and add a `TiketAction` with `PICActionType.TIDAK_AKTIF`.
                - If `end_date` is cleared, reactivate or create `TiketPIC` records
                    for related tickets and log reactivation or creation actions.
                """
        from ..models.tiket import Tiket
        from ..models.tiket_pic import TiketPIC
        from ..models.tiket_action import TiketAction
        from django.utils import timezone
        from django.db.models import Q
        
        # Get the original object before save
        original_pic = PIC.objects.get(pk=self.object.pk)
        
        # Map PIC tipe to TiketPIC role
        tipe_to_role = {
            PIC.TipePIC.P3DE: TiketPIC.Role.P3DE,
            PIC.TipePIC.PIDE: TiketPIC.Role.PIDE,
            PIC.TipePIC.PMDE: TiketPIC.Role.PMDE,
        }
        role = tipe_to_role.get(self.object.tipe)
        current_time = timezone.now()
        tipe_label = dict(PIC.TipePIC.choices).get(self.object.tipe, self.object.tipe)
        
        # Check if end_date is being set (was None, now has value) - DEACTIVATION
        if original_pic.end_date is None and form.cleaned_data.get('end_date') is not None:
            if role:
                # Find TiketPIC records for this user and role, but ONLY for tikets with this sub_jenis_data
                deactivate_tiket_pcs = TiketPIC.objects.filter(
                    id_user=self.object.id_user,
                    role=role,
                    active=True,  # Only deactivate currently active ones
                    id_tiket__id_periode_data__id_sub_jenis_data_ilap=self.object.id_sub_jenis_data_ilap
                )
                
                action_logged = False
                # Mark these TiketPIC records as inactive and add logs
                for tiket_pic in deactivate_tiket_pcs:
                    tiket_pic.active = False
                    tiket_pic.save(update_fields=['active'])
                    
                    # Add log to TiketAction
                    TiketAction.objects.create(
                        id_tiket=tiket_pic.id_tiket,
                        id_user=self.request.user,
                        timestamp=current_time,
                        action=PICActionType.TIDAK_AKTIF,
                        catatan=f'{tipe_label} {self.object.id_user.username} tidak aktif'
                    )
                    # No logging needed for this iteration
        
        # Check if end_date is being cleared (was set, now is None) - REACTIVATION
        elif original_pic.end_date is not None and form.cleaned_data.get('end_date') is None:
            if role:
                # Find all tikets using this sub_jenis_data with status < 7 (not dibatalkan or selesai)
                # AND with tgl_terima_dip >= pic.start_date
                active_tikets = Tiket.objects.filter(
                    id_periode_data__id_sub_jenis_data_ilap=self.object.id_sub_jenis_data_ilap,
                    status__lt=STATUS_DIBATALKAN  # status < STATUS_DIBATALKAN (not dibatalkan or selesai)
                ).filter(
                    Q(tgl_terima_dip__gte=self.object.start_date) | Q(tgl_terima_dip__isnull=True)
                )
                
                action_logged = False
                # Create or reactivate TiketPIC records for this user
                for tiket in active_tikets:
                    # Check if user already has a PIC record for this tiket and role
                    existing_pic = TiketPIC.objects.filter(
                        id_tiket=tiket,
                        id_user=self.object.id_user,
                        role=role
                    ).first()
                    
                    if existing_pic:
                        # Update existing record - reactivate and set timestamp if null
                        update_fields = []
                        is_reactivation = False
                        filled_timestamp = False
                        if not existing_pic.active:
                            existing_pic.active = True
                            update_fields.append('active')
                            is_reactivation = True
                        if existing_pic.timestamp is None:
                            existing_pic.timestamp = current_time
                            update_fields.append('timestamp')
                            filled_timestamp = True
                        if update_fields:
                            existing_pic.save(update_fields=update_fields)
                        
                        # Add log if reactivated or timestamp filled
                        if is_reactivation or filled_timestamp:
                            TiketAction.objects.create(
                                id_tiket=tiket,
                                id_user=self.request.user,
                                timestamp=current_time,
                                action=PICActionType.DIAKTIFKAN_KEMBALI,
                                catatan=f'{tipe_label} {self.object.id_user.username} diaktifkan kembali'
                            )
                            action_logged = True
                    else:
                        # Create new TiketPIC with timestamp
                        TiketPIC.objects.create(
                            id_tiket=tiket,
                            id_user=self.object.id_user,
                            role=role,
                            active=True,
                            timestamp=current_time
                        )
                        
                        # Add log for new assignment
                        TiketAction.objects.create(
                            id_tiket=tiket,
                            id_user=self.request.user,
                            timestamp=current_time,
                            action=PICActionType.DITAMBAHKAN,
                            catatan=f'{tipe_label} {self.object.id_user.username} ditambahkan'
                        )
                
                # No fallback logging - only log to tikets where changes were made
        
        return super().form_valid(form)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        return self.render_form_response(form)
    
    def get_queryset(self):
        """Filter by tipe to ensure users only access their PIC type"""
        qs = super().get_queryset()
        if self.tipe:
            qs = qs.filter(tipe=self.tipe)
        return qs


class PICDeleteView(LoginRequiredMixin, DeleteView):
    """Delete view for `PIC` entries and associated side-effects.

    Deleting a `PIC` will also find `TiketPIC` records for the same user,
    role and `id_sub_jenis_data_ilap` and delete them; a `TiketAction` log
    with `PICActionType.TIDAK_AKTIF` is created for each affected ticket.

    Response behavior:
    - AJAX clients receive a JSON payload with `success` and `redirect`.
    - Non-AJAX clients receive a JSON redirect as well and a Django
        success message is registered so the frontend can show a toast.
    """
    model = PIC
    template_name = 'pic/confirm_delete.html'
    tipe = None
    
    def get_tipe_display(self):
        """Get display name for the tipe"""
        if self.tipe:
            return dict(PIC.TipePIC.choices).get(self.tipe, self.tipe)
        return "PIC"
    
    def get_success_url(self):
        tipe_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_list',
            PIC.TipePIC.PIDE: 'pic_pide_list',
            PIC.TipePIC.PMDE: 'pic_pmde_list',
        }
        return reverse_lazy(tipe_url_map.get(self.tipe, 'home'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipe'] = self.tipe
        context['tipe_display'] = self.get_tipe_display()
        tipe_delete_url_map = {
            PIC.TipePIC.P3DE: 'pic_p3de_delete',
            PIC.TipePIC.PIDE: 'pic_pide_delete',
            PIC.TipePIC.PMDE: 'pic_pmde_delete',
        }
        context['form_action'] = reverse(tipe_delete_url_map.get(self.tipe, 'home'), args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        """Delete PIC and mark all associated TiketPIC records as inactive"""
        from ..models.tiket_pic import TiketPIC
        from ..models.tiket_action import TiketAction
        from django.utils import timezone
        
        self.object = self.get_object()
        name = str(self.object)
        pic = self.object
        
        # Map PIC tipe to TiketPIC role
        tipe_to_role = {
            PIC.TipePIC.P3DE: TiketPIC.Role.P3DE,
            PIC.TipePIC.PIDE: TiketPIC.Role.PIDE,
            PIC.TipePIC.PMDE: TiketPIC.Role.PMDE,
        }
        role = tipe_to_role.get(pic.tipe)
        current_time = timezone.now()
        tipe_label = dict(PIC.TipePIC.choices).get(pic.tipe, pic.tipe)
        
        # Find TiketPIC records for this user and role, but ONLY for tikets with this sub_jenis_data
        if role:
            delete_tiket_pcs = TiketPIC.objects.filter(
                id_user=pic.id_user,
                role=role,
                id_tiket__id_periode_data__id_sub_jenis_data_ilap=pic.id_sub_jenis_data_ilap
            )
            
            # Delete TiketPIC records and log the action
            for tiket_pic in delete_tiket_pcs:
                tiket = tiket_pic.id_tiket
                tiket_pic.delete()
                
                # Add log to TiketAction
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=request.user,
                    timestamp=current_time,
                    action=PICActionType.TIDAK_AKTIF,
                    catatan=f'{tipe_label} {pic.id_user.username} dihapus'
                )
        
        # Now delete the PIC object
        pic.delete()
        
        # For AJAX clients, set a server-side message and return a redirect URL
        # so the base template can render the toast uniformly.
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.success(request, f'{self.get_tipe_display()} "{name}" berhasil dihapus.')
            return JsonResponse({'success': True, 'redirect': self.get_success_url()})
        messages.success(request, f'{self.get_tipe_display()} "{name}" berhasil dihapus.')
        return JsonResponse({'success': True, 'redirect': self.get_success_url()})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)
    
    def get_queryset(self):
        """Filter by tipe to ensure users only access their PIC type"""
        qs = super().get_queryset()
        if self.tipe:
            qs = qs.filter(tipe=self.tipe)
        return qs


# Concrete views for each PIC type
class PICP3DEListView(AdminP3DERequiredMixin, PICListView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/list.html'  # Keep old template for backward compatibility


class PICP3DECreateView(AdminP3DERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/form.html'


class PICP3DEUpdateView(AdminP3DERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/form.html'


class PICP3DEDeleteView(AdminP3DERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.P3DE
    template_name = 'pic_p3de/confirm_delete.html'


class PICPIDEListView(AdminPIDERequiredMixin, PICListView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/list.html'


class PICPIDECreateView(AdminPIDERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/form.html'


class PICPIDEUpdateView(AdminPIDERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/form.html'


class PICPIDEDeleteView(AdminPIDERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.PIDE
    template_name = 'pic_pide/confirm_delete.html'


class PICPMDEListView(AdminPMDERequiredMixin, PICListView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/list.html'


class PICPMDECreateView(AdminPMDERequiredMixin, PICCreateView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/form.html'


class PICPMDEUpdateView(AdminPMDERequiredMixin, PICUpdateView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/form.html'


class PICPMDEDeleteView(AdminPMDERequiredMixin, PICDeleteView):
    tipe = PIC.TipePIC.PMDE
    template_name = 'pic_pmde/confirm_delete.html'


# DataTables server-side processing
def _pic_data_common(request, tipe):
    """Common DataTables server-side endpoint for `PIC` objects.

    Expected GET parameters (DataTables conventions):
    - `draw`, `start`, `length` for paging.
    - `columns_search[]` list for per-column filtering: [sub_jenis_data, user, start_date, end_date].
    - `search[value]` for global search.
    - `order[0][column]`, `order[0][dir]` for ordering.

    Returns JSON with the standard DataTables fields: `draw`,
    `recordsTotal`, `recordsFiltered`, and `data` (list of rows). Each row
    contains: `id`, `sub_jenis_data_ilap`, `user`, `start_date`, `end_date`,
    and `actions` HTML for edit/delete buttons. Permission checks are not
    enforced here; callers should wrap this function with appropriate
    decorators to restrict access.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = PIC.objects.filter(tipe=tipe).select_related('id_sub_jenis_data_ilap', 'id_user').all()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Sub Jenis Data ILAP
            qs = qs.filter(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # User
            from django.db.models import Q
            qs = qs.filter(Q(id_user__username__icontains=columns_search[1]) | 
                          Q(id_user__first_name__icontains=columns_search[1]) |
                          Q(id_user__last_name__icontains=columns_search[1]))
        if len(columns_search) > 2 and columns_search[2]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[3])

    # Global search
    search_value = request.GET.get('search[value]')
    if search_value:
        from django.db.models import Q
        qs = qs.filter(
            Q(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=search_value) |
            Q(id_user__username__icontains=search_value) |
            Q(id_user__first_name__icontains=search_value) |
            Q(id_user__last_name__icontains=search_value) |
            Q(start_date__icontains=search_value) |
            Q(end_date__icontains=search_value)
        )

    records_filtered = qs.count()

    # Ordering
    order_column_idx = int(request.GET.get('order[0][column]', '0'))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_columns = ['id_sub_jenis_data_ilap__nama_sub_jenis_data', 'id_user__username', 'start_date', 'end_date']
    if 0 <= order_column_idx < len(order_columns):
        order_field = order_columns[order_column_idx]
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)

    # Pagination
    qs = qs[start:start + length]

    # Map tipe to URL names
    tipe_url_map = {
        PIC.TipePIC.P3DE: ('pic_p3de_update', 'pic_p3de_delete'),
        PIC.TipePIC.PIDE: ('pic_pide_update', 'pic_pide_delete'),
        PIC.TipePIC.PMDE: ('pic_pmde_update', 'pic_pmde_delete'),
    }
    update_url_name, delete_url_name = tipe_url_map.get(tipe, ('', ''))

    # Format data
    data = []
    for obj in qs:
        user_display = f"{obj.id_user.first_name} {obj.id_user.last_name}".strip()
        if not user_display:
            user_display = obj.id_user.username
        
        data.append({
            'id': obj.id,
            'sub_jenis_data_ilap': obj.id_sub_jenis_data_ilap.nama_sub_jenis_data,
            'user': user_display,
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
            'actions': f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse(update_url_name, args=[obj.pk])}' title='Edit'><i class='ri-edit-line'></i></button>"
                       f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse(delete_url_name, args=[obj.pk])}' title='Delete'><i class='ri-delete-bin-line'></i></button>"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_p3de']).exists())
@require_GET
def pic_p3de_data(request):
    """DataTables endpoint for P3DE `PIC` rows.

    Permissions: user must be logged in and a member of `admin` or
    `admin_p3de`. Returns the same JSON shape as `_pic_data_common`.
    """
    return _pic_data_common(request, PIC.TipePIC.P3DE)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pide']).exists())
@require_GET
def pic_pide_data(request):
    """DataTables endpoint for PIDE `PIC` rows.

    Permissions: user must be logged in and a member of `admin` or
    `admin_pide`. Returns the same JSON shape as `_pic_data_common`.
    """
    return _pic_data_common(request, PIC.TipePIC.PIDE)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'admin_pmde']).exists())
@require_GET
def pic_pmde_data(request):
    """DataTables endpoint for PMDE `PIC` rows.

    Permissions: user must be logged in and a member of `admin` or
    `admin_pmde`. Returns the same JSON shape as `_pic_data_common`.
    """
    return _pic_data_common(request, PIC.TipePIC.PMDE)
