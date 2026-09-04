from django import forms
from django.contrib.auth.models import Group

from ..models.aturan_durasi_jatuh_tempo import AturanDurasiJatuhTempo
from ..models.ilap import ILAP
from ..models.jenis_data_ilap import JenisDataILAP
from .base import AutoRequiredFormMixin

SEKSI_LABELS = {'user_pide': 'PIDE', 'user_pmde': 'PMDE'}


class AturanDurasiJatuhTempoForm(AutoRequiredFormMixin, forms.ModelForm):
    """Form aturan durasi jatuh tempo satu seksi untuk satu tahun.

    ILAP dan Sub Jenis Data keduanya opsional: dikosongkan berarti aturan umum
    tahun itu. Diisi berarti pengecualian, dan yang paling spesifik menang saat
    Generate Otomatis mencari durasi.
    """

    class Meta:
        model = AturanDurasiJatuhTempo
        fields = [
            'seksi', 'tahun', 'durasi_prioritas', 'durasi_non_prioritas',
            'id_ilap', 'id_sub_jenis_data',
        ]
        widgets = {
            'tahun': forms.NumberInput(attrs={'min': 2000, 'max': 2100}),
            'durasi_prioritas': forms.NumberInput(attrs={'min': 1}),
            'durasi_non_prioritas': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['seksi'].queryset = Group.objects.filter(
            name__in=SEKSI_LABELS
        ).order_by('name')
        self.fields['seksi'].label_from_instance = (
            lambda obj: SEKSI_LABELS.get(obj.name, obj.name)
        )

        self.fields['id_ilap'].queryset = ILAP.objects.all().order_by('nama_ilap')
        self.fields['id_ilap'].required = False
        self.fields['id_ilap'].empty_label = 'Semua ILAP (aturan umum)'

        self.fields['id_sub_jenis_data'].queryset = (
            JenisDataILAP.objects.all().order_by('id_sub_jenis_data')
        )
        self.fields['id_sub_jenis_data'].required = False
        self.fields['id_sub_jenis_data'].empty_label = 'Semua Sub Jenis Data'

    def clean(self):
        cleaned_data = super().clean()
        seksi = cleaned_data.get('seksi')
        tahun = cleaned_data.get('tahun')
        id_ilap = cleaned_data.get('id_ilap')
        id_sub = cleaned_data.get('id_sub_jenis_data')

        for name in ('durasi_prioritas', 'durasi_non_prioritas'):
            nilai = cleaned_data.get(name)
            if nilai is not None and nilai < 1:
                self.add_error(name, 'Durasi harus lebih besar dari 0 hari.')

        # Sub Jenis Data yang diisi harus milik ILAP yang diisi, kalau dua-duanya
        # diisi — kalau tidak, cakupan aturannya tidak bisa dijelaskan.
        if id_sub and id_ilap and id_sub.id_ilap_id != id_ilap.pk:
            self.add_error('id_sub_jenis_data', (
                f'Sub Jenis Data "{id_sub}" bukan milik ILAP "{id_ilap}".'
            ))
            return cleaned_data

        # Tolak duplikat lebih dulu dengan pesan yang jelas, sebelum
        # UniqueConstraint database yang bicara.
        if seksi and tahun is not None:
            bentrok = AturanDurasiJatuhTempo.objects.filter(
                seksi=seksi,
                tahun=tahun,
                id_ilap=id_ilap,
                id_sub_jenis_data=id_sub,
            )
            if self.instance.pk:
                bentrok = bentrok.exclude(pk=self.instance.pk)
            if bentrok.exists():
                cakupan = id_sub or id_ilap or 'semua ILAP'
                self.add_error('tahun', (
                    f'Aturan untuk {SEKSI_LABELS.get(seksi.name, seksi.name)} tahun '
                    f'{tahun} dengan cakupan "{cakupan}" sudah ada.'
                ))

        return cleaned_data
