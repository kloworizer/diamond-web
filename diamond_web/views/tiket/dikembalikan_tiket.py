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
    """Allow PIDE PICs to return/reject tikets back to P3DE for revision.

    This view enables PIDE users to reject a tiket and send it back to P3DE
    when the data is incomplete, invalid, or needs clarification. The return
    updates the tiket status and creates an audit trail entry.

    Model: Tiket
    Form: DikembalikanTiketForm (accepts return reason/notes)
    Template: tiket/dikembalikan_tiket_form.html or modal variant for AJAX

    Workflow Step: PIDE can return tiket to P3DE during identification/analysis phase

    Access Control:
    - Requires @login_required
    - Requires UserPIDERequiredMixin (user must be in user_pide group)
    - Requires test_func() - user must be ACTIVE PIDE PIC for this tiket

    Side Effects on Form Submission:
    - Tiket.status set to STATUS_DIKEMBALIKAN (returned)
    - Tiket.tgl_dikembalikan set to current datetime
    - TiketAction created with:
        - action: TiketActionType.DIKEMBALIKAN
        - catatan: User-provided return reason
        - timestamp: Current datetime
    - Notification objects created for all active P3DE PICs for this tiket
    """
    model = Tiket
    form_class = DikembalikanTiketForm
    template_name = 'tiket/dikembalikan_tiket_form.html'
    
    def test_func(self):
        """Verify user is an ACTIVE PIDE PIC for this tiket.

        Returns True only if user is actively assigned to this tiket with
        PIDE role, False otherwise (blocks non-PIC users from editing).

        Query:
        - Filters TiketPIC by id_tiket, id_user, active=True, role=PIDE
        """
        tiket = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.PIDE
        ).exists()

    def get_template_names(self):
        """Return modal template for AJAX requests, full page otherwise.

        AJAX requests (X-Requested-With=XMLHttpRequest) get a modal dialog
        template for inline display, while regular requests get full page.
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/dikembalikan_tiket_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """Build context with tiket information for the return form.

        Populates context with:
        - context['form_action']: URL for form submission
        - context['page_title']: Display title with tiket number
        - context['tiket']: The tiket being returned

        Used by both single-tiket views and batch operations.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('dikembalikan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Kembalikan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission: update tiket status and notify P3DE.

        Within transaction:
        1. Set tiket.status to STATUS_DIKEMBALIKAN
        2. Set tiket.tgl_dikembalikan to current datetime
        3. Create TiketAction record with return reason (catatan)
        4. Query all active P3DE PICs assigned to tiket
        5. Create Notification for each P3DE PIC with formatted message
        6. Return JsonResponse (AJAX) or redirect with success message

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
        """Redirect to tiket detail page after successful return.

        User is redirected back to view the tiket with updated status
        and the new audit trail entry (TiketAction).
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
