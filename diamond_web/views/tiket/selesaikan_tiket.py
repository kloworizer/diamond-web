"""Selesaikan Tiket View - PMDE action to complete tiket with QC information"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.selesaikan_tiket import SelesaikanTiketForm
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_PENGENDALIAN_MUTU, STATUS_SELESAI
from ..mixins import UserPMDERequiredMixin


class SelesaikanTiketView(LoginRequiredMixin, UserPMDERequiredMixin, UpdateView):
    """View for completing tiket with QC information by PMDE."""
    model = Tiket
    form_class = SelesaikanTiketForm
    template_name = 'tiket/selesaikan_tiket_form.html'
    
    def test_func(self):
        """Check if user is active PIC PMDE for this tiket and status is 6 (Pengendalian Mutu)"""
        tiket = self.get_object()
        return (
            TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=self.request.user,
                active=True,
                role=TiketPIC.Role.PMDE
            ).exists()
            and tiket.status == STATUS_PENGENDALIAN_MUTU  # STATUS_PENGENDALIAN_MUTU
        )

    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/selesaikan_tiket_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('selesaikan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Selesaikan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to complete tiket with QC information."""
        try:
            with transaction.atomic():
                now = datetime.now()

                self.object = form.save(commit=False)
                self.object.status = STATUS_SELESAI
                self.object.save()

                # Create first action: PENGENDALIAN_MUTU (to record QC phase with details)
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=now,
                    action=TiketActionType.PENGENDALIAN_MUTU,
                    catatan=f'Sudah QC:{self.object.sudah_qc}, Lolos QC:{self.object.lolos_qc}, Tidak Lolos QC:{self.object.tidak_lolos_qc}, QC C:{self.object.qc_c}'
                )

                # Create second action: SELESAI (final status)
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=now,
                    action=TiketActionType.SELESAI,
                    catatan='Tiket selesai diproses'
                )

                message = f'Tiket "{self.object.nomor_tiket}" berhasil diselesaikan.'

                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': message
                    })

                messages.success(self.request, message)
                return super().form_valid(form)

        except Exception as e:
            error_message = f'Gagal menyelesaikan tiket: {str(e)}'
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                }, status=400)
            else:
                messages.error(self.request, error_message)
                return self.form_invalid(form)

    def form_invalid(self, form):
        """Return form errors for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Form tidak valid',
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
