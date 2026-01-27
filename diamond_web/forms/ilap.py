from django import forms
from ..models.ilap import ILAP


class KategoriChoiceField(forms.ModelChoiceField):
    """Custom ModelChoiceField that uses id_kategori as the value instead of pk."""
    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            # Try to get by id_kategori first
            return self.queryset.get(id_kategori=value)
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            # Fall back to pk for compatibility
            return self.queryset.get(pk=value)
    
    def prepare_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'id_kategori'):
            return value.id_kategori
        return value


class ILAPForm(forms.ModelForm):
    id_kategori = KategoriChoiceField(queryset=None)
    
    class Meta:
        model = ILAP
        fields = ['id_kategori', 'id_ilap', 'nama_ilap']
        widgets = {
            'id_ilap': forms.TextInput(attrs={'readonly': 'readonly'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the queryset for the custom field
        from ..models.kategori_ilap import KategoriILAP
        self.fields['id_kategori'].queryset = KategoriILAP.objects.all()
        
        # Always make id_ilap readonly visually
        self.fields['id_ilap'].widget.attrs['readonly'] = 'readonly'
        self.fields['id_ilap'].widget.attrs['class'] = 'form-control'
        self.fields['id_ilap'].required = False
        
        if self.instance.pk:
            # In edit mode, disable both id_ilap and id_kategori - only allow editing nama_ilap
            self.fields['id_ilap'].disabled = True
            self.fields['id_kategori'].disabled = True
        # In create mode, keep id_ilap readonly but not disabled so value can be submitted
