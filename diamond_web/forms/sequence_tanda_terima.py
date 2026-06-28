"""Form for Sequence Tanda Terima management."""

from django import forms
from django.core.exceptions import ValidationError
from ..models.sequence_tanda_terima import SequenceTandaTerima
from ..models.tanda_terima_data import TandaTerimaData


class SequenceTandaTerimaForm(forms.ModelForm):
    """Form for creating and updating Sequence Tanda Terima entries."""

    class Meta:
        model = SequenceTandaTerima
        fields = ['tahun', 'nomor_terakhir']
        widgets = {
            'tahun': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contoh: 2026',
                'min': 2020,
                'max': 2099,
            }),
            'nomor_terakhir': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nomor terakhir yang digunakan',
                'min': 0,
            }),
        }
        labels = {
            'tahun': 'Tahun',
            'nomor_terakhir': 'Nomor Terakhir',
        }
        help_texts = {
            'tahun': 'Tahun untuk sequence ini.',
            'nomor_terakhir': 'Nomor terakhir yang sudah digunakan. Nomor berikutnya akan dimulai dari nilai ini + 1. Contoh: isi 100 maka nomor berikutnya adalah 101.',
        }

    def clean_tahun(self):
        """Validate tahun is reasonable."""
        tahun = self.cleaned_data.get('tahun')
        if tahun and (tahun < 1900 or tahun > 2100):
            raise ValidationError('Tahun harus antara 1900 dan 2100.')
        return tahun

    def clean(self):
        """Check if editing is allowed when there are existing records for this year."""
        cleaned_data = super().clean()
        tahun = cleaned_data.get('tahun')
        instance = self.instance

        # If editing an existing instance, check if there are already TandaTerimaData for this year
        if instance and instance.pk:
            if TandaTerimaData.objects.filter(tahun_terima=tahun).exists():
                raise ValidationError(
                    f'Tidak dapat mengubah data untuk tahun {tahun} karena sudah ada Tanda Terima Data yang tercatat untuk tahun tersebut.'
                )
        return cleaned_data
