from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin


class SpecialRequestForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for toggling the Special Request flag of a tiket by P3DE/PIDE."""
    special_request = forms.BooleanField(
        label='Special Request',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'role': 'switch',
        }),
        required=False
    )
    catatan = forms.CharField(
        label='Catatan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan catatan perubahan special request (opsional)',
            'rows': 3
        }),
        required=False
    )

    class Meta:
        model = Tiket
        fields = ['special_request']
