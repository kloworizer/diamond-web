from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin
from ..utils import validate_not_future_datetime, normalize_server_datetime


class TransferKePMDEForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for transferring tiket to PMDE by PIDE."""
    baris_i = forms.IntegerField(
        label='Baris I',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0',
            'min': '0'
        }),
        required=True
    )
    baris_u = forms.IntegerField(
        label='Baris U',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0',
            'min': '0'
        }),
        required=True
    )
    baris_res = forms.IntegerField(
        label='Baris Res',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0',
            'min': '0'
        }),
        required=True
    )
    baris_cde = forms.IntegerField(
        label='Baris CDE',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0',
            'min': '0'
        }),
        required=True
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

    def clean(self):
        cleaned_data = super().clean()

        # Validate tgl_transfer >= tgl_rekam_pide
        tgl_transfer = cleaned_data.get('tgl_transfer')
        if tgl_transfer and self.instance and self.instance.tgl_rekam_pide:
            transfer = normalize_server_datetime(tgl_transfer)
            rekam = normalize_server_datetime(self.instance.tgl_rekam_pide)
            if transfer < rekam:
                raise forms.ValidationError(
                    'Tanggal Transfer tidak boleh sebelum Tanggal Rekam PIDE '
                    f'({rekam.strftime("%d/%m/%Y %H:%M")}).'
                )

        # Validate baris sum
        baris_i = cleaned_data.get('baris_i') or 0
        baris_u = cleaned_data.get('baris_u') or 0
        baris_res = cleaned_data.get('baris_res') or 0
        baris_cde = cleaned_data.get('baris_cde') or 0

        total = baris_i + baris_u + baris_res + baris_cde
        baris_lengkap = self.instance.baris_lengkap if self.instance.pk else 0

        if baris_lengkap is not None and total != baris_lengkap:
            msg = (
                f'Jumlah Baris I + Baris U + Baris Res + Baris CDE ({total}) '
                f'tidak sama dengan Baris Lengkap ({baris_lengkap}).'
            )
            raise forms.ValidationError(msg)

        return cleaned_data
