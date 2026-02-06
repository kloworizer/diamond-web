"""Rekam Tiket Workflow Step - Step 1: Record/Register"""

from datetime import datetime
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views import View

from ...models.tiket import Tiket
from ...models.tiket_action import TiketAction
from ...models.tiket_pic import TiketPIC
from ...models.pic_p3de import PICP3DE
from ...models.pic_pide import PICPIDE
from ...models.pic_pmde import PICPMDE
from ...models.periode_jenis_data import PeriodeJenisData
from ...models.jenis_prioritas_data import JenisPrioritasData
from ...models.klasifikasi_jenis_data import KlasifikasiJenisData
from ...forms.tiket import TiketForm
from .base import WorkflowStepCreateView


class ILAPPeriodeDataAPIView(View):
    """API view to fetch periode jenis data for a specific ILAP."""
    
    def get(self, request, ilap_id):
        try:
            # Get all periode jenis data for the given ILAP
            periode_data_list = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap__id_ilap_id=ilap_id
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
                        for pic in PICP3DE.objects.filter(
                            id_sub_jenis_data_ilap=jenis_data
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_p3de = '-'

                try:
                    pic_pide = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PICPIDE.objects.filter(
                            id_sub_jenis_data_ilap=jenis_data
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_pide = '-'

                try:
                    pic_pmde = ', '.join([
                        (pic.id_user.get_full_name().strip() or pic.id_user.username)
                        for pic in PICPMDE.objects.filter(
                            id_sub_jenis_data_ilap=jenis_data
                        ).select_related('id_user')[:3]
                    ]) or '-'
                except Exception:
                    pic_pmde = '-'

                data.append({
                    'id': pd.id,
                    'id_sub_jenis_data': jenis_data.id_sub_jenis_data,
                    'nama_sub_jenis_data': jenis_data.nama_sub_jenis_data,
                    'nama_ilap': ilap.nama_ilap,
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

        for role_value, pic_qs in (
            (2, PICP3DE.objects.filter(id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap)),
            (3, PICPIDE.objects.filter(id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap)),
            (4, PICPMDE.objects.filter(id_sub_jenis_data_ilap=periode_jenis_data.id_sub_jenis_data_ilap)),
        ):
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
