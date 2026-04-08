from django import forms
from ..models.kpp import KPP
from .base import AutoRequiredFormMixin


class KPPForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = KPP
        fields = ['kode_kpp', 'nama_kpp']
