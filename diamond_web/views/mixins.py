from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin
from ..models.tiket_pic import TiketPIC


class AdminRequiredMixin(UserPassesTestMixin):
    """Require membership in the `admin` group.

    Use this mixin on class-based views to restrict access to users who
    belong to the `admin` group. It delegates to Django's
    `UserPassesTestMixin` and implements `test_func`.
    """
    def test_func(self):
        return self.request.user.groups.filter(name='admin').exists()


class AdminP3DERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `admin_p3de` groups.

    Intended for views that should be accessible by central admins and the
    P3DE administrative group. Returns True when the current user is a
    member of either group.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()


class AdminPIDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `admin_pide` groups.

    Use this for views that should be reachable by global admins and PIDE
    administrators.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide']).exists()


class AdminPMDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `admin_pmde` groups."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde']).exists()


class UserP3DERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `user_p3de` groups.

    This mixin is used when both administrative and regular P3DE users
    should be allowed access. If the request is AJAX and the user lacks
    permission, a JSON 403 response is returned to keep the client-side
    flow simple; otherwise the standard `handle_no_permission` path is
    taken.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de', 'user_p3de']).exists()

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class UserPIDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `user_pide` groups.

    Similar to `UserP3DERequiredMixin` but for PIDE users. Returns a JSON
    403 for AJAX requests when permission is denied, otherwise falls back
    to the standard `handle_no_permission` behavior.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide', 'user_pide']).exists()

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class UserPMDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `user_pmde` groups.

    Similar to `UserP3DERequiredMixin` but for PMDE users. Returns a JSON
    403 for AJAX requests when permission is denied, otherwise falls back
    to the standard `handle_no_permission` behavior.
    """
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde', 'user_pmde']).exists()

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class ActiveTiketPICRequiredMixin(UserPassesTestMixin):
    """Allow access to admins or active PICs assigned to a tiket.

    This mixin resolves the tiket instance either from `self.object` or by
    calling `get_object()`. Administrators and superusers are always
    allowed. For other users, the method verifies that the user has an
    active `TiketPIC` assignment for the tiket with one of the allowed
    roles (P3DE, PIDE, PMDE).
    """
    def test_func(self):
        user = self.request.user
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True
        tiket = getattr(self, 'object', None)
        if tiket is None:
            try:
                tiket = self.get_object()
            except Exception:
                return False
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=user,
            active=True,
            role__in=[TiketPIC.Role.P3DE, TiketPIC.Role.PIDE, TiketPIC.Role.PMDE]
        ).exists()


class ActiveTiketPICRequiredForEditMixin(UserPassesTestMixin):
    """Require active PIC assignment to allow edit operations on tiket-related objects.

    The mixin supports views where the tiket primary key may be provided via
    `kwargs['tiket_pk']`, `self.tiket_pk`, or resolved from the view's
    `get_object()` result. Superusers and `admin` group members are
    always permitted. When the permission check fails during an AJAX
    request, a JSON 403 response is returned; otherwise an HTTP 403 is
    raised.
    """
    def test_func(self):
        user = self.request.user
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True
        
        # Get tiket from kwargs or object
        tiket_pk = self.kwargs.get('tiket_pk') or getattr(self, 'tiket_pk', None)
        if tiket_pk is None:
            # Try to get from object
            try:
                obj = self.get_object()
                if hasattr(obj, 'id_tiket'):
                    tiket_pk = obj.id_tiket.pk
                elif hasattr(obj, 'id_tiket_id'):
                    tiket_pk = obj.id_tiket_id
            except Exception:
                return False
        
        if tiket_pk is None:
            return False
        
        from ..models.tiket import Tiket
        try:
            tiket = Tiket.objects.get(pk=tiket_pk)
            return TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=user,
                active=True
            ).exists()
        except Tiket.DoesNotExist:
            return False
    
    def handle_no_permission(self):
        from django.http import HttpResponseForbidden
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "message": "Anda bukan PIC aktif untuk tiket ini."}, 
                status=403
            )
        return HttpResponseForbidden("Anda bukan PIC aktif untuk tiket ini.")


class ActiveTiketP3DERequiredForEditMixin(UserPassesTestMixin):
    """Require active P3DE PIC assignment for edit operations.

    Similar to `ActiveTiketPICRequiredForEditMixin` but restricts to PICs
    whose `role` is specifically `P3DE`.
    """
    def test_func(self):
        user = self.request.user
        # Allow superuser or admin group
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True

        # Get tiket from kwargs or object
        tiket_pk = self.kwargs.get('tiket_pk') or getattr(self, 'tiket_pk', None)
        if tiket_pk is None:
            try:
                obj = self.get_object()
                if hasattr(obj, 'id_tiket'):
                    tiket_pk = obj.id_tiket.pk
                elif hasattr(obj, 'id_tiket_id'):
                    tiket_pk = obj.id_tiket_id
                elif hasattr(obj, 'pk'):
                    tiket_pk = obj.pk
            except Exception:
                return False

        if tiket_pk is None:
            return False

        from ..models.tiket import Tiket
        from ..models.tiket_pic import TiketPIC
        try:
            tiket = Tiket.objects.get(pk=tiket_pk)
            return TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=user,
                active=True,
                role=TiketPIC.Role.P3DE
            ).exists()
        except Tiket.DoesNotExist:
            return False

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "message": "Anda bukan PIC P3DE aktif untuk tiket ini."}, 
                status=403
            )
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Anda bukan PIC P3DE aktif untuk tiket ini.")


def has_active_tiket_pic(user):
    """Return True if `user` has any active `TiketPIC` assignments.

    Returns a boolean and is safe to call with `None` or anonymous users.
    """
    if not user or not user.is_authenticated:
        return False
    return TiketPIC.objects.filter(id_user=user, active=True).exists()


def get_active_p3de_ilap_ids(user):
    """Return ILAP IDs where `user` is an active P3DE PIC.

    The helper restricts PIC assignments to the P3DE `tipe`, ensures the
    assignment `start_date` is in the past, and that `end_date` is either
    null or in the future. Returns a list of distinct ILAP primary keys.
    """
    if not user or not user.is_authenticated:
        return []
    
    from datetime import datetime
    from django.db.models import Q
    from ..models.pic import PIC
    
    today = datetime.now().date()
    
    # Get ILAPs where user is assigned as P3DE PIC with active date range
    return PIC.objects.filter(
        tipe=PIC.TipePIC.P3DE,
        id_user=user,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).values_list(
        'id_sub_jenis_data_ilap__id_ilap_id',
        flat=True
    ).distinct()


def can_access_tiket_list(user):
    """Return True when `user` should be allowed to view tiket listings.

    Rules applied:
    - Superusers and `admin` group members are always allowed.
    - Members of `user_p3de`, `user_pide`, or `user_pmde` groups are
      allowed.
    - Otherwise, the user must have at least one `TiketPIC` record.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name='admin').exists():
        return True
    if user.groups.filter(name__in=['user_p3de', 'user_pide', 'user_pmde']).exists():
        return True
    return TiketPIC.objects.filter(id_user=user).exists()


class ActiveTiketPICListRequiredMixin(UserPassesTestMixin):
    """Require admin/superuser or any active `TiketPIC` assignment.

    Use this mixin for list views where any active PIC should be allowed to
    access tiket lists for their assignments.
    """
    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name='admin').exists():
            return True
        return TiketPIC.objects.filter(id_user=user, active=True).exists()


class UserFormKwargsMixin:
    """Add the current request user to form `kwargs`.

    Views that need the `user` in their form constructors can mix this in
    so forms receive `kwargs['user'] = request.user` automatically.
    """
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class AjaxFormMixin:
    """Mixin to provide consistent AJAX form handling for Create/Update views."""

    class AjaxFormMixin:
        """Provide consistent AJAX handling for Create/Update views.

        Behavior summary:
        - If the request contains the `ajax` GET parameter the view will
          return rendered form HTML (for client-side injection) instead of a
          full page.
        - On successful form submission for AJAX requests the mixin returns
          a JSON payload containing `success: true` and optionally
          `redirect` pointing to the success URL. The mixin also registers
          the configured `success_message` in Django messages so the client
          sees the toast after a full navigation.
        - Non-AJAX flows remain compatible with standard Django CBV
          behavior.
        """

        ajax_param = "ajax"
        success_message = ""

        def is_ajax(self):
            request = getattr(self, "request", None)
            return request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest"

        def render_form_html(self, form):
            """Render the form template to an HTML string (used for AJAX)."""
            return render_to_string(
                self.template_name,
                self.get_context_data(form=form),
                request=self.request,
            )

        def render_form_response(self, form):
            """Return either a JSON html payload (when `?ajax=1`) or full response."""
            if self.request.GET.get(self.ajax_param):
                return JsonResponse({"html": self.render_form_html(form)})
            return self.render_to_response(self.get_context_data(form=form))

        def form_valid(self, form):
            """Save valid form and return JSON redirect for AJAX clients.

            The method also registers `success_message` into Django messages so
            that client-side toasts can be rendered after a redirect.
            """
            self.object = form.save()
            message = self.get_success_message(form)
            if self.is_ajax():
                # For AJAX requests, set server-side message and instruct client to
                # redirect to the success URL so that the message is rendered via
                # Django messages (displayed by base template as a toast).
                if message:
                    messages.success(self.request, message)
                try:
                    redirect_url = self.get_success_url()
                except Exception:
                    redirect_url = getattr(self, 'success_url', None)
                payload = {"success": True}
                if redirect_url:
                    payload["redirect"] = redirect_url
                return JsonResponse(payload)
            if message:
                messages.success(self.request, message)
            return super().form_valid(form)

        def form_invalid(self, form):
            """Return form HTML for AJAX invalid submissions, otherwise default."""
            if self.is_ajax():
                return JsonResponse({"success": False, "html": self.render_form_html(form)})
            return super().form_invalid(form)

        def get_success_message(self, form):  # noqa: ARG002 - form kept for parity with Django patterns
            """Format and return the success message for this view.

            The method intentionally accepts `form` for signature parity with
            other patterns but does not require it.
            """
            if not self.success_message:
                return ""
            try:
                return self.success_message.format(object=self.object)
            except Exception:
                return self.success_message
