from django import forms
from ..models.jenis_prioritas_data import JenisPrioritasData


class JenisPrioritasDataForm(forms.ModelForm):
    class Meta:
        model = JenisPrioritasData
        fields = ['id_sub_jenis_data_ilap', 'no_nd', 'tahun', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        id_sub = cleaned_data.get('id_sub_jenis_data_ilap')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        tahun = cleaned_data.get('tahun')

        if id_sub and start_date:
            # Check duplicate id_sub + tahun to avoid DB UniqueConstraint triggering
            if tahun:
                dup_qs = JenisPrioritasData.objects.filter(
                    id_sub_jenis_data_ilap=id_sub,
                    tahun=tahun
                )
                if self.instance.pk:
                    dup_qs = dup_qs.exclude(pk=self.instance.pk)
                if dup_qs.exists():
                    self.add_error('tahun', (
                        f"Entri dengan Sub Jenis Data ILAP '{id_sub}' dan Tahun '{tahun}' sudah ada."
                    ))
                    return cleaned_data
            # Duplicate start_date check
            qs = JenisPrioritasData.objects.filter(
                id_sub_jenis_data_ilap=id_sub,
                start_date=start_date
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('start_date', (
                    f"Entri dengan sub jenis data '{id_sub}' dan start date '{start_date}' sudah ada. Silakan gunakan start date yang berbeda."
                ))
                return cleaned_data

            # Overlap: check for intersecting ranges
            overlapping = JenisPrioritasData.objects.filter(id_sub_jenis_data_ilap=id_sub)
            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            for other in overlapping:
                s1 = other.start_date
                e1 = other.end_date or None
                s2 = start_date
                e2 = end_date or None
                if not (e1 is not None and e1 < s2 or e2 is not None and e2 < s1):
                    self.add_error('start_date', (
                        f"Rentang tanggal bertumpuk dengan entri lain untuk Sub Jenis Data ini."
                    ))
                    return cleaned_data

        return cleaned_data
