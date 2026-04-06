from django import forms
from ..models.kanwil import Kanwil


class KanwilForm(forms.ModelForm):
    class Meta:
        model = Kanwil
        fields = ['kode_kanwil', 'nama_kanwil']
