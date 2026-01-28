from django import forms
from ..models.pic_pide import PICPIDE

class PICPIDEForm(forms.ModelForm):
    class Meta:
        model = PICPIDE
        fields = ['id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
