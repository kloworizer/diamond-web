from django import forms
from ..models.cara_penyampaian import CaraPenyampaian

class CaraPenyampaianForm(forms.ModelForm):
    class Meta:
        model = CaraPenyampaian
        fields = ['deskripsi']
