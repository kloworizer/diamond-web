"""Kirim Tiket Workflow Step - Generate ND Pengantar PIDE"""

from datetime import datetime

from django.views.generic import FormView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.db import models as db_models
from django.shortcuts import redirect, get_object_or_404
from django.core.paginator import Paginator
from django.utils.html import format_html
from django.template.loader import render_to_string

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.kirim_pide_temp import KirimPideTemp
from ...models.ilap import ILAP
from ...models.notification import Notification
from ...forms.kirim_tiket import KirimTiketForm
from ...forms.kirim_ke_pide import KirimKePideForm
from ..mixins import UserP3DERequiredMixin, get_active_p3de_ilap_ids
from ...constants.tiket_status import STATUS_DITELITI, STATUS_DIKEMBALIKAN, STATUS_DIKIRIM_KE_PIDE
from ...constants.tiket_action_types import TiketActionType
from ..bulk_document_generation import _generate_docx_for_tickets


class KirimTiketView(LoginRequiredMixin, UserP3DERequiredMixin, FormView):
    """P3DE workflow step to generate ND Pengantar PIDE template.

    Shows tikets with status Diteliti/Dikembalikan where the current user is
    an active P3DE PIC. The user selects tikets via checkboxes and clicks
    'Generate Template' to:

    1. Save the selected tiket IDs and user ID to the KirimPideTemp table
       with a shared, auto-incremented id_temp value.
    2. Generate and download an ND Pengantar PIDE document using the bulk
       document generation engine (_generate_docx_for_tickets).

    Supports both single-tiket (from the tiket detail AJAX modal) and batch
    modes (standalone page with checkbox list).

    Form: KirimTiketForm (validates tiket_ids only)
    Template: tiket/kirim_tiket_form.html or modal variant for AJAX

    Access Control:
    - Requires @login_required
    - Requires UserP3DERequiredMixin (user in user_p3de / admin group)

    Side Effects on Submission:
    - Creates KirimPideTemp records for each selected tiket (shared id_temp)
    - Returns a DOCX file download (ND Pengantar PIDE) for non-AJAX requests
    - Returns JSON redirect to download URL for AJAX requests
    """
    form_class = KirimTiketForm
    template_name = 'tiket/kirim_tiket_form.html'
    success_url = reverse_lazy('tiket_list')

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def get_context_data(self, **kwargs):
        """Build context with tikets available for template generation.

        Single-tiket mode (tiket_pk in URL):
        - context['single_tiket']: The specific tiket
        - context['tikets']: None

        Batch mode (no tiket_pk):
        - context['tikets']: Tikets where:
            * status_tiket in (DITELITI, DIKEMBALIKAN)
            * tanda_terima=True (receipt data recorded)
            * User is active P3DE PIC for each tiket
          Display columns: nomor tiket, nama ilap, sub jenis data, status tiket
        - context['single_tiket']: None

        Both modes:
        - context['form_action']: Form submission URL
        - context['page_title']: 'Generate ND Pengantar PIDE'
        - context['workflow_step']: 'kirim_tiket'
        """
        context = super().get_context_data(**kwargs)
        tiket_pk = self.kwargs.get('tiket_pk')
        context['page_title'] = 'Generate ND Pengantar PIDE'
        context['workflow_step'] = 'kirim_tiket'

        selected_ilap_id = self.request.GET.get('ilap_id', '')
        context['selected_ilap_id'] = selected_ilap_id

        if tiket_pk:
            tiket = Tiket.objects.get(pk=tiket_pk)
            context['single_tiket'] = tiket
            context['form_action'] = reverse(
                'kirim_tiket_from_tiket', kwargs={'tiket_pk': tiket_pk}
            )
            context['tikets'] = None
            # ILAP options based on user access for single-tiket mode
            if self.request.user.is_superuser or self.request.user.groups.filter(
                name__in=['admin', 'admin_p3de']
            ).exists():
                ilap_options = ILAP.objects.order_by('nama_ilap')
            else:
                ilap_ids = get_active_p3de_ilap_ids(self.request.user)
                ilap_options = ILAP.objects.filter(id__in=ilap_ids).order_by('nama_ilap')
        else:
            # Build the base tiket queryset first (without ILAP filter)
            tikets = Tiket.objects.filter(
                status_tiket__in=[STATUS_DITELITI, STATUS_DIKEMBALIKAN],
                tanda_terima=True,
                tiketpic__active=True,
                tiketpic__role=TiketPIC.Role.P3DE,
                tiketpic__id_user=self.request.user,
            ).exclude(
                id__in=KirimPideTemp.objects.values('id_tiket_id'),
            ).exclude(
                id_status_penelitian__deskripsi='Tidak Lengkap',
            )

            # Derive ILAP options from the actual tiket list (before filter)
            ilap_ids_in_list = set(
                tikets.values_list(
                    'id_periode_data__id_sub_jenis_data_ilap__id_ilap_id',
                    flat=True,
                ).distinct()
            )
            ilap_options = ILAP.objects.filter(
                id__in=ilap_ids_in_list
            ).order_by('nama_ilap')

            # --- Apply ILAP filter if selected ---
            if selected_ilap_id:
                tikets = tikets.filter(
                    id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=selected_ilap_id
                )

            tikets = tikets.select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_status_penelitian',
            ).distinct().order_by('id')

            paginator = Paginator(tikets, 25)
            page_number = self.request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            context['tikets'] = page_obj.object_list
            context['page_obj'] = page_obj
            context['paginator'] = paginator
            context['total_count'] = paginator.count
            context['form_action'] = reverse('kirim_tiket')

        context['ilap_options'] = ilap_options
        context['selected_ilap_id'] = selected_ilap_id

        # --- KirimPideTemp groups for Tab 2 (always show all, no ILAP filter) ---
        temp_groups_qs = KirimPideTemp.objects.filter(id_user=self.request.user)

        temp_groups = list(
            temp_groups_qs
            .values('id_temp')
            .annotate(jumlah_tiket=db_models.Count('id_tiket'))
            .order_by('-id_temp')
        )

        # Attach list of nomor_tiket to each group
        for group in temp_groups:
            tiket_nomor_list = (
                KirimPideTemp.objects.filter(
                    id_temp=group['id_temp'],
                    id_user=self.request.user,
                )
                .select_related('id_tiket')
                .values_list('id_tiket__nomor_tiket', flat=True)
            )
            group['daftar_nomor_tiket'] = list(tiket_nomor_list)

        context['temp_groups'] = temp_groups
        return context

    # ------------------------------------------------------------------
    # Template selection
    # ------------------------------------------------------------------
    def get_template_names(self):
        """Return modal template for AJAX requests, full page otherwise."""
        if self.is_ajax_request():
            return ['tiket/kirim_tiket_modal_form.html']
        return [self.template_name]

    # ------------------------------------------------------------------
    # Initial / form kwargs
    # ------------------------------------------------------------------
    def get_initial(self):
        """Pre-populate tiket_ids for single-tiket mode."""
        initial = super().get_initial()
        tiket_pk = self.kwargs.get('tiket_pk')
        if tiket_pk:
            initial['tiket_ids'] = str(tiket_pk)
        return initial

    def get_form_kwargs(self):
        """Ensure tiket_ids is populated from checkboxes on POST.

        Handles both the explicit tiket_ids hidden field and the
        tiket-select checkbox array used in the batch template.
        """
        kwargs = super().get_form_kwargs()
        if self.request.method == 'POST':
            data = self.request.POST.copy()
            selected_ids = data.get('tiket_ids')
            if not selected_ids:
                selected_ids = ','.join(
                    self.request.POST.getlist('tiket-select')
                )
            if selected_ids:
                data['tiket_ids'] = selected_ids
            kwargs['data'] = data
        return kwargs

    # ------------------------------------------------------------------
    # AJAX helpers
    # ------------------------------------------------------------------
    def is_ajax_request(self):
        """Check whether the request is an AJAX (XMLHttpRequest) call."""
        return self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def get_json_response(self, success=True, message='', errors=None,
                          redirect=None):
        """Return a standardised JSON payload for AJAX clients."""
        response = {'success': success, 'message': message}
        if errors:
            response['errors'] = errors
        if redirect:
            response['redirect'] = redirect
        return JsonResponse(response)

    # ------------------------------------------------------------------
    # Form submission
    # ------------------------------------------------------------------
    def form_valid(self, form):
        """Handle form submission: save temp records + generate DOCX.

        For non-AJAX (batch page): returns the DOCX file directly.
        For AJAX (modal): returns JSON with redirect to download URL,
        since file downloads cannot be triggered from fetch().
        """
        try:
            tiket_ids = [
                int(pid.strip())
                for pid in form.cleaned_data['tiket_ids'].split(',')
                if pid.strip()
            ]

            # --- Handle "select all pages" mode ---
            select_all_pages = self.request.POST.get('select_all_pages') == 'true'
            if select_all_pages:
                all_ids_qs = Tiket.objects.filter(
                    status_tiket__in=[STATUS_DITELITI, STATUS_DIKEMBALIKAN],
                    tanda_terima=True,
                    tiketpic__active=True,
                    tiketpic__role=TiketPIC.Role.P3DE,
                    tiketpic__id_user=self.request.user,
                ).exclude(
                    id__in=KirimPideTemp.objects.values('id_tiket_id'),
                ).exclude(
                    id_status_penelitian__deskripsi='Tidak Lengkap',
                )

                # Apply ILAP filter to "select all pages" if provided
                ilap_id = self.request.POST.get('ilap_id', '')
                if ilap_id:
                    all_ids_qs = all_ids_qs.filter(
                        id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=ilap_id
                    )

                all_ids = list(all_ids_qs.distinct().values_list('pk', flat=True))
            else:
                all_ids = tiket_ids

            tikets = Tiket.objects.filter(id__in=all_ids)

            # --- Permission check ---
            unauthorized = []
            already_generated = []
            already_temp_ids = set(
                KirimPideTemp.objects.values_list('id_tiket_id', flat=True)
            )
            for tiket in tikets:
                if tiket.pk in already_temp_ids:
                    already_generated.append(tiket.nomor_tiket)
                elif not TiketPIC.objects.filter(
                    id_tiket=tiket,
                    id_user=self.request.user,
                    active=True,
                    role=TiketPIC.Role.P3DE,
                ).exists():
                    unauthorized.append(tiket.nomor_tiket)

            if already_generated:
                msg = (
                    'Tiket berikut sudah pernah digenerate template-nya: '
                    f"{', '.join(already_generated)}. "
                    'Silakan hapus dari KirimPideTemp terlebih dahulu.'
                )
                if self.is_ajax_request():
                    return self.get_json_response(success=False, message=msg)
                messages.error(self.request, msg)
                return self.form_invalid(form)

            if unauthorized:
                msg = (
                    'Anda bukan PIC P3DE aktif untuk tiket: '
                    f'{", ".join(unauthorized)}'
                )
                if self.is_ajax_request():
                    return self.get_json_response(success=False, message=msg)
                messages.error(self.request, msg)
                return self.form_invalid(form)

            with transaction.atomic():
                # --- Generate an incremental id_temp ---
                max_temp = (
                    KirimPideTemp.objects.aggregate(
                        max_id=db_models.Max('id_temp')
                    )['max_id']
                    or 0
                )
                new_id_temp = max_temp + 1

                # --- Persist to KirimPideTemp ---
                for tiket in tikets:
                    KirimPideTemp.objects.create(
                        id_temp=new_id_temp,
                        id_tiket=tiket,
                        id_user=self.request.user,
                    )

            # --- Non-AJAX: generate and return DOCX directly ---
            if not self.is_ajax_request():
                selected_tickets = list(
                    Tiket.objects.filter(id__in=all_ids)
                    .select_related(
                        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                        'id_periode_data__id_periode_pengiriman',
                        'id_periode_data__id_sub_jenis_data_ilap__id_status_data',
                        'id_status_penelitian',
                    )
                    .prefetch_related(
                        'id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata_set__id_klasifikasi_tabel',
                    )
                    .order_by('id')
                )

                response = _generate_docx_for_tickets(
                    selected_tickets,
                    'nd_pengantar',
                    f'nd_pengantar_pide_{new_id_temp}',
                )
                if response:
                    return response

                # Fallback
                messages.success(self.request, 'Template berhasil digenerate.')
                return super().form_valid(form)

            # --- AJAX: return JSON with download redirect ---
            download_url = reverse(
                'kirim_tiket_download',
                kwargs={'id_temp': new_id_temp},
            )
            return self.get_json_response(
                success=True,
                message='Template berhasil digenerate.',
                redirect=download_url,
            )

        except Exception as e:
            error_message = f'Gagal generate template: {str(e)}'
            if self.is_ajax_request():
                return self.get_json_response(
                    success=False, errors={'__all__': [error_message]}
                )
            messages.error(self.request, error_message)
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Return validation errors in the appropriate format."""
        if self.is_ajax_request():
            return self.get_json_response(success=False, errors=form.errors)
        return super().form_invalid(form)


class DownloadNDPengantarView(LoginRequiredMixin, UserP3DERequiredMixin, View):
    """Serve the ND Pengantar PIDE document for a given id_temp.

    Looks up the KirimPideTemp records, loads the associated tikets, and
    generates the DOCX on-the-fly using _generate_docx_for_tickets.
    Used for AJAX-triggered downloads (from the tiket detail modal).
    """
    def get(self, request, id_temp):
        temp_records = list(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .select_related('id_tiket')
        )
        if not temp_records:
            messages.error(request, 'Data template tidak ditemukan.')
            return redirect('tiket_list')

        # Verify the requesting user owns this temp batch
        if any(r.id_user != request.user for r in temp_records):
            return HttpResponseForbidden('Anda tidak berhak mengakses data ini.')

        tiket_ids = [r.id_tiket_id for r in temp_records]

        selected_tickets = list(
            Tiket.objects.filter(id__in=tiket_ids)
            .select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_periode_pengiriman',
                'id_periode_data__id_sub_jenis_data_ilap__id_status_data',
                'id_status_penelitian',
            )
            .prefetch_related(
                'id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata_set__id_klasifikasi_tabel',
            )
            .order_by('id')
        )

        response = _generate_docx_for_tickets(
            selected_tickets,
            'nd_pengantar',
            f'nd_pengantar_pide_{id_temp}',
        )
        if response:
            return response

        messages.error(request, 'Gagal menghasilkan dokumen.')
        return redirect('tiket_list')


class KirimPideTempUpdateView(LoginRequiredMixin, UserP3DERequiredMixin, View):
    """Update KirimPideTemp tickets for a given id_temp.

    GET: Returns modal HTML with all eligible tickets shown as checkboxes.
         Existing tickets in this id_temp are pre-checked.
    POST: Adds newly checked tickets and removes unchecked ones.
    """

    def get_eligible_tikets(self, request, id_temp):
        """Return queryset of all tikets eligible for this id_temp.

        Includes tikets already in this id_temp plus tikets not in any temp batch.
        Excludes tikets that belong to OTHER temp batches.
        """
        # Tickets already in THIS id_temp
        existing_ids = set(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .values_list('id_tiket_id', flat=True)
        )
        # All tiket IDs in ANY temp batch (except current one)
        other_temp_ids = set(
            KirimPideTemp.objects.exclude(id_temp=id_temp)
            .values_list('id_tiket_id', flat=True)
        )
        return Tiket.objects.filter(
            status_tiket__in=[STATUS_DITELITI, STATUS_DIKEMBALIKAN],
            tanda_terima=True,
            tiketpic__active=True,
            tiketpic__role=TiketPIC.Role.P3DE,
            tiketpic__id_user=request.user,
        ).exclude(
            id__in=other_temp_ids,
        ).exclude(
            id_status_penelitian__deskripsi='Tidak Lengkap',
        ).select_related(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
            'id_status_penelitian',
        ).distinct().order_by('id')

    def get(self, request, id_temp):
        """Return modal HTML with all eligible tikets as checkboxes."""
        temp_records = list(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .select_related('id_tiket')
        )
        if not temp_records:
            return JsonResponse(
                {'success': False, 'message': 'Data tidak ditemukan.'},
                status=404,
            )
        if any(r.id_user != request.user for r in temp_records):
            return JsonResponse(
                {'success': False, 'message': 'Anda tidak berhak.'},
                status=403,
            )

        existing_tiket_ids = set(r.id_tiket_id for r in temp_records)
        eligible_tikets = self.get_eligible_tikets(request, id_temp)

        # Attach is_in_temp flag to each tiket
        all_tikets = []
        for tiket in eligible_tikets:
            tiket.is_in_temp = tiket.pk in existing_tiket_ids
            # Flatten related fields for easier template access
            tiket.nama_ilap = (
                tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap.nama_ilap
                if tiket.id_periode_data and
                tiket.id_periode_data.id_sub_jenis_data_ilap and
                tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
                else '-'
            )
            tiket.nama_sub_jenis_data = (
                tiket.id_periode_data.id_sub_jenis_data_ilap.nama_sub_jenis_data
                if tiket.id_periode_data and
                tiket.id_periode_data.id_sub_jenis_data_ilap
                else '-'
            )
            all_tikets.append(tiket)

        html = render_to_string(
            'tiket/kirim_pide_temp_update_modal.html',
            {
                'id_temp': id_temp,
                'all_tikets': all_tikets,
            },
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})

    def post(self, request, id_temp):
        """Update selected tikets: add newly checked, remove unchecked."""
        temp_records = list(
            KirimPideTemp.objects.filter(id_temp=id_temp)
        )
        if not temp_records:
            return JsonResponse(
                {'success': False, 'message': 'Data tidak ditemukan.'},
                status=404,
            )
        if any(r.id_user != request.user for r in temp_records):
            return JsonResponse(
                {'success': False, 'message': 'Anda tidak berhak.'},
                status=403,
            )

        checked_ids = set()
        raw_ids = request.POST.getlist('tiket_ids')
        for tid in raw_ids:
            try:
                checked_ids.add(int(tid))
            except (ValueError, TypeError):
                pass

        if not checked_ids:
            return JsonResponse(
                {'success': False, 'message': 'Pilih minimal satu tiket.'},
            )

        existing_ids = set(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .values_list('id_tiket_id', flat=True)
        )

        # Tickets to remove: in existing but NOT in checked list
        to_remove_ids = existing_ids - checked_ids
        # Tickets to add: in checked list but NOT in existing
        to_add_ids = checked_ids - existing_ids

        eligible = self.get_eligible_tikets(request, id_temp)
        eligible_ids = set(eligible.values_list('pk', flat=True))

        removed = 0
        added = 0
        with transaction.atomic():
            if to_remove_ids:
                # Only remove tickets that belong to this id_temp
                removed_count, _ = KirimPideTemp.objects.filter(
                    id_temp=id_temp,
                    id_tiket_id__in=to_remove_ids,
                ).delete()
                removed = removed_count

            for tid_int in to_add_ids:
                if tid_int in eligible_ids:
                    KirimPideTemp.objects.create(
                        id_temp=id_temp,
                        id_tiket_id=tid_int,
                        id_user=request.user,
                    )
                    added += 1

        messages_parts = []
        if added:
            messages_parts.append(f'{added} tiket ditambahkan.')
        if removed:
            messages_parts.append(f'{removed} tiket dihapus.')
        message = ' '.join(messages_parts) if messages_parts else 'Tidak ada perubahan.'

        return JsonResponse({
            'success': True,
            'message': message,
        })


class KirimPideTempDeleteView(LoginRequiredMixin, UserP3DERequiredMixin, View):
    """Delete all KirimPideTemp records for a given id_temp."""

    def post(self, request, id_temp):
        records = list(KirimPideTemp.objects.filter(id_temp=id_temp))
        if not records:
            return JsonResponse(
                {'success': False, 'message': 'Data tidak ditemukan.'},
                status=404,
            )
        if any(r.id_user != request.user for r in records):
            return JsonResponse(
                {'success': False, 'message': 'Anda tidak berhak.'},
                status=403,
            )
        pks = [r.pk for r in records]
        count, _ = KirimPideTemp.objects.filter(pk__in=pks).delete()
        return JsonResponse({
            'success': True,
            'message': f'{count} record berhasil dihapus.',
        })


class KirimKePIDEView(LoginRequiredMixin, UserP3DERequiredMixin, View):
    """Send tickets in a KirimPideTemp group to PIDE.

    GET: Returns modal HTML with form for ND Nadine reference details.
    POST: Updates all tickets in the group to 'Dikirim ke PIDE' status,
          sets ND Nadine reference fields, logs TiketAction, and cleans up
          the temp records.
    """

    def get(self, request, id_temp):
        """Return modal HTML with form for Kirim ke PIDE."""
        temp_records = list(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .select_related('id_tiket')
        )
        if not temp_records:
            return JsonResponse(
                {'success': False, 'message': 'Data tidak ditemukan.'},
                status=404,
            )
        if any(r.id_user != request.user for r in temp_records):
            return JsonResponse(
                {'success': False, 'message': 'Anda tidak berhak.'},
                status=403,
            )

        tikets = Tiket.objects.filter(
            id__in=[r.id_tiket_id for r in temp_records]
        ).select_related(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        )

        form = KirimKePideForm()

        html = render_to_string(
            'tiket/kirim_ke_pide_modal.html',
            {
                'form': form,
                'id_temp': id_temp,
                'tikets': tikets,
                'jumlah_tiket': len(temp_records),
                'form_action': reverse('kirim_ke_pide', kwargs={'id_temp': id_temp}),
            },
            request=request,
        )
        return JsonResponse({'success': True, 'html': html})

    def post(self, request, id_temp):
        """Update all tickets in the group to status 'Dikirim ke PIDE'."""
        temp_records = list(
            KirimPideTemp.objects.filter(id_temp=id_temp)
            .select_related('id_tiket')
        )
        if not temp_records:
            return JsonResponse(
                {'success': False, 'message': 'Data tidak ditemukan.'},
                status=404,
            )
        if any(r.id_user != request.user for r in temp_records):
            return JsonResponse(
                {'success': False, 'message': 'Anda tidak berhak.'},
                status=403,
            )

        tiket_ids = [r.id_tiket_id for r in temp_records]
        tikets = Tiket.objects.filter(id__in=tiket_ids)

        form = KirimKePideForm(request.POST, tiket_list=list(tikets))
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'message': 'Form tidak valid.',
                'errors': form.errors,
            }, status=400)

        now = datetime.now()

        try:
            with transaction.atomic():
                tgl_nadine = form.cleaned_data.get('tgl_nadine')
                nomor_nd_nadine = form.cleaned_data.get('nomor_nd_nadine')
                tgl_kirim_pide = form.cleaned_data.get('tgl_kirim_pide')

                sender_name = (request.user.get_full_name() or request.user.username).strip()

                for tiket in tikets:
                    tiket.status_tiket = STATUS_DIKIRIM_KE_PIDE
                    if tgl_nadine:
                        tiket.tgl_nadine = tgl_nadine
                    if nomor_nd_nadine:
                        tiket.nomor_nd_nadine = nomor_nd_nadine
                    if tgl_kirim_pide:
                        tiket.tgl_kirim_pide = tgl_kirim_pide
                    tiket.save()

                    TiketAction.objects.create(
                        id_tiket=tiket,
                        id_user=request.user,
                        timestamp=now,
                        action=TiketActionType.DIKIRIM_KE_PIDE,
                        catatan=f'tiket dikirim ke PIDE',
                    )

                    # Send notification to active PIDE PICs
                    tiket_detail_path = reverse('tiket_detail', kwargs={'pk': tiket.pk})
                    notif_message = format_html(
                        'Tiket <a href="{}">{}</a> telah dikirim ke PIDE oleh {}.',
                        tiket_detail_path,
                        tiket.nomor_tiket or str(tiket.pk),
                        sender_name,
                    )
                    active_pide_pics = TiketPIC.objects.filter(
                        id_tiket=tiket,
                        active=True,
                        role=TiketPIC.Role.PIDE,
                    ).select_related('id_user')
                    for pic in active_pide_pics:
                        Notification.objects.create(
                            recipient=pic.id_user,
                            title='Tiket Dikirim ke PIDE',
                            message=notif_message,
                        )

                # Clean up temp records
                KirimPideTemp.objects.filter(id_temp=id_temp).delete()

            message = f'{len(tikets)} tiket berhasil dikirim ke PIDE.'
            return JsonResponse({'success': True, 'message': message})

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Gagal mengirim tiket: {str(e)}',
            }, status=500)
