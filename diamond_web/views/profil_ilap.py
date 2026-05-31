from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.http import JsonResponse
from datetime import datetime
import json

from ..models.ilap import ILAP
from ..models.jenis_data_ilap import JenisDataILAP
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..models.periode_jenis_data import PeriodeJenisData
from ..models.tiket import Tiket
from .mixins import UserP3DERequiredMixin

__all__ = ['ProfilILAPListView', 'ProfilILAPDetailView']


class ProfilILAPListView(LoginRequiredMixin, UserP3DERequiredMixin, TemplateView):
    """List view for ILAP profiles with basic information."""
    template_name = 'profil_ilap/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    
    def render_to_response(self, context, **response_kwargs):
        # Check if request wants JSON data (for DataTables)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or self.request.GET.get('format') == 'json':
            return self.get_data_json()
        return super().render_to_response(context, **response_kwargs)
    
    def get_data_json(self):
        """Return data in JSON format for DataTables"""
        ilaps = ILAP.objects.all().select_related(
            'id_kategori',
            'id_kategori_wilayah',
            'id_kpp'
        ).order_by('id_ilap')
        
        data = []
        for ilap in ilaps:
            data.append({
                'id_ilap': ilap.id_ilap,
                'kategori': ilap.id_kategori.nama_kategori if ilap.id_kategori else '---',
                'nama': ilap.nama_ilap,
                'wilayah': ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else '---',
                'actions': f'<a href="/profil-ilap/{ilap.pk}/" class="btn btn-sm btn-info"><i class="feather-eye me-1"></i>View</a>'
            })
        
        return JsonResponse({'data': data})


class ProfilILAPDetailView(LoginRequiredMixin, UserP3DERequiredMixin, DetailView):
    """Detail view for ILAP profile with jenis_data_ilap breakdown and tiket counts."""
    model = ILAP
    template_name = 'profil_ilap/detail.html'
    context_object_name = 'ilap'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ilap = self.get_object()
        
        # Get all jenis_data_ilap for this ILAP
        jenis_data_list = JenisDataILAP.objects.filter(
            id_ilap=ilap
        ).select_related('id_jenis_tabel', 'id_status_data')
        
        # Get current year and years for columns
        current_year = datetime.now().year
        current_month = datetime.now().month
        years = [current_year - 2, current_year - 1, current_year, current_year + 1]
        
        # Process each jenis_data_ilap
        jenis_data_details = []
        for jenis_data in jenis_data_list:
            # Get klassifikasi jenis data (dasar hukum)
            klassifikasi_list = KlasifikasiJenisData.objects.filter(
                id_sub_jenis_data=jenis_data
            ).select_related('id_klasifikasi_tabel')
            
            # Get periode jenis data
            periode_jenis_data = PeriodeJenisData.objects.filter(
                id_sub_jenis_data_ilap=jenis_data
            ).select_related('id_periode_pengiriman')
            
            if periode_jenis_data.exists():
                pjd = periode_jenis_data.first()
                periode_pengiriman = pjd.id_periode_pengiriman
                
                # Get dasar hukum list
                dasar_hukum_list = ', '.join([
                    k.id_klasifikasi_tabel.deskripsi 
                    for k in klassifikasi_list
                ])
                
                # Calculate tiket counts per year and periode
                year_periode_data = {}
                for year in years:
                    # Determine number of periods for this year
                    periode_type = periode_pengiriman.periode_penyampaian.lower()
                    
                    if periode_type == 'bulanan':
                        total_periodes = 12
                        if year == current_year:
                            # For current year, count up to current month
                            total_periodes = current_month
                    elif periode_type == 'triwulan':
                        total_periodes = 4
                        if year == current_year:
                            total_periodes = (current_month - 1) // 3 + 1
                    elif periode_type == 'semester':
                        total_periodes = 2
                        if year == current_year:
                            total_periodes = 1 if current_month < 7 else 2
                    elif periode_type == 'tahunan':
                        total_periodes = 1
                    else:
                        total_periodes = 12
                    
                    # Count tikets for this jenis_data_ilap for each period
                    tiket_counts = []
                    for periode in range(1, total_periodes + 1):
                        tiket_count = Tiket.objects.filter(
                            id_periode_data__id_sub_jenis_data_ilap=jenis_data,
                            tahun=year,
                            periode=periode
                        ).count()
                        tiket_counts.append(tiket_count)
                    
                    # Format as "sum/total"
                    tiket_sum = sum(tiket_counts)
                    year_periode_data[year] = f"{tiket_sum}/{total_periodes}"
                
                jenis_data_details.append({
                    'jenis_data': jenis_data,
                    'dasar_hukum': dasar_hukum_list,
                    'periode_penyampaian': periode_pengiriman.periode_penyampaian,
                    'periode_penerimaan': periode_pengiriman.periode_penerimaan,
                    'year_data': year_periode_data,
                })
        
        context['jenis_data_details'] = jenis_data_details
        context['years'] = years
        
        return context
