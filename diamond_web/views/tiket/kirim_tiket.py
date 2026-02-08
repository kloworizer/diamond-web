"""Kirim Tiket Workflow Step - Send/Submit Tiket"""

from datetime import datetime
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.kirim_tiket import KirimTiketForm
from ...constants.tiket_action_types import TiketActionType
from ..mixins import UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin


class KirimTiketView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, FormView):
    """View for Kirim Tiket workflow step."""
    form_class = KirimTiketForm
    
    # Authorization handled by ActiveTiketP3DERequiredForEditMixin
    template_name = 'tiket/kirim_tiket_form.html'
    success_url = reverse_lazy('tiket_list')

    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.is_ajax_request():
            return ['tiket/kirim_tiket_modal_form.html']
        return [self.template_name]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tiket_pk = self.kwargs.get('tiket_pk')
        context['page_title'] = 'Kirim Tiket'
        context['workflow_step'] = 'kirim_tiket'
        if tiket_pk:
            tiket = Tiket.objects.get(pk=tiket_pk)
            context['single_tiket'] = tiket
            context['form_action'] = reverse('kirim_tiket_from_tiket', kwargs={'tiket_pk': tiket_pk})
        else:
            context['tikets'] = Tiket.objects.all()
            context['form_action'] = reverse('kirim_tiket')
        return context

    def get_initial(self):
        initial = super().get_initial()
        tiket_pk = self.kwargs.get('tiket_pk')
        if tiket_pk:
            initial['tiket_ids'] = str(tiket_pk)
        return initial
    
    def is_ajax_request(self):
        """Check if the request is an AJAX request."""
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    def get_json_response(self, success=True, message="", errors=None, redirect=None):
        """Generate standardized JSON response for AJAX requests."""
        response = {
            'success': success,
            'message': message,
        }
        if errors:
            response['errors'] = errors
        if redirect:
            response['redirect'] = redirect
        return JsonResponse(response)
    
    def form_valid(self, form):
        """Handle form submission."""
        try:
            with transaction.atomic():
                nomor_nd_nadine = form.cleaned_data['nomor_nd_nadine']
                tgl_nadine = form.cleaned_data['tgl_nadine']
                tgl_kirim_pide = form.cleaned_data['tgl_kirim_pide']
                tiket_ids = [int(id.strip()) for id in form.cleaned_data['tiket_ids'].split(',') if id.strip()]
                
                # Get tikets
                tikets = Tiket.objects.filter(id__in=tiket_ids)

                # Verify user is active P3DE PIC for each tiket
                unauthorized = []
                for tiket in tikets:
                    if not TiketPIC.objects.filter(id_tiket=tiket, id_user=self.request.user, active=True, role=TiketPIC.Role.P3DE).exists():
                        unauthorized.append(tiket.nomor_tiket)
                if unauthorized:
                    msg = f"Anda bukan PIC P3DE aktif untuk tiket: {', '.join(unauthorized)}"
                    if self.is_ajax_request():
                        return self.get_json_response(success=False, message=msg)
                    messages.error(self.request, msg)
                    return self.form_invalid(form)
                
                # Update each tiket
                for tiket in tikets:
                    tiket.nomor_nd_nadine = nomor_nd_nadine
                    tiket.tgl_nadine = tgl_nadine
                    tiket.tgl_kirim_pide = tgl_kirim_pide
                    tiket.status = 4  # Change status to 4 (Dikirim ke PIDE)
                    tiket.save()
                    
                    # Record tiket_action for audit trail
                    TiketAction.objects.create(
                        id_tiket=tiket,
                        id_user=self.request.user,
                        timestamp=datetime.now(),
                        action=TiketActionType.DIKIRIM_KE_PIDE,
                        catatan="tiket dikirim ke PIDE"
                    )
                
                message = f'Successfully updated {len(tikets)} tiket(s) and sent to NADINE/PIDE.'
                
                if self.is_ajax_request():
                    return self.get_json_response(
                        success=True,
                        message=message,
                        redirect=self.success_url
                    )
                else:
                    messages.success(self.request, message)
                    return super().form_valid(form)
        
        except Exception as e:
            error_message = f'Error updating tikets: {str(e)}'
            if self.is_ajax_request():
                return self.get_json_response(
                    success=False,
                    errors={'__all__': [error_message]}
                )
            else:
                messages.error(self.request, error_message)
                return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Handle form validation errors."""
        if self.is_ajax_request():
            return self.get_json_response(
                success=False,
                errors=form.errors
            )
        return super().form_invalid(form)
