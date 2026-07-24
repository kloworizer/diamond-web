from django import forms
from django.db.models import Q, Exists, OuterRef
from django.contrib.auth.models import Group
from ..models.tiket import Tiket
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.ilap import ILAP
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from datetime import datetime
from .base import AutoRequiredFormMixin
from ..utils import validate_not_future_datetime, normalize_server_datetime

class TiketForm(AutoRequiredFormMixin, forms.ModelForm):
    satuan_data = forms.ChoiceField(
        choices=[(1, 'Baris')],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Satuan Data',
        required=True
    )
    id_ilap = forms.ModelChoiceField(
        queryset=ILAP.objects.all(),
        empty_label="Pilih ILAP",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_ilap'
        }),
        label='ILAP',
        required=True
    )

    class Meta:
        model = Tiket
        fields = ['id_ilap', 'id_periode_data', 'periode', 'tahun', 'penyampaian', 'tgl_terima_vertikal', 'tgl_terima_dip', 'nomor_surat_pengantar', 'tanggal_surat_pengantar', 'nama_pengirim', 'id_bentuk_data', 'id_cara_penyampaian', 'baris_diterima', 'satuan_data', 'status_ketersediaan_data', 'alasan_ketidaktersediaan']
        widgets = {
            'id_periode_data': forms.Select(attrs={'class': 'form-select', 'id': 'id_periode_data'}),
            'periode': forms.Select(attrs={'class': 'form-select', 'id': 'id_periode'}),
            'tahun': forms.Select(attrs={'class': 'form-select'}),
            'tgl_terima_vertikal': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'tgl_terima_dip': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'nomor_surat_pengantar': forms.TextInput(attrs={'class': 'form-control'}),
            'tanggal_surat_pengantar': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'nama_pengirim': forms.TextInput(attrs={'class': 'form-control'}),
            'id_bentuk_data': forms.Select(attrs={'class': 'form-select'}),
            'id_cara_penyampaian': forms.Select(attrs={'class': 'form-select'}),
            'penyampaian': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_penyampaian', 'type': 'number', 'min': '0'}),
            'baris_diterima': forms.NumberInput(attrs={'class': 'form-control'}),
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
        from ..views.mixins import get_active_p3de_ilap_ids
        allowed_ilap_ids = set(get_active_p3de_ilap_ids(self.user)) if self.user and self.user.is_authenticated else set()

        if self.user and (self.user.is_superuser or self.user.groups.filter(name__in=['admin', 'admin_p3de', 'kasi_p3de']).exists()):
            jenis_data_with_pic = JenisDataILAP.objects.values_list(
                'id_sub_jenis_data', flat=True
            ).distinct()
        elif allowed_ilap_ids:
            jenis_data_with_pic = JenisDataILAP.objects.filter(
                id_ilap_id__in=allowed_ilap_ids
            ).values_list('id_sub_jenis_data', flat=True).distinct()
        else:
            # Fallback when user has no specific PIC filter or form instantiated without user kwarg:
            # Show all JenisDataILAP so ILAP select dropdown is never empty
            jenis_data_with_pic = JenisDataILAP.objects.values_list(
                'id_sub_jenis_data', flat=True
            ).distinct()

        # Previously we required active PIDE/PMDE durasi here which hid ILAPs when
        # durasi entries were missing. Keep only the P3DE PIC requirement so ILAPs
        # with assigned P3DE are shown; durasi validation is enforced later
        # during tiket creation in the view.
        valid_jenis_data_ids = set(jenis_data_with_pic)

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
        # Override label_from_instance to show rich format in the dropdown
        self.fields['id_periode_data'].label_from_instance = self._format_periode_data_label
        # Django automatically sets required=True for non-nullable fields and required=False for nullable fields
        # No need to manually set required status - it's inherited from the model

        # Generate year choices (current year to 20 years back)
        current_year = datetime.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 20, current_year + 1)]
        self.fields['tahun'].widget.choices = year_choices

        # Set default value for tahun to current year if creating new instance
        if not self.instance.pk:
            self.fields['tahun'].initial = current_year

        # Make nomor_surat_pengantar, tanggal_surat_pengantar, and nama_pengirim optional
        self.fields['nomor_surat_pengantar'].required = False
        self.fields['tanggal_surat_pengantar'].required = False
        self.fields['nama_pengirim'].required = False

        # Populate id_periode_data queryset based on selected ILAP (POST or instance)
        ilap_id = None
        if self.data and self.data.get('id_ilap'):
            ilap_id = self.data.get('id_ilap')
        elif self.instance and self.instance.pk and hasattr(self.instance, 'id_periode_data') and self.instance.id_periode_data:
            ilap_id = self.instance.id_periode_data.id_sub_jenis_data_ilap.id_ilap_id
            self.fields['id_ilap'].initial = self.instance.id_periode_data.id_sub_jenis_data_ilap.id_ilap

        if ilap_id:
            # Only show valid periode jenis data for the selected ILAP
            periode_queryset = PeriodeJenisData.objects.filter(
                id__in=valid_periode_ids,
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id
            ).select_related('id_sub_jenis_data_ilap', 'id_periode_pengiriman').distinct()
            
            # For non-admin users, further filter to only show PeriodeJenisData where they are an active P3DE PIC
            if self.user and not (self.user.is_superuser or self.user.groups.filter(name='admin').exists()):
                from ..models.pic import PIC
                periode_queryset = periode_queryset.filter(
                    id_sub_jenis_data_ilap__pic__tipe='P3DE',
                    id_sub_jenis_data_ilap__pic__id_user=self.user,
                    id_sub_jenis_data_ilap__pic__start_date__lte=today,
                ).filter(
                    Q(id_sub_jenis_data_ilap__pic__end_date__isnull=True) |
                    Q(id_sub_jenis_data_ilap__pic__end_date__gte=today)
                ).distinct()

            self.fields['id_periode_data'].queryset = periode_queryset

    def _format_periode_data_label(self, obj):
        """Format PeriodeJenisData label for the dropdown."""
        label = (
            f"{obj.id_sub_jenis_data_ilap.id_sub_jenis_data} - "
            f"{obj.id_sub_jenis_data_ilap.nama_sub_jenis_data} - "
            f"{obj.id_sub_jenis_data_ilap.nama_tabel_I} - "
            f"{obj.id_periode_pengiriman.periode_penerimaan}"
        )
        if obj.end_date:
            label += f" ({obj.end_date.isoformat()})"
        return label


    def clean_tgl_terima_vertikal(self):
        value = self.cleaned_data.get('tgl_terima_vertikal')
        return validate_not_future_datetime(value, "Tanggal Terima Vertikal")

    def clean_tgl_terima_dip(self):
        value = self.cleaned_data.get('tgl_terima_dip')
        return validate_not_future_datetime(value, "Tanggal Terima DIP")

    def clean(self):
        cleaned_data = super().clean()
        tgl_vertikal = cleaned_data.get('tgl_terima_vertikal')
        tgl_dip = cleaned_data.get('tgl_terima_dip')
        if tgl_vertikal and tgl_dip:
            tgl_vertikal = normalize_server_datetime(tgl_vertikal)
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_dip < tgl_vertikal:
                raise forms.ValidationError(
                    'Tanggal Terima DIP tidak boleh sebelum Tanggal Terima Vertikal '
                    f'({tgl_vertikal.strftime("%d/%m/%Y %H:%M")}).'
                )
        # Validasi: tgl_terima_dip tidak boleh melebihi end_date periode
        id_periode_data = cleaned_data.get('id_periode_data')
        if id_periode_data and id_periode_data.end_date and tgl_dip:
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_dip.date() > id_periode_data.end_date:
                raise forms.ValidationError(
                    f'Tanggal Terima DIP ({tgl_dip.strftime("%d/%m/%Y %H:%M")}) tidak boleh '
                    f'melebihi end date periode ({id_periode_data.end_date.isoformat()}).'
                )
        return cleaned_data

    def clean_tanggal_surat_pengantar(self):
        value = self.cleaned_data.get('tanggal_surat_pengantar')
        return validate_not_future_datetime(value, "Tanggal Surat Pengantar")

    def clean_status_ketersediaan_data(self):
        # The template renders status_ketersediaan_data as radio buttons with values "1" or "0".
        # Django's CheckboxInput.value_from_datadict uses bool(value), which makes bool("0") == True.
        # We override here to correctly map "1" -> True and "0" -> False.
        value = self.data.get('status_ketersediaan_data', '1')
        return value == '1'
