"""Form for Sequence Tanda Terima management."""

from django import forms
from django.core.exceptions import ValidationError
from ..models.sequence_tanda_terima import SequenceTandaTerima
from ..models.tanda_terima_data import TandaTerimaData


class SequenceTandaTerimaForm(forms.ModelForm):
    """Form for creating and updating Sequence Tanda Terima entries."""

    class Meta:
        model = SequenceTandaTerima
        fields = ['seksi', 'tahun', 'nomor_terakhir']
        widgets = {
            'seksi': forms.Select(attrs={'class': 'form-select'}),
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
            'seksi': 'Seksi',
            'tahun': 'Tahun',
            'nomor_terakhir': 'Nomor Terakhir',
        }
        help_texts = {
            'seksi': 'P3DE memakai nomor ...TTD/PJ.1031/..., P3DER memakai ...TTD/PJ.1032/....',
            'tahun': 'Tahun untuk sequence ini.',
            'nomor_terakhir': 'Nomor terakhir yang sudah digunakan. Nomor berikutnya akan dimulai dari nilai ini + 1. Contoh: isi 100 maka nomor berikutnya adalah 101.',
        }

    def __init__(self, *args, seksi_choices=None, **kwargs):
        """
        Args:
            seksi_choices: The seksi the editing admin manages (``P3DE``,
                ``P3DER``); every seksi when None. A single seksi is preselected.
        """
        super().__init__(*args, **kwargs)
        if seksi_choices is not None:
            field = self.fields['seksi']
            field.choices = [(value, label) for value, label in field.choices if value in seksi_choices]
            if len(field.choices) == 1:
                # An admin of one seksi has nothing to choose.
                self.initial.setdefault('seksi', field.choices[0][0])
                field.required = False
        if self.instance.pk:
            # The series of an existing sequence is fixed.
            self.fields['seksi'].disabled = True

    def clean_seksi(self):
        """Fall back to the only seksi offered when none was posted."""
        seksi = self.cleaned_data.get('seksi')
        choices = self.fields['seksi'].choices
        if not seksi and len(choices) == 1:
            seksi = choices[0][0]
        return seksi

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
        seksi = cleaned_data.get('seksi')
        instance = self.instance

        # If editing an existing instance, check if there are already
        # TandaTerimaData for this year in the same seksi's series.
        if instance and instance.pk:
            if TandaTerimaData.objects.filter(seksi=seksi, tahun_terima=tahun).exists():
                raise ValidationError(
                    f'Tidak dapat mengubah data {seksi} untuk tahun {tahun} karena sudah ada Tanda Terima Data yang tercatat untuk tahun tersebut.'
                )
        return cleaned_data
