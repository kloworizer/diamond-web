from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.http import JsonResponse
from django.db.models import Q
from datetime import datetime

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
        """Add additional context data for the ILAP list view.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
                context data.

        Returns:
            dict: Template context data including any additional variables
                for rendering the page.
        """
        context = super().get_context_data(**kwargs)
        return context
    
    def render_to_response(self, context, **response_kwargs):
        """Render the response, returning JSON for AJAX requests or HTML otherwise.

        If the request is an AJAX request (``XMLHttpRequest``) or the
        ``format`` parameter is ``json``, returns a JSON response for
        DataTables integration. Otherwise delegates to the parent class.

        Args:
            context (dict): The template context data.
            **response_kwargs: Additional keyword arguments for the response.

        Returns:
            JsonResponse: If the request expects JSON data.
            django.http.HttpResponse: The rendered HTML template otherwise.
        """
        # Check if request wants JSON data (for DataTables)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest' or self.request.GET.get('format') == 'json':
            return self.get_data_json()
        return super().render_to_response(context, **response_kwargs)
    
    def get_data_json(self):
        """Build and return a JSON response for DataTables server-side processing.

        Handles pagination, global search, per-column filtering, ordering,
        and record counts required by the DataTables jQuery plugin.

        Returns:
            JsonResponse: A JSON object containing:
                - draw (int): Echoes the draw parameter from the request.
                - recordsTotal (int): Total records before filtering.
                - recordsFiltered (int): Total records after filtering.
                - data (list): Paginated list of ILAP row dictionaries.
        """
        draw = int(self.request.GET.get('draw', 1))
        start = int(self.request.GET.get('start', 0))
        length = int(self.request.GET.get('length', 10))
        search_value = self.request.GET.get('search[value]', '').strip()
        
        # Column order mapping
        order_columns = {
            0: 'id_ilap',
            1: 'id_kategori__nama_kategori',
            2: 'nama_ilap',
            3: 'id_kategori_wilayah__deskripsi',
        }
        
        # Base queryset
        base_qs = ILAP.objects.all().select_related(
            'id_kategori',
            'id_kategori_wilayah',
        ).prefetch_related(
            'ilap_kpp_relations__id_kpp',
        )
        
        # Total records (without filtering)
        records_total = base_qs.count()
        
        # Apply global search
        if search_value:
            global_filter = Q(id_ilap__icontains=search_value) | \
                            Q(nama_ilap__icontains=search_value) | \
                            Q(id_kategori__nama_kategori__icontains=search_value) | \
                            Q(id_kategori_wilayah__deskripsi__icontains=search_value)
            base_qs = base_qs.filter(global_filter)
        
        # Apply individual column searches (sent via custom parameters)
        for i in range(4):  # columns 0-3
            col_search = self.request.GET.get(f'columns[{i}][search][value]', '').strip()
            if col_search:
                col_map = {
                    0: Q(id_ilap__icontains=col_search),
                    1: Q(id_kategori__nama_kategori__icontains=col_search),
                    2: Q(nama_ilap__icontains=col_search),
                    3: Q(id_kategori_wilayah__deskripsi__icontains=col_search),
                }
                base_qs = base_qs.filter(col_map.get(i, Q()))
        
        # Records after filtering
        records_filtered = base_qs.count()
        
        # Apply ordering
        order_column_idx = self.request.GET.get('order[0][column]')
        order_dir = self.request.GET.get('order[0][dir]', 'asc')
        if order_column_idx is not None:
            order_col = order_columns.get(int(order_column_idx))
            if order_col:
                if order_dir == 'desc':
                    order_col = f'-{order_col}'
                base_qs = base_qs.order_by(order_col)
        else:
            base_qs = base_qs.order_by('id_ilap')
        
        # Apply pagination
        ilaps = base_qs[start:start + length]
        
        # Build data rows
        data = []
        for ilap in ilaps:
            data.append({
                'id_ilap': ilap.id_ilap,
                'kategori': ilap.id_kategori.nama_kategori if ilap.id_kategori else '---',
                'nama': ilap.nama_ilap,
                'wilayah': ilap.id_kategori_wilayah.deskripsi if ilap.id_kategori_wilayah else '---',
                'actions': f'<a href="/profil-ilap/{ilap.pk}/" class="btn btn-sm btn-info"><i class="feather-eye me-1"></i>View</a>'
            })
        
        return JsonResponse({
            'draw': draw,
            'recordsTotal': records_total,
            'recordsFiltered': records_filtered,
            'data': data,
        })


class ProfilILAPDetailView(LoginRequiredMixin, UserP3DERequiredMixin, DetailView):
    """Detail view for ILAP profile with jenis_data_ilap breakdown and tiket counts."""
    model = ILAP
    template_name = 'profil_ilap/detail.html'
    context_object_name = 'ilap'

    def get_context_data(self, **kwargs):
        """Add context data for the ILAP detail view including jenis_data breakdown.

        Gathers all ``JenisDataILAP`` records associated with the current ILAP,
        their associated legal bases (klasifikasi), and calculates tiket
        submission counts per year and period.

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
                context data.

        Returns:
            dict: Template context containing:
                - ilap (ILAP): The current ILAP object.
                - jenis_data_details (list): Processed details for each
                  jenis_data_ilap.
                - years (list): Range of years displayed in the template.
        """
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
