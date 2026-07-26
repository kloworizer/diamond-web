from django import forms
from ..models.dasar_hukum import DasarHukum
from .base import AutoRequiredFormMixin

class DasarHukumForm(AutoRequiredFormMixin, forms.ModelForm):
    class Meta:
        model = DasarHukum
        fields = ['kategori', 'deskripsi', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                f'Tanggal Berakhir ({end_date.strftime("%d/%m/%Y")}) tidak boleh sebelum '
                f'Tanggal Mulai ({start_date.strftime("%d/%m/%Y")}).'
            )
        return cleaned_data
