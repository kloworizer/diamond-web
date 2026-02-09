from django import forms
from ..models.periode_jenis_data import PeriodeJenisData

class PeriodeJenisDataForm(forms.ModelForm):
    class Meta:
        model = PeriodeJenisData
        fields = ['id_sub_jenis_data_ilap', 'id_periode_pengiriman', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        id_sub = cleaned_data.get('id_sub_jenis_data_ilap')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if id_sub and start_date:
            # Duplicate start_date check
            qs = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap=id_sub,
                start_date=start_date
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('start_date', (
                    f"Periode dengan sub jenis data '{id_sub}' dan start date '{start_date}' sudah ada. Silakan gunakan start date yang berbeda."
                ))
                return cleaned_data

            # Overlap: check for existing open-ended or intersecting ranges
            overlapping = PeriodeJenisData.objects.filter(id_sub_jenis_data_ilap=id_sub)
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            for other in overlapping:
                s1 = other.start_date
                e1 = other.end_date or None
                s2 = start_date
                e2 = end_date or None
                # treat None as open-ended; overlap if ranges intersect
                if not (e1 is not None and e1 < s2 or e2 is not None and e2 < s1):
                    self.add_error('start_date', (
                        f"Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini."
                    ))
                    return cleaned_data

        return cleaned_data
