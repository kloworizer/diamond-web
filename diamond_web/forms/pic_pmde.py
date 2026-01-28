from django import forms
from ..models.pic_pmde import PICPMDE

class PICPMDEForm(forms.ModelForm):
    class Meta:
        model = PICPMDE
        fields = ['id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
