from django import forms
from ..models.tiket import Tiket
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.ilap import ILAP
from ..models.pic import PIC
from datetime import datetime

class TiketForm(forms.ModelForm):
    id_ilap = forms.ModelChoiceField(
        queryset=ILAP.objects.all(),
        empty_label="Pilih ILAP",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_ilap'
        }),
        label='ILAP',
        required=True
    )
    
    class Meta:
        model = Tiket
        fields = ['id_ilap', 'id_periode_data', 'periode', 'tahun', 'tgl_terima_vertikal', 'tgl_terima_dip']
        widgets = {
            'id_periode_data': forms.Select(attrs={'class': 'form-control', 'id': 'id_periode_data'}),
            'periode': forms.Select(attrs={'class': 'form-control', 'id': 'id_periode'}),
            'tahun': forms.Select(attrs={'class': 'form-control'}),
            'tgl_terima_vertikal': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'tgl_terima_dip': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize ILAP dropdown (only ILAP with P3DE PIC)
        self.fields['id_ilap'].queryset = ILAP.objects.filter(
            jenisdatailap__pic__tipe=PIC.TipePIC.P3DE,
            jenisdatailap__periodejenisdata__isnull=False
        ).select_related(
            'id_kategori', 'id_kategori_wilayah'
        ).distinct()
        
        # Initialize id_periode_data with empty queryset
        self.fields['id_periode_data'].queryset = PeriodeJenisData.objects.none()
        self.fields['id_periode_data'].label = 'Jenis Data ILAP'
        self.fields['id_periode_data'].required = True
        self.fields['periode'].required = True
        self.fields['periode'].widget.attrs['required'] = 'required'
        self.fields['tgl_terima_vertikal'].required = True
        self.fields['tgl_terima_dip'].required = True
        
        # Generate year choices (current year to 20 years back)
        current_year = datetime.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 20, current_year + 1)]
        self.fields['tahun'].widget.choices = year_choices
        
        # Set default value for tahun to current year if creating new instance
        if not self.instance.pk:
            self.fields['tahun'].initial = current_year
        
        # Populate id_periode_data queryset based on selected ILAP (POST or instance)
        ilap_id = None
        if self.data and self.data.get('id_ilap'):
            ilap_id = self.data.get('id_ilap')
        elif self.instance and self.instance.pk and hasattr(self.instance, 'id_periode_data') and self.instance.id_periode_data:
            ilap_id = self.instance.id_periode_data.id_sub_jenis_data_ilap.id_ilap_id
            self.fields['id_ilap'].initial = self.instance.id_periode_data.id_sub_jenis_data_ilap.id_ilap

        if ilap_id:
            self.fields['id_periode_data'].queryset = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id
            ).select_related('id_sub_jenis_data_ilap')
