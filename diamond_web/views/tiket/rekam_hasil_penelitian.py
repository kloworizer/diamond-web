"""Rekam Hasil Penelitian View"""

from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.rekam_hasil_penelitian import RekamHasilPenelitianForm
from ...constants.tiket_action_types import TiketActionType
from ..mixins import UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin
from ...constants.tiket_status import STATUS_DITELITI


class RekamHasilPenelitianView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, UpdateView):
    """Allow P3DE PICs to record research results for a tiket.

    This view enables P3DE users to record research outcomes (test results,
    research date, rows found) and transition the tiket to DITELITI status.
    The submission updates the tiket and creates an audit trail entry.

    Model: Tiket
    Form: RekamHasilPenelitianForm (collects test results, research date, baris_p3de)
    Template: tiket/rekam_hasil_penelitian_form.html or modal variant for AJAX

    Workflow Step: P3DE records research findings and marks tiket as researched

    Access Control:
    - Requires @login_required
    - Requires UserP3DERequiredMixin (user must be in user_p3de group)
    - Requires ActiveTiketP3DERequiredForEditMixin - user must be ACTIVE P3DE PIC for this tiket

    Side Effects on Form Submission:
    - Tiket.status set to STATUS_DITELITI (researched)
    - Tiket.tgl_teliti set to current datetime
    - Tiket.baris_p3de updated with form value
    - TiketAction created with:
        - action: TiketActionType.DITELITI
        - catatan: User-provided notes or auto-message based on create/update
        - timestamp: Current datetime
    """
    model = Tiket
    form_class = RekamHasilPenelitianForm
    
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
    template_name = 'tiket/rekam_hasil_penelitian_form.html'
    
    def get_template_names(self):
        """Return modal template for AJAX requests, full page otherwise.

        AJAX requests (X-Requested-With=XMLHttpRequest) get a modal dialog
        template for inline display, while regular requests get full page.
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/rekam_hasil_penelitian_modal_form.html']
        return [self.template_name]
    
    def get_success_url(self):
        """Redirect to tiket detail page after successful research recording.

        User is redirected back to view the tiket with updated status
        and the new audit trail entry (TiketAction).
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        """Build context with tiket information for the research recording form.

        Populates context with:
        - context['form_action']: URL for form submission
        - context['page_title']: Display title with tiket number
        - context['tiket']: The tiket for which research results are being recorded

        Used by both single-tiket views and batch operations.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('rekam_hasil_penelitian', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Rekam Hasil Penelitian - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission: update tiket status and create audit entry.

        Within transaction:
        1. Set tiket.status to STATUS_DITELITI (researched)
        2. Set tiket.tgl_teliti to current datetime
        3. Update tiket.baris_p3de with form value
        4. Create TiketAction record with research notes (catatan)
        5. Return JsonResponse (AJAX) or redirect with success message

        Catatan generation:
        - On update: 'Hasil penelitian diubah' (research results changed)
        - On create: 'Hasil penelitian direkam' (research results recorded)
        - With form field: Uses form catatan field instead

        Returns:
        - JsonResponse {'success': True, 'message': ...} for AJAX requests
        - Redirect to tiket detail for non-AJAX requests
        """
        # Get current timestamp to use for both tiket and action
        now = datetime.now()
        
        # Update the tiket with new baris_p3de value
        self.object = form.save(commit=False)
        self.object.status = STATUS_DITELITI  # Change status to STATUS_DITELITI (Diteliti)
        self.object.tgl_teliti = now
        self.object.save()
        
        # Get catatan from form
        is_update = bool(self.object.pk)
        catatan = form.cleaned_data.get(
            'catatan',
            'Hasil penelitian diubah' if is_update else 'Hasil penelitian direkam'
        )
        
        # Create tiket_action entry for audit trail with same timestamp
        TiketAction.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=now,
            action=TiketActionType.DITELITI,
            catatan=catatan
        )
        
        # Check if AJAX request
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        # Return response
        messages.success(
            self.request,
            f'Hasil penelitian untuk tiket "{self.object.nomor_tiket}" telah direkam.'
        )
        return super().form_valid(form)

