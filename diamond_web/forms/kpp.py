from django import forms
from ..models.kpp import KPP


class KPPForm(forms.ModelForm):
    class Meta:
        model = KPP
        fields = ['kode_kpp', 'nama_kpp']
