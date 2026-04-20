from django import forms
from import_export import resources, fields
from import_export.widgets import Widget 
from ..models.tiket import Tiket
from ..constants.tiket_status import STATUS_LABELS


class LaporanKelengkapanDataFilterForm(forms.Form):
    """Form untuk filter Laporan Kelengkapan Data."""

    PERIODE_TYPE_CHOICES = [
        ('', '-- Pilih Jenis Periode --'),
        ('bulanan', 'Bulanan'),
        ('triwulanan', 'Triwulanan'),
        ('semester', 'Semester'),
        ('tahunan', 'Tahunan'),
    ]

    BULAN_CHOICES = [
        ('', '-- Pilih Periode --'),
        ('1', 'Januari'),
        ('2', 'Februari'),
        ('3', 'Maret'), 
        ('4', 'April'),
        ('5', 'Mei'),
        ('6', 'Juni'),
        ('7', 'Juli'),
        ('8', 'Agustus'),
        ('9', 'September'),
        ('10', 'Oktober'),
        ('11', 'November'),
        ('12', 'Desember'),
    ]

    TRIWULAN_CHOICES = [
        ('', '-- Pilih Periode --'),
        ('1', 'Triwulan 1 (Jan - Mar)'),
        ('2', 'Triwulan 2 (Apr - Jun)'),        
        ('3', 'Triwulan 3 (Jul - Sep)'),
        ('4', 'Triwulan 4 (Oct - Dec)'),    
    ]

    SEMESTER_CHOICES = [
        ('', '-- Pilih Periode --'),
        ('1', 'Semester 1 (Jan - Jun)'),
        ('2', 'Semester 2 (Jul - Dec)'),
    ]

    TAHUNAN_CHOICES = [
        ('', '-- Pilih Periode --'),
        ('all', 'Seluruh Tahun'),
    ]   

    periode_type = forms.ChoiceField(
        choices=PERIODE_TYPE_CHOICES,
        label='Jenis Periode',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filter-periode-type',
            'required': True,
        })
    )

    periode = forms.ChoiceField(
        label='Periode Transfer',
        choices=BULAN_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filter-periode',
            'required': True,
        }),
        required=False
    )

    tahun = forms.ChoiceField(
        label='Tahun Transfer',
        choices=[('', '-- Pilih Tahun --')],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filter-tahun',
            'required': True,
        }),
        required=False
    )

    def __init__(self, *args, years=None, **kwargs):
        super().__init__(*args, **kwargs)
        if years:
            self.fields['tahun'].choices = [('', '-- Pilih Tahun --')] + [
                (str(year), str(year)) for year in years
            ]

class TiketExportResource(resources.ModelResource):
    """Resource for exporting Tiket data with QC fields."""
    nama_ilap = fields.Field(column_name='Nama ILAP', attribute='id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap')
    jenis_data = fields.Field(column_name='Jenis Data', attribute='id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    nomor_tiket = fields.Field(column_name='Nomor Tiket', attribute='nomor_tiket')
    status = fields.Field(column_name='Status')
    data_diterima = fields.Field(column_name='Data Diterima', attribute='baris_diterima')
    tabel = fields.Field(column_name='Nama Tabel', attribute='id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi')
    qc_c = fields.Field(column_name='QC C', attribute='qc_c')
    
    class Meta:
        model = Tiket
        fields = ('nama_ilap', 'jenis_data', 'nomor_tiket', 'status', 'data_diterima', 'tabel', 'qc_c')
        export_order = fields

    def dehydrate_status(self, obj):
        return STATUS_LABELS.get(obj.status_tiket, 'Unknown')

    def dehydrate_data_diterima(self, tiket):
        return tiket.baris_diterima or 0

    def dehydrate_qc_c(self, tiket):
        return tiket.qc_c or 0
    
