"""Identifikasi Tiket View - PIDE action to mark tiket as identified"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.template.loader import render_to_string

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_IDENTIFIKASI
from ...forms.identifikasi_tiket import IdentifikasiTiketForm
from ..mixins import UserPIDERequiredMixin


class IdentifikasiTiketView(LoginRequiredMixin, UserPIDERequiredMixin, UpdateView):
    """Allow PIDE PICs to mark tikets as identified and start analysis.

    This view enables PIDE users to transition a tiket to IDENTIFIKASI status,
    marking the start of the identification/data analysis phase. Updates tiket
    status and creates an audit trail entry.

    Model: Tiket
    Template: Tiket detail view (redirects after POST)

    Workflow Step: PIDE marks tiket as identified after receiving it from P3DE

    Access Control:
    - Requires @login_required
    - Requires UserPIDERequiredMixin (user must be in user_pide group)
    - Requires test_func() - user must be ACTIVE PIDE PIC AND tiket in DIKIRIM_KE_PIDE status

    GET Request:
    - Returns form HTML for AJAX display in modal
    - Used by frontend to dynamically load form content

    Side Effects on POST Submission:
    - Tiket.status set to STATUS_IDENTIFIKASI
    - TiketAction created with:
        - action: TiketActionType.IDENTIFIKASI
        - catatan: 'Mulai proses identifikasi' (fixed message)
        - timestamp: Current datetime
    """
    model = Tiket
    form_class = IdentifikasiTiketForm
    
    def test_func(self):
        """Verify user is ACTIVE PIDE PIC and tiket is in DIKIRIM_KE_PIDE status.

        Returns True only if:
        1. User is actively assigned to this tiket with PIDE role
        2. Tiket.status == 4 (STATUS_DIKIRIM_KE_PIDE)

        False otherwise (blocks non-PIC or wrong status tikets from being updated).

        Queries:
        - TiketPIC for active PIDE assignment
        - Checks tiket.status on get_object()
        """
        tiket = self.get_object()
        return (
            TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=self.request.user,
                active=True,
                role=TiketPIC.Role.PIDE
            ).exists()
            and tiket.status_tiket == 4  # STATUS_DIKIRIM_KE_PIDE
        )

    def get(self, request, *args, **kwargs):
        """Handle GET request: return form HTML for AJAX modal.

        Returns form HTML that will be displayed in the modal.
        For AJAX requests, returns HTML content.

        Returns:
        - HTML form content for modal display
        """
        tiket = self.get_object()
        form = self.form_class(instance=tiket)
        
        context = {
            'form': form,
            'tiket': tiket,
            'form_action': reverse('identifikasi_tiket', kwargs={'pk': tiket.pk})
        }
        
        form_html = render_to_string('tiket/identifikasi_tiket_modal_form.html', context, request=request)
        return JsonResponse({'html': form_html})

    def post(self, request, *args, **kwargs):
        """Set self.object then delegate to Django's UpdateView form processing."""
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle valid form: mark tiket as IDENTIFIKASI and create audit entry.

        Updates tiket.status to STATUS_IDENTIFIKASI and sets tgl_rekam_pide
        from validated form data. Creates TiketAction record. Supports both
        AJAX (returns JsonResponse) and non-AJAX (redirects).

        Returns:
        - JsonResponse {'success': True, 'message': ...} for AJAX requests
        - Redirect to tiket detail for non-AJAX requests
        """
        now = datetime.now()
        tgl_rekam_pide = form.cleaned_data.get('tgl_rekam_pide') or now

        tiket = self.object
        tiket.status_tiket = STATUS_IDENTIFIKASI
        tiket.tgl_rekam_pide = tgl_rekam_pide
        tiket.save()

        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=now,
            action=TiketActionType.IDENTIFIKASI,
            catatan='Mulai proses identifikasi'
        )

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Tiket "{tiket.nomor_tiket}" telah diidentifikasi.'
            })

        messages.success(
            self.request,
            f'Tiket "{tiket.nomor_tiket}" telah diidentifikasi.'
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        """Return validation errors as JSON for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_message = ' '.join(
                str(err)
                for errors in form.errors.values()
                for err in errors
            ) or 'Format tanggal tidak valid.'
            return JsonResponse({'success': False, 'message': error_message})
        return super().form_invalid(form)

    def get_success_url(self):
        """Redirect to tiket detail page after successful status update.

        User is redirected back to view the tiket with updated status
        and the new audit trail entry (TiketAction).
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
