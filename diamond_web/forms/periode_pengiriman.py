from django import forms
from ..models.periode_pengiriman import PeriodePengiriman
from .base import AutoRequiredFormMixin

class PeriodePengirimanForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = PeriodePengiriman
        fields = ['periode_penyampaian', 'periode_penerimaan']
