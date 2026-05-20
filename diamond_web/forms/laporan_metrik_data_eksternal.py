from django import forms
from import_export import resources, fields

import calendar
from datetime import datetime

from ..models.ilap import ILAP 
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.tiket import Tiket
from ..constants.tiket_status import STATUS_LABELS
from ..constants.jenis_tabel import JENIS_TABEL_DIIDENTIFIKASI, JENIS_TABEL_TIDAK_DIIDENTIFIKASI


class LaporanMetrikDataEksternalFilterForm(forms.Form):
    """Form untuk filter Laporan Metrik Data Eksternal."""

    id_ilap = forms.ChoiceField(
        choices=[('all', 'Pilih Semua')],
        label='ILAP',
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'filter-id-ilap'
        })
    )

    tgl_mulai = forms.DateTimeField(
        label='Tanggal Mulai',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'filter-tgl-mulai'
        }),
        required=True
    )
    tgl_akhir = forms.DateTimeField(
        label='Tanggal Akhir',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
            'id': 'filter-tgl-akhir'
        }),
        required=True
    )

    id_jenis_data = forms.ChoiceField(
        choices=[('all', 'Pilih Semua')],
        label='Jenis Data ILAP',
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'filter-id-jenis-data'
        })
    )

    # Independent cascading selectors for filtering
    nama_sub_jenis_data = forms.ChoiceField(
        choices=[('all', 'Pilih Semua')],
        label='Nama Subjenis Data',
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'filter-nama-sub-jenis-data'
        })
    )
    nama_tabel_I = forms.ChoiceField(
        choices=[('all', 'Pilih Semua')],
        label='Nama Tabel I',
        required=False,
        initial='all',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'filter-nama-tabel-I'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Default date range to current month
        today = datetime.now()
        year = today.year
        month = today.month
        start_of_month = datetime(year, month, 1, 0, 0, 0)
        _, last_day = calendar.monthrange(year, month)
        end_of_month = datetime(year, month, last_day, 23, 59, 59)
        self.fields['tgl_mulai'].initial = start_of_month
        self.fields['tgl_akhir'].initial = end_of_month
        
        # Populate ILAP choices
        ilap_qs = ILAP.objects.all().order_by('nama_ilap')
        self.fields['id_ilap'].choices = [('all', 'Pilih Semua')] + [(obj.id, obj.nama_ilap) for obj in ilap_qs]
        self.fields['id_ilap'].initial = 'all'

        # Populate Jenis Data choices
        jenis_data_qs = JenisDataILAP.objects.all().order_by('nama_sub_jenis_data')
        self.fields['id_jenis_data'].choices = [('all', 'Pilih Semua')] + [(obj.id, obj.nama_sub_jenis_data) for obj in jenis_data_qs]
        self.fields['id_jenis_data'].initial = 'all'
        
        # Populate cascading selector choices from existing data
        sub_jenis_qs = JenisDataILAP.objects.values_list('nama_sub_jenis_data', flat=True).distinct()
        sub_jenis_choices = [('all', 'Pilih Semua')] + [(v, v) for v in sorted(set(sub_jenis_qs)) if v]
        self.fields['nama_sub_jenis_data'].choices = sub_jenis_choices
        self.fields['nama_sub_jenis_data'].initial = 'all'
        
        tabel_i_qs = JenisDataILAP.objects.values_list('nama_tabel_I', flat=True).distinct()
        tabel_i_choices = [('all', 'Pilih Semua')] + [(v, v) for v in sorted(set(tabel_i_qs)) if v]
        self.fields['nama_tabel_I'].choices = tabel_i_choices
        self.fields['nama_tabel_I'].initial = 'all'




class LaporanMetrikDataEksternalExportResource(resources.ModelResource):
    """Resource for exporting Laporan Metrik Data Eksternal to XLSX."""
    
    nama_ilap = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap')
    jenis_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data')
    subjenis_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    tabel_bank_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I')
    nomor_tiket = fields.Field(attribute='nomor_tiket')
    jumlah_data_masuk = fields.Field(attribute='baris_diterima')
    jumlah_data_tidak_teridentifikasi = fields.Field(attribute='baris_u')
    jumlah_data_res = fields.Field(attribute='baris_res')

    # Calculated fields 
    jumlah_data_teridentifikasi = fields.Field()
    jumlah_data_tidak_diidentifikasi = fields.Field()
    persentase = fields.Field()
    
    class Meta:
        model = Tiket
        fields = (
            'nama_ilap', 'jenis_data', 'subjenis_data', 
            'tabel_bank_data', 'nomor_tiket', 
            'jumlah_data_masuk', 
            'jumlah_data_teridentifikasi', 
            'jumlah_data_tidak_teridentifikasi', 
            'jumlah_data_tidak_diidentifikasi', 
            'jumlah_data_res',
            'persentase'
        )
        export_order = fields
    
    def dehydrate_jumlah_data_masuk(self, obj):
        """Return null values as 0."""
        return obj.baris_diterima or 0
    
    def dehydrate_jumlah_data_tidak_teridentifikasi(self, obj):
        """Return null values as 0."""
        return obj.baris_u or 0

    def dehydrate_jumlah_data_teridentifikasi(self, obj):
        """Fetch id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel
        to determine if data is Diidentifikasi or not.
        Return 0 if baris_i is null, or if id_jenis_tabel is not Diidentifikasi.
        Return baris_i if id_jenis_tabel is Diidentifikasi.
        """
        if obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel.id != JENIS_TABEL_DIIDENTIFIKASI:
            return 0
        else:
            return obj.baris_i or 0

    def dehydrate_jumlah_data_tidak_diidentifikasi(self, obj):
        """Fetch id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel
        to determine if data is Tidak Diidentifikasi or not.
        Return 0 if baris_i is null, or if id_jenis_tabel is not Tidak Diidentifikasi.
        Return baris_i if id_jenis_tabel is Tidak Diidentifikasi.
        """
        if obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel.id != JENIS_TABEL_TIDAK_DIIDENTIFIKASI:
            return 0
        else:
            return obj.baris_i or 0

    def dehydrate_jumlah_data_res(self, obj):
        """Return null values as 0."""
        return obj.baris_res or 0

    def dehydrate_persentase(self, obj):
        """Fetch id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel
        to determine if data is Diidentifikasi ('1') or not.
        Return empty string ('') if baris_diterima is 0, or if id_jenis_tabel is not '1' (Diidentifikasi).
        Otherwise, calculate (baris_i / baris_diterima) * 100.
        Return the calculation result as a string, formatted as percentage.
        """
        if obj.baris_diterima == 0:
            return ''
        else:
            return f"{(obj.baris_i or 0) / obj.baris_diterima * 100:.2f}%"

