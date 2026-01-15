from django import forms
from ..models.ilap import ILAP


class ILAPForm(forms.ModelForm):
    class Meta:
        model = ILAP
        fields = ['id_kategori', 'id_ilap', 'nama_ilap']
        widgets = {
            'id_ilap': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Always make id_ilap readonly visually
        self.fields['id_ilap'].widget.attrs['readonly'] = 'readonly'
        self.fields['id_ilap'].widget.attrs['class'] = 'form-control'
        self.fields['id_ilap'].required = False
        
        if self.instance.pk:
            # In edit mode, disable both id_ilap and id_kategori - only allow editing nama_ilap
            self.fields['id_ilap'].disabled = True
            self.fields['id_kategori'].disabled = True
        # In create mode, keep id_ilap readonly but not disabled so value can be submitted
