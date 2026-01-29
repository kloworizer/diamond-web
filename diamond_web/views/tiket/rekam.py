"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...forms.tiket import TiketForm
from .base import WorkflowStepCreateView, WorkflowStepDetailView


class TiketRekamCreateView(WorkflowStepCreateView):
    """Create view for Rekam Tiket workflow step."""
    model = Tiket
    form_class = TiketForm
    template_name = 'tiket/workflows/rekam/form.html'
    success_url = reverse_lazy('tiket_list')
    
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
        today = timezone.now().date()
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
            timestamp=timezone.now(),
            action=1,
            catatan="tiket direkam"
        )
        
        # Create tiket_pic entry to assign to current user
        TiketPIC.objects.create(
            id_tiket=self.object,
            id_user=self.request.user,
            timestamp=timezone.now(),
            role=1
        )
        
        # Return response
        if self.is_ajax_request():
            return self.get_json_response(
                success=True,
                message=f'Tiket "{nomor_tiket}" created successfully.',
                redirect=self.success_url
            )
        else:
            messages.success(
                self.request,
                f'Tiket "{nomor_tiket}" created successfully.'
            )
            return None


class TiketRekamDetailView(WorkflowStepDetailView):
    """Detail view for viewing a tiket after Rekam step."""
    model = Tiket
    template_name = 'tiket/workflows/rekam/detail.html'
    context_object_name = 'tiket'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tiket_actions'] = TiketAction.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        context['tiket_pics'] = TiketPIC.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        status_labels = {
            1: 'Direkam',
            2: 'Diteliti',
            3: 'Dikirim ke PIDE',
            4: 'Dibatalkan',
            5: 'Dikembalikan'
        }
        context['status_label'] = status_labels.get(self.object.status, '-')
        context['page_title'] = f'Detail Tiket {self.object.nomor_tiket}'
        context['workflow_step'] = 'rekam'
        return context
