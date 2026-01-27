from django import forms
from ..models.periode_jenis_data import PeriodeJenisData

class PeriodeJenisDataForm(forms.ModelForm):
    class Meta:
        model = PeriodeJenisData
        fields = ['id_sub_jenis_data_ilap', 'id_periode_pengiriman', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
