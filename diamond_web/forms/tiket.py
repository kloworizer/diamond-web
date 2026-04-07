from django import forms
from django.db.models import Q, Exists, OuterRef
from django.contrib.auth.models import Group
from ..models.tiket import Tiket
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.ilap import ILAP
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from datetime import datetime
from .base import AutoRequiredFormMixin

class TiketForm(AutoRequiredFormMixin, forms.ModelForm):
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
        fields = ['id_ilap', 'id_periode_data', 'periode', 'tahun', 'penyampaian', 'tgl_terima_vertikal', 'tgl_terima_dip', 'nomor_surat_pengantar', 'tanggal_surat_pengantar', 'nama_pengirim', 'id_bentuk_data', 'id_cara_penyampaian', 'baris_p3de', 'status_ketersediaan_data', 'alasan_ketidaktersediaan']
        widgets = {
            'id_periode_data': forms.Select(attrs={'class': 'form-control', 'id': 'id_periode_data'}),
            'periode': forms.Select(attrs={'class': 'form-control', 'id': 'id_periode'}),
            'tahun': forms.Select(attrs={'class': 'form-control'}),
            'tgl_terima_vertikal': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'tgl_terima_dip': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'nomor_surat_pengantar': forms.TextInput(attrs={'class': 'form-control'}),
            'tanggal_surat_pengantar': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'nama_pengirim': forms.TextInput(attrs={'class': 'form-control'}),
            'id_bentuk_data': forms.Select(attrs={'class': 'form-control'}),
            'id_cara_penyampaian': forms.Select(attrs={'class': 'form-control'}),
            'penyampaian': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_penyampaian', 'type': 'number', 'min': '0'}),
            'baris_p3de': forms.NumberInput(attrs={'class': 'form-control'}),
            'status_ketersediaan_data': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'alasan_ketidaktersediaan': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Alasan jika data tidak tersedia'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Get today's date for active durasi filtering
        today = datetime.now().date()
        
        # Get PIDE and PMDE groups
        pide_group = Group.objects.get(name='user_pide')
        pmde_group = Group.objects.get(name='user_pmde')
        
        # Get all JenisDataILAP IDs that have:
        # 1. PIC P3DE assigned
        # 2. Active PIDE durasi
        # 3. Active PMDE durasi
        from ..models.jenis_data_ilap import JenisDataILAP
        
        # JenisData with active P3DE PIC assignments (restricted to current user if not admin)
        if self.user and (self.user.is_superuser or self.user.groups.filter(name='admin').exists()):
            jenis_data_with_pic = JenisDataILAP.objects.values_list(
                'id_sub_jenis_data', flat=True
            ).distinct()
        else:
            from ..views.mixins import get_active_p3de_ilap_ids
            allowed_ilap_ids = set(get_active_p3de_ilap_ids(self.user))
            jenis_data_with_pic = JenisDataILAP.objects.filter(
                id_ilap_id__in=allowed_ilap_ids
            ).values_list('id_sub_jenis_data', flat=True).distinct()
        
        # JenisData with active PIDE durasi
        jenis_data_with_pide = JenisDataILAP.objects.filter(
            durasijatuhtempo__seksi=pide_group,
            durasijatuhtempo__start_date__lte=today
        ).filter(
            Q(durasijatuhtempo__end_date__isnull=True) | Q(durasijatuhtempo__end_date__gte=today)
        ).values_list('id_sub_jenis_data', flat=True).distinct()
        
        # JenisData with active PMDE durasi
        jenis_data_with_pmde = JenisDataILAP.objects.filter(
            durasijatuhtempo__seksi=pmde_group,
            durasijatuhtempo__start_date__lte=today
        ).filter(
            Q(durasijatuhtempo__end_date__isnull=True) | Q(durasijatuhtempo__end_date__gte=today)
        ).values_list('id_sub_jenis_data', flat=True).distinct()
        
        # Get intersection - JenisData that have ALL three requirements
        valid_jenis_data_ids = set(jenis_data_with_pic) & set(jenis_data_with_pide) & set(jenis_data_with_pmde)
        
        # Get valid PeriodeJenisData IDs
        valid_periode_ids = PeriodeJenisData.objects.filter(
            id_sub_jenis_data_ilap__id_sub_jenis_data__in=valid_jenis_data_ids
        ).values_list('id', flat=True)
        
        # Show only ILAPs that have at least one valid PeriodeJenisData
        self.fields['id_ilap'].queryset = ILAP.objects.filter(
            jenisdatailap__periodejenisdata__id__in=valid_periode_ids
        ).select_related(
            'id_kategori', 'id_kategori_wilayah'
        ).distinct()
        
        # Initialize id_periode_data with empty queryset
        self.fields['id_periode_data'].queryset = PeriodeJenisData.objects.none()
        self.fields['id_periode_data'].label = 'Jenis Data ILAP'
        # Django automatically sets required=True for non-nullable fields and required=False for nullable fields
        # No need to manually set required status - it's inherited from the model
        
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
            # Only show valid periode jenis data for the selected ILAP
            self.fields['id_periode_data'].queryset = PeriodeJenisData.objects.filter(
                id__in=valid_periode_ids,
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id
            ).select_related('id_sub_jenis_data_ilap').distinct()
