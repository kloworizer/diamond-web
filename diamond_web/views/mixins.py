from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin
from ..models.tiket_pic import TiketPIC


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin users."""
    def test_func(self):
        return self.request.user.groups.filter(name='admin').exists()


class AdminP3DERequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin and admin_p3de users."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()


class AdminPIDERequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin and admin_pide users."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide']).exists()


class AdminPMDERequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin and admin_pmde users."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde']).exists()


class UserP3DERequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin and user_p3de users."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'user_p3de']).exists()

    def handle_no_permission(self):
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class ActiveTiketPICRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin or active PIC assigned to tiket."""
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
    """Mixin to restrict edit operations to admin or active PIC assigned to tiket."""
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


def has_active_tiket_pic(user):
    if not user or not user.is_authenticated:
        return False
    return TiketPIC.objects.filter(id_user=user, active=True).exists()


def get_active_p3de_ilap_ids(user):
    """Get all ILAP IDs where user is assigned as P3DE PIC with active date range."""
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
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name='admin').exists():
        return True
    if user.groups.filter(name__in=['user_p3de', 'user_pide', 'user_pmde']).exists():
        return True
    return TiketPIC.objects.filter(id_user=user).exists()


class ActiveTiketPICListRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin/superuser or any active PIC."""
    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name='admin').exists():
            return True
        return TiketPIC.objects.filter(id_user=user, active=True).exists()


class UserFormKwargsMixin:
    """Mixin to pass request user into form kwargs."""
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class AjaxFormMixin:
    """Mixin to provide consistent AJAX form handling for Create/Update views."""

    ajax_param = "ajax"
    success_message = ""

    def is_ajax(self):
        request = getattr(self, "request", None)
        return request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def render_form_html(self, form):
        return render_to_string(
            self.template_name,
            self.get_context_data(form=form),
            request=self.request,
        )

    def render_form_response(self, form):
        if self.request.GET.get(self.ajax_param):
            return JsonResponse({"html": self.render_form_html(form)})
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        self.object = form.save()
        message = self.get_success_message(form)
        if self.is_ajax():
            payload = {"success": True}
            if message:
                payload["message"] = message
            return JsonResponse(payload)
        if message:
            messages.success(self.request, message)
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.is_ajax():
            return JsonResponse({"success": False, "html": self.render_form_html(form)})
        return super().form_invalid(form)

    def get_success_message(self, form):  # noqa: ARG002 - form kept for parity with Django patterns
        if not self.success_message:
            return ""
        try:
            return self.success_message.format(object=self.object)
        except Exception:
            return self.success_message
