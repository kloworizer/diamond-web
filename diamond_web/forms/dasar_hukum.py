from django import forms
from ..models.dasar_hukum import DasarHukum

class DasarHukumForm(forms.ModelForm):
    class Meta:
        model = DasarHukum
        fields = ['deskripsi']
