from django import forms
from django.utils import timezone
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin


class KirimKePideForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for sending tickets to PIDE.

    Collects the ND Nadine reference details before updating ticket status
    to 'Dikirim ke PIDE'. All fields are required for submission.
    """

    tgl_nadine = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'DD/MM/YYYY HH:MM',
            },
            format='%Y-%m-%dT%H:%M',
        ),
    )
    nomor_nd_nadine = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nomor ND Nadine',
            }
        ),
    )
    tgl_kirim_pide = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(
            attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'DD/MM/YYYY HH:MM',
            },
            format='%Y-%m-%dT%H:%M',
        ),
    )

    class Meta:
        model = Tiket
        fields = [
            'tgl_nadine',
            'nomor_nd_nadine',
            'tgl_kirim_pide',
        ]
