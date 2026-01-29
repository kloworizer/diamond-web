"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from datetime import datetime
from django.urls import reverse_lazy, reverse
from django.contrib import messages

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.tiket import TiketForm
from .base import WorkflowStepCreateView


class TiketRekamCreateView(WorkflowStepCreateView):
    """Create view for Rekam Tiket workflow step."""
    model = Tiket
    form_class = TiketForm
    template_name = 'tiket/workflows/rekam/form.html'
    
    def get_success_url(self):
        """Redirect to detail view after successful creation."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tiket_rekam_create')
        context['page_title'] = 'Rekam Penerimaan Data'
        context['workflow_step'] = 'rekam'
        return context

    def perform_workflow_action(self, form):
        """Implement the Rekam workflow logic."""
        periode_jenis_data = form.cleaned_data['id_periode_data']
        id_sub_jenis_data = periode_jenis_data.id_sub_jenis_data_ilap.id_sub_jenis_data
        
        # Generate nomor_tiket: id_sub_jenis_data + yymmdd + 3 digit sequence
        today = datetime.now().date()
        yymmdd = today.strftime('%y%m%d')
        
        nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
        count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
        sequence = str(count + 1).zfill(3)
        
        nomor_tiket = f"{nomor_tiket_prefix}{sequence}"
        
        # Save the tiket with status = 1 (Direkam)
        self.object = form.save(commit=False)
        self.object.nomor_tiket = nomor_tiket
        self.object.status = 1
        self.object.save()
        
        # Create tiket_action entry for audit trail
        TiketAction.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=datetime.now(),
            action=1,
            catatan="tiket direkam"
        )
        
        # Create tiket_pic entry to assign to current user
        TiketPIC.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=datetime.now(),
            role=1
        )
        
        # Return response
        if self.is_ajax_request():
            return self.get_json_response(
                success=True,
                message=f'Tiket "{nomor_tiket}" created successfully.',
                redirect=self.get_success_url()
            )
        else:
            messages.success(
                self.request,
                f'Tiket "{nomor_tiket}" created successfully.'
            )
            return None
