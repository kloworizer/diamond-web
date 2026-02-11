"""Identifikasi Tiket View - PIDE action to mark tiket as identified"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_IDENTIFIKASI
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

    Side Effects on Submission:
    - Tiket.status set to STATUS_IDENTIFIKASI
    - TiketAction created with:
        - action: TiketActionType.IDENTIFIKASI
        - catatan: 'Mulai proses identifikasi' (fixed message)
        - timestamp: Current datetime
    """
    model = Tiket
    
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
            and tiket.status == 4  # STATUS_DIKIRIM_KE_PIDE
        )

    def post(self, request, *args, **kwargs):
        """Handle POST request: mark tiket as IDENTIFIKASI and create audit entry.

        Updates tiket.status to STATUS_IDENTIFIKASI and creates TiketAction record.
        Supports both AJAX (returns JsonResponse) and non-AJAX (redirects).

        Returns:
        - JsonResponse {'success': True, 'message': ...} for AJAX requests
        - Redirect to tiket detail for non-AJAX requests
        """
        tiket = self.get_object()
        now = datetime.now()

        tiket.status = STATUS_IDENTIFIKASI
        tiket.save()

        # Create tiket action
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=request.user,
            timestamp=now,
            action=TiketActionType.IDENTIFIKASI,
            catatan='Mulai proses identifikasi'
        )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Tiket "{tiket.nomor_tiket}" telah diidentifikasi.'
            })

        messages.success(
            request,
            f'Tiket "{tiket.nomor_tiket}" telah diidentifikasi.'
        )
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        """Redirect to tiket detail page after successful status update.

        User is redirected back to view the tiket with updated status
        and the new audit trail entry (TiketAction).
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
