from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from ..models.tiket_pic import TiketPIC

# The user group each TiketPIC role draws its PICs from - the same groups the
# PIC menu offers (`PICForm`).
ROLE_USER_GROUP = {
    TiketPIC.Role.P3DE: 'user_p3de',
    TiketPIC.Role.PIDE: 'user_pide',
    TiketPIC.Role.PMDE: 'user_pmde',
}


def _user_label(user):
    full_name = f'{user.first_name} {user.last_name}'.strip()
    return f'{full_name} ({user.username})' if full_name else user.username


class KelolaPICTiketForm(forms.Form):
    """Add (``instance=None``) or change one `TiketPIC` row of a single tiket.

    The choices are the users of the role's seksi group, minus superusers and
    whoever is already an active PIC of that role on the tiket. When changing a
    row, its current user stays selectable even if they would otherwise be left
    out, so the form can be saved with only the status changed.
    """
    id_user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='User',
        empty_label='Pilih user',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    active = forms.BooleanField(
        label='Aktif',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, tiket, role, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tiket = tiket
        self.role = role
        self.instance = instance

        sudah_aktif = TiketPIC.objects.filter(
            id_tiket=tiket, role=role, active=True,
        ).values('id_user')
        candidates = (
            Q(groups__name=ROLE_USER_GROUP[role])
            & ~Q(pk__in=sudah_aktif)
            # Superusers sit in every user group; they are not PIC candidates.
            & Q(is_superuser=False)
        )
        if instance is not None:
            candidates |= Q(pk=instance.id_user_id)
            self.initial.setdefault('id_user', instance.id_user_id)
            self.initial.setdefault('active', instance.active)
        else:
            # A new PIC is always active; there is nothing to choose.
            del self.fields['active']

        field = self.fields['id_user']
        field.queryset = User.objects.filter(candidates).distinct().order_by('username')
        field.label_from_instance = _user_label

    def clean(self):
        cleaned = super().clean()
        user = cleaned.get('id_user')
        if user is None:
            return cleaned

        if self.instance is None:
            return cleaned

        active = cleaned.get('active', False)
        if user.pk == self.instance.id_user_id:
            if active == self.instance.active:
                raise forms.ValidationError('Tidak ada perubahan.')
        elif not active:
            # Changing the user is a hand-over to the new user; handing over to
            # someone who is not active would leave the role to nobody.
            self.add_error('active', 'PIC pengganti harus berstatus aktif.')
        return cleaned
