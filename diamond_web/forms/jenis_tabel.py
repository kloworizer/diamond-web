from django import forms
from ..models.jenis_tabel import JenisTabel

class JenisTabelForm(forms.ModelForm):
    class Meta:
        model = JenisTabel
        fields = ['deskripsi']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deskripsi'].widget.attrs.update({'class': 'form-control'})
