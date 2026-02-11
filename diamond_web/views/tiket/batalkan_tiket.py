"""Batalkan Tiket View"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.batalkan_tiket import BatalkanTiketForm
from ...constants.tiket_action_types import TiketActionType
from ..mixins import UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin
from ...constants.tiket_status import STATUS_DIBATALKAN


class BatalkanTiketView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, UpdateView):
    """Allow P3DE PIC to cancel/reject a tiket during processing.

    This view enables P3DE users to mark a tiket as DIBATALKAN (canceled),
    typically when the data is invalid, duplicate, or no longer needed.
    The cancellation updates the tiket status and creates an audit trail entry.

    Model: Tiket
    Form: BatalkanTiketForm (accepts cancellation reason/notes)
    Template: tiket/batalkan_tiket_form.html or modal variant for AJAX
    
    Workflow Step: P3DE can cancel tiket at any point before it's sent to PIDE
    
    Access Control:
    - Requires @login_required
    - Requires UserP3DERequiredMixin (user must be in user_p3de group)
    - Requires test_func() - user must be ACTIVE P3DE PIC for this tiket

    Side Effects on Form Submission:
    - Tiket.status set to STATUS_DIBATALKAN (canceled)
    - Tiket.tgl_dibatalkan set to current datetime
    - TiketAction created with:
        - action: TiketActionType.DIBATALKAN
        - catatan: User-provided cancellation reason
        - timestamp: Current datetime
    """
    model = Tiket
    form_class = BatalkanTiketForm
    template_name = 'tiket/batalkan_tiket_form.html'
    
    def test_func(self):
        """Verify user is an ACTIVE P3DE PIC for this tiket.

        Returns True only if user is actively assigned to this tiket with
        P3DE role, False otherwise (blocks non-PIC users from editing).

        Query:
        - Filters TiketPIC by id_tiket, id_user, active=True, role=P3DE
        """
        tiket = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.P3DE
        ).exists()

    def get_template_names(self):
        """Return modal template for AJAX requests, full page otherwise.

        AJAX requests (X-Requested-With=XMLHttpRequest) get a modal dialog
        template for inline display, while regular requests get full page.
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/batalkan_tiket_modal_form.html']
        return [self.template_name]

    def get_success_url(self):
        """Redirect to the tiket detail page after cancellation.

        User is redirected back to the tiket view so they can see the
        updated status and audit trail entry.
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        """Prepare form context with action URL, title, and tiket reference."""
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('batalkan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Batalkan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to update tiket status and create action record."""
        now = datetime.now()

        self.object = form.save(commit=False)
        self.object.status = STATUS_DIBATALKAN  # Change status to STATUS_DIBATALKAN (Dibatalkan)
        self.object.tgl_dibatalkan = now
        self.object.save()

        catatan = form.cleaned_data.get('catatan', 'Tiket dibatalkan')

        TiketAction.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=now,
            action=TiketActionType.DIBATALKAN,
            catatan=catatan
        )

        messages.success(
            self.request,
            f'Tiket "{self.object.nomor_tiket}" telah dibatalkan.'
        )
        return super().form_valid(form)
