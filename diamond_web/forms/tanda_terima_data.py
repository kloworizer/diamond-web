from django import forms
from ..models.tanda_terima_data import TandaTerimaData
from ..models.tiket import Tiket


class TandaTerimaDataForm(forms.ModelForm):
    tiket_ids = forms.ModelMultipleChoiceField(
        queryset=Tiket.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Pilih Tiket"
    )
    
    class Meta:
        model = TandaTerimaData
        fields = ['nomor_tanda_terima', 'tanggal_tanda_terima', 'id_ilap', 'deskripsi']
        widgets = {
            'tanggal_tanda_terima': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'tiket_ids':
                field.widget.attrs.update({'class': 'form-control'})
        
        # Pre-select tikets if editing
        if self.instance.pk:
            self.fields['tiket_ids'].initial = self.instance.detil_items.values_list('id_tiket', flat=True)
