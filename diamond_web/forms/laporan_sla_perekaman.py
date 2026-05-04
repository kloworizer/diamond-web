from django import forms
from import_export import resources, fields
from import_export.widgets import DateTimeWidget
import calendar
from datetime import datetime

from ..models.ilap import ILAP 
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.tiket import Tiket
from ..constants.jenis_tabel import JENIS_TABEL_DIIDENTIFIKASI, JENIS_TABEL_TIDAK_DIIDENTIFIKASI


class LaporanSLAPerekamanFilterForm(forms.Form):
    """Form untuk filter Laporan SLA Perekaman."""

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




class LaporanSLAPerekamanExportResource(resources.ModelResource):
    """Resource for exporting Laporan SLA Perekaman to XLSX."""
    
    nama_ilap = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap')
    nama_jenis_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data')
    nama_sub_jenis_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    nama_tabel_I = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I')
    nomor_tiket = fields.Field(attribute='nomor_tiket')
    tgl_terima_pide = fields.Field(attribute='tgl_kirim_pide',widget=DateTimeWidget(format='%d/%m/%Y'))
    tgl_mulai_identifikasi = fields.Field(attribute='tgl_rekam_pide',widget=DateTimeWidget(format='%d/%m/%Y'))

    # Calculated fields 
    sla_perekaman = fields.Field()

    class Meta:
        model = Tiket
        fields = (
            'nama_ilap', 'nama_jenis_data', 'nama_sub_jenis_data', 'nama_tabel_I', 'nomor_tiket', 
            'tgl_terima_pide', 'tgl_mulai_identifikasi',
            'sla_perekaman'
        )
        export_order = fields

    def dehydrate_sla_perekaman(self, obj):
        """Calculate SLA in days. Same day = 1 day, next day = 2 days."""
        if obj.tgl_kirim_pide and obj.tgl_rekam_pide:
            diff = (obj.tgl_rekam_pide.date() - obj.tgl_kirim_pide.date()).days + 1
            return f"{diff} hari"
        return ''
