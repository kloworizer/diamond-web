"""Edit Tiket View - P3DE action to change the isian of a tiket via modal.

For the PIC that owns a tiket, it may be edited only while it is in status
Direkam and no tanda terima has been created yet. Once a tanda terima exists
the isian is locked and the only remaining action is cancelling the tiket.

P3DE administrators (`admin`, `admin_p3de`, superusers) are exempt from that
lock so they can correct a tiket at any point in the workflow. Their edits are
recorded in the audit trail exactly like a PIC edit.
"""

from datetime import datetime
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import UpdateView
from django.http import JsonResponse
from django.db import transaction

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.pic import PIC
from ...forms.edit_tiket import EditTiketForm
from ...constants.tiket_action_types import TiketActionType
from ...constants.tiket_status import STATUS_DIREKAM
from ..mixins import is_admin_p3de


class EditTiketView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Allow the active P3DE PIC (or a P3DE admin) to edit a tiket's isian.

    Model: Tiket
    Form: EditTiketForm
    Template: tiket/edit_tiket_modal_form.html (AJAX modal)

    Access Control:
    - Requires @login_required
    - test_func() allows either:
        * a P3DE administrator (superuser, `admin` or `admin_p3de`), at any
          status and regardless of the tanda terima, or
        * the active P3DE PIC that owns the tiket, but only while
          tiket.status_tiket == STATUS_DIREKAM and tiket.tanda_terima is False

    Editable fields:
    - Everyone: the isian recorded at rekam time (periode/tahun, surat
      pengantar, bentuk & cara penyampaian, baris diterima, tanggal terima)
    - P3DE admins additionally: hasil penelitian (tgl teliti, baris lengkap /
      tidak lengkap, with status penelitian recalculated from them) and
      pengiriman ke PIDE (tgl nadine, nomor ND nadine, tgl kirim PIDE)

    Side Effects on Form Submission:
    - Tiket editable fields are updated (status_tiket is never changed)
    - A TiketAction (TiketActionType.DIUBAH) is recorded for the audit trail,
      for admin and PIC edits alike
    """
    model = Tiket
    form_class = EditTiketForm
    template_name = 'tiket/edit_tiket_modal_form.html'

    def _is_editable(self, tiket):
        """For a PIC, a tiket is editable only while Direkam and without a
        tanda terima. P3DE admins bypass this check entirely."""
        return tiket.status_tiket == STATUS_DIREKAM and not tiket.tanda_terima

    def test_func(self):
        user = self.request.user
        # P3DE administrators may correct a tiket whenever needed, so the
        # Direkam / tanda terima lock does not apply to them.
        if is_admin_p3de(user):
            return True
        tiket = self.get_object()
        if not self._is_editable(tiket):
            return False
        sub_jenis_data_ilap = tiket.id_periode_data.id_sub_jenis_data_ilap
        is_tiket_pic = TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=user,
            active=True,
            role=TiketPIC.Role.P3DE,
        ).exists()
        is_active_pic = PIC.objects.filter(
            tipe=PIC.TipePIC.P3DE,
            id_user=user,
            id_sub_jenis_data_ilap=sub_jenis_data_ilap,
            end_date__isnull=True,
        ).exists()
        return is_tiket_pic and is_active_pic

    def handle_no_permission(self):
        """Return a JSON 403 for AJAX requests, standard handling otherwise."""
        request = getattr(self, 'request', None)
        if request is not None and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
        return super().handle_no_permission()

    def get_form_kwargs(self):
        """Expose the later workflow isian to P3DE admins only."""
        kwargs = super().get_form_kwargs()
        kwargs['is_admin'] = is_admin_p3de(self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tiket = self.object
        sub_jenis_data_ilap = tiket.id_periode_data.id_sub_jenis_data_ilap
        ilap = sub_jenis_data_ilap.id_ilap

        context['form_action'] = reverse('edit_tiket', kwargs={'pk': tiket.pk})
        context['page_title'] = f'Ubah Isian Tiket - {tiket.nomor_tiket}'
        context['tiket'] = tiket
        # Periode options are populated client-side based on the periode penerimaan.
        context['periode_penerimaan'] = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
        # Whether tgl_terima_vertikal applies (regional ILAP), mirroring the rekam form.
        kategori_wilayah = ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else ''
        context['is_regional'] = 'regional' in (kategori_wilayah or '').lower()
        # Drives the admin-only section of the modal (hasil penelitian and
        # pengiriman ke PIDE); the form drops those fields for a PIC.
        context['is_admin_p3de'] = is_admin_p3de(self.request.user)
        return context

    def _build_catatan(self, form, original):
        """Summarise the changed fields (old → new) for the audit trail.

        Produces "isian tiket diubah — <Field>: <old> → <new>; ..." and always
        clamps the result to the catatan column length (255 chars).

        `original` is the tiket as stored before the edit, used to report the
        previous value of each changed field.
        """
        catatan_field = TiketAction._meta.get_field('catatan')
        max_len = catatan_field.max_length or 255

        parts = []
        for name in form.changed_data:
            try:
                label = Tiket._meta.get_field(name).verbose_name
            except Exception:
                label = name
            old_value = getattr(original, name, None) if original is not None else None
            new_value = form.cleaned_data.get(name)
            parts.append(
                f'{label}: {self._format_value(old_value)} → {self._format_value(new_value)}'
            )

        if parts:
            catatan = 'isian tiket diubah — ' + '; '.join(parts)
        else:
            catatan = 'isian tiket diubah'

        if len(catatan) > max_len:
            catatan = catatan[:max_len - 1].rstrip() + '…'
        return catatan

    @staticmethod
    def _format_value(value):
        """Render a field value compactly for the catatan text."""
        if value is None or value == '':
            return '-'
        if hasattr(value, 'deskripsi'):
            return value.deskripsi
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y %H:%M')
        return str(value)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Capture the pre-edit state before the form mutates the row so
                # the audit note can report each field's previous value.
                original = Tiket.objects.filter(pk=form.instance.pk).first()
                catatan = self._build_catatan(form, original)
                self.object = form.save()

                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=datetime.now(),
                    action=TiketActionType.DIUBAH,
                    catatan=catatan,
                )

                message = f'Isian tiket "{self.object.nomor_tiket}" berhasil diperbarui.'

                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': message})

                messages.success(self.request, message)
                return super().form_valid(form)
        except Exception as e:
            error_message = f'Gagal memperbarui isian tiket: {str(e)}'
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_message}, status=400)
            messages.error(self.request, error_message)
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Return validation errors as JSON for AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            error_messages = []
            for field, errors in form.errors.items():
                for err in errors:
                    error_messages.append(f'{field}: {err}' if field != '__all__' else err)
            message = '; '.join(error_messages) or 'Form tidak valid'
            return JsonResponse({
                'success': False,
                'message': message,
                'errors': form.errors,
            }, status=400)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
