from django import forms
from django.contrib.auth.models import Group
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo

class DurasiJatuhTempoForm(forms.ModelForm):
    # Custom field to display friendly names
    seksi = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        label='Seksi',
        disabled=True
    )
    
    class Meta:
        model = DurasiJatuhTempo
        fields = ['id_sub_jenis_data', 'seksi', 'durasi', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        group_name = kwargs.pop('group_name', None)
        super().__init__(*args, **kwargs)
        
        if group_name:
            # Filter seksi to only show the specific group
            self.fields['seksi'].queryset = Group.objects.filter(name=group_name)
            
            # Set initial value if creating new record
            if not self.instance.pk:
                try:
                    group = Group.objects.get(name=group_name)
                    self.fields['seksi'].initial = group
                except Group.DoesNotExist:
                    pass
            
            # Customize the display label
            def label_from_instance(obj):
                if obj.name == 'user_pide':
                    return 'PIDE'
                elif obj.name == 'user_pmde':
                    return 'PMDE'
                return obj.name
            
            self.fields['seksi'].label_from_instance = label_from_instance
