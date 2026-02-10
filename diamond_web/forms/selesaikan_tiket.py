from django import forms
from ..models.tiket import Tiket


class SelesaikanTiketForm(forms.ModelForm):
    """Form for completing tiket with QC information by PMDE."""
    sudah_qc = forms.IntegerField(
        label='Sudah QC',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=True
    )
    lolos_qc = forms.IntegerField(
        label='Lolos QC',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=True
    )
    tidak_lolos_qc = forms.IntegerField(
        label='Tidak Lolos QC',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=True
    )
    qc_c = forms.IntegerField(
        label='QC C',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0'
        }),
        required=True
    )

    class Meta:
        model = Tiket
        fields = ['sudah_qc', 'lolos_qc', 'tidak_lolos_qc', 'qc_c']
