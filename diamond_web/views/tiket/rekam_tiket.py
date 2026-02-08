"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from datetime import datetime
from django.urls import reverse
from django.contrib import messages
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
from ...constants.tiket_action_types import TiketActionType
from ...forms.tiket import TiketForm
from ..mixins import UserFormKwargsMixin, UserP3DERequiredMixin, get_active_p3de_ilap_ids

logger = logging.getLogger(__name__)


class ILAPPeriodeDataAPIView(View):
    """API view to fetch periode jenis data for a specific ILAP."""
    
    def get(self, request, ilap_id):
        try:
            from django.contrib.auth.models import Group
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
    """API view to check if jenis prioritas data exists for a given jenis data and tahun."""
    
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
    """API view to check if tiket already exists for sub jenis data, periode, and tahun."""

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
    """API view to preview generated nomor tiket based on selected periode data."""

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
    """Create view for Rekam Tiket workflow step."""
    model = Tiket
    form_class = TiketForm
    template_name = 'tiket/rekam_tiket_form.html'
    
    def get_success_url(self):
        """Redirect to detail view after successful creation."""
        return reverse('tiket_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_action'] = reverse('tiket_rekam_create')
        context['page_title'] = 'Rekam Penerimaan Data'
        context['workflow_step'] = 'rekam'
        return context

    def form_valid(self, form):
        try:
            periode_jenis_data = form.cleaned_data['id_periode_data']
            id_sub_jenis_data = periode_jenis_data.id_sub_jenis_data_ilap.id_sub_jenis_data
            today = datetime.now().date()

            nomor_tiket = self._generate_nomor_tiket(id_sub_jenis_data, today)

            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.nomor_tiket = nomor_tiket
                self.object.status = 1

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

                TiketAction.objects.create(
                    id_tiket=self.object,
                    id_user=self.request.user,
                    timestamp=datetime.now(),
                    action=TiketActionType.DIREKAM,
                    catatan="tiket direkam"
                )

                self._assign_tiket_pics(periode_jenis_data, today)

            messages.success(self.request, f'Tiket "{nomor_tiket}" berhasil dibuat.')
            return super().form_valid(form)
        except Exception as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

    def _generate_nomor_tiket(self, id_sub_jenis_data, today):
        yymmdd = today.strftime('%y%m%d')
        nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
        count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
        sequence = str(count + 1).zfill(3)
        return f"{nomor_tiket_prefix}{sequence}"

    def _set_durasi_fields(self, periode_jenis_data, today):
        from django.contrib.auth.models import Group

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

    def _assign_tiket_pics(self, periode_jenis_data, today):
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

        active_filter = Q(start_date__lte=today) & Q(end_date__isnull=True)
        additional_pics = []

        for role_value, tipe in (
            (TiketPIC.Role.P3DE, PIC.TipePIC.P3DE),
            (TiketPIC.Role.PIDE, PIC.TipePIC.PIDE),
            (TiketPIC.Role.PMDE, PIC.TipePIC.PMDE),
        ):
            pic_qs = PIC.objects.filter(
                tipe=tipe,
                id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap
            )
            for pic in pic_qs.filter(active_filter):
                additional_pics.append(
                    TiketPIC(
                        id_tiket=self.object,
                        id_user=pic.id_user,
                        timestamp=datetime.now(),
                        role=role_value
                    )
                )

        if additional_pics:
            TiketPIC.objects.bulk_create(additional_pics)

