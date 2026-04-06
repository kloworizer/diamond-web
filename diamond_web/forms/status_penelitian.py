from django import forms
from ..models.status_penelitian import StatusPenelitian

class StatusPenelitianForm(forms.ModelForm):
    class Meta:
        model = StatusPenelitian
        fields = ['deskripsi']
        widgets = {
            'deskripsi': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan deskripsi status penelitian'
            }),
        }
