"""Rekam Hasil Penelitian View"""

from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.http import JsonResponse

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...forms.rekam_hasil_penelitian import RekamHasilPenelitianForm


class RekamHasilPenelitianView(LoginRequiredMixin, UpdateView):
    """View for recording research results (Rekam Hasil Penelitian)."""
    model = Tiket
    form_class = RekamHasilPenelitianForm
    template_name = 'tiket/rekam_hasil_penelitian_form.html'
    
    def get_template_names(self):
        """Return modal template for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['tiket/rekam_hasil_penelitian_modal_form.html']
        return [self.template_name]
    
    def get_success_url(self):
        """Redirect back to tiket detail after saving."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('rekam_hasil_penelitian', kwargs={'pk': self.object.pk})
        context['page_title'] = f'Rekam Hasil Penelitian - {self.object.nomor_tiket}'
        context['tiket'] = self.object
        return context

    def form_valid(self, form):
        """Handle form submission to update tiket status and create action record."""
        # Get current timestamp to use for both tiket and action
        now = datetime.now()
        
        # Update the tiket with new baris_p3de value
        self.object = form.save(commit=False)
        self.object.status = 4  # Change status to "Diteliti"
        self.object.tgl_teliti = now
        self.object.save()
        
        # Get catatan from form
        catatan = form.cleaned_data.get('catatan', 'Hasil penelitian direkam')
        
        # Create tiket_action entry for audit trail with same timestamp
        TiketAction.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=now,
            action=4,
            catatan=catatan
        )
        
        # Check if AJAX request
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        # Return response
        messages.success(
            self.request,
            f'Hasil penelitian untuk tiket "{self.object.nomor_tiket}" telah direkam.'
        )
        return super().form_valid(form)

