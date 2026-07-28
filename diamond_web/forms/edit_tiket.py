from django import forms
from django.db.models import Q
from datetime import datetime
from ..models.tiket import Tiket
from ..models.bentuk_data import BentukData
from .base import AutoRequiredFormMixin
from ..utils import validate_not_future_datetime, normalize_server_datetime, combine_date_with_current_time


class EditTiketForm(AutoRequiredFormMixin, forms.ModelForm):
    """Edit the isian of an existing tiket.

    A tiket may only be edited by its active P3DE PIC while it is in status
    Direkam and no tanda terima has been created yet; P3DE admins may edit at
    any status (both enforced in the view).

    The editable fields mirror the recording (rekam) form and reuse the exact
    same validation rules. ILAP / jenis data ILAP / status ketersediaan are
    intentionally NOT editable here — they establish the tiket's identity and
    changing them would invalidate the generated nomor tiket and PIC
    assignments.
    """

    class Meta:
        model = Tiket
        fields = [
            'periode', 'tahun', 'penyampaian',
            'nomor_surat_pengantar', 'tanggal_surat_pengantar', 'nama_pengirim',
            'id_bentuk_data', 'id_cara_penyampaian', 'baris_diterima',
            'tgl_terima_vertikal', 'tgl_terima_dip',
        ]
        widgets = {
            'periode': forms.Select(attrs={'class': 'form-control', 'id': 'id_edit_periode'}),
            'tahun': forms.Select(attrs={'class': 'form-control', 'id': 'id_edit_tahun'}),
            'penyampaian': forms.NumberInput(attrs={
                'class': 'form-control', 'id': 'id_edit_penyampaian',
                'readonly': True, 'style': 'background-color: #e9ecef;', 'min': '0',
            }),
            'nomor_surat_pengantar': forms.TextInput(attrs={'class': 'form-control'}),
            'tanggal_surat_pengantar': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d',
            ),
            'nama_pengirim': forms.TextInput(attrs={'class': 'form-control'}),
            'id_bentuk_data': forms.Select(attrs={'class': 'form-control'}),
            'id_cara_penyampaian': forms.Select(attrs={'class': 'form-control'}),
            'baris_diterima': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_edit_baris_diterima', 'min': '0'}),
            'tgl_terima_vertikal': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_terima_vertikal'},
                format='%Y-%m-%d',
            ),
            'tgl_terima_dip': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control', 'id': 'id_edit_tgl_terima_dip'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Year choices (current year to 20 years back), same as the rekam form.
        current_year = datetime.now().year
        year_choices = [(year, str(year)) for year in range(current_year - 20, current_year + 1)]
        self.fields['tahun'].widget.choices = year_choices

        # Periode options depend on the periode penerimaan and are populated
        # client-side. Seed the widget with the stored value so it renders as
        # the selected option before the JS repopulates the dropdown.
        if self.instance and self.instance.pk and self.instance.periode is not None:
            self.fields['periode'].widget.choices = [(self.instance.periode, str(self.instance.periode))]

        # Hide the "Data Tidak Tersedia" bentuk data option: a tiket recorded
        # with available data must not be switched to it here (mirrors the
        # rekam form which hides it client-side). The tiket's own bentuk data
        # is always kept selectable — a P3DE admin may edit a "data tidak
        # tersedia" tiket, and dropping its current value would force an
        # unrelated change before the form could be saved.
        bentuk_data_qs = BentukData.objects.exclude(deskripsi__icontains='tidak tersedia')
        current_bentuk_data_id = getattr(self.instance, 'id_bentuk_data_id', None)
        if current_bentuk_data_id:
            bentuk_data_qs = BentukData.objects.filter(
                Q(pk=current_bentuk_data_id) | ~Q(deskripsi__icontains='tidak tersedia')
            )
        self.fields['id_bentuk_data'].queryset = bentuk_data_qs

        # Surat pengantar fields and tanggal terima vertikal are optional
        # (mirrors the rekam form).
        self.fields['nomor_surat_pengantar'].required = False
        self.fields['tanggal_surat_pengantar'].required = False
        self.fields['nama_pengirim'].required = False
        self.fields['tgl_terima_vertikal'].required = False

    def clean_tgl_terima_vertikal(self):
        value = self.cleaned_data.get('tgl_terima_vertikal')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Terima Vertikal")

    def clean_tgl_terima_dip(self):
        value = self.cleaned_data.get('tgl_terima_dip')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Terima DIP")

    def clean_tanggal_surat_pengantar(self):
        value = self.cleaned_data.get('tanggal_surat_pengantar')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Surat Pengantar")

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
        # Validasi: tgl_terima_dip tidak boleh melebihi end_date periode.
        # id_periode_data is not editable here, so read it from the instance.
        id_periode_data = getattr(self.instance, 'id_periode_data', None)
        if id_periode_data and id_periode_data.end_date and tgl_dip:
            tgl_dip = normalize_server_datetime(tgl_dip)
            if tgl_dip.date() > id_periode_data.end_date:
                raise forms.ValidationError(
                    f'Tanggal Terima DIP ({tgl_dip.strftime("%d/%m/%Y %H:%M")}) tidak boleh '
                    f'melebihi end date periode ({id_periode_data.end_date.isoformat()}).'
                )
        return cleaned_data
