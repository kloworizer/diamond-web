from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, TemplateView, DetailView
from django.contrib import messages
from urllib.parse import quote_plus, unquote_plus
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from ..models.tanda_terima_data import TandaTerimaData
from ..models.detil_tanda_terima import DetilTandaTerima
from ..models.tiket_action import TiketAction
from ..models.tiket_pic import TiketPIC
from ..models.tiket import Tiket
from ..forms.tanda_terima_data import TandaTerimaDataForm
from ..constants.tiket_action_types import TandaTerimaActionType
from .mixins import AjaxFormMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin
from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE


class TandaTerimaDataListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for `TandaTerimaData` entries for P3DE users.

    Renders `tanda_terima_data/list.html`. Non-admin users are restricted
    to records where they are an active `TiketPIC` with role P3DE. When the
    view is redirected from a delete operation it reads `deleted` and
    `name` query parameters (URL-encoded) and registers a Django
    `messages.success` notification for the frontend toast.
    """
    template_name = 'tanda_terima_data/list.html'

    def get(self, request, *args, **kwargs):
        deleted = request.GET.get('deleted')
        name = request.GET.get('name')
        if deleted and name:
            try:
                name = unquote_plus(name)
                messages.success(request, f'Tanda Terima Data "{name}" dibatalkan.')
            except Exception:
                pass
        return super().get(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def tanda_terima_data_data(request):
    """DataTables server-side endpoint for `TandaTerimaData`.

    GET parameters (DataTables): `draw`, `start`, `length`, `columns_search[]`,
    `search[value]`, `order[0][column]`, `order[0][dir]`.

    Permissions: wrapped by decorators to allow only users in `admin` or
    `user_p3de` groups. Non-admin users are further restricted to
    `TandaTerimaData` instances that reference tickets where they are an
    active P3DE `TiketPIC`.

    Returns: JSON with `draw`, `recordsTotal`, `recordsFiltered`, and
    `data` rows. Each row includes `id`, `nomor_tanda_terima`,
    `tanggal_tanda_terima`, `id_ilap`, `deskripsi`, `id_perekam`, `status`,
    and `actions` HTML depending on the requesting user's permissions.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = TandaTerimaData.objects.select_related('id_ilap', 'id_perekam').all()
    if not request.user.is_superuser and not request.user.groups.filter(name='admin').exists():
        qs = qs.filter(
            detil_items__id_tiket__tiketpic__id_user=request.user,
            detil_items__id_tiket__tiketpic__role=TiketPIC.Role.P3DE
        ).distinct()
    records_total = qs.count()

    # Column-specific filtering
    columns_search = request.GET.getlist('columns_search[]')
    if columns_search:
        if columns_search[0]:  # Nomor Tanda Terima
            qs = qs.filter(nomor_tanda_terima__icontains=columns_search[0])
        if len(columns_search) > 1 and columns_search[1]:  # Tanggal
            qs = qs.filter(tanggal_tanda_terima__icontains=columns_search[1])
        if len(columns_search) > 2 and columns_search[2]:  # ILAP
            qs = qs.filter(id_ilap__nama_ilap__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:  # Deskripsi
            qs = qs.filter(deskripsi__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:  # Perekam
            qs = qs.filter(id_perekam__username__icontains=columns_search[4])
        if len(columns_search) > 5 and columns_search[5]:  # Status
            status_value = columns_search[5].strip().lower()
            if status_value in ['dibatalkan', 'batal', 'false', '0']:
                qs = qs.filter(active=False)
            elif status_value in ['aktif', 'active', 'true', '1']:
                qs = qs.filter(active=True)

    records_filtered = qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    columns = ['nomor_tanda_terima', 'tanggal_tanda_terima', 'id_ilap__nama_ilap', 'deskripsi', 'id_perekam__username', 'active']
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'nomor_tanda_terima'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('-tanggal_tanda_terima')
    else:
        qs = qs.order_by('-tanggal_tanda_terima')

    qs_page = qs[start:start + length]

    data = []
    from django.db.models import Q

    for obj in qs_page:
        status_text = 'Aktif' if obj.active else 'Dibatalkan'
        can_edit = obj.detil_items.filter(
                Q(id_tiket__status__lt=STATUS_DIKIRIM_KE_PIDE) | Q(id_tiket__status__isnull=True)
        ).exists()
        
        # Check if user is active PIC for any tiket in this tanda terima
        is_active_pic = TiketPIC.objects.filter(
            id_tiket__detiltandaterima__id_tanda_terima=obj,
            id_user=request.user,
            active=True,
            role=TiketPIC.Role.P3DE
        ).exists()
        
        actions_html = ''
        # Show view button only for active PIC
        if is_active_pic:
            actions_html = f"<button class='btn btn-sm btn-info me-1' data-action='view' data-url='{reverse('tanda_terima_data_view', args=[obj.pk])}' title='Detail'><i class='ri-eye-line'></i></button>"
        
        # Show delete button only for active PIC when tanda terima is active
        if obj.active and can_edit and is_active_pic:
            actions_html += f"<button class='btn btn-sm btn-warning' data-action='delete' data-url='{reverse('tanda_terima_data_delete', args=[obj.pk])}' title='Batalkan'><i class='ri-close-circle-line'></i></button>"
        
        data.append({
            'id': obj.pk,
            'nomor_tanda_terima': obj.nomor_tanda_terima,
            'tanggal_tanda_terima': obj.tanggal_tanda_terima.strftime('%Y-%m-%d %H:%M'),
            'id_ilap': str(obj.id_ilap),
            'deskripsi': obj.deskripsi,
            'id_perekam': obj.id_perekam.username,
            'status': status_text,
            'actions': actions_html
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def tanda_terima_next_number(request):
    """Return next sequential `nomor_tanda_terima` for a given year.

    Query params:
    - `tanggal` (optional): ISO date or datetime. If omitted current date
      year is used.

    Response JSON: { 'success': True, 'nomor_tanda_terima': <string> }
    """
    tanggal_param = request.GET.get('tanggal')
    tanggal = parse_datetime(tanggal_param) if tanggal_param else None
    if tanggal is None and tanggal_param:
        tanggal = parse_date(tanggal_param)

    tahun = (tanggal or timezone.now()).year
    suffix = f"/{tahun}"

    existing_numbers = TandaTerimaData.objects.filter(
        nomor_tanda_terima__endswith=suffix
    ).values_list('nomor_tanda_terima', flat=True)

    max_seq = 0
    for nomor in existing_numbers:
        try:
            seq_part = nomor.split('/')[0]
            max_seq = max(max_seq, int(seq_part))
        except Exception:
            continue

    next_seq = max_seq + 1
    nomor_tanda_terima = f"{str(next_seq).zfill(5)}/{tahun}"

    return JsonResponse({
        'success': True,
        'nomor_tanda_terima': nomor_tanda_terima
    })


@login_required
@user_passes_test(lambda u: u.groups.filter(name__in=['admin', 'user_p3de']).exists())
@require_GET
def tanda_terima_tikets_by_ilap(request):
    """Return available `Tiket` options for a given ILAP for selection.

    Query params:
    - `ilap_id` (required): ILAP primary key.
    - `tanda_terima_id` (optional): current tanda terima id when editing to
        allow already-selected tickets to remain selected.

    Behavior:
    - Filters `Tiket` with `status < STATUS_DIKIRIM_KE_PIDE` and that
        reference the given ILAP via `id_periode_data__id_sub_jenis_data_ilap`.
    - Excludes tickets already assigned to an active `TandaTerimaData` for
        the same ILAP (unless they belong to the editing `tanda_terima_id`).

    Returns JSON: { 'success': True, 'data': [ {id,label,selected,disabled}, ... ] }
    """
    ilap_id = request.GET.get('ilap_id')
    tanda_terima_id = request.GET.get('tanda_terima_id')  # Optional, for edit mode
    
    if not ilap_id:
        return JsonResponse({'success': False, 'error': 'ilap_id is required'}, status=400)

    # Get existing tikets if editing
    existing_tiket_ids = set()
    if tanda_terima_id:
        try:
            existing_tiket_ids = set(
                DetilTandaTerima.objects.filter(id_tanda_terima_id=int(tanda_terima_id))
                .values_list('id_tiket_id', flat=True)
            )
        except (ValueError, TypeError):
            pass

    # Get tikets assigned to active tanda terima for THIS ILAP (exclude current one if editing)
    other_assigned_tiket_ids = set(
        DetilTandaTerima.objects.filter(
            id_tanda_terima__active=True,
            id_tanda_terima__id_ilap_id=ilap_id
        ).exclude(
            id_tanda_terima_id=tanda_terima_id
        ).values_list('id_tiket_id', flat=True)
    )

    # Get available tikets
    available_tikets = Tiket.objects.filter(
        status__lt=STATUS_DIKIRIM_KE_PIDE,
        id_periode_data__id_sub_jenis_data_ilap__id_ilap_id=ilap_id
    ).exclude(
        id__in=other_assigned_tiket_ids
    ).order_by('nomor_tiket')

    data = [
        {
            'id': t.id,
            'label': t.nomor_tiket or f"Tiket {t.id}",
            'selected': t.id in existing_tiket_ids,
            'disabled': t.id in existing_tiket_ids  # Disable existing tikets
        }
        for t in available_tikets
    ]

    return JsonResponse({'success': True, 'data': data})


class TandaTerimaDataCreateView(LoginRequiredMixin, UserP3DERequiredMixin, AjaxFormMixin, CreateView):
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_url = reverse_lazy('tanda_terima_data_list')
    success_message = 'Tanda Terima Data "{object}" berhasil dibuat.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_create')
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        # Set the logged-in user as id_perekam
        form.instance.id_perekam = self.request.user
        response = super().form_valid(form)
        
        # Save selected tikets to DetilTandaTerima
        tiket_ids = form.cleaned_data.get('tiket_ids', [])
        for tiket in tiket_ids:
            # Ensure we have a Tiket instance whether the form returned
            # an instance or a primary key
            if hasattr(tiket, 'id'):
                tiket_obj = tiket
            else:
                try:
                    tiket_obj = Tiket.objects.get(pk=tiket)
                except Exception:
                    # skip invalid tiket ids
                    continue

            DetilTandaTerima.objects.create(
                id_tanda_terima=self.object,
                id_tiket=tiket_obj
            )

            # Mark tiket as having tanda terima and persist
            tiket_obj.tanda_terima = True
            tiket_obj.save(update_fields=["tanda_terima"])

            TiketAction.objects.create(
                id_tiket=tiket_obj,
                id_user=self.request.user,
                timestamp=timezone.now(),
                action=TandaTerimaActionType.DIREKAM,
                catatan='Tanda terima dibuat'
            )
        
        return response


class TandaTerimaDataFromTiketCreateView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, AjaxFormMixin, CreateView):
    """Create Tanda Terima Data from a specific Tiket."""
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_message = 'Tanda Terima Data "{object}" berhasil dibuat.'

    def get_success_url(self):
        return reverse('tiket_detail', kwargs={'pk': self.kwargs['tiket_pk']})
    
    def test_func(self):
        """Check if user is active PIC for this tiket"""
        tiket_pk = self.kwargs.get('tiket_pk')
        if not tiket_pk:
            return False
        try:
            tiket = Tiket.objects.get(pk=tiket_pk)
            return TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=self.request.user,
                    active=True,
                    role=TiketPIC.Role.P3DE
            ).exists()
        except Tiket.DoesNotExist:
            return False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tiket_pk'] = self.kwargs.get('tiket_pk')
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_from_tiket_create', args=[self.kwargs['tiket_pk']])
        from ..models.tiket import Tiket
        context['tiket'] = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        return context

    def get(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        return self.render_form_response(form)

    def form_valid(self, form):
        from ..models.tiket import Tiket
        
        # Set the logged-in user as id_perekam
        form.instance.id_perekam = self.request.user
        # Ensure ILAP is set from tiket for single-tiket flow
        tiket = Tiket.objects.get(pk=self.kwargs['tiket_pk'])
        if tiket.id_periode_data:
            form.instance.id_ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
        
        # Save the form (this sets self.object)
        self.object = form.save()
        
        # Create DetilTandaTerima for the specific tiket
        DetilTandaTerima.objects.create(
            id_tanda_terima=self.object,
            id_tiket=tiket
        )

        # Update tiket status and record action
        tiket.tanda_terima = True
        tiket.save(update_fields=["tanda_terima"])
        TiketAction.objects.create(
            id_tiket=tiket,
            id_user=self.request.user,
            timestamp=timezone.now(),
            action=TandaTerimaActionType.DIREKAM,
            catatan='Tanda terima dibuat'
        )
        
        # Now handle the response (AJAX or redirect)
        message = self.get_success_message(form)
        if self.is_ajax():
            payload = {"success": True}
            if message:
                payload["message"] = message
            return JsonResponse(payload)
        if message:
            messages.success(self.request, message)
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())


class TandaTerimaDataUpdateView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, AjaxFormMixin, UpdateView):
    model = TandaTerimaData
    form_class = TandaTerimaDataForm
    template_name = 'tanda_terima_data/form.html'
    success_url = reverse_lazy('tanda_terima_data_list')
    success_message = 'Tanda Terima Data "{object}" berhasil diperbarui.'
    
    def test_func(self):
        """Check if user is active PIC for any tiket in this tanda terima"""
        tanda_terima = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket__detiltandaterima__id_tanda_terima=tanda_terima,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.P3DE
        ).exists()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_update', args=[self.object.pk])
        context['tanda_terima_id'] = self.object.pk  # Pass ID for edit mode
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Prevent edit if any tiket in this tanda terima is dibatalkan
        if not self.object.active or self.object.detil_items.filter(id_tiket__status__gte=STATUS_DIKIRIM_KE_PIDE).exists():
            return JsonResponse({'success': False, 'message': 'Tanda terima atau tiket sudah dibatalkan, tidak dapat diedit.', 'html': '<div class="alert alert-warning">Tanda terima atau tiket sudah dibatalkan, tidak dapat diedit.</div>'})
        form = self.get_form()
        return self.render_form_response(form)
    
    def form_valid(self, form):
        # Save the form first (this is done by the parent UpdateView)
        self.object = form.save()
        
        try:
            # Update tiket selections
            tiket_ids = form.cleaned_data.get('tiket_ids', [])
            
            # Get existing tiket IDs before deletion
            existing_tiket_ids = set(
                DetilTandaTerima.objects.filter(id_tanda_terima=self.object)
                .values_list('id_tiket_id', flat=True)
            )
            
            # Delete existing detil items
            DetilTandaTerima.objects.filter(id_tanda_terima=self.object).delete()
            
            # Create new detil items and update tiket status
            for tiket in tiket_ids:
                # Resolve tiket instance if needed
                if hasattr(tiket, 'id'):
                    tiket_obj = tiket
                else:
                    try:
                        tiket_obj = Tiket.objects.get(pk=tiket)
                    except Exception:
                        continue

                DetilTandaTerima.objects.create(
                    id_tanda_terima=self.object,
                    id_tiket=tiket_obj
                )

                # Determine whether this tiket was newly added
                is_new_tiket = tiket_obj.id not in existing_tiket_ids

                # If newly added, mark tanda_terima and record action
                if is_new_tiket:
                    tiket_obj.tanda_terima = True
                    tiket_obj.save(update_fields=["tanda_terima"])
                    TiketAction.objects.create(
                        id_tiket=tiket_obj,
                        id_user=self.request.user,
                        timestamp=timezone.now(),
                        action=TandaTerimaActionType.DIREKAM,
                        catatan='Tanda terima dibuat'
                    )
            
            # Return AJAX response
            message = self.get_success_message(form)
            if self.is_ajax():
                payload = {"success": True}
                if message:
                    payload["message"] = message
                return JsonResponse(payload)
            
            # Return non-AJAX response
            messages.success(self.request, message)
            return HttpResponseRedirect(self.get_success_url())
            
        except Exception as e:
            # Return error response
            if self.is_ajax():
                return JsonResponse({
                    'success': False,
                    'message': str(e),
                    'html': f'<div class="alert alert-danger"><strong>Error:</strong> {str(e)}</div>'
                }, status=200)
            else:
                raise


class TandaTerimaDataDeleteView(LoginRequiredMixin, UserP3DERequiredMixin, ActiveTiketP3DERequiredForEditMixin, DeleteView):
    model = TandaTerimaData
    template_name = 'tanda_terima_data/confirm_delete.html'
    success_url = reverse_lazy('tanda_terima_data_list')
    
    def test_func(self):
        """Check if user is active PIC for any tiket in this tanda terima"""
        tanda_terima = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket__detiltandaterima__id_tanda_terima=tanda_terima,
            id_user=self.request.user,
            active=True,
            role=TiketPIC.Role.P3DE
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tanda_terima_data_delete', args=[self.object.pk])
        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.GET.get('ajax'):
            from django.template.loader import render_to_string
            html = render_to_string(self.template_name, self.get_context_data(object=self.object), request=request)
            return JsonResponse({'html': html})
        return self.render_to_response(self.get_context_data())

    def delete(self, request, *args, **kwargs):
        from django.utils import timezone
        self.object = self.get_object()
        name = str(self.object)
        if self.object.active:
            self.object.active = False
            self.object.save(update_fields=['active'])

            # Add TiketAction for all tiket in this tanda terima and set tanda_terima flag to False
            detil_items = self.object.detil_items.select_related('id_tiket').all()
            for detil in detil_items:
                tiket = detil.id_tiket
                tiket.tanda_terima = False
                tiket.save(update_fields=["tanda_terima"])
                TiketAction.objects.create(
                    id_tiket=tiket,
                    id_user=request.user,
                    timestamp=timezone.now(),
                    action=TandaTerimaActionType.DIBATALKAN,
                    catatan='Tanda terima dibatalkan'
                )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'Tanda Terima Data "{name}" dibatalkan.'
            })
        messages.success(request, f'Tanda Terima Data "{name}" dibatalkan.')
        return JsonResponse({'success': True, 'redirect': self.success_url})

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)


class TandaTerimaDataViewOnly(LoginRequiredMixin, ActiveTiketP3DERequiredForEditMixin, DetailView):
    """Display tanda terima data details with related tiket information."""
    model = TandaTerimaData
    template_name = 'tanda_terima_data/view.html'
    context_object_name = 'tanda_terima'
    
    def test_func(self):
        """Check if user is active PIC for any tiket in this tanda terima"""
        tanda_terima = self.get_object()
        return TiketPIC.objects.filter(
            id_tiket__detiltandaterima__id_tanda_terima=tanda_terima,
            id_user=self.request.user,
            active=True
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['detil_items'] = DetilTandaTerima.objects.filter(id_tanda_terima=self.object).select_related('id_tiket')
        return context
