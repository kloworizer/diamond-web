from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView
from diamond_web.forms.profil import ProfilForm


__all__ = ['ProfilView']


class ProfilView(LoginRequiredMixin, FormView):
    """Combined profile & password change view.

    Authenticated users can update their ``first_name``, ``last_name`` and
    optionally change their password — all on a single page.

    On success a Django ``messages.success`` toast is emitted and the page
    re-renders so the user sees the updated values immediately.
    """
    template_name = 'registration/profil.html'
    form_class = ProfilForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['instance'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['first_name'] = self.request.user.first_name
        initial['last_name'] = self.request.user.last_name
        return initial

    def form_valid(self, form):
        user = form.save()
        # Keep the user logged in after password change
        update_session_auth_hash(self.request, user)
        messages.success(self.request, 'Profil berhasil diperbarui.')
        return self.render_to_response(self.get_context_data(form=form))
