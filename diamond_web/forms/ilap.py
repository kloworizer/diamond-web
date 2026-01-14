from django import forms
from ..models.ilap import ILAP


class ILAPForm(forms.ModelForm):
    class Meta:
        model = ILAP
        fields = ['id_ilap', 'id_kategori', 'nama_ilap']
