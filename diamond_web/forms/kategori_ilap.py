from django import forms
from ..models.kategori_ilap import KategoriILAP

class KategoriILAPForm(forms.ModelForm):
    class Meta:
        model = KategoriILAP
        fields = ['id_kategori', 'nama_kategori']