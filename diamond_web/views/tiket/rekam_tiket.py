"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from datetime import datetime
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q
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
from ...forms.tiket import TiketForm
from .base import WorkflowStepCreateView

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
            
            # Get all JenisDataILAP IDs that have:
            # 1. PIC P3DE assigned
            # 2. Active PIDE durasi
            # 3. Active PMDE durasi
            from ...models.jenis_data_ilap import JenisDataILAP
            
            # JenisData with PIC P3DE
            jenis_data_with_pic = JenisDataILAP.objects.filter(
                pic__tipe=PIC.TipePIC.P3DE
            ).values_list('id_sub_jenis_data', flat=True).distinct()
            
            # JenisData with active PIDE durasi
            jenis_data_with_pide = JenisDataILAP.objects.filter(
                durasijatuhtempo__seksi=pide_group,
                durasijatuhtempo__start_date__lte=today
            ).filter(
                Q(durasijatuhtempo__end_date__isnull=True) | Q(durasijatuhtempo__end_date__gte=today)
            ).values_list('id_sub_jenis_data', flat=True).distinct()
            
            # JenisData with active PMDE durasi
            jenis_data_with_pmde = JenisDataILAP.objects.filter(
                durasijatuhtempo__seksi=pmde_group,
                durasijatuhtempo__start_date__lte=today
            ).filter(
                Q(durasijatuhtempo__end_date__isnull=True) | Q(durasijatuhtempo__end_date__gte=today)
            ).values_list('id_sub_jenis_data', flat=True).distinct()
            
            # Get intersection - JenisData that have ALL three requirements
            valid_jenis_data_ids = set(jenis_data_with_pic) & set(jenis_data_with_pide) & set(jenis_data_with_pmde)
            
            # Get only valid periode jenis data for the given ILAP
            periode_data_list = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id,
                id_sub_jenis_data_ilap__id_sub_jenis_data__in=valid_jenis_data_ids
            ).select_related(
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
                            id_sub_jenis_data_ilap=jenis_data
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_p3de = '-'

                try:
                    pic_pide = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PIC.objects.filter(
                            tipe=PIC.TipePIC.PIDE,
                            id_sub_jenis_data_ilap=jenis_data
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_pide = '-'

                try:
                    pic_pmde = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PIC.objects.filter(
                            tipe=PIC.TipePIC.PMDE,
                            id_sub_jenis_data_ilap=jenis_data
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


class TiketRekamCreateView(WorkflowStepCreateView):
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

    def perform_workflow_action(self, form):
        """Implement the Rekam workflow logic."""
        try:
            periode_jenis_data = form.cleaned_data['id_periode_data']
            id_sub_jenis_data = periode_jenis_data.id_sub_jenis_data_ilap.id_sub_jenis_data
            
            # Generate nomor_tiket: id_sub_jenis_data + yymmdd + 3 digit sequence
            today = datetime.now().date()
            yymmdd = today.strftime('%y%m%d')
            
            nomor_tiket_prefix = f"{id_sub_jenis_data}{yymmdd}"
            count = Tiket.objects.filter(nomor_tiket__startswith=nomor_tiket_prefix).count()
            sequence = str(count + 1).zfill(3)
            
            nomor_tiket = f"{nomor_tiket_prefix}{sequence}"
            
            # Save the tiket with status = 1 (Direkam)
            self.object = form.save(commit=False)
            self.object.nomor_tiket = nomor_tiket
            self.object.status = 1
            
            # Set id_jenis_prioritas_data based on tahun from form
            tahun = form.cleaned_data.get('tahun')
            if tahun:
                jenis_prioritas = JenisPrioritasData.objects.filter(
                    id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap,
                    tahun=str(tahun)
                ).first()
                if jenis_prioritas:
                    self.object.id_jenis_prioritas_data = jenis_prioritas
            
            # Set id_durasi_jatuh_tempo_pide (active PIDE group)
            from django.contrib.auth.models import Group
            pide_durasi_found = False
            try:
                pide_group = Group.objects.get(name='user_pide')
                # Try to find active durasi (no end_date or within date range)
                durasi_pide = periode_jenis_data.id_sub_jenis_data_ilap.durasijatuhtempo_set.filter(
                    seksi=pide_group
                ).filter(
                    Q(end_date__isnull=True) | Q(start_date__lte=today, end_date__gte=today)
                ).first()
                if durasi_pide:
                    self.object.id_durasi_jatuh_tempo_pide = durasi_pide
                    pide_durasi_found = True
            except Group.DoesNotExist:
                pass
            
            # Set id_durasi_jatuh_tempo_pmde (active PMDE group)
            pmde_durasi_found = False
            try:
                pmde_group = Group.objects.get(name='user_pmde')
                # Try to find active durasi (no end_date or within date range)
                durasi_pmde = periode_jenis_data.id_sub_jenis_data_ilap.durasijatuhtempo_set.filter(
                    seksi=pmde_group
                ).filter(
                    Q(end_date__isnull=True) | Q(start_date__lte=today, end_date__gte=today)
                ).first()
                if durasi_pmde:
                    self.object.id_durasi_jatuh_tempo_pmde = durasi_pmde
                    pmde_durasi_found = True
            except Group.DoesNotExist:
                pass
            
            # Check if both required durasi fields are set
            if not pide_durasi_found:
                raise ValueError(
                    f"Durasi Jatuh Tempo PIDE (active) not found for data type: "
                    f"{periode_jenis_data.id_sub_jenis_data_ilap.nama_sub_jenis_data}. "
                    f"Please configure Durasi Jatuh Tempo for PIDE before creating tickets."
                )
            if not pmde_durasi_found:
                raise ValueError(
                    f"Durasi Jatuh Tempo PMDE (active) not found for data type: "
                    f"{periode_jenis_data.id_sub_jenis_data_ilap.nama_sub_jenis_data}. "
                    f"Please configure Durasi Jatuh Tempo for PMDE before creating tickets."
                )
            
            self.object.save()
            
            # Create tiket_action entry for audit trail
            TiketAction.objects.create(
                id_tiket=self.object,
                id_user=self.request.user,
                timestamp=datetime.now(),
                action=1,
                catatan="tiket direkam"
            )
            
            # Create tiket_pic entry to assign to current user
            TiketPIC.objects.create(
                id_tiket=self.object,
                id_user=self.request.user,
                timestamp=datetime.now(),
                role=1
            )

            # Assign related PICs (P3DE, PIDE, PMDE) for the same sub jenis data
            active_filter = Q(start_date__lte=today) & (Q(end_date__isnull=True) | Q(end_date__gte=today))
            additional_pics = []

            for role_value, tipe in (
                (2, PIC.TipePIC.P3DE),
                (3, PIC.TipePIC.PIDE),
                (4, PIC.TipePIC.PMDE),
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
            
            # Return response
            if self.is_ajax_request():
                return self.get_json_response(
                    success=True,
                    message=f'Tiket "{nomor_tiket}" created successfully.',
                    redirect=self.get_success_url()
                )
            else:
                messages.success(
                    self.request,
                    f'Tiket "{nomor_tiket}" created successfully.'
                )
                return None
        except Exception as e:
            # Pass exception to be handled by form_valid's exception handler
            raise

