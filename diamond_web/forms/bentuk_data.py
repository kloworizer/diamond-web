from django import forms
from ..models.bentuk_data import BentukData

class BentukDataForm(forms.ModelForm):
    class Meta:
        model = BentukData
        fields = ['deskripsi']
