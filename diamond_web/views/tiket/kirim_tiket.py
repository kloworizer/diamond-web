"""Kirim Tiket Workflow Step - Send/Submit Tiket"""

from datetime import datetime
from django.views.generic import FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...forms.kirim_tiket import KirimTiketForm
from ..mixins import AdminRequiredMixin


class KirimTiketView(LoginRequiredMixin, AdminRequiredMixin, FormView):
    """View for Kirim Tiket workflow step."""
    form_class = KirimTiketForm
    template_name = 'tiket/workflows/kirim_tiket/form.html'
    success_url = reverse_lazy('tiket_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Kirim Tiket'
        context['workflow_step'] = 'kirim_tiket'
        context['tikets'] = Tiket.objects.all()
        return context
    
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
                
                # Update each tiket
                for tiket in tikets:
                    tiket.nomor_nd_nadine = nomor_nd_nadine
                    tiket.tgl_nadine = tgl_nadine
                    tiket.tgl_kirim_pide = tgl_kirim_pide
                    tiket.status = 3  # Change status to 3
                    tiket.save()
                    
                    # Record tiket_action for audit trail
                    TiketAction.objects.create(
                        id_tiket=tiket,
                        id_user=self.request.user,
                        timestamp=datetime.now(),
                        action=3,  # Action 3 for "Kirim"
                        catatan="tiket dikirim ke nadine/pide"
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
