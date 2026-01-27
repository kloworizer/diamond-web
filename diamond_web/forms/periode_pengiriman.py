from django import forms
from ..models.periode_pengiriman import PeriodePengiriman

class PeriodePengirimanForm(forms.ModelForm):
    class Meta:
        model = PeriodePengiriman
        fields = ['deskripsi']
