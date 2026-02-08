from django import forms
from ..models.pic import PIC
from django.contrib.auth.models import User

class PICForm(forms.ModelForm):
    class Meta:
        model = PIC
        fields = ['tipe', 'id_sub_jenis_data_ilap', 'id_user', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, tipe=None, **kwargs):
        super().__init__(*args, **kwargs)

        # If editing (instance exists), disable all fields except start_date and end_date
        if self.instance.pk:
            for field_name in self.fields:
                if field_name not in ['start_date', 'end_date']:
                    self.fields[field_name].disabled = True

        # If tipe is provided (for specific PIC type views), filter users by group
        if tipe:
            # Set the tipe field value and make it read-only (only for new instances)
            if self.instance.pk is None:
                self.initial['tipe'] = tipe
                self.fields['tipe'].widget = forms.HiddenInput()

            # Map tipe to user group
            group_mapping = {
                PIC.TipePIC.P3DE: 'user_p3de',
                PIC.TipePIC.PIDE: 'user_pide',
                PIC.TipePIC.PMDE: 'user_pmde',
            }
            group_name = group_mapping.get(tipe)
            if group_name:
                self.fields['id_user'].queryset = User.objects.filter(groups__name=group_name).distinct()

        # Customize user field to show first_name and last_name
        self.fields['id_user'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name} ({obj.username})" if obj.first_name or obj.last_name else obj.username

    def clean(self):
        cleaned_data = super().clean()
        tipe = cleaned_data.get('tipe')
        id_sub_jenis_data_ilap = cleaned_data.get('id_sub_jenis_data_ilap')
        id_user = cleaned_data.get('id_user')
        start_date = cleaned_data.get('start_date')
        
        if tipe and id_sub_jenis_data_ilap and id_user and start_date:
            # Check for existing PIC with same user, sub_jenis_data, and start_date
            existing_pic = PIC.objects.filter(
                tipe=tipe,
                id_sub_jenis_data_ilap=id_sub_jenis_data_ilap,
                id_user=id_user,
                start_date=start_date
            )
            
            # Exclude current instance if updating
            if self.instance.pk:
                existing_pic = existing_pic.exclude(pk=self.instance.pk)
            
            if existing_pic.exists():
                raise forms.ValidationError(
                    f"PIC dengan user '{id_user.username}', sub jenis data '{id_sub_jenis_data_ilap}', "
                    f"dan start date '{start_date}' sudah ada. Silakan gunakan start date yang berbeda."
                )
            
            # Check for overlapping date ranges (same user and sub_jenis_data without end_date)
            overlapping_pic = PIC.objects.filter(
                tipe=tipe,
                id_sub_jenis_data_ilap=id_sub_jenis_data_ilap,
                id_user=id_user,
                end_date__isnull=True  # Active PIC without end_date
            )
            
            # Exclude current instance if updating
            if self.instance.pk:
                overlapping_pic = overlapping_pic.exclude(pk=self.instance.pk)
            
            if overlapping_pic.exists():
                raise forms.ValidationError(
                    f"Sudah ada PIC aktif untuk user '{id_user.username}' dan sub jenis data '{id_sub_jenis_data_ilap}'. "
                    f"Silakan set end_date pada PIC yang ada terlebih dahulu."
                )
        
        return cleaned_data
