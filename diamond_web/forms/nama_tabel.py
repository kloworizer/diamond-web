from django import forms
from ..models.jenis_data_ilap import JenisDataILAP

class NamaTabelForm(forms.ModelForm):
    class Meta:
        model = JenisDataILAP
        fields = ['nama_tabel_I', 'nama_tabel_U']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
