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
from ..utils.pic_profil import pic_profil_link, pic_profil_visibility
from .mixins import (
    AjaxFormMixin,
    AdminP3DERequiredMixin,
    AdminPIDERequiredMixin,
    AdminPMDERequiredMixin,
    AdminAnyRequiredMixin,
    UserP3DERequiredMixin,
    UserPIDERequiredMixin,
    UserPMDERequiredMixin,
    SafeDeleteMixin,
)


class PICListView(LoginRequiredMixin, TemplateView):
    """List view for `PIC` entries of a specific `tipe`.

    Subclasses must set the `tipe` attribute to one of `PIC.TipePIC` values
    (e.g. `PIC.TipePIC.P3DE`) and apply the appropriate access mixin
    (e.g., `UserP3DERequiredMixin` for views that allow both admins and
    regular P3DE users). Renders `pic/list.html` by default and provides
    the following context variables for templates:

    - ``tipe``: raw stored `tipe` value
    - ``tipe_display``: human-readable label for the `tipe`
    - ``is_admin``: boolean indicating if the user has an admin role for
      this PIC type (controls visibility of CUD buttons)

    Access Control:
    - Requires @login_required (LoginRequiredMixin)
    - Concrete subclasses add role-specific mixins (e.g., UserP3DERequiredMixin)

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
        tipe_display = self.get_tipe_display()
        context['tipe_display'] = tipe_display
        context['is_admin'] = self.is_admin_user()
        context['page_title'] = f'PIC {tipe_display}'
        return context

    def is_admin_user(self):
        """Return True if the current user has an admin role for this PIC type."""
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name='admin').exists():
            return True
        # Check type-specific admin group
        admin_group_map = {
            PIC.TipePIC.P3DE: 'admin_p3de',
            PIC.TipePIC.PIDE: 'admin_pide',
            PIC.TipePIC.PMDE: 'admin_pmde',
        }
        admin_group = admin_group_map.get(self.tipe)
        if admin_group and user.groups.filter(name=admin_group).exists():
            return True
        return False

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


def _assign_pic_to_open_tikets(user, role, sub_jenis_data_ilap, tipe_label, admin_user, current_time):
    """Put `user` on every still-open tiket of `sub_jenis_data_ilap` as `role`.

    Creates a `TiketPIC` when the user has none for that tiket/role, reactivates
    one that was switched off, and writes a `TiketAction` for each tiket that
    actually changed. Tikets already cancelled or finished are left alone.
    """
    from ..models.tiket import Tiket
    from ..models.tiket_pic import TiketPIC
    from ..models.tiket_action import TiketAction

    active_tikets = Tiket.objects.filter(
        id_periode_data__id_sub_jenis_data_ilap=sub_jenis_data_ilap,
        status_tiket__lt=STATUS_DIBATALKAN
    )

    for tiket in active_tikets:
        existing_pic = TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=user,
            role=role
        ).first()

        if existing_pic:
            was_inactive = not existing_pic.active
            update_fields = []

            if was_inactive:
                existing_pic.active = True
                update_fields.append('active')

            # Fill timestamp if null
            if existing_pic.timestamp is None:
                existing_pic.timestamp = current_time
                update_fields.append('timestamp')

            if not update_fields:
                continue

            existing_pic.save(update_fields=update_fields)

            # Log with appropriate message
            if was_inactive:
                action_type = PICActionType.DIAKTIFKAN_KEMBALI
                message = f'{tipe_label} {user.username} diaktifkan kembali'
            else:
                action_type = PICActionType.DITAMBAHKAN
                message = f'{tipe_label} {user.username} ditambahkan'
        else:
            # Create new TiketPIC with timestamp
            TiketPIC.objects.create(
                id_tiket=tiket,
                id_user=user,
                role=role,
                active=True,
                timestamp=current_time
            )
            action_type = PICActionType.DITAMBAHKAN
            message = f'{tipe_label} {user.username} ditambahkan'

        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=admin_user,
            timestamp=current_time,
            action=action_type,
            catatan=message
        )


def _unassign_pic_from_open_tikets(user, role, sub_jenis_data_ilap, tipe_label,
                                   admin_user, current_time, catatan=None,
                                   open_only=True):
    """Deactivate `user`'s active `TiketPIC` records for `sub_jenis_data_ilap`.

    `open_only` restricts the change to tikets that are still open, which is what
    a PIC hand-over wants: a cancelled or finished tiket keeps the person who
    actually worked it. Pass ``open_only=False`` to sweep every tiket.
    """
    from ..models.tiket_pic import TiketPIC
    from ..models.tiket_action import TiketAction

    tiket_pcs = TiketPIC.objects.filter(
        id_user=user,
        role=role,
        active=True,  # Only deactivate currently active ones
        id_tiket__id_periode_data__id_sub_jenis_data_ilap=sub_jenis_data_ilap
    )
    if open_only:
        tiket_pcs = tiket_pcs.filter(id_tiket__status_tiket__lt=STATUS_DIBATALKAN)

    if catatan is None:
        catatan = f'{tipe_label} {user.username} tidak aktif'

    for tiket_pic in tiket_pcs:
        tiket_pic.active = False
        tiket_pic.save(update_fields=['active'])

        # Add log to TiketAction
        TiketAction.objects.create(
            id_tiket=tiket_pic.id_tiket,
            id_user=admin_user,
            timestamp=current_time,
            action=PICActionType.TIDAK_AKTIF,
            catatan=catatan
        )


class PICCreateView(LoginRequiredMixin, AdminAnyRequiredMixin, AjaxFormMixin, CreateView):
    """Create view for `PIC` assignments.

    Requires membership in any admin group (admin, admin_p3de, admin_pide, admin_pmde).
    Subclasses can further restrict with specific role mixins (e.g., AdminP3DERequiredMixin).

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

    Access Control:
    - Requires @login_required (LoginRequiredMixin)
    - Requires admin role (AdminAnyRequiredMixin) - blocks regular users from accessing base view
    - Subclasses further restrict with specific admin roles (e.g., AdminP3DERequiredMixin)
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
        from ..models.tiket_pic import TiketPIC
        from django.utils import timezone
        from django.contrib.auth.models import User

        response = super().form_valid(form)

        # Get the newly created PIC object
        pic = self.object

        # Get admin user for PIC action logging
        admin_user = User.objects.get(username='admin')

        # Map PIC tipe to TiketPIC role
        tipe_to_role = {
            PIC.TipePIC.P3DE: TiketPIC.Role.P3DE,
            PIC.TipePIC.PIDE: TiketPIC.Role.PIDE,
            PIC.TipePIC.PMDE: TiketPIC.Role.PMDE,
        }
        role = tipe_to_role.get(pic.tipe)
        current_time = timezone.now()
        tipe_label = dict(PIC.TipePIC.choices).get(pic.tipe, pic.tipe)

        if role:
            # Only log to tikets where changes were actually made
            _assign_pic_to_open_tikets(
                pic.id_user, role, pic.id_sub_jenis_data_ilap,
                tipe_label, admin_user, current_time
            )

        return response


class PICUpdateView(LoginRequiredMixin, AdminAnyRequiredMixin, AjaxFormMixin, UpdateView):
    """Update view for `PIC` entries.

    Requires membership in any admin group (admin, admin_p3de, admin_pide, admin_pmde).
    Subclasses can further restrict with specific role mixins (e.g., AdminP3DERequiredMixin).

    When the `id_user` field is changed the view treats the edit as a
    hand-over: the previous user is deactivated on the still-open tickets
    referencing the same `id_sub_jenis_data_ilap` and the new user is assigned
    to those tickets the same way `PICCreateView` assigns a brand new PIC.

    When the `end_date` field is set on a `PIC` (transition from None ->
    date) this view will deactivate related `TiketPIC` records (for
    tickets referencing the same `id_sub_jenis_data_ilap`) and create
    `TiketAction` logs. When `end_date` is cleared (date -> None) it will
    attempt to reactivate or create `TiketPIC` records for relevant active
    tickets and log the actions.

    The view preserves standard AJAX behavior through `AjaxFormMixin`.

    Access Control:
    - Requires @login_required (LoginRequiredMixin)
    - Requires admin role (AdminAnyRequiredMixin) - blocks regular users from accessing base view
    - Subclasses further restrict with specific admin roles (e.g., AdminP3DERequiredMixin)
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
        """Propagate the edit to `TiketPIC` / `TiketAction`.

        Behavior:
        - If the user is swapped for someone else, the previous user is
            deactivated on the still-open tikets and the new user is assigned to
            them exactly as a fresh PIC would be (created or reactivated, with a
            `PICActionType.DITAMBAHKAN` log). A hand-over that also carries an
            `end_date` only removes the old user - nobody takes over.
        - If `end_date` is newly set, deactivate matching active `TiketPIC`
            records and add a `TiketAction` with `PICActionType.TIDAK_AKTIF`.
        - If `end_date` is cleared, reactivate or create `TiketPIC` records
            for related tickets and log reactivation or creation actions.
        """
        from ..models.tiket_pic import TiketPIC
        from django.utils import timezone
        from django.contrib.auth.models import User

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

        # Get admin user for PIC action logging
        admin_user = User.objects.get(username='admin')

        # `self.object` already carries the submitted values at this point, so the
        # previous holder has to come from the row re-read above.
        new_user = self.object.id_user
        new_end_date = form.cleaned_data.get('end_date')
        sub_jenis_data = self.object.id_sub_jenis_data_ilap
        user_changed = original_pic.id_user_id != new_user.pk

        if role and user_changed:
            # Hand-over: the tiket loses the old PIC and gains the new one in the
            # same edit, so it is never left without anybody assigned.
            _unassign_pic_from_open_tikets(
                original_pic.id_user, role, sub_jenis_data,
                tipe_label, admin_user, current_time,
                catatan=f'{tipe_label} {original_pic.id_user.username} diganti '
                        f'oleh {new_user.username}'
            )
            # An edit that also sets an end_date is not a hand-over - the PIC is
            # closed, so nobody replaces them.
            if new_end_date is None:
                _assign_pic_to_open_tikets(
                    new_user, role, sub_jenis_data,
                    tipe_label, admin_user, current_time
                )

        # Check if end_date is being set (was None, now has value) - DEACTIVATION
        elif role and original_pic.end_date is None and new_end_date is not None:
            # Find TiketPIC records for this user and role, but ONLY for tikets with this sub_jenis_data
            _unassign_pic_from_open_tikets(
                original_pic.id_user, role, sub_jenis_data,
                tipe_label, admin_user, current_time,
                open_only=False
            )

        # Check if end_date is being cleared (was set, now is None) - REACTIVATION
        elif role and original_pic.end_date is not None and new_end_date is None:
            # No fallback logging - only log to tikets where changes were made
            _assign_pic_to_open_tikets(
                new_user, role, sub_jenis_data,
                tipe_label, admin_user, current_time
            )

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


class PICDeleteView(SafeDeleteMixin, LoginRequiredMixin, AdminAnyRequiredMixin, DeleteView):
    """Delete view for `PIC` entries and associated side-effects.

    Requires membership in any admin group (admin, admin_p3de, admin_pide, admin_pmde).
    Subclasses can further restrict with specific role mixins (e.g., AdminP3DERequiredMixin).

    Deleting a `PIC` will also find `TiketPIC` records for the same user,
    role and `id_sub_jenis_data_ilap` and delete them; a `TiketAction` log
    with `PICActionType.TIDAK_AKTIF` is created for each affected ticket.

    Response behavior:
    - AJAX clients receive a JSON payload with `success` and `redirect`.
    - Non-AJAX clients receive a JSON redirect as well and a Django
        success message is registered so the frontend can show a toast.

    Access Control:
    - Requires @login_required (LoginRequiredMixin)
    - Requires admin role (AdminAnyRequiredMixin) - blocks regular users from accessing base view
    - Subclasses further restrict with specific admin roles (e.g., AdminP3DERequiredMixin)
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
        from django.contrib.auth.models import User
        
        self.object = self.get_object()
        name = str(self.object)
        pic = self.object
        
        # Get admin user for PIC action logging
        admin_user = User.objects.get(username='admin')
        
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
                    id_user=admin_user,
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
class PICP3DEListView(UserP3DERequiredMixin, PICListView):
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


class PICPIDEListView(UserPIDERequiredMixin, PICListView):
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


class PICPMDEListView(UserPMDERequiredMixin, PICListView):
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
def _is_data_admin(request, tipe):
    """Return True if the requesting user has admin access for this PIC type."""
    user = request.user
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name='admin').exists():
        return True
    admin_group_map = {
        PIC.TipePIC.P3DE: 'admin_p3de',
        PIC.TipePIC.PIDE: 'admin_pide',
        PIC.TipePIC.PMDE: 'admin_pmde',
    }
    admin_group = admin_group_map.get(tipe)
    if admin_group and user.groups.filter(name=admin_group).exists():
        return True
    return False


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
    and `actions` HTML for edit/delete buttons (only for admin users).
    Permission checks are not enforced here; callers should wrap this
    function with appropriate decorators to restrict access.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    is_admin = _is_data_admin(request, tipe)

    qs = PIC.objects.filter(tipe=tipe).select_related('id_sub_jenis_data_ilap__id_ilap', 'id_user').all()
    
    # Apply Global Dashboard Filters
    qs = apply_global_pic_filters(qs, request, base_model='pic')
    
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ILAP
            qs = qs.filter(id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data_ilap__id_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Nama Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Username
            qs = qs.filter(id_user__username__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Full Name
            from django.db.models import Q
            qs = qs.filter(Q(id_user__first_name__icontains=columns_search[4]) |
                          Q(id_user__last_name__icontains=columns_search[4]))
        if len(columns_search) > 5 and columns_search[5]:  # Start Date
            qs = qs.filter(start_date__icontains=columns_search[5])
        if len(columns_search) > 6 and columns_search[6]:  # End Date
            qs = qs.filter(end_date__icontains=columns_search[6])

    # Global search
    search_value = request.GET.get('search[value]')
    if search_value:
        from django.db.models import Q
        qs = qs.filter(
            Q(id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=search_value) |
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
    order_columns = ['id_sub_jenis_data_ilap__id_ilap__nama_ilap', 'id_sub_jenis_data_ilap__id_sub_jenis_data', 'id_sub_jenis_data_ilap__nama_sub_jenis_data', 'id_user__username', 'id_user__first_name', 'start_date', 'end_date']
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

    # Resolved once for the whole page: whether a name is a link depends on
    # who is reading, and the rule costs a query to work out.
    can_view = pic_profil_visibility(request.user)

    # Format data
    data = []
    for obj in qs:
        user_display = f"{obj.id_user.first_name} {obj.id_user.last_name}".strip()
        if not user_display:
            user_display = obj.id_user.username
        
        row = {
            'id': obj.id,
            'ilap': obj.id_sub_jenis_data_ilap.id_ilap.nama_ilap,
            'id_sub_jenis_data': obj.id_sub_jenis_data_ilap.id_sub_jenis_data,
            'nama_sub_jenis_data': obj.id_sub_jenis_data_ilap.nama_sub_jenis_data,
            'username': obj.id_user.username,
            # The name is the way into everything else this person holds, so it
            # links to their Profil PIC page here as it does everywhere else.
            'full_name': pic_profil_link(obj.id_user, can_view, label=user_display),
            'start_date': obj.start_date.strftime('%Y-%m-%d') if obj.start_date else '',
            'end_date': obj.end_date.strftime('%Y-%m-%d') if obj.end_date else '',
        }
        
        # Only include action buttons for admin users
        if is_admin:
            row['actions'] = (
                f"<button class='btn btn-sm btn-primary me-1' data-action='edit' data-url='{reverse(update_url_name, args=[obj.pk])}' title='Edit'><i class='feather-edit'></i></button>"
                f"<button class='btn btn-sm btn-danger' data-action='delete' data-url='{reverse(delete_url_name, args=[obj.pk])}' title='Delete'><i class='feather-trash-2'></i></button>"
            )
        else:
            row['actions'] = ''
        
        data.append(row)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


@login_required
@require_GET
def pic_p3de_data(request):
    """DataTables endpoint for P3DE `PIC` rows.

    Permissions: user must be logged in and a member of `admin`,
    `admin_p3de`, or `user_p3de`. Returns the same JSON shape as
    `_pic_data_common`. Action buttons are only included for admin users.
    """
    return _pic_data_common(request, PIC.TipePIC.P3DE)


@login_required
@require_GET
def pic_pide_data(request):
    """DataTables endpoint for PIDE `PIC` rows.

    Permissions: user must be logged in and a member of `admin`,
    `admin_pide`, or `user_pide`. Returns the same JSON shape as
    `_pic_data_common`. Action buttons are only included for admin users.
    """
    return _pic_data_common(request, PIC.TipePIC.PIDE)


@login_required
@require_GET
def pic_pmde_data(request):
    """DataTables endpoint for PMDE `PIC` rows.

    Permissions: user must be logged in and a member of `admin`,
    `admin_pmde`, or `user_pmde`. Returns the same JSON shape as
    `_pic_data_common`. Action buttons are only included for admin users.
    """
    return _pic_data_common(request, PIC.TipePIC.PMDE)


class UnifiedPICListView(LoginRequiredMixin, TemplateView):
    template_name = 'pic/unified_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        is_central_admin = user.is_superuser or user.groups.filter(name='admin').exists()
        
        can_view_p3de = is_central_admin or user.groups.filter(name__in=['admin_p3de', 'user_p3de']).exists()
        can_view_pide = is_central_admin or user.groups.filter(name__in=['admin_pide', 'user_pide']).exists()
        can_view_pmde = is_central_admin or user.groups.filter(name__in=['admin_pmde', 'user_pmde']).exists()

        context['is_admin_p3de'] = user.is_superuser or user.groups.filter(name__in=['admin', 'admin_p3de']).exists()
        context['is_admin_pide'] = user.is_superuser or user.groups.filter(name__in=['admin', 'admin_pide']).exists()
        context['is_admin_pmde'] = user.is_superuser or user.groups.filter(name__in=['admin', 'admin_pmde']).exists()
        
        context['can_view_p3de'] = can_view_p3de
        context['can_view_pide'] = can_view_pide
        context['can_view_pmde'] = can_view_pmde
        
        # Calculate Summary Stats for Dashboard Widgets
        from ..models.jenis_data_ilap import JenisDataILAP
        from ..models.ilap import ILAP
        from ..models.pic import PIC
        from ..models.kategori_ilap import KategoriILAP
        import json
        from django.db.models import F, Value, CharField
        from django.db.models.functions import Concat
        
        context['total_matrix_rows'] = JenisDataILAP.objects.count()
        context['total_ilap'] = ILAP.objects.count()
        
        # Count distinct users acting as PIC per role
        context['total_pic_p3de'] = PIC.objects.filter(tipe=PIC.TipePIC.P3DE).values('id_user_id').distinct().count()
        context['total_pic_pide'] = PIC.objects.filter(tipe=PIC.TipePIC.PIDE).values('id_user_id').distinct().count()
        context['total_pic_pmde'] = PIC.objects.filter(tipe=PIC.TipePIC.PMDE).values('id_user_id').distinct().count()

        # Prepare Filter Options (JSON)
        kategori_ilap_list = list(KategoriILAP.objects.values('id', 'nama_kategori'))
        ilap_list = list(ILAP.objects.values('id', 'nama_ilap', 'id_kategori_id'))
        jenis_data_list = list(JenisDataILAP.objects.values('id', 'nama_sub_jenis_data', 'id_ilap_id'))
        
        def get_pic_users(tipe):
            qs = PIC.objects.filter(tipe=tipe, end_date__isnull=True).annotate(
                full_name=Concat('id_user__first_name', Value(' '), 'id_user__last_name', output_field=CharField())
            ).values('id_user_id', 'id_user__username', 'full_name', 'id_sub_jenis_data_ilap_id', 'id_sub_jenis_data_ilap__id_ilap_id')
            
            users_dict = {}
            for item in qs:
                uid = item['id_user_id']
                if uid not in users_dict:
                    full_name = item['full_name'].strip()
                    display_text = f"{full_name} - {item['id_user__username']}" if full_name else item['id_user__username']
                    users_dict[uid] = {
                        'id': uid,
                        'text': display_text,
                        'ilap_ids': set(),
                        'jenis_data_ids': set(),
                    }
                if item['id_sub_jenis_data_ilap__id_ilap_id']:
                    users_dict[uid]['ilap_ids'].add(item['id_sub_jenis_data_ilap__id_ilap_id'])
                if item['id_sub_jenis_data_ilap_id']:
                    users_dict[uid]['jenis_data_ids'].add(item['id_sub_jenis_data_ilap_id'])
                    
            # Convert sets to lists
            users_list = []
            for user_data in users_dict.values():
                user_data['ilap_ids'] = list(user_data['ilap_ids'])
                user_data['jenis_data_ids'] = list(user_data['jenis_data_ids'])
                users_list.append(user_data)
                
            return users_list
            
        context['filter_options'] = json.dumps({
            'kategori_ilap': [{'id': x['id'], 'text': x['nama_kategori']} for x in kategori_ilap_list],
            'ilap': [{'id': x['id'], 'text': x['nama_ilap'], 'kategori_id': x['id_kategori_id']} for x in ilap_list],
            'jenis_data': [{'id': x['id'], 'text': x['nama_sub_jenis_data'], 'ilap_id': x['id_ilap_id']} for x in jenis_data_list],
            'pic_p3de': get_pic_users(PIC.TipePIC.P3DE),
            'pic_pide': get_pic_users(PIC.TipePIC.PIDE),
            'pic_pmde': get_pic_users(PIC.TipePIC.PMDE),
        })
        # Determine default tab based on user's primary group
        default_tab = 'matrix'
        if user.groups.filter(name__in=['admin_p3de', 'user_p3de']).exists():
            default_tab = 'p3de'
        elif user.groups.filter(name__in=['admin_pide', 'user_pide']).exists():
            default_tab = 'pide'
        elif user.groups.filter(name__in=['admin_pmde', 'user_pmde']).exists():
            default_tab = 'pmde'
            
        context['default_tab'] = default_tab
        context['page_title'] = 'Daftar PIC Terpadu'
        return context

def apply_global_pic_filters(qs, request, base_model='jenis_data'):
    """Helper function to apply global filters from the PIC Dashboard to any queryset."""
    filter_ilap_kategori = request.GET.getlist('filter_ilap_kategori[]')
    filter_ilap = request.GET.getlist('filter_ilap[]')
    filter_jenis_data = request.GET.getlist('filter_jenis_data[]')
    filter_pic_p3de = request.GET.getlist('filter_pic_p3de[]')
    filter_pic_pide = request.GET.getlist('filter_pic_pide[]')
    filter_pic_pmde = request.GET.getlist('filter_pic_pmde[]')

    if base_model == 'jenis_data':
        if filter_ilap_kategori:
            qs = qs.filter(id_ilap__id_kategori_id__in=filter_ilap_kategori)
        if filter_ilap:
            qs = qs.filter(id_ilap_id__in=filter_ilap)
        if filter_jenis_data:
            qs = qs.filter(id__in=filter_jenis_data)
        if filter_pic_p3de:
            qs = qs.filter(pic__tipe='P3DE', pic__id_user_id__in=filter_pic_p3de, pic__end_date__isnull=True)
        if filter_pic_pide:
            qs = qs.filter(pic__tipe='PIDE', pic__id_user_id__in=filter_pic_pide, pic__end_date__isnull=True)
        if filter_pic_pmde:
            qs = qs.filter(pic__tipe='PMDE', pic__id_user_id__in=filter_pic_pmde, pic__end_date__isnull=True)
            
    elif base_model == 'pic':
        if filter_ilap_kategori:
            qs = qs.filter(id_sub_jenis_data_ilap__id_ilap__id_kategori_id__in=filter_ilap_kategori)
        if filter_ilap:
            qs = qs.filter(id_sub_jenis_data_ilap__id_ilap_id__in=filter_ilap)
        if filter_jenis_data:
            qs = qs.filter(id_sub_jenis_data_ilap_id__in=filter_jenis_data)
            
        if filter_pic_p3de:
            qs = qs.filter(id_sub_jenis_data_ilap__pic__tipe='P3DE', 
                           id_sub_jenis_data_ilap__pic__id_user_id__in=filter_pic_p3de,
                           id_sub_jenis_data_ilap__pic__end_date__isnull=True)
        if filter_pic_pide:
            qs = qs.filter(id_sub_jenis_data_ilap__pic__tipe='PIDE', 
                           id_sub_jenis_data_ilap__pic__id_user_id__in=filter_pic_pide,
                           id_sub_jenis_data_ilap__pic__end_date__isnull=True)
        if filter_pic_pmde:
            qs = qs.filter(id_sub_jenis_data_ilap__pic__tipe='PMDE', 
                           id_sub_jenis_data_ilap__pic__id_user_id__in=filter_pic_pmde,
                           id_sub_jenis_data_ilap__pic__end_date__isnull=True)
                           
    return qs.distinct()

@login_required
@require_GET
def pic_matrix_data(request):
    """DataTables endpoint for the Unified PIC Matrix Tab."""
    from ..models.jenis_data_ilap import JenisDataILAP
    
    try:
        draw = int(request.GET.get('draw', '1'))
    except (ValueError, TypeError):
        draw = 1
    try:
        start = int(request.GET.get('start', '0'))
    except (ValueError, TypeError):
        start = 0
    try:
        length = int(request.GET.get('length', '10'))
    except (ValueError, TypeError):
        length = 10

    # Base QuerySet: All JenisDataILAP
    qs = JenisDataILAP.objects.select_related('id_ilap').all()
    records_total = qs.count()

    # Apply Global Dashboard Filters
    qs = apply_global_pic_filters(qs, request, base_model='jenis_data')

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # ILAP
            qs = qs.filter(id_ilap__nama_ilap__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # ID Sub Jenis Data
            qs = qs.filter(id_sub_jenis_data__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # Nama Sub Jenis Data
            qs = qs.filter(nama_sub_jenis_data__icontains=columns_search[2])

    # Global search
    search_value = request.GET.get('search[value]')
    if search_value:
        from django.db.models import Q
        qs = qs.filter(
            Q(id_ilap__nama_ilap__icontains=search_value) |
            Q(nama_sub_jenis_data__icontains=search_value) |
            Q(id_sub_jenis_data__icontains=search_value)
        )

    records_filtered = qs.count()

    # Ordering
    order_column_idx = int(request.GET.get('order[0][column]', '0'))
    order_dir = request.GET.get('order[0][dir]', 'asc')
    order_columns = ['id_ilap__nama_ilap', 'id_sub_jenis_data', 'nama_sub_jenis_data']
    if 0 <= order_column_idx < len(order_columns):
        order_field = order_columns[order_column_idx]
        if order_dir == 'desc':
            order_field = f'-{order_field}'
        qs = qs.order_by(order_field)
    else:
        qs = qs.order_by('id_ilap__nama_ilap', 'id_sub_jenis_data')

    # Pagination
    qs = qs[start:start + length]

    # Pre-fetch active PICs for these JenisDataILAP
    jenis_data_ids = [obj.pk for obj in qs]
    active_pics = PIC.objects.filter(
        id_sub_jenis_data_ilap__in=jenis_data_ids,
        end_date__isnull=True
    ).select_related('id_user')
    
    # Map PICs by JenisDataILAP ID and Type
    pic_map = {}
    for pic in active_pics:
        key = (pic.id_sub_jenis_data_ilap_id, pic.tipe)
        if key not in pic_map:
            pic_map[key] = []
        
        full_name = f"{pic.id_user.first_name} {pic.id_user.last_name}".strip()
        if full_name:
            user_display = f"{full_name} - {pic.id_user.username}"
        else:
            user_display = pic.id_user.username
            
        pic_map[key].append({
            'username': pic.id_user.username,
            'display': user_display,
            'pic_id': pic.id,
            'user_id': pic.id_user_id
        })

    can_view = pic_profil_visibility(request.user)

    data = []
    for obj in qs:
        row = {
            'ilap': obj.id_ilap.nama_ilap,
            'id_sub_jenis_data': obj.id_sub_jenis_data,
            'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            'pic_p3de': '',
            'pic_pide': '',
            'pic_pmde': ''
        }
        
        for tipe, col in [(PIC.TipePIC.P3DE, 'pic_p3de'), (PIC.TipePIC.PIDE, 'pic_pide'), (PIC.TipePIC.PMDE, 'pic_pmde')]:
            pics = pic_map.get((obj.pk, tipe), [])
            if pics:
                links = []
                from django.utils.html import escape
                for p in pics:
                    # Construct mock user object for pic_profil_link
                    from collections import namedtuple
                    UserMock = namedtuple('User', ['pk', 'username'])
                    mock_user = UserMock(pk=p['user_id'], username=p['username'])
                    link_html = pic_profil_link(mock_user, can_view, label=p['display'])
                    links.append(f'<div class="text-truncate" title="{escape(p["display"])}">{link_html}</div>')
                row[col] = "".join(links)
            else:
                row[col] = '<span class="text-muted fst-italic" style="font-size: 0.8rem;">Belum ada PIC</span>'
                
        data.append(row)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


@login_required
def jenis_data_ilap_info_ajax(request, pk):
    """AJAX view to fetch classification details of a JenisDataILAP."""
    try:
        from ..models.jenis_data_ilap import JenisDataILAP
        from ..models.jenis_prioritas_data import JenisPrioritasData
        obj = JenisDataILAP.objects.select_related('id_ilap__id_kategori').get(pk=pk)
        
        # Check if it has an active priority mapping
        has_prioritas = JenisPrioritasData.objects.filter(id_sub_jenis_data_ilap=obj).exists()
        
        # Check if it has a linked periode data
        from ..models.periode_jenis_data import PeriodeJenisData
        periode_obj = PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap=obj).select_related('id_periode_pengiriman').first()
        periode_str = periode_obj.id_periode_pengiriman.periode_penyampaian if periode_obj else '-'
        
        return JsonResponse({
            'success': True,
            'kategori_ilap': obj.id_ilap.id_kategori.nama_kategori,
            'jenis_data': obj.nama_jenis_data,
            'subjenis_data': obj.nama_sub_jenis_data,
            'is_prioritas': has_prioritas,
            'periode_data': periode_str
        })
    except JenisDataILAP.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Jenis Data tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

