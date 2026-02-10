"""Transfer ke PMDE View - PIDE action to transfer tiket to PMDE"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.utils.html import format_html
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.notification import Notification
from ...forms.transfer_ke_pmde import TransferKePMDEForm
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_PENGENDALIAN_MUTU
from ..mixins import UserPIDERequiredMixin


class TransferKePMDEView(LoginRequiredMixin, UserPIDERequiredMixin, UpdateView):
    """View for transferring tiket to PMDE by PIDE."""
    model = Tiket
    form_class = TransferKePMDEForm
    template_name = 'tiket/transfer_ke_pmde_form.html'
    
    def test_func(self):
        """Check if user is active PIC PIDE for this tiket and status is 5 (Identifikasi)"""
        tiket = self.get_object()
        return (
            TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=self.request.user,
                active=True,
                role=TiketPIC.Role.PIDE
            ).exists()
            and tiket.status == 5  # STATUS_IDENTIFIKASI
        )

    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/transfer_ke_pmde_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('transfer_ke_pmde', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Transfer ke PMDE - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to transfer tiket to PMDE and notify PMDE PIC."""
        try:
            with transaction.atomic():
                now = datetime.now()

                self.object = form.save(commit=False)
                self.object.status = STATUS_PENGENDALIAN_MUTU
                self.object.save()

                # Create tiket action
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=now,
                    action=TiketActionType.DITRANSFER_KE_PMDE,
                    catatan=f'Transfer ke PMDE - I:{self.object.baris_i}, U:{self.object.baris_u}, Res:{self.object.baris_res}, CDE:{self.object.baris_cde}'
                )

                # Send notification to active PMDE PIC
                active_pmde_pics = TiketPIC.objects.filter(
                    id_tiket=self.object,
                    active=True,
                    role=TiketPIC.Role.PMDE
                ).select_related('id_user')

                # Build URLs and notification message
                try:
                    _ = self.request.build_absolute_uri(reverse('tiket_detail', kwargs={'pk': self.object.pk}))
                except Exception:
                    _ = reverse('tiket_detail', kwargs={'pk': self.object.pk})
                detail_path = reverse('tiket_detail', kwargs={'pk': self.object.pk})
                sender_name = (self.request.user.get_full_name() or self.request.user.username).strip()
                link_text = self.object.nomor_tiket or str(self.object.pk)
                
                # Use format_html to safely escape values and produce a SafeString
                notif_message = format_html(
                    'Tiket <a href="{}">{}</a> telah ditransfer ke Pengendalian Mutu oleh {}',
                    detail_path,
                    link_text,
                    sender_name
                )

                # Create notifications for each PMDE active PIC
                for pic in active_pmde_pics:
                    recipient = pic.id_user
                    Notification.objects.create(
                        recipient=recipient,
                        title='Tiket Ditransfer ke Pengendalian Mutu',
                        message=notif_message
                    )

                message = f'Tiket "{self.object.nomor_tiket}" telah ditransfer ke PMDE dan notifikasi dikirim.'

                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': message
                    })

                messages.success(self.request, message)
                return super().form_valid(form)

        except Exception as e:
            error_message = f'Gagal memperbarui tiket: {str(e)}'
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
        """Redirect back to tiket detail after saving."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
