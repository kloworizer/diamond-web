from django.contrib import messages
from django.http import JsonResponse
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


def has_active_tiket_pic(user):
    if not user or not user.is_authenticated:
        return False
    return TiketPIC.objects.filter(id_user=user, active=True).exists()


def can_access_tiket_list(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name='admin').exists():
        return True
    if user.groups.filter(name='user_p3de').exists():
        return True
    return has_active_tiket_pic(user)


class ActiveTiketPICListRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict list access to admin/superuser, user_p3de, or any active PIC."""
    def test_func(self):
        return can_access_tiket_list(self.request.user)


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
