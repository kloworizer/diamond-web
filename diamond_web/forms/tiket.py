from django import forms
from ..models.tiket import Tiket
from ..models.periode_jenis_data import PeriodeJenisData

class TiketForm(forms.ModelForm):
    class Meta:
        model = Tiket
        fields = ['id_periode_data', 'periode', 'tahun', 'tgl_terima_vertikal', 'tgl_terima_dip']
        widgets = {
            'id_periode_data': forms.Select(attrs={'class': 'form-control'}),
            'periode': forms.NumberInput(attrs={'class': 'form-control'}),
            'tahun': forms.NumberInput(attrs={'class': 'form-control'}),
            'tgl_terima_vertikal': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'tgl_terima_dip': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
