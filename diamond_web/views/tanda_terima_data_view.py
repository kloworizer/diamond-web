from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from ..models.tanda_terima_data import TandaTerimaData
from ..models.detil_tanda_terima import DetilTandaTerima

class TandaTerimaDataViewOnly(LoginRequiredMixin, DetailView):
    model = TandaTerimaData
    template_name = 'tanda_terima_data/view.html'
    context_object_name = 'tanda_terima'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detil_items'] = DetilTandaTerima.objects.filter(id_tanda_terima=self.object).select_related('id_tiket')
        return context
