from django import forms
from ..models.pic_p3de import PICP3DE
from django.contrib.auth.models import User

class PICP3DEForm(forms.ModelForm):
    class Meta:
        model = PICP3DE
        fields = ['id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter users to only show those in user_p3de group
        self.fields['id_user'].queryset = User.objects.filter(groups__name='user_p3de').distinct()
        # Customize user field to show first_name and last_name
        self.fields['id_user'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name} ({obj.username})" if obj.first_name or obj.last_name else obj.username
