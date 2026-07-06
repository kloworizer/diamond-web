# d:\diamond-web\diamond_web\forms\laporan_hasil_pengolahan_data_prioritas.py
from django import forms
from import_export import resources, fields
from ..models.tiket import Tiket
from ..constants.jenis_tabel import JENIS_TABEL_DIIDENTIFIKASI, JENIS_TABEL_TIDAK_DIIDENTIFIKASI
from ..utils import format_periode


class LaporanHasilPengolahanDataPrioritasFilterForm(forms.Form):
    """Form untuk filter Laporan Hasil Pengolahan Data Prioritas."""

    PERIODE_TYPE_CHOICES = [
        ('', 'Pilih Jenis Periode'),
        ('bulanan', 'Bulanan'),
        ('triwulanan', 'Triwulanan'),
        ('semester', 'Semester'),
        ('tahunan', 'Tahunan'),
    ]

    BULAN_CHOICES = [
        ('', 'Pilih Periode'),
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
        ('', 'Pilih Periode'),
        ('1', 'Triwulan 1 (Jan - Mar)'),
        ('2', 'Triwulan 2 (Apr - Jun)'),        
        ('3', 'Triwulan 3 (Jul - Sep)'),
        ('4', 'Triwulan 4 (Oct - Dec)'),    
    ]

    SEMESTER_CHOICES = [
        ('', 'Pilih Periode'),
        ('1', 'Semester 1 (Jan - Jun)'),
        ('2', 'Semester 2 (Jul - Dec)'),
    ]

    TAHUNAN_CHOICES = [
        ('', 'Pilih Periode'),
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
        choices=[('', 'Pilih Tahun')],
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
            self.fields['tahun'].choices = [('', 'Pilih Tahun')] + [
                (str(year), str(year)) for year in sorted(years, reverse=True)
            ]


class LaporanHasilPengolahanDataPrioritasExportResource(resources.ModelResource):
    """Resource for exporting Laporan Hasil Pengolahan Data Prioritas to XLSX."""
    
    nama_ilap = fields.Field(column_name='NAMA ILAP', attribute='id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap')
    nama_jenis_data = fields.Field(column_name='NAMA JENIS DATA', attribute='id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    nama_tabel_kpde = fields.Field(column_name='NAMA TABEL KPDE', attribute='id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I')
    nama_tabel_bankdata = fields.Field(column_name='NAMA TABEL BANK DATA', attribute='id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I')
    nama_tabel_bankdata_u = fields.Field(column_name='NAMA_TABEL_BANKDATA_U', attribute='id_periode_data__id_sub_jenis_data_ilap__nama_tabel_U')
    periode_data = fields.Field(column_name='PERIODE_DATA', attribute='id_periode_data__id_periode_pengiriman__periode_penyampaian')
    id_tiket = fields.Field(column_name='ID_TIKET', attribute='nomor_tiket')
    periode_tiket = fields.Field(column_name='PERIODE_TIKET')
    
    data_diterima = fields.Field(column_name='DATA DITERIMA (P3DE)', attribute='baris_diterima')
    data_lengkap = fields.Field(column_name='DATA LENGKAP (P3DE)', attribute='baris_lengkap')
    data_klarifikasi = fields.Field(column_name='DATA KLARIFIKASI (P3DE)', attribute='baris_tidak_lengkap')
    
    # Kolom DATA DITERIMA berulang sesuai permintaan input
    data_diterima_v2 = fields.Field(column_name='DATA DITERIMA (PIDE)', attribute='baris_diterima')
    
    data_direkam = fields.Field(column_name='DATA DIREKAM')
    data_teridentifikasi = fields.Field(column_name='DATA TERIDENTIFIKASI')
    data_tidak_teridentifikasi = fields.Field(column_name='DATA TIDAK TERIDENTIFIKASI', attribute='baris_u')
    data_belum_diidentifikasi = fields.Field(column_name='DATA BELUM DIIDENTIFIKASI')
    data_tidak_diidentifikasi = fields.Field(column_name='DATA TIDAK DIIDENTIFIKASI')
    data_diterima_tabel_i = fields.Field(column_name='DATA DITERIMA (TABEL I)')
    
    data_lolos_qc = fields.Field(column_name='DATA LOLOS QC', attribute='lolos_qc')
    data_tidak_lolos_qc = fields.Field(column_name='DATA TIDAK LOLOS QC', attribute='tidak_lolos_qc')
    data_belum_qc = fields.Field(column_name='DATA BELUM QC', attribute='qc_c')
    
    keterangan = fields.Field(column_name='KETERANGAN')

    class Meta:
        model = Tiket
        fields = (
            'nama_ilap', 'nama_jenis_data', 'nama_tabel_kpde', 'nama_tabel_bankdata', 'nama_tabel_bankdata_u',
            'periode_data', 'id_tiket', 'periode_tiket', 'data_diterima', 'data_lengkap', 'data_klarifikasi',
            'data_diterima_v2', 'data_direkam', 'data_teridentifikasi', 'data_tidak_teridentifikasi',
            'data_belum_diidentifikasi', 'data_tidak_diidentifikasi', 'data_diterima_tabel_i',
            'data_lolos_qc', 'data_tidak_lolos_qc', 'data_belum_qc', 'keterangan'
        )
        export_order = fields

    def dehydrate_periode_tiket(self, obj):
        """Format periode tiket menjadi string yang mudah dibaca."""
        if obj.id_periode_data and obj.id_periode_data.id_periode_pengiriman:
            return format_periode(
                obj.id_periode_data.id_periode_pengiriman.periode_penerimaan,
                obj.periode,
                obj.tahun
            )
        return "-"

    def dehydrate_data_direkam(self, obj):
        """Hitung data direkam (I + U)."""
        return (obj.baris_i or 0) + (obj.baris_u or 0)

    def dehydrate_data_teridentifikasi(self, obj):
        """
        Mengambil baris_i jika jenis tabel adalah Diidentifikasi.
        Jika tidak, return 0.
        """
        if (obj.id_periode_data and 
            obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel_id == JENIS_TABEL_DIIDENTIFIKASI):
            return obj.baris_i or 0
        return 0

    def dehydrate_data_tidak_diidentifikasi(self, obj):
        """
        Mengambil baris_i jika jenis tabel adalah Tidak Diidentifikasi.
        """
        if (obj.id_periode_data and 
            obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel_id == JENIS_TABEL_TIDAK_DIIDENTIFIKASI):
            return obj.baris_i or 0
        return 0

    def dehydrate_data_belum_diidentifikasi(self, obj):
        """
        Selisih antara data diterima dengan yang sudah direkam (I+U).
        Hanya berlaku jika jenis tabel adalah Diidentifikasi.
        """
        if (obj.id_periode_data and 
            obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel_id == JENIS_TABEL_DIIDENTIFIKASI):
            total_direkam = (obj.baris_i or 0) + (obj.baris_u or 0)
            return max(0, (obj.baris_diterima or 0) - total_direkam)
        return 0

    def dehydrate_data_diterima_tabel_i(self, obj):
        """Alias untuk data teridentifikasi."""
        return self.dehydrate_data_teridentifikasi(obj)

    def dehydrate_data_klarifikasi(self, obj):
        return obj.baris_tidak_lengkap or 0

    def dehydrate_data_lolos_qc(self, obj):
        return obj.lolos_qc or 0

    def dehydrate_data_tidak_lolos_qc(self, obj):
        return obj.tidak_lolos_qc or 0

    def dehydrate_data_belum_qc(self, obj):
        return obj.qc_c or 0

    def dehydrate_keterangan(self, obj):
        return ""
