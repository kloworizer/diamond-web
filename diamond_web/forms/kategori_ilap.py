from django import forms
from ..models.kategori_ilap import KategoriILAP

class KategoriILAPForm(forms.ModelForm):
    class Meta:
        model = KategoriILAP
        fields = ['id_kategori', 'nama_kategori']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if editing an existing instance, make id_kategori read-only
        if getattr(self.instance, 'pk', None):
            self.fields['id_kategori'].disabled = True
            self.fields['id_kategori'].widget.attrs['readonly'] = True