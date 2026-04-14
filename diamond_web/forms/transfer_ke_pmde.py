from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin
from ..utils import validate_not_future_datetime


class TransferKePMDEForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for transferring tiket to PMDE by PIDE."""
    baris_i = forms.IntegerField(
        label='Baris I',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=False
    )
    baris_u = forms.IntegerField(
        label='Baris U',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=False
    )
    baris_res = forms.IntegerField(
        label='Baris Res',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=False
    )
    baris_cde = forms.IntegerField(
        label='Baris CDE',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=False
    )
    tgl_transfer = forms.DateTimeField(
        label='Tanggal Transfer',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        required=True
    )

    class Meta:
        model = Tiket
        fields = ['baris_i', 'baris_u', 'baris_res', 'baris_cde', 'tgl_transfer']

    def clean_tgl_transfer(self):
        value = self.cleaned_data.get('tgl_transfer')
        return validate_not_future_datetime(value, "Tanggal Transfer")
