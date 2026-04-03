from django import forms
from ..models.status_data import StatusData

class StatusDataForm(forms.ModelForm):
    class Meta:
        model = StatusData
        fields = ['deskripsi']
