from django import forms
from ..models.pic_p3de import PICP3DE

class PICP3DEForm(forms.ModelForm):
    class Meta:
        model = PICP3DE
        fields = ['id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
