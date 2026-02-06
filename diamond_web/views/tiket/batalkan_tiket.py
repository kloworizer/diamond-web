"""Batalkan Tiket View"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...forms.batalkan_tiket import BatalkanTiketForm


class BatalkanTiketView(LoginRequiredMixin, UpdateView):
    """View for canceling a tiket (Batalkan Tiket)."""
    model = Tiket
    form_class = BatalkanTiketForm
    template_name = 'tiket/batalkan_tiket_form.html'

    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/batalkan_tiket_modal_form.html']
        return [self.template_name]

    def get_success_url(self):
        """Redirect back to tiket detail after saving."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('batalkan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Batalkan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to update tiket status and create action record."""
        now = datetime.now()

        self.object = form.save(commit=False)
        self.object.status = 9  # Change status to "Dibatalkan"
        self.object.tgl_dibatalkan = now
        self.object.save()

        catatan = form.cleaned_data.get('catatan', 'Tiket dibatalkan')

        TiketAction.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=now,
            action=9,
            catatan=catatan
        )

        messages.success(
            self.request,
            f'Tiket "{self.object.nomor_tiket}" telah dibatalkan.'
        )
        return super().form_valid(form)
