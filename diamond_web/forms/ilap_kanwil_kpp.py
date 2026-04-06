from django import forms
from ..models.ilap_kanwil_kpp import ILAPKanwilKPP


class ILAPKanwilKPPForm(forms.ModelForm):
    class Meta:
        model = ILAPKanwilKPP
        fields = ['id_ilap', 'id_kpp']
