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
    """Allow PIDE PICs to transfer identified tikets to PMDE for quality control.

    This view enables PIDE users to transfer a tiket to PMDE (Pengendalian Mutu)
    after identification is complete. The transfer updates the tiket status and
    creates an audit trail entry with identified rows (I, U, Res, CDE).

    Model: Tiket
    Form: TransferKePMDEForm (collects identified rows: baris_i, baris_u, baris_res, baris_cde)
    Template: tiket/transfer_ke_pmde_form.html or modal variant for AJAX

    Workflow Step: PIDE transfers identified tiket to PMDE for quality control phase

    Access Control:
    - Requires @login_required
    - Requires UserPIDERequiredMixin (user must be in user_pide group)
    - Requires test_func() - user must be ACTIVE PIDE PIC AND tiket in IDENTIFIKASI status

    Side Effects on Form Submission:
    - Tiket.status set to STATUS_PENGENDALIAN_MUTU (quality control)
    - TiketAction created with:
        - action: TiketActionType.DITRANSFER_KE_PMDE
        - catatan: Identified rows summary (I, U, Res, CDE counts)
        - timestamp: Current datetime
    - Notification objects created for all active PMDE PICs for this tiket
    """
    model = Tiket
    form_class = TransferKePMDEForm
    template_name = 'tiket/transfer_ke_pmde_form.html'
    
    def test_func(self):
        """Verify user is ACTIVE PIDE PIC and tiket is in IDENTIFIKASI status.

        Returns True only if:
        1. User is actively assigned to this tiket with PIDE role
        2. Tiket.status == 5 (STATUS_IDENTIFIKASI)

        False otherwise (blocks non-PIC or wrong status tikets from being transferred).

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
            and tiket.status == 5  # STATUS_IDENTIFIKASI
        )

    def get_template_names(self):
        """Return modal template for AJAX requests, full page otherwise.

        AJAX requests (X-Requested-With=XMLHttpRequest) get a modal dialog
        template for inline display, while regular requests get full page.
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/transfer_ke_pmde_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """Build context with tiket information for the transfer form.

        Populates context with:
        - context['form_action']: URL for form submission
        - context['page_title']: Display title with tiket number
        - context['tiket']: The tiket being transferred

        Used by both single-tiket views and batch operations.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('transfer_ke_pmde', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Transfer ke PMDE - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission: update tiket status and notify PMDE.

        Within transaction:
        1. Set tiket.status to STATUS_PENGENDALIAN_MUTU
        2. Create TiketAction record with identified rows summary (I, U, Res, CDE)
        3. Query all active PMDE PICs assigned to tiket
        4. Create Notification for each PMDE PIC with formatted message
        5. Return JsonResponse (AJAX) or redirect with success message

        Raises:
        - Exception handlers catch any errors and return error responses

        Returns:
        - JsonResponse {'success': True/False, 'message': ...} for AJAX
        - Redirect to tiket detail for non-AJAX requests
        """
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
        """Return validation errors as JSON for AJAX requests.

        Handles both AJAX (returns JsonResponse with form errors) and
        non-AJAX requests (returns parent form_invalid response).
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Form tidak valid',
                'errors': form.errors
            }, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        """Redirect to tiket detail page after successful transfer.

        User is redirected back to view the tiket with updated status
        and the new audit trail entry (TiketAction) containing row counts.
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
