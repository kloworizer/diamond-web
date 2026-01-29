from django import forms
from ..models.jenis_prioritas_data import JenisPrioritasData


class JenisPrioritasDataForm(forms.ModelForm):
    class Meta:
        model = JenisPrioritasData
        fields = ['id_sub_jenis_data_ilap', 'no_nd', 'tahun', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
