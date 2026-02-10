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
    """View for marking a tiket as identified by PIDE (Identifikasi)."""
    model = Tiket
    
    def test_func(self):
        """Check if user is active PIC PIDE for this tiket and status is 4 (Dikirim ke PIDE)"""
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
        """Handle POST request to mark tiket as identified."""
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
        """Redirect back to tiket detail after saving."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
