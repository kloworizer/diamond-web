"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from datetime import datetime, timedelta
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.views.generic import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
import logging

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.pic import PIC
from ...models.periode_jenis_data import PeriodeJenisData
from ...models.jenis_prioritas_data import JenisPrioritasData
from ...models.klasifikasi_jenis_data import KlasifikasiJenisData
from ...constants.tiket_action_types import TiketActionType, PICActionType
from ...forms.tiket import TiketForm
from ..mixins import UserFormKwargsMixin, UserP3DERequiredMixin, get_active_p3de_ilap_ids
from ...constants.tiket_status import STATUS_DIREKAM

logger = logging.getLogger(__name__)


class ILAPPeriodeDataAPIView(View):
    """AJAX API endpoint to fetch available periode jenis data for an ILAP.

    Returns a JSON array of periode data entries that meet all active criteria:
    - PIDE has active Durasi Jatuh Tempo (deadline duration)
    - PMDE has active Durasi Jatuh Tempo
    - User has permission to access the ILAP (P3DE PICs only see their ILAPs)

    HTTP Method: GET
    URL Parameter: ilap_id (ILAP primary key)

    Query Parameters:
    - Filters PeriodeJenisData by:
      * id_sub_jenis_data_ilap__id_ilap_id = ilap_id
      * Active PIDE durasi (start_date <= today, end_date null or >= today)
      * Active PMDE durasi (start_date <= today, end_date null or >= today)
    - Applies user access control via get_active_p3de_ilap_ids (non-admin users)
    - Uses select_related for optimization on ILAP, kategori, kategori_wilayah, jenis_tabel

    Returns JSON with success flag and data array containing:
    - id, nama_ilap, kategori_ilap, kategori_wilayah
    - jenis_tabel, jenis_prioritas, klasifikasi, deskripsi_periode
    - pic_p3de, pic_pide, pic_pmde (comma-separated active PICs)

    Side Effects:
    - Queries PIC table to fetch current active PICs for each role
    - Queries KlasifikasiJenisData for classification text
    - Queries JenisPrioritasData for priority flag
    - Logs errors if query fails for individual records
    """
    
    def get(self, request, ilap_id):
        try:
            from datetime import datetime
            
            today = datetime.now().date()
            
            # Get PIDE and PMDE groups
            pide_group = Group.objects.get(name='user_pide')
            pmde_group = Group.objects.get(name='user_pmde')
            
            # Get only valid PeriodeJenisData for the given ILAP with:
            # 1. Active PIC P3DE
            # 2. Active PIDE durasi
            # 3. Active PMDE durasi
            periode_data_list = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id,
            ).filter(
                Q(
                    id_sub_jenis_data_ilap__durasijatuhtempo__seksi=pide_group,
                    id_sub_jenis_data_ilap__durasijatuhtempo__start_date__lte=today,
                    id_sub_jenis_data_ilap__durasijatuhtempo__end_date__isnull=True
                ) |
                Q(
                    id_sub_jenis_data_ilap__durasijatuhtempo__seksi=pide_group,
                    id_sub_jenis_data_ilap__durasijatuhtempo__start_date__lte=today,
                    id_sub_jenis_data_ilap__durasijatuhtempo__end_date__gte=today
                )
            ).filter(
                Q(
                    id_sub_jenis_data_ilap__durasijatuhtempo__seksi=pmde_group,
                    id_sub_jenis_data_ilap__durasijatuhtempo__start_date__lte=today,
                    id_sub_jenis_data_ilap__durasijatuhtempo__end_date__isnull=True
                ) |
                Q(
                    id_sub_jenis_data_ilap__durasijatuhtempo__seksi=pmde_group,
                    id_sub_jenis_data_ilap__durasijatuhtempo__start_date__lte=today,
                    id_sub_jenis_data_ilap__durasijatuhtempo__end_date__gte=today
                )
            )

            if not (request.user.is_superuser or request.user.groups.filter(name='admin').exists()):
                allowed_ilap_ids = set(get_active_p3de_ilap_ids(request.user))
                if allowed_ilap_ids:
                    periode_data_list = periode_data_list.filter(
                        id_sub_jenis_data_ilap__id_ilap_id__in=allowed_ilap_ids
                    )
                else:
                    periode_data_list = periode_data_list.none()

            periode_data_list = periode_data_list.select_related(
                'id_sub_jenis_data_ilap__id_ilap__id_kategori',
                'id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah',
                'id_sub_jenis_data_ilap__id_jenis_tabel',
                'id_periode_pengiriman'
            ).distinct()
            
            data = []
            for pd in periode_data_list:
                jenis_data = pd.id_sub_jenis_data_ilap
                ilap = jenis_data.id_ilap

                try:
                    klasifikasi_text = ', '.join([
                        item.id_klasifikasi_tabel.deskripsi
                        for item in KlasifikasiJenisData.objects.filter(
                            id_jenis_data_ilap=jenis_data
                        ).select_related('id_klasifikasi_tabel')
                    ]) or '-'
                except Exception:
                    klasifikasi_text = '-'

                try:
                    has_prioritas = JenisPrioritasData.objects.filter(
                        id_sub_jenis_data_ilap=jenis_data
                    ).exists()
                    jenis_prioritas_text = 'Ya' if has_prioritas else 'Tidak'
                except Exception:
                    jenis_prioritas_text = '-'

                try:
                    pic_p3de = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PIC.objects.filter(
                            tipe=PIC.TipePIC.P3DE,
                            id_sub_jenis_data_ilap=jenis_data,
                            start_date__lte=today,
                            end_date__isnull=True
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_p3de = '-'

                try:
                    pic_pide = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PIC.objects.filter(
                            tipe=PIC.TipePIC.PIDE,
                            id_sub_jenis_data_ilap=jenis_data,
                            start_date__lte=today,
                            end_date__isnull=True
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_pide = '-'

                try:
                    pic_pmde = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PIC.objects.filter(
                            tipe=PIC.TipePIC.PMDE,
                            id_sub_jenis_data_ilap=jenis_data,
                            start_date__lte=today,
                            end_date__isnull=True
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_pmde = '-'

                data.append({
                    'id': pd.id,
                    'id_sub_jenis_data': jenis_data.id_sub_jenis_data,
                    'nama_sub_jenis_data': jenis_data.nama_sub_jenis_data,                    'jenis_data_id': jenis_data.id_sub_jenis_data,                    'nama_ilap': ilap.nama_ilap,
                    'kategori_ilap': ilap.id_kategori.nama_kategori if ilap.id_kategori else '-',
                    'kategori_wilayah': ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else '-',
                    'jenis_tabel': jenis_data.id_jenis_tabel.deskripsi if jenis_data.id_jenis_tabel else '-',
                    'jenis_prioritas': jenis_prioritas_text,
                    'klasifikasi': klasifikasi_text,
                    'deskripsi_periode': pd.id_periode_pengiriman.deskripsi,
                    'pic_p3de': pic_p3de,
                    'pic_pide': pic_pide,
                    'pic_pmde': pic_pmde
                })
            
            return JsonResponse({
                'success': True,
                'data': data
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CheckJenisPrioritasAPIView(View):
    """AJAX API endpoint to check if jenis prioritas data exists for a sub jenis data.

    Used during tiket creation to determine if priority data exists for the
    selected sub jenis data and tahun (year), which may affect workflow or
    display of additional fields.

    HTTP Method: GET
    URL Parameters:
    - jenis_data_id: Sub jenis data identifier (e.g., 'KM0330101')
    - tahun: Year (e.g., '2026')

    Returns JSON with success flag and has_prioritas boolean.

    Database Queries:
    - Filters JenisPrioritasData by:
        * id_sub_jenis_data_ilap__id_sub_jenis_data = jenis_data_id
        * tahun = tahun (as string)
    - Returns existence check result (no full object needed)
    """
    
    def get(self, request, jenis_data_id, tahun):
        try:
            from ...models.jenis_data_ilap import JenisDataILAP
            
            # Check if jenis prioritas exists for this jenis data and tahun
            # jenis_data_id is a string like 'KM0330101'
            has_prioritas = JenisPrioritasData.objects.filter(
                id_sub_jenis_data_ilap__id_sub_jenis_data=jenis_data_id,
                tahun=str(tahun)
            ).exists()
            
            return JsonResponse({
                'success': True,
                'has_prioritas': has_prioritas
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class CheckTiketExistsAPIView(View):
    """AJAX API endpoint to check for existing tikets with same data signature.

    Prevents duplicate tiket creation by checking if a tiket already exists
    for the same sub jenis data, periode (month), and tahun (year) combination.

    HTTP Method: GET
    Query Parameters:
    - periode_data_id: PeriodeJenisData ID
    - periode: Period/month number (int)
    - tahun: Year (int)

    Returns JSON with success flag, exists boolean, and nomor_tiket list of
    any existing tikets with the same signature.

    Database Queries:
    - Fetches PeriodeJenisData and extracts id_sub_jenis_data
    - Queries Tiket where:
        * id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data = id_sub_jenis_data
        * periode = periode
        * tahun = tahun
    - Returns list of existing nomor_tiket values for duplicate checking

    Raises:
    - Returns 400 if required parameters missing
    - Returns 400 if PeriodeJenisData not found
    """

    def get(self, request):
        try:
            periode_data_id = request.GET.get('periode_data_id')
            periode = request.GET.get('periode')
            tahun = request.GET.get('tahun')

            if not (periode_data_id and periode and tahun):
                return JsonResponse({'success': False, 'error': 'Missing parameters'}, status=400)

            periode_data = PeriodeJenisData.objects.select_related('id_sub_jenis_data_ilap').get(pk=periode_data_id)
            id_sub_jenis_data = periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data

            existing_qs = Tiket.objects.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data=id_sub_jenis_data,
                periode=int(periode),
                tahun=int(tahun)
            )
            existing_numbers = list(existing_qs.values_list('nomor_tiket', flat=True))
            exists = len(existing_numbers) > 0

            return JsonResponse({'success': True, 'exists': exists, 'nomor_tiket': existing_numbers})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class PreviewNomorTiketAPIView(View):
    """AJAX API endpoint to preview generated tiket nomor before creation.

    Generates and returns a preview of the tiket number (nomor_tiket) that
    will be assigned based on the selected periode data. Uses format:
    <id_sub_jenis_data><YYMMDD><sequence>

    HTTP Method: GET
    Query Parameters:
    - periode_data_id: PeriodeJenisData ID

    Nomor Tiket Format:
    - YYMMDD: Current date formatted as year-month-day (2-digit year)
    - sequence: 3-digit zero-padded counter (001, 002, ...)
    - Example: 'KM0330101260211001' = KM0330101 + 260211 + 001

    Returns JSON with success flag and nomor_tiket preview string.

    Database Queries:
    - Fetches PeriodeJenisData with select_related for optimization
    - Counts existing Tiket records with same nomor_tiket prefix
    - Uses COUNT to determine next sequence number

    Side Effects:
    - Uses current datetime for YYMMDD generation
    - Queries database to calculate next sequence number

    Raises:
    - Returns 400 if periode_data_id missing
    - Returns 400 if PeriodeJenisData not found
    """

    def get(self, request):
        try:
            periode_data_id = request.GET.get('periode_data_id')
            if not periode_data_id:
                return JsonResponse({'success': False, 'error': 'Missing periode_data_id'}, status=400)

            periode_data = PeriodeJenisData.objects.select_related('id_sub_jenis_data_ilap').get(pk=periode_data_id)
            id_sub_jenis_data = periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data

            today = datetime.now().date()
            yymmdd = today.strftime('%y%m%d')
            nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
            count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
            sequence = str(count + 1).zfill(3)
            nomor_tiket = f"{nomor_tiket_prefix}{sequence}"

            return JsonResponse({'success': True, 'nomor_tiket': nomor_tiket})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class TiketRekamCreateView(LoginRequiredMixin, UserP3DERequiredMixin, UserFormKwargsMixin, CreateView):
    """P3DE workflow step to register/record new tiket (first step).

    This view allows P3DE users to create new tikets by selecting data source
    (ILAP), sub jenis data, period, and year. The creation generates a unique
    nomor_tiket and automatically assigns all relevant PICs (P3DE, PIDE, PMDE).

    Model: Tiket
    Form: TiketForm (collects id_periode_data, periode, tahun, id_jenis_prioritas_data)
    Template: tiket/rekam_tiket_form.html

    Workflow Step: Initial tiket registration (DIREKAM status)

    Access Control:
    - Requires @login_required
    - Requires UserP3DERequiredMixin (user must be in user_p3de group)
    - Requires UserFormKwargsMixin (passes user to form for ILAP filtering)
    - User must have active P3DE PIC assignment for selected ILAP/sub jenis data

    Side Effects on Form Submission:
    - Tiket creation within transaction:
        - nomor_tiket auto-generated: <sub_jenis_data><YYMMDD><sequence>
        - status set to STATUS_DIREKAM
        - id_durasi_jatuh_tempo_pide and _pmde assigned from PeriodeJenisData
        - id_jenis_prioritas_data assigned if exists for year
        - tgl_diterima and tgl_mulai_data set from form
    - TiketAction created with DIREKAM action type (base timestamp)
    - TiketPIC assignments for all active PICs:
        - Current user added if not already P3DE PIC
        - All active P3DE, PIDE, PMDE PICs from PIC table assigned
    - PICActionType.DITAMBAHKAN TiketAction created for each PIC
    - Signals triggered for tiket creation (may send notifications)

    Error Handling:
    - Validates Durasi Jatuh Tempo exists for PIDE and PMDE (raises ValueError)
    - Prevents creation if durasi not configured
    - Collects form errors and re-displays on failure
    """
    model = Tiket
    form_class = TiketForm
    template_name = 'tiket/rekam_tiket_form.html'
    
    def get_success_url(self):
        """Redirect to tiket detail page after successful creation.

        User is redirected to the newly created tiket's detail view where they
        can see all assigned PICs and the initial DIREKAM audit trail entry.
        """
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        """Build context with form information and workflow metadata.

        Populates context with:
        - context['form_action']: URL for form submission (tiket_rekam_create)
        - context['page_title']: Display title "Rekam Penerimaan Data"
        - context['workflow_step']: Identifies this as 'rekam' step in workflow

        Used by template to render form and provide workflow context to user.
        """
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tiket_rekam_create')
        context['page_title'] = 'Rekam Penerimaan Data'
        context['workflow_step'] = 'rekam'
        return context

    def form_valid(self, form):
        """Handle form submission: create tiket with nomor_tiket and assign PICs.

        Within transaction:
        1. Generate nomor_tiket based on sub_jenis_data and current date
        2. Set tiket.status to STATUS_DIREKAM
        3. Assign durasi_jatuh_tempo from PeriodeJenisData (raises ValueError if missing)
        4. Assign id_jenis_prioritas_data if exists for specified year
        5. Save tiket object
        6. Create TiketAction DIREKAM record (base timestamp)
        7. Call _assign_tiket_pics to assign all P3DE, PIDE, PMDE PICs
        8. Display success message with generated nomor_tiket
        9. Redirect to tiket detail page

        Raises:
        - ValueError if Durasi Jatuh Tempo not configured for PIDE or PMDE
        - All exceptions caught and added to form errors for re-display

        Returns:
        - Redirect to tiket detail on success
        - Form with errors re-displayed on failure
        """
        try:
            periode_jenis_data = form.cleaned_data['id_periode_data']
            id_sub_jenis_data = periode_jenis_data.id_sub_jenis_data_ilap.id_sub_jenis_data
            today = datetime.now().date()

            nomor_tiket = self._generate_nomor_tiket(id_sub_jenis_data, today)

            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.nomor_tiket = nomor_tiket
                self.object.status = STATUS_DIREKAM

                tahun = form.cleaned_data.get('tahun')
                if tahun:
                    jenis_prioritas = JenisPrioritasData.objects.filter(
                        id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap,
                        tahun=str(tahun)
                    ).first()
                    if jenis_prioritas:
                        self.object.id_jenis_prioritas_data = jenis_prioritas

                self._set_durasi_fields(periode_jenis_data, today)
                self.object.save()

                # Use a fixed base timestamp so subsequent PIC actions are recorded after DIREKAM
                base_action_time = datetime.now()
                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=base_action_time,
                    action=TiketActionType.DIREKAM,
                    catatan="tiket direkam"
                )

                self._assign_tiket_pics(periode_jenis_data, today, base_time=base_action_time)

            messages.success(self.request, f'Tiket "{nomor_tiket}" berhasil dibuat.')
            return super().form_valid(form)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

    def _generate_nomor_tiket(self, id_sub_jenis_data, today):
        """Generate unique tiket number based on sub jenis data and current date.

        Format: <id_sub_jenis_data><YYMMDD><sequence>
        Example: KM0330101 + 260211 + 001 = KM0330101260211001

        Algorithm:
        1. Create prefix from id_sub_jenis_data + YYMMDD
        2. Count existing tikets with same prefix
        3. Calculate sequence as count + 1, zero-padded to 3 digits

        Args:
        - id_sub_jenis_data: Sub jenis data ID (e.g., 'KM0330101')
        - today: date object for generating YYMMDD

        Returns:
        - Generated nomor_tiket string (guaranteed unique for this prefix)

        Database Query:
        - Filters Tiket by nomor_tiket__startswith = prefix to count existing
        """
        yymmdd = today.strftime('%y%m%d')
        nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
        count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
        sequence = str(count + 1).zfill(3)
        return f"{nomor_tiket_prefix}{sequence}"

    def _set_durasi_fields(self, periode_jenis_data, today):
        """Assign durasi jatuh tempo (deadline) for PIDE and PMDE.

        Fetches active Durasi Jatuh Tempo records for both PIDE and PMDE groups
        from the sub jenis data ilap, validating that both exist and are currently
        active (start_date <= today and end_date null or >= today).

        Args:
        - periode_jenis_data: PeriodeJenisData object containing sub_jenis_data_ilap
        - today: date object for filtering active durations

        Side Effects:
        - Sets self.object.id_durasi_jatuh_tempo_pide
        - Sets self.object.id_durasi_jatuh_tempo_pmde

        Raises:
        - ValueError if PIDE durasi not found or not active
        - ValueError if PMDE durasi not found or not active
        - Error message includes data type name for debugging

        Database Queries:
        - Filters DurasiJatuhTempo by seksi (PIDE/PMDE groups) and date range
        - Uses first() to get single active record (assumes one active per group)
        """

        pide_group = Group.objects.get(name='user_pide')
        pmde_group = Group.objects.get(name='user_pmde')

        durasi_pide = periode_jenis_data.id_sub_jenis_data_ilap.durasijatuhtempo_set.filter(
            seksi=pide_group
        ).filter(
            Q(end_date__isnull=True) | Q(start_date__lte=today, end_date__gte=today)
        ).first()
        if not durasi_pide:
            raise ValueError(
                f"Durasi Jatuh Tempo PIDE (active) not found for data type: "
                f"{periode_jenis_data.id_sub_jenis_data_ilap.nama_sub_jenis_data}. "
                f"Please configure Durasi Jatuh Tempo for PIDE before creating tickets."
            )
        self.object.id_durasi_jatuh_tempo_pide = durasi_pide

        durasi_pmde = periode_jenis_data.id_sub_jenis_data_ilap.durasijatuhtempo_set.filter(
            seksi=pmde_group
        ).filter(
            Q(end_date__isnull=True) | Q(start_date__lte=today, end_date__gte=today)
        ).first()
        if not durasi_pmde:
            raise ValueError(
                f"Durasi Jatuh Tempo PMDE (active) not found for data type: "
                f"{periode_jenis_data.id_sub_jenis_data_ilap.nama_sub_jenis_data}. "
                f"Please configure Durasi Jatuh Tempo for PMDE before creating tickets."
            )
        self.object.id_durasi_jatuh_tempo_pmde = durasi_pmde

    def _assign_tiket_pics(self, periode_jenis_data, today, base_time=None):
        """Assign all active P3DE, PIDE, PMDE PICs to the tiket.

        Performs two operations:
        1. Adds current user as P3DE PIC if not already assigned in PIC table
        2. Adds all active P3DE, PIDE, PMDE PICs from PIC table to TiketPIC

        Args:
        - periode_jenis_data: PeriodeJenisData for this tiket's sub_jenis_data_ilap
        - today: date object for filtering active PIC assignments
        - base_time: datetime to use as base for PICActionType timestamps (optional)

        Side Effects:
        - Creates TiketPIC records for each PIC assignment
        - Creates PICActionType.DITAMBAHKAN TiketAction for each PIC
        - Timestamps for PIC actions are base_time + offset (1-based index)
          to ensure ordering after DIREKAM action and prevent duplicates

        Database Queries:
        - Checks if current user is P3DE PIC in PIC table
        - Filters PIC table for active (start_date <= today, end_date null) assignments
        - Queries by tipe (P3DE, PIDE, PMDE) and id_sub_jenis_data_ilap
        - Iterates through all matches to create TiketPIC and TiketAction records

        Timestamp Logic:
        - If base_time provided: action_time = base_time + timedelta(microseconds=1+idx)
        - If base_time not provided: action_time = datetime.now()
        - Ensures PIC actions always ordered after DIREKAM action in audit trail
        """
        current_user_is_p3de_pic = PIC.objects.filter(
            tipe=PIC.TipePIC.P3DE,
            id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap,
            id_user=self.request.user,
            start_date__lte=today,
            end_date__isnull=True
        ).exists()
        if not current_user_is_p3de_pic:
            TiketPIC.objects.create(
                id_tiket=self.object,
                id_user=self.request.user,
                timestamp=datetime.now(),
                role=TiketPIC.Role.P3DE
            )
            tipe_label = dict(PIC.TipePIC.choices).get(PIC.TipePIC.P3DE, PIC.TipePIC.P3DE)
            # Ensure PIC action timestamp is after base_time (if provided)
            action_time = (base_time + timedelta(microseconds=1)) if base_time else datetime.now()
            TiketAction.objects.create(
                id_tiket=self.object,
                id_user=self.request.user,
                timestamp=action_time,
                action=PICActionType.DITAMBAHKAN,
                catatan=f'{tipe_label} {self.request.user.username} ditambahkan'
            )

        active_filter = Q(start_date__lte=today) & Q(end_date__isnull=True)
        for role_value, tipe in (
            (TiketPIC.Role.P3DE, PIC.TipePIC.P3DE),
            (TiketPIC.Role.PIDE, PIC.TipePIC.PIDE),
            (TiketPIC.Role.PMDE, PIC.TipePIC.PMDE),
        ):
            pic_qs = PIC.objects.filter(
                tipe=tipe,
                id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap
            )
            tipe_label = dict(PIC.TipePIC.choices).get(tipe, tipe)
            for idx, pic in enumerate(pic_qs.filter(active_filter), start=1):
                tiket_pic = TiketPIC.objects.create(
                    id_tiket=self.object,
                    id_user=pic.id_user,
                    timestamp=datetime.now(),
                    role=role_value
                )

                # Use base_time + offset to guarantee ordering after DIREKAM
                if base_time:
                    action_time = base_time + timedelta(microseconds=1 + idx)
                else:
                    action_time = datetime.now()

                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=action_time,
                    action=PICActionType.DITAMBAHKAN,
                    catatan=f'{tipe_label} {pic.id_user.username} ditambahkan'
                )

