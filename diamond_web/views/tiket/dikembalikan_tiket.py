"""Dikembalikan Tiket View - PIDE action to return tiket to P3DE"""

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
from ...forms.dikembalikan_tiket import DikembalikanTiketForm
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_DIKEMBALIKAN
from ..mixins import UserPIDERequiredMixin


class DikembalikanTiketView(LoginRequiredMixin, UserPIDERequiredMixin, UpdateView):
    """View for returning a tiket by PIDE (Dikembalikan)."""
    model = Tiket
    form_class = DikembalikanTiketForm
    template_name = 'tiket/dikembalikan_tiket_form.html'
    
    def test_func(self):
        """Check if user is active PIC PIDE for this tiket"""
        tiket = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.PIDE
        ).exists()

    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/dikembalikan_tiket_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('dikembalikan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Kembalikan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to return tiket and notify P3DE."""
        try:
            with transaction.atomic():
                now = datetime.now()

                self.object = form.save(commit=False)
                self.object.status = STATUS_DIKEMBALIKAN
                self.object.tgl_dikembalikan = now
                self.object.save()

                catatan = form.cleaned_data.get('catatan', 'Tiket dikembalikan oleh PIDE')

                # Create tiket action
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=now,
                    action=TiketActionType.DIKEMBALIKAN,
                    catatan=catatan
                )

                # Send notification to active P3DE PIC
                active_p3de_pics = TiketPIC.objects.filter(
                    id_tiket=self.object,
                    active=True,
                    role=TiketPIC.Role.P3DE
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
                    'Tiket <a href="{}">{}</a> telah dikembalikan oleh {} dengan catatan: {}',
                    detail_path,
                    link_text,
                    sender_name,
                    catatan
                )

                # Create notifications for each P3DE active PIC
                for pic in active_p3de_pics:
                    recipient = pic.id_user
                    Notification.objects.create(
                        recipient=recipient,
                        title='Tiket Dikembalikan',
                        message=notif_message
                    )

                message = f'Tiket "{self.object.nomor_tiket}" telah dikembalikan dan notifikasi dikirim ke P3DE.'

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
