"""Tiket Detail View"""

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from .base import WorkflowStepDetailView


class TiketDetailView(WorkflowStepDetailView):
    """Detail view for viewing a tiket."""
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
        
        # Get workflow step based on status
        workflow_steps = {
            1: 'rekam',
            2: 'teliti',
            3: 'kirim_pide',
            4: 'batal',
            5: 'kembali'
        }
        context['workflow_step'] = workflow_steps.get(self.object.status, 'rekam')
        return context
