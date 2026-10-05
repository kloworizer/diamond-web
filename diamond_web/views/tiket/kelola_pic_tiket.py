"""Kelola PIC Tiket - an admin adds, changes or removes the PICs of one tiket.

The change applies to that tiket's own `TiketPIC` rows alone: the PIC table is
never written and no other tiket is touched. The rows are ordinary TiketPIC
rows, so later changes in the PIC menu treat them like any other.

Access mirrors the PIC menu (`tiket_pic_roles_managed_by`): `admin_p3de` /
`admin_p3der` (each on the tikets of their own seksi), `admin_pide` and
`admin_pmde` manage the PICs of their own role; superusers and the `admin`
group manage all three. Every change is written to the tiket's
TiketAction trail under the admin who made it.
"""

from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from ...constants.tiket_action_types import PICActionType
from ...forms.kelola_pic_tiket import KelolaPICTiketForm
from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ..mixins import tiket_pic_roles_managed_by


def _label(role):
    return f'PIC {TiketPIC.Role(role).label}'


def _catat(tiket, admin, now, action, catatan):
    TiketAction.objects.create(
        id_tiket=tiket, id_user=admin, timestamp=now, action=action, catatan=catatan,
    )


def tambah_pic(tiket, user, role, admin, now, keterangan=''):
    """Make `user` an active PIC of `role` on `tiket`.

    Reuses the user's existing row for that role when there is one (it can only
    be inactive - the form keeps active PICs out of the choices) instead of
    creating a duplicate.
    """
    row = (
        TiketPIC.objects.filter(id_tiket=tiket, id_user=user, role=role)
        .order_by('id').first()
    )
    if row:
        row.active = True
        if row.timestamp is None:
            row.timestamp = now
        row.save(update_fields=['active', 'timestamp'])
        action, kata = PICActionType.DIAKTIFKAN_KEMBALI, 'diaktifkan kembali'
    else:
        TiketPIC.objects.create(
            id_tiket=tiket, id_user=user, role=role,
            active=True, timestamp=now,
        )
        action, kata = PICActionType.DITAMBAHKAN, 'ditambahkan'
    _catat(tiket, admin, now, action,
           f'{_label(role)} {user.username} {kata} langsung di tiket{keterangan}')


def ubah_pic(pic, user, active, admin, now):
    """Apply an edit of `pic` to `user` / `active`.

    Same user: only the status changes. Another user: a hand-over, as in the PIC
    menu - the old row stays as inactive history and `user` becomes an active
    PIC of the role.
    """
    tiket, role = pic.id_tiket, pic.role
    lama = pic.id_user
    if user.pk == lama.pk:
        pic.active = active
        pic.save(update_fields=['active'])
        if active:
            action, kata = PICActionType.DIAKTIFKAN_KEMBALI, 'diaktifkan kembali'
        else:
            action, kata = PICActionType.TIDAK_AKTIF, 'dinonaktifkan'
        _catat(tiket, admin, now, action,
               f'{_label(role)} {lama.username} {kata} langsung di tiket')
        return

    was_active = pic.active
    pic.active = False
    pic.save(update_fields=['active'])
    if was_active:
        _catat(tiket, admin, now, PICActionType.TIDAK_AKTIF,
               f'{_label(role)} {lama.username} diganti oleh {user.username} langsung di tiket')
    tambah_pic(tiket, user, role, admin, now, keterangan=f' (menggantikan {lama.username})')


def hapus_pic(pic, admin, now):
    """Delete `pic` from its tiket and log it."""
    tiket, role, user = pic.id_tiket, pic.role, pic.id_user
    pic.delete()
    _catat(tiket, admin, now, PICActionType.TIDAK_AKTIF,
           f'{_label(role)} {user.username} dihapus langsung di tiket')


class _KelolaPICTiketBase(LoginRequiredMixin, View):
    """Resolve the tiket and the role being managed, and check the admin may.

    Subclasses implement `resolve_role()`; a role the user does not administer
    is refused with 403 (JSON for AJAX).
    """
    template_name = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.tiket = get_object_or_404(Tiket, pk=kwargs['pk'])
        role = self.resolve_role()
        if role is None or role not in tiket_pic_roles_managed_by(request.user, self.tiket):
            if self.is_ajax():
                return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
            raise PermissionDenied()
        self.role = TiketPIC.Role(role)
        return super().dispatch(request, *args, **kwargs)

    def resolve_role(self):
        raise NotImplementedError

    def is_ajax(self):
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def render_html(self, **context):
        context.setdefault('tiket', self.tiket)
        context.setdefault('role_label', _label(self.role))
        context.setdefault('role_code', self.role.label.lower())
        return render_to_string(self.template_name, context, request=self.request)

    def success(self, message):
        return JsonResponse({'success': True, 'message': message})

    def failure(self, message, **context):
        return JsonResponse(
            {'success': False, 'message': message, 'html': self.render_html(**context)},
            status=400,
        )


class _KelolaSatuPICMixin:
    """For views acting on one existing row: the row decides the role."""

    def resolve_role(self):
        self.pic = get_object_or_404(
            TiketPIC.objects.select_related('id_user'),
            pk=self.kwargs['pic_pk'], id_tiket=self.tiket,
        )
        return self.pic.role


class TambahPICTiketView(_KelolaPICTiketBase):
    """GET: the add form for `?role=`; POST: add the chosen user as PIC."""
    template_name = 'tiket/kelola_pic_tiket_modal_form.html'

    def resolve_role(self):
        raw = self.request.POST.get('role') or self.request.GET.get('role')
        try:
            role = int(raw)
        except (TypeError, ValueError):
            return None
        return role if role in TiketPIC.Role.values else None

    def form_context(self, form):
        return {
            'form': form,
            'role': self.role,
            'form_action': reverse('tiket_pic_tambah', kwargs={'pk': self.tiket.pk}),
            'submit_label': 'Tambah PIC',
        }

    def get(self, request, *args, **kwargs):
        form = KelolaPICTiketForm(tiket=self.tiket, role=self.role)
        return HttpResponse(self.render_html(**self.form_context(form)))

    def post(self, request, *args, **kwargs):
        form = KelolaPICTiketForm(request.POST, tiket=self.tiket, role=self.role)
        if not form.is_valid():
            return self.failure('Periksa kembali isian form.', **self.form_context(form))
        user = form.cleaned_data['id_user']
        with transaction.atomic():
            tambah_pic(self.tiket, user, self.role, request.user, datetime.now())
        return self.success(f'{_label(self.role)} {user.username} berhasil ditambahkan ke tiket ini.')


class UbahPICTiketView(_KelolaSatuPICMixin, _KelolaPICTiketBase):
    """GET: the edit form for one PIC row; POST: apply the change."""
    template_name = 'tiket/kelola_pic_tiket_modal_form.html'

    def form_context(self, form):
        return {
            'form': form,
            'pic': self.pic,
            'form_action': reverse(
                'tiket_pic_ubah', kwargs={'pk': self.tiket.pk, 'pic_pk': self.pic.pk},
            ),
            'submit_label': 'Simpan',
        }

    def get(self, request, *args, **kwargs):
        form = KelolaPICTiketForm(tiket=self.tiket, role=self.role, instance=self.pic)
        return HttpResponse(self.render_html(**self.form_context(form)))

    def post(self, request, *args, **kwargs):
        form = KelolaPICTiketForm(
            request.POST, tiket=self.tiket, role=self.role, instance=self.pic,
        )
        if not form.is_valid():
            message = '; '.join(form.non_field_errors()) or 'Periksa kembali isian form.'
            return self.failure(message, **self.form_context(form))
        with transaction.atomic():
            ubah_pic(
                self.pic, form.cleaned_data['id_user'], form.cleaned_data['active'],
                request.user, datetime.now(),
            )
        return self.success(f'{_label(self.role)} tiket ini berhasil diubah.')


class HapusPICTiketView(_KelolaSatuPICMixin, _KelolaPICTiketBase):
    """GET: the delete confirmation; POST: delete the PIC row."""
    template_name = 'tiket/hapus_pic_tiket_modal_form.html'

    def confirm_context(self):
        # Removing the last active PIC leaves the role to nobody - say so.
        last_active = self.pic.active and not TiketPIC.objects.filter(
            id_tiket=self.tiket, role=self.role, active=True,
        ).exclude(pk=self.pic.pk).exists()
        return {
            'pic': self.pic,
            'last_active': last_active,
            'form_action': reverse(
                'tiket_pic_hapus', kwargs={'pk': self.tiket.pk, 'pic_pk': self.pic.pk},
            ),
        }

    def get(self, request, *args, **kwargs):
        return HttpResponse(self.render_html(**self.confirm_context()))

    def post(self, request, *args, **kwargs):
        username = self.pic.id_user.username
        with transaction.atomic():
            hapus_pic(self.pic, request.user, datetime.now())
        return self.success(f'{_label(self.role)} {username} berhasil dihapus dari tiket ini.')
