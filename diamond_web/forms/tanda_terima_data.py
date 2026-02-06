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
        tiket_pk = kwargs.pop('tiket_pk', None)
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'tiket_ids':
                field.widget.attrs.update({'class': 'form-control'})
        
        # If tiket_pk is provided, remove the tiket_ids field and pre-fill id_ilap
        if tiket_pk:
            # Remove the tiket_ids field entirely
            del self.fields['tiket_ids']
            # Pre-fill id_ilap from tiket
            tiket = Tiket.objects.get(pk=tiket_pk)
            if tiket.id_periode_data:
                self.fields['id_ilap'].initial = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
            # Disable ILAP dropdown for single tiket flow
            self.fields['id_ilap'].disabled = True
        # Pre-select tikets if editing
        elif self.instance.pk:
            self.fields['tiket_ids'].initial = self.instance.detil_items.values_list('id_tiket', flat=True)

    def clean_id_ilap(self):
        if self.fields['id_ilap'].disabled:
            return self.fields['id_ilap'].initial
        return self.cleaned_data.get('id_ilap')
