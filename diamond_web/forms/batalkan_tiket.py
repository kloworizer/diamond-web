from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin


class BatalkanTiketForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for canceling a tiket."""
    catatan = forms.CharField(
        label='Catatan',
        initial='Tiket dibatalkan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan catatan pembatalan',
            'rows': 4
        }),
        required=True
    )

    class Meta:
        model = Tiket
        fields = []
