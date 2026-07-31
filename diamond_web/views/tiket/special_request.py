"""Special Request View - P3DE/PIDE action to toggle the special request flag"""

from datetime import datetime
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.special_request import SpecialRequestForm
from ...constants.tiket_action_types import SpecialRequestActionType
from ...constants.tiket_status import (
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
)


class SpecialRequestView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allow the active PIC that owns the tiket to toggle its special request flag.

    Model: Tiket
    Form: SpecialRequestForm (special_request checkbox + tgl_special_request
          due date + optional catatan)
    Template: tiket/special_request_modal_form.html (AJAX modal)

    Access Control:
    - Requires @login_required
    - Requires test_func() - user must be the ACTIVE PIC whose role owns the
      tiket for its current status:
        * status 1-3 -> active P3DE PIC
        * status 4-5 -> active PIDE PIC
        * status 6   -> active PMDE PIC
        * status 7-8 -> nobody (final states)

    Side Effects on Form Submission:
    - Tiket.special_request updated to the submitted value
    - Tiket.tgl_special_request updated to the submitted due date (cleared by
      the form whenever special_request is off)
    - TiketAction created only when the flag or the due date actually changed:
        - action: SpecialRequestActionType.DIAKTIFKAN / DINONAKTIFKAN
        - catatan: user note, or a default description naming the due date
    """
    model = Tiket
    form_class = SpecialRequestForm
    template_name = 'tiket/special_request_modal_form.html'

    def test_func(self):
        """Verify the user is the ACTIVE PIC that owns the tiket for its status.

        The role allowed to edit follows the tiket status; final statuses
        (Dibatalkan/Selesai) allow no one.
        """
        tiket = self.get_object()
        status = tiket.status_tiket
        if status in (STATUS_DIREKAM, STATUS_DITELITI, STATUS_DIKEMBALIKAN):
            role = TiketPIC.Role.P3DE
        elif status in (STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI):
            role = TiketPIC.Role.PIDE
        elif status == STATUS_PENGENDALIAN_MUTU:
            role = TiketPIC.Role.PMDE
        else:  # STATUS_DIBATALKAN, STATUS_SELESAI
            return False
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=self.request.user,
            active=True,
            role=role,
        ).exists()

    def handle_no_permission(self):
        """Return a JSON 403 for AJAX requests, standard handling otherwise."""
        request = getattr(self, 'request', None)
        if request is not None and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        return super().handle_no_permission()

    def get_context_data(self, **kwargs):
        """Build context with tiket information for the special request form."""
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('special_request_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Ubah Permintaan Khusus - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    @staticmethod
    def _format_due_date(value):
        """Render the due date for the audit note / toast message."""
        return value.strftime('%d-%m-%Y') if value else 'tidak ditentukan'

    def form_valid(self, form):
        """Handle form submission: update the flag and record the audit trail.

        Within transaction:
        1. Compare submitted flag and due date with the stored ones
        2. Save tiket with the new special_request / tgl_special_request values
        3. Create a TiketAction only when either of them changed
        4. Return JsonResponse (AJAX) or redirect with success message
        """
        try:
            with transaction.atomic():
                now = datetime.now()

                previous = Tiket.objects.filter(pk=self.object.pk).values(
                    'special_request', 'tgl_special_request'
                ).first() or {}

                self.object = form.save(commit=False)
                new_value = self.object.special_request
                new_due_date = self.object.tgl_special_request
                self.object.save(update_fields=['special_request', 'tgl_special_request'])

                flag_changed = previous.get('special_request') != new_value
                due_date_changed = previous.get('tgl_special_request') != new_due_date
                if flag_changed or due_date_changed:
                    catatan = (form.cleaned_data.get('catatan') or '').strip()
                    due_date_text = self._format_due_date(new_due_date)
                    if new_value:
                        action = SpecialRequestActionType.DIAKTIFKAN
                        if flag_changed:
                            default_catatan = f'permintaan khusus diaktifkan, jatuh tempo {due_date_text}'
                        else:
                            default_catatan = f'jatuh tempo permintaan khusus diubah menjadi {due_date_text}'
                    else:
                        action = SpecialRequestActionType.DINONAKTIFKAN
                        default_catatan = 'permintaan khusus dinonaktifkan'

                    TiketAction.objects.create(
                        id_tiket=self.object,
                        id_user=self.request.user,
                        timestamp=now,
                        action=action,
                        catatan=catatan or default_catatan
                    )

                    if flag_changed:
                        status_text = 'diaktifkan' if new_value else 'dinonaktifkan'
                        message = f'Permintaan Khusus tiket "{self.object.nomor_tiket}" telah {status_text}.'
                    else:
                        message = (
                            f'Jatuh tempo Permintaan Khusus tiket "{self.object.nomor_tiket}" '
                            f'telah diubah menjadi {due_date_text}.'
                        )
                else:
                    message = f'Permintaan Khusus tiket "{self.object.nomor_tiket}" tidak berubah.'

                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': message,
                        'special_request': new_value,
                        'tgl_special_request': (
                            new_due_date.strftime('%d-%m-%Y') if new_due_date else None
                        ),
                    })

                messages.success(self.request, message)
                return super().form_valid(form)

        except Exception as e:
            error_message = f'Gagal memperbarui permintaan khusus: {str(e)}'
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                }, status=400)
            else:
                messages.error(self.request, error_message)
                return self.form_invalid(form)

    def form_invalid(self, form):
        """Return validation errors as JSON for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_messages = []
            for field, errors in form.errors.items():
                for err in errors:
                    error_messages.append(f'{field}: {err}' if field != '__all__' else err)
            message = '; '.join(error_messages) or 'Form tidak valid'
            return JsonResponse({
                'success': False,
                'message': message,
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        """Redirect to tiket detail page after a successful update."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
