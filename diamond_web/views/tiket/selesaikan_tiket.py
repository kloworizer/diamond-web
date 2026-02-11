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
    """Allow PMDE PICs to complete tikets with quality control information.

    This view enables PMDE users to finalize a tiket with quality control (QC)
    information and transition it to SELESAI (completed) status. The completion
    updates the tiket and creates two audit trail entries (QC phase and completion).

    Model: Tiket
    Form: SelesaikanTiketForm (collects QC data: sudah_qc, lolos_qc, tidak_lolos_qc, qc_c)
    Template: tiket/selesaikan_tiket_form.html or modal variant for AJAX

    Workflow Step: PMDE completes tiket with QC results (final step)

    Access Control:
    - Requires @login_required
    - Requires UserPMDERequiredMixin (user must be in user_pmde group)
    - Requires test_func() - user must be ACTIVE PMDE PIC AND tiket in PENGENDALIAN_MUTU status

    Side Effects on Form Submission:
    - Tiket.status set to STATUS_SELESAI (completed)
    - Two TiketAction records created with same timestamp:
        1. PENGENDALIAN_MUTU action: Records QC summary (sudah_qc, lolos_qc, tidak_lolos_qc, qc_c counts)
        2. SELESAI action: Marks completion ('Tiket selesai diproses')
    """
    model = Tiket
    form_class = SelesaikanTiketForm
    template_name = 'tiket/selesaikan_tiket_form.html'
    
    def test_func(self):
        """Verify user is ACTIVE PMDE PIC and tiket is in PENGENDALIAN_MUTU status.

        Returns True only if:
        1. User is actively assigned to this tiket with PMDE role
        2. Tiket.status == STATUS_PENGENDALIAN_MUTU (6)

        False otherwise (blocks non-PIC or wrong status tikets from being completed).

        Queries:
        - TiketPIC for active PMDE assignment
        - Checks tiket.status on get_object()
        """
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
        """Return modal template for AJAX requests, full page otherwise.

        AJAX requests (X-Requested-With=XMLHttpRequest) get a modal dialog
        template for inline display, while regular requests get full page.
        """
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/selesaikan_tiket_modal_form.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        """Build context with tiket information for the completion form.

        Populates context with:
        - context['form_action']: URL for form submission
        - context['page_title']: Display title with tiket number
        - context['tiket']: The tiket being completed

        Used by both single-tiket views and batch operations.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('selesaikan_tiket', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Selesaikan Tiket - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission: finalize tiket with QC information.

        Within transaction:
        1. Set tiket.status to STATUS_SELESAI
        2. Create TiketAction with PENGENDALIAN_MUTU action (records QC phase with counts)
        3. Create TiketAction with SELESAI action (marks final completion)
        4. Return JsonResponse (AJAX) or redirect with success message

        QC Information Captured:
        - sudah_qc: Count of records that have undergone QC
        - lolos_qc: Count of records that passed QC
        - tidak_lolos_qc: Count of records that failed QC
        - qc_c: QC C flag or count

        Returns:
        - JsonResponse {'success': True/False, 'message': ...} for AJAX
        - Redirect to tiket detail for non-AJAX requests
        """
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
        """Redirect to tiket detail page after successful completion.

        User is redirected back to view the tiket with final SELESAI status
        and both audit trail entries (PENGENDALIAN_MUTU and SELESAI actions).
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
