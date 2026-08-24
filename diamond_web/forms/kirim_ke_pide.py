from django import forms
from django.utils import timezone
from ..models.tiket import Tiket
from .base import AutoRequiredFormMixin
from ..utils import (
    validate_not_future_datetime,
    normalize_server_datetime,
    combine_date_with_current_time,
    lift_time_above,
)


class KirimKePideForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form for sending tickets to PIDE.

    Collects the ND Nadine reference details before updating ticket status
    to 'Dikirim ke PIDE'. All fields are required for submission.
    """

    tgl_nadine = forms.DateTimeField(
        required=True,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'DD/MM/YYYY',
            },
            format='%Y-%m-%d',
        ),
    )
    nomor_nd_nadine = forms.CharField(
        required=True,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nomor ND Nadine',
            }
        ),
    )
    tgl_kirim_pide = forms.DateTimeField(
        required=True,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'DD/MM/YYYY',
            },
            format='%Y-%m-%d',
        ),
    )

    class Meta:
        model = Tiket
        fields = [
            'tgl_nadine',
            'nomor_nd_nadine',
            'tgl_kirim_pide',
        ]

    def __init__(self, *args, **kwargs):
        self.tiket_list = kwargs.pop('tiket_list', None)
        super().__init__(*args, **kwargs)
        self.fields['tgl_nadine'].input_formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        self.fields['tgl_kirim_pide'].input_formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']

    def clean_tgl_nadine(self):
        value = self.cleaned_data.get('tgl_nadine')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Nadine")

    def clean_tgl_kirim_pide(self):
        value = self.cleaned_data.get('tgl_kirim_pide')
        value = combine_date_with_current_time(value)
        return validate_not_future_datetime(value, "Tanggal Kirim PIDE")

    def clean(self):
        cleaned_data = super().clean()
        tgl_nadine = cleaned_data.get('tgl_nadine')
        tgl_kirim_pide = cleaned_data.get('tgl_kirim_pide')
        tikets = self.tiket_list
        if tikets is not None:
            # A single submitted tgl_nadine/tgl_kirim_pide is applied to every
            # selected tiket, so the same-day lift below has to clear every
            # tiket's tgl_teliti floor at once -- track the highest one.
            nadine_floor = None
            kirim_floor = None
            for tiket in tikets:
                if tiket.tgl_teliti:
                    teliti = normalize_server_datetime(tiket.tgl_teliti)
                    if tgl_nadine:
                        nadine = normalize_server_datetime(tgl_nadine)
                        if nadine.date() < teliti.date():
                            raise forms.ValidationError(
                                f'Tanggal Nadine tidak boleh sebelum Tanggal Teliti '
                                f'({teliti.strftime("%d/%m/%Y %H:%M")}) untuk tiket {tiket.nomor_tiket}.'
                            )
                        if nadine.date() == teliti.date() and (nadine_floor is None or teliti > nadine_floor):
                            nadine_floor = teliti
                    if tgl_kirim_pide:
                        kirim = normalize_server_datetime(tgl_kirim_pide)
                        if kirim.date() < teliti.date():
                            raise forms.ValidationError(
                                f'Tanggal Kirim PIDE tidak boleh sebelum Tanggal Teliti '
                                f'({teliti.strftime("%d/%m/%Y %H:%M")}) untuk tiket {tiket.nomor_tiket}.'
                            )
                        if kirim.date() == teliti.date() and (kirim_floor is None or teliti > kirim_floor):
                            kirim_floor = teliti
            if nadine_floor is not None:
                tgl_nadine = lift_time_above(tgl_nadine, nadine_floor)
                cleaned_data['tgl_nadine'] = tgl_nadine
            if kirim_floor is not None:
                tgl_kirim_pide = lift_time_above(tgl_kirim_pide, kirim_floor)
                cleaned_data['tgl_kirim_pide'] = tgl_kirim_pide
        if tgl_nadine and tgl_kirim_pide:
            nadine = normalize_server_datetime(tgl_nadine)
            kirim = normalize_server_datetime(tgl_kirim_pide)
            if kirim.date() < nadine.date():
                raise forms.ValidationError(
                    'Tanggal Kirim PIDE tidak boleh sebelum Tanggal Nadine '
                    f'({nadine.strftime("%d/%m/%Y %H:%M")}).'
                )
            elif kirim.date() == nadine.date():
                cleaned_data['tgl_kirim_pide'] = lift_time_above(tgl_kirim_pide, nadine)
        return cleaned_data
