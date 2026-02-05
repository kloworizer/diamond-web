"""Tiket Detail View"""

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from .base import WorkflowStepDetailView


class TiketDetailView(WorkflowStepDetailView):
    """Detail view for viewing a tiket."""
    model = Tiket
    template_name = 'tiket/tiket_detail.html'
    context_object_name = 'tiket'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Define status labels and badge classes
        status_labels = {
            1: 'Direkam',
            2: 'Backup direkam',
            3: 'Diteliti',
            4: 'Dikirim ke PIDE',
            5: 'Dibatalkan',
            6: 'Dikembalikan',
            7: 'Identifikasi',
            8: 'Pengendalian Mutu',
            9: 'Selesai'
        }
        
        action_badges = {
            1: {'label': 'Direkam', 'class': 'bg-primary'},
            2: {'label': 'Backup direkam', 'class': 'bg-info'},
            3: {'label': 'Diteliti', 'class': 'bg-secondary'},
            4: {'label': 'Dikirim ke PIDE', 'class': 'bg-warning'},
            5: {'label': 'Dibatalkan', 'class': 'bg-danger'},
            6: {'label': 'Dikembalikan', 'class': 'bg-info'},
            7: {'label': 'Identifikasi', 'class': 'bg-info'},
            8: {'label': 'Pengendalian Mutu', 'class': 'bg-secondary'},
            9: {'label': 'Selesai', 'class': 'bg-success'}
        }
        
        role_badges = {
            1: {'label': 'Admin', 'class': 'bg-success'},
            2: {'label': 'P3DE', 'class': 'bg-primary'},
            3: {'label': 'PIDE', 'class': 'bg-info'},
            4: {'label': 'PMDE', 'class': 'bg-warning'}
        }
        
        # Get actions and enrich with badge info
        tiket_actions = TiketAction.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        for action in tiket_actions:
            badge = action_badges.get(action.action, {'label': str(action.action), 'class': 'bg-secondary'})
            action.badge_label = badge['label']
            action.badge_class = badge['class']
        
        # Get PICs and enrich with badge info
        tiket_pics = TiketPIC.objects.filter(
            id_tiket=self.object
        ).select_related('id_user').order_by('-timestamp')
        
        for pic in tiket_pics:
            badge = role_badges.get(pic.role, {'label': str(pic.role), 'class': 'bg-info'})
            pic.badge_label = badge['label']
            pic.badge_class = badge['class']
        
        context['tiket_actions'] = tiket_actions
        context['tiket_pics'] = tiket_pics
        context['status_label'] = status_labels.get(self.object.status, '-')
        context['page_title'] = f'Detail Tiket {self.object.nomor_tiket}'
        
        # Get workflow step based on status
        workflow_steps = {
            1: 'rekam',
            2: 'backup',
            3: 'teliti',
            4: 'kirim_pide',
            5: 'batal',
            6: 'kembali',
            7: 'identifikasi',
            8: 'pengendalian_mutu',
            9: 'selesai'
        }
        context['workflow_step'] = workflow_steps.get(self.object.status, 'rekam')
        return context
