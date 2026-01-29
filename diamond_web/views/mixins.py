from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin to restrict access to admin users."""
    def test_func(self):
        return self.request.user.groups.filter(name__in=['admin', 'admin_p3de']).exists()


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
