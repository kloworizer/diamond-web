from django import forms
from ..models.tiket import Tiket
from ..models.detil_tanda_terima import DetilTandaTerima
from .base import AutoRequiredFormMixin
from ..utils import validate_not_future_datetime, normalize_server_datetime, combine_date_with_current_time


class RekamHasilPenelitianForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for recording research results."""

    catatan = forms.CharField(
        label='Catatan',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Masukkan catatan tambahan',
            'rows': 3
        }),
        required=False
    )

    class Meta:
        model = Tiket
        fields = ['tgl_teliti', 'baris_lengkap', 'baris_tidak_lengkap']
        labels = {
            'tgl_teliti': 'Tanggal Teliti',
            'baris_lengkap': 'Baris Lengkap',
            'baris_tidak_lengkap': 'Baris Tidak Lengkap',
        }
        widgets = {
            'tgl_teliti': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'},
                format='%Y-%m-%d',
            ),
            'baris_lengkap': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'id_baris_lengkap',
                'min': '0',
            }),
            'baris_tidak_lengkap': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'id_baris_tidak_lengkap',
                'min': '0',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tgl_teliti'].required = True
        self.fields['baris_lengkap'].required = True
        self.fields['baris_tidak_lengkap'].required = True
        self.fields['tgl_teliti'].input_formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']

        # Pre-format tgl_teliti for the date-only input
        if self.instance and self.instance.tgl_teliti:
            self.initial['tgl_teliti'] = self.instance.tgl_teliti.strftime('%Y-%m-%d')

        # Set default catatan
        default_catatan = 'Hasil penelitian diubah' if self.instance and self.instance.tgl_teliti else 'Hasil penelitian direkam'
        if not self.initial.get('catatan'):
            self.fields['catatan'].initial = default_catatan

    def clean_tgl_teliti(self):
        value = self.cleaned_data.get('tgl_teliti')
        value = combine_date_with_current_time(value)
        value = validate_not_future_datetime(value, "Tanggal Teliti")
        if value and self.instance and self.instance.tgl_terima_dip:
            value = normalize_server_datetime(value)
            tgl_terima_dip = normalize_server_datetime(self.instance.tgl_terima_dip)
            if value < tgl_terima_dip:
                raise forms.ValidationError(
                    f'Tanggal Teliti tidak boleh sebelum Tanggal Terima DIP '
                    f'({tgl_terima_dip.strftime("%d/%m/%Y %H:%M")}).'
                )

        # Tanda Terima (the step immediately before Rekam Hasil Penelitian) is
        # a separate table, not reachable via a Tiket field, so it needs its
        # own lookup here rather than being covered by the tgl_terima_dip
        # check above.
        if value and self.instance and self.instance.pk:
            detil = (
                DetilTandaTerima.objects
                .filter(id_tiket_id=self.instance.pk)
                .select_related('id_tanda_terima')
                .first()
            )
            if detil and detil.id_tanda_terima and detil.id_tanda_terima.tanggal_tanda_terima:
                tanggal_tanda_terima = normalize_server_datetime(
                    detil.id_tanda_terima.tanggal_tanda_terima
                )
                if value < tanggal_tanda_terima:
                    raise forms.ValidationError(
                        f'Tanggal Teliti tidak boleh sebelum Tanggal Tanda Terima '
                        f'({tanggal_tanda_terima.strftime("%d/%m/%Y %H:%M")}).'
                    )
        return value

    def clean(self):
        cleaned_data = super().clean()
        baris_lengkap = cleaned_data.get('baris_lengkap')
        baris_tidak_lengkap = cleaned_data.get('baris_tidak_lengkap')

        if baris_lengkap is not None and baris_tidak_lengkap is not None:
            if self.instance and self.instance.baris_diterima is not None:
                total = baris_lengkap + baris_tidak_lengkap
                if total != self.instance.baris_diterima:
                    raise forms.ValidationError(
                        f'Baris lengkap + baris tidak lengkap ({total}) '
                        f'harus sama dengan baris diterima ({self.instance.baris_diterima}).'
                    )

        return cleaned_data

