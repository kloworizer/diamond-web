from django import forms
from import_export import resources, fields
from import_export.widgets import Widget
from ..models.tiket import Tiket
from ..constants.tiket_status import STATUS_LABELS


class LaporanPengendalianMutuFilterForm(forms.Form):
    """Form untuk filter Laporan Pengendalian Mutu."""

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

    periode = forms.CharField(
        label='Periode Transfer',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filter-periode',
            'required': True,
        }),
        required=False
    )

    tahun = forms.IntegerField(
        label='Tahun Transfer',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'filter-tahun',
            'required': True,
        }),
        required=False
    )

    def __init__(self, *args, years=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Convert periode to Select widget properly
        self.fields['periode'] = forms.ChoiceField(
            label='Periode Transfer',
            choices=self.BULAN_CHOICES,
            widget=forms.Select(attrs={
                'class': 'form-select',
                'id': 'filter-periode',
                'required': True,
            }),
            required=False
        )

        # Set tahun choices from available years
        tahun_choices = [('', '-- Pilih Tahun --')]
        if years:
            tahun_choices.extend([(str(year), str(year)) for year in years])

        self.fields['tahun'] = forms.ChoiceField(
            label='Tahun Transfer',
            choices=tahun_choices,
            widget=forms.Select(attrs={
                'class': 'form-select',
                'id': 'filter-tahun',
                'required': True,
            }),
            required=False
        )


class TiketExportResource(resources.ModelResource):
    """Resource for exporting Tiket data with QC fields."""
    
    nama_ilap = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap')
    nama_sub_jenis_data = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data')
    nama_tabel = fields.Field(attribute='id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi')
    nomor_tiket = fields.Field(attribute='nomor_tiket')
    status_tiket = fields.Field()
    data_diterima = fields.Field(attribute='baris_diterima')
    data_direkam = fields.Field()
    data_teridentifikasi_i = fields.Field(attribute='baris_i')
    data_tidak_teridentifikasi_u = fields.Field(attribute='baris_u')
    lolos_qc = fields.Field(attribute='lolos_qc')
    tidak_lolos_qc = fields.Field(attribute='tidak_lolos_qc')
    qc_p = fields.Field(attribute='qc_p')
    qc_x = fields.Field(attribute='qc_x')
    qc_w = fields.Field(attribute='qc_w')
    qc_v = fields.Field(attribute='qc_v')
    qc_a = fields.Field(attribute='qc_a')
    qc_n = fields.Field(attribute='qc_n')
    qc_y = fields.Field(attribute='qc_y')
    qc_z = fields.Field(attribute='qc_z')
    qc_d = fields.Field(attribute='qc_d')
    qc_u = fields.Field(attribute='qc_u')
    qc_c = fields.Field(attribute='qc_c')
    
    class Meta:
        model = Tiket
        fields = (
            'nama_ilap', 'nama_sub_jenis_data', 'nama_tabel', 'nomor_tiket', 'status_tiket',
            'data_diterima', 'data_direkam', 'data_teridentifikasi_i', 'data_tidak_teridentifikasi_u',
            'lolos_qc', 'tidak_lolos_qc', 'qc_p', 'qc_x', 'qc_w', 'qc_v', 'qc_a', 'qc_n', 
            'qc_y', 'qc_z', 'qc_d', 'qc_u', 'qc_c'
        )
        export_order = fields
    
    def dehydrate_status_tiket(self, obj):
        """Return human-readable status label."""
        return STATUS_LABELS.get(obj.status_tiket, 'Unknown')
    
    def dehydrate_data_direkam(self, obj):
        """Calculate total recorded data (I + U)."""
        return (obj.baris_i or 0) + (obj.baris_u or 0)
    
    def dehydrate_data_diterima(self, obj):
        """Return null values as 0."""
        return obj.baris_diterima or 0
    
    def dehydrate_lolos_qc(self, obj):
        """Return null values as 0."""
        return obj.lolos_qc or 0
    
    def dehydrate_tidak_lolos_qc(self, obj):
        """Return null values as 0."""
        return obj.tidak_lolos_qc or 0
    
    def dehydrate_qc_p(self, obj):
        """Return null values as 0."""
        return obj.qc_p or 0
    
    def dehydrate_qc_x(self, obj):
        """Return null values as 0."""
        return obj.qc_x or 0
    
    def dehydrate_qc_w(self, obj):
        """Return null values as 0."""
        return obj.qc_w or 0
    
    def dehydrate_qc_v(self, obj):
        """Return null values as 0."""
        return obj.qc_v or 0
    
    def dehydrate_qc_a(self, obj):
        """Return null values as 0."""
        return obj.qc_a or 0
    
    def dehydrate_qc_n(self, obj):
        """Return null values as 0."""
        return obj.qc_n or 0
    
    def dehydrate_qc_y(self, obj):
        """Return null values as 0."""
        return obj.qc_y or 0
    
    def dehydrate_qc_z(self, obj):
        """Return null values as 0."""
        return obj.qc_z or 0
    
    def dehydrate_qc_d(self, obj):
        """Return null values as 0."""
        return obj.qc_d or 0
    
    def dehydrate_qc_u(self, obj):
        """Return null values as 0."""
        return obj.qc_u or 0
    
    def dehydrate_qc_c(self, obj):
        """Return null values as 0."""
        return obj.qc_c or 0
