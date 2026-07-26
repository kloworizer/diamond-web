from django import forms
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin


class SelesaikanTiketForm(AutoRequiredFormMixin, forms.ModelForm):
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

    def clean(self):
        cleaned_data = super().clean()
        lolos_qc = cleaned_data.get('lolos_qc')
        tidak_lolos_qc = cleaned_data.get('tidak_lolos_qc')

        if lolos_qc is not None and tidak_lolos_qc is not None:
            if self.instance and self.instance.baris_i is not None:
                total = lolos_qc + tidak_lolos_qc
                if total != self.instance.baris_i:
                    raise forms.ValidationError(
                        f'Lolos QC + tidak lolos QC ({total}) '
                        f'harus sama dengan baris I ({self.instance.baris_i}).'
                    )

        return cleaned_data
