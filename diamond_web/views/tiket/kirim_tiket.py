"""Kirim Tiket Workflow Step - Generate ND Pengantar PIDE"""

from django.views.generic import FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.db import models as db_models
from django.shortcuts import redirect
from django.core.paginator import Paginator

from ...models.tiket import Tiket
from ...models.tiket_pic import TiketPIC
from ...models.kirim_pide_temp import KirimPideTemp
from ...forms.kirim_tiket import KirimTiketForm
from ..mixins import UserP3DERequiredMixin
from ...constants.tiket_status import STATUS_DITELITI, STATUS_DIKEMBALIKAN
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

        if tiket_pk:
            tiket = Tiket.objects.get(pk=tiket_pk)
            context['single_tiket'] = tiket
            context['form_action'] = reverse(
                'kirim_tiket_from_tiket', kwargs={'tiket_pk': tiket_pk}
            )
            context['tikets'] = None
        else:
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
            ).select_related(
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
                all_ids = list(
                    Tiket.objects.filter(
                        status_tiket__in=[STATUS_DITELITI, STATUS_DIKEMBALIKAN],
                        tanda_terima=True,
                        tiketpic__active=True,
                        tiketpic__role=TiketPIC.Role.P3DE,
                        tiketpic__id_user=self.request.user,
                    ).exclude(
                        id__in=KirimPideTemp.objects.values('id_tiket_id'),
                    ).exclude(
                        id_status_penelitian__deskripsi='Tidak Lengkap',
                    ).distinct().values_list('pk', flat=True)
                )
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
