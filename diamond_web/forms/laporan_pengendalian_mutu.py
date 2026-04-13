from django import forms


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
