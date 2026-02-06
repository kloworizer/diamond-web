from django import forms
from ..models.pic import PIC
from django.contrib.auth.models import User

class PICForm(forms.ModelForm):
    class Meta:
        model = PIC
        fields = ['tipe', 'id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, tipe=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If tipe is provided (for specific PIC type views), filter users by group
        if tipe:
            # Set the tipe field value and make it read-only
            if self.instance.pk is None:  # Only for new instances
                self.initial['tipe'] = tipe
                self.fields['tipe'].widget = forms.HiddenInput()
            
            # Map tipe to user group
            group_mapping = {
                PIC.TipePIC.P3DE: 'user_p3de',
                PIC.TipePIC.PIDE: 'user_pide',
                PIC.TipePIC.PMDE: 'user_pmde',
            }
            
            group_name = group_mapping.get(tipe)
            if group_name:
                self.fields['id_user'].queryset = User.objects.filter(groups__name=group_name).distinct()
        
        # Customize user field to show first_name and last_name
        self.fields['id_user'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name} ({obj.username})" if obj.first_name or obj.last_name else obj.username
