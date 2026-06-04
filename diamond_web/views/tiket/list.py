"""Tiket list view - shared across all workflow steps."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse

from ...models.tiket import Tiket
from ...models.tiket_pic import TiketPIC
from ...models.pic import PIC
from ...models.periode_jenis_data import PeriodeJenisData
from ...models.periode_pengiriman import PeriodePengiriman
from ...models.kategori_ilap import KategoriILAP
from ...models.ilap import ILAP
from ...models.jenis_data_ilap import JenisDataILAP
from ...models.kanwil import Kanwil
from ...models.kpp import KPP
from ...models.kategori_wilayah import KategoriWilayah
from ...models.jenis_tabel import JenisTabel
from ...models.dasar_hukum import DasarHukum
from ...models.detil_tanda_terima import DetilTandaTerima
from ...models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..mixins import can_access_tiket_list
from ...constants.tiket_status import STATUS_LABELS
from .documents import _is_p3de_user, _format_periode_tiket
from ...models.durasi_jatuh_tempo import DurasiJatuhTempo


class TiketListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display a paginated list of all tikets with DataTables integration.

    This view renders a template with a DataTables table that displays tikets
    accessible to the logged-in user. Access control is enforced via
    `test_func()` using the `can_access_tiket_list` helper to verify the user
    has permission to view tiket listings (admins, superusers, or users with
    active TiketPIC assignments).

    Template: tiket/list.html

    Context:
    - No additional context variables beyond standard Django template context.
      DataTables initialization is handled client-side via tiket_data endpoint.
    """
    template_name = 'tiket/list.html'

    def test_func(self):
        """Verify the user is allowed to access tiket listings.

        Returns True if user is admin, superuser, or has an active TiketPIC
        assignment, False otherwise.
        """
        return can_access_tiket_list(self.request.user)


@login_required
@user_passes_test(lambda u: can_access_tiket_list(u))
@require_GET
def tiket_data(request):
    """DataTables server-side endpoint for tiket listing with dynamic filtering.

    This AJAX endpoint handles server-side processing for DataTables, including
    pagination, sorting, and column-based filtering. Non-admin users only see
    tikets where they are assigned as a TiketPIC.

    GET Parameters (DataTables standard):
    - draw: DataTables draw counter (for synchronizing responses with requests)
    - start: Record offset for pagination (default 0)
    - length: Number of records per page (default 10)
    - columns_search[]: Array of search values for each column:
        [0] nomor_tiket: Filter by ticket number (partial match)
        [1] nama_sub_jenis_data: Filter by sub-data type name
        [2] periode: Filter by period value
        [3] tahun: Filter by year value
        [4] status: Filter by tiket status
    - order[0][column]: Index of column to sort by
    - order[0][dir]: Sort direction (asc/desc)

    Returns JSON with keys:
    - draw: Echo of request draw parameter
    - recordsTotal: Total count before filtering
    - recordsFiltered: Total count after filtering
    - data: Array of tiket objects with fields:
        id, nomor_tiket, nama_ilap, nama_sub_jenis_data,
        periode_formatted, status, actions (view button)

    Side Effects/Database Queries:
    - Queries Tiket with select_related('id_periode_data__id_sub_jenis_data_ilap')
    - Non-admins: filters by TiketPIC.id_user=request.user
    - Formats periode display based on type (daily/weekly/monthly/etc)
    - Joins related ILAP and sub-jenis-data tables for display names

    Access Control:
    - Requires @login_required
    - Requires can_access_tiket_list permission
    - @require_GET enforces GET-only access
    """
    base_qs = Tiket.objects.select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_periode_pengiriman'
    ).all()
    if not request.user.groups.filter(name='admin').exists() and not request.user.is_superuser:
        base_qs = base_qs.filter(
            tiketpic__id_user=request.user
        ).distinct()

    # Helper to split comma-separated multi-select values
    def _split_filter_options(v):
        if not v:
            return []
        return [x.strip() for x in v.split(',') if x.strip()]

    # Return dynamic filter options for dropdowns
    if request.GET.get('get_filter_options'):
        # Get ALL current filter values (comma-separated for multi-select)
        raw_nomor_tiket = request.GET.get('nomor_tiket', '')
        raw_tahun = request.GET.get('tahun', '')
        raw_periode = request.GET.get('periode', '')
        raw_pic_p3de = request.GET.get('pic_p3de', '')
        raw_pic_pide = request.GET.get('pic_pide', '')
        raw_pic_pmde = request.GET.get('pic_pmde', '')
        raw_kategori_ilap = request.GET.get('kategori_ilap', '')
        raw_ilap = request.GET.get('ilap', '')
        raw_jenis_data = request.GET.get('jenis_data', '')
        raw_sub_jenis_data = request.GET.get('sub_jenis_data', '')
        raw_kanwil = request.GET.get('kanwil', '')
        raw_kpp = request.GET.get('kpp', '')
        raw_kategori_wilayah = request.GET.get('kategori_wilayah', '')
        raw_jenis_tabel = request.GET.get('jenis_tabel', '')
        raw_dasar_hukum = request.GET.get('dasar_hukum', '')
        raw_periode_pengiriman = request.GET.get('periode_pengiriman', '')
        raw_periode_penerimaan = request.GET.get('periode_penerimaan', '')
        raw_status = request.GET.get('status', '')
        
        filter_nomor_tiket = _split_filter_options(raw_nomor_tiket)
        filter_tahun = _split_filter_options(raw_tahun)
        filter_periode = _split_filter_options(raw_periode)
        filter_pic_p3de = _split_filter_options(raw_pic_p3de)
        filter_pic_pide = _split_filter_options(raw_pic_pide)
        filter_pic_pmde = _split_filter_options(raw_pic_pmde)
        filter_kategori_ilap = _split_filter_options(raw_kategori_ilap)
        filter_ilap = _split_filter_options(raw_ilap)
        filter_jenis_data = _split_filter_options(raw_jenis_data)
        filter_sub_jenis_data = _split_filter_options(raw_sub_jenis_data)
        filter_kanwil = _split_filter_options(raw_kanwil)
        filter_kpp = _split_filter_options(raw_kpp)
        filter_kategori_wilayah = _split_filter_options(raw_kategori_wilayah)
        filter_jenis_tabel = _split_filter_options(raw_jenis_tabel)
        filter_dasar_hukum = _split_filter_options(raw_dasar_hukum)
        filter_periode_pengiriman = _split_filter_options(raw_periode_pengiriman)
        filter_periode_penerimaan = _split_filter_options(raw_periode_penerimaan)
        filter_status = _split_filter_options(raw_status)
        
        # Build a fully filtered queryset based on ALL current selections (except each dropdown's own filter)
        # This ensures changing any dropdown dynamically narrows down the options in all others.
        filtered_qs = base_qs
        
        if filter_nomor_tiket:
            filtered_qs = filtered_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                filtered_qs = filtered_qs.filter(tahun__in=int_years)
        
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        filtered_qs = filtered_qs.filter(periode=int(pval))
                        type_to_penerimaan = {
                            'bulanan': 'Bulanan',
                            'triwulanan': 'Triwulanan',
                            'semester': 'Semester',
                            'tahunan': 'Tahunan',
                        }
                        if ptype in type_to_penerimaan:
                            filtered_qs = filtered_qs.filter(
                                id_periode_data__id_periode_pengiriman__periode_penerimaan=type_to_penerimaan[ptype]
                            )
                    except ValueError:
                        pass
        
        if filter_periode_penerimaan:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        
        if filter_pic_p3de:
            filtered_qs = filtered_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        
        if filter_pic_pide:
            filtered_qs = filtered_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        
        if filter_pic_pmde:
            filtered_qs = filtered_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        
        if filter_kategori_ilap:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        
        if filter_sub_jenis_data:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        
        if filter_ilap:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        
        if filter_jenis_data:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        
        if filter_kanwil:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        
        if filter_kpp:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        
        if filter_kategori_wilayah:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        
        if filter_jenis_tabel:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        
        if filter_dasar_hukum:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        
        if filter_periode_pengiriman:
            filtered_qs = filtered_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                filtered_qs = filtered_qs.filter(status_tiket__in=int_statuses)
        
        nomor_options = []
        nomor_seen = set()
        for n in filtered_qs.order_by('id').values_list('nomor_tiket', flat=True):
            if not n or n in nomor_seen:
                continue
            nomor_seen.add(n)
            nomor_options.append({'id': n, 'name': n})

        # Tahun options - filter by ALL selections EXCEPT tahun itself
        tahun_filter_qs = base_qs
        if filter_nomor_tiket:
            tahun_filter_qs = tahun_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        tahun_filter_qs = tahun_filter_qs.filter(periode=int(pval))
                    except ValueError:
                        pass
        if filter_periode_penerimaan:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        if filter_pic_p3de:
            tahun_filter_qs = tahun_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            tahun_filter_qs = tahun_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            tahun_filter_qs = tahun_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_kategori_ilap:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        if filter_ilap:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        if filter_jenis_data:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        if filter_sub_jenis_data:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        if filter_kanwil:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            tahun_filter_qs = tahun_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                tahun_filter_qs = tahun_filter_qs.filter(status_tiket__in=int_statuses)
        
        tahun_options = []
        tahun_seen = set()
        for y in tahun_filter_qs.values_list('tahun', flat=True).distinct().order_by('tahun'):
            if y is None:
                continue
            y_str = str(y)
            if y_str in tahun_seen:
                continue
            tahun_seen.add(y_str)
            tahun_options.append({'id': y_str, 'name': y_str})

        # Get available periode values from filtered data — exclude periode self-filter
        periode_filter_qs = base_qs
        if filter_nomor_tiket:
            periode_filter_qs = periode_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                periode_filter_qs = periode_filter_qs.filter(tahun__in=int_years)
        if filter_pic_p3de:
            periode_filter_qs = periode_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            periode_filter_qs = periode_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            periode_filter_qs = periode_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_kategori_ilap:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        if filter_ilap:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        if filter_jenis_data:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        if filter_sub_jenis_data:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        if filter_kanwil:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            periode_filter_qs = periode_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                periode_filter_qs = periode_filter_qs.filter(status_tiket__in=int_statuses)
        
        periode_raw_qs = periode_filter_qs.values_list(
            'periode',
            'id_periode_data__id_periode_pengiriman__periode_penerimaan'
        ).distinct()
        bulan_names = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        bulanan_opts = {}
        triwulan_opts = {}
        semester_opts = {}
        tahunan_opts = {}
        
        for period_val, penerimaan in periode_raw_qs:
            if period_val is None:
                continue
            penerimaan = (penerimaan or '').strip().lower()
            idx = int(period_val)
            
            if 'triwulan' in penerimaan and 1 <= idx <= 4:
                triwulan_opts[idx] = {'id': f'triwulanan:{idx}', 'name': f'Triwulan {idx}'}
            elif 'semester' in penerimaan and 1 <= idx <= 2:
                semester_opts[idx] = {'id': f'semester:{idx}', 'name': f'Semester {idx}'}
            elif 'tahunan' in penerimaan:
                tahunan_opts[1] = {'id': 'tahunan:1', 'name': 'Tahunan'}
            elif 1 <= idx <= 12:
                bulanan_opts[idx] = {'id': f'bulanan:{idx}', 'name': bulan_names[idx - 1]}

        # Combine: bulanan (sorted), then triwulan, then semester, then tahunan
        periode_options = []
        for idx in sorted(bulanan_opts):
            periode_options.append(bulanan_opts[idx])
        for idx in sorted(triwulan_opts):
            periode_options.append(triwulan_opts[idx])
        for idx in sorted(semester_opts):
            periode_options.append(semester_opts[idx])
        for idx in sorted(tahunan_opts):
            periode_options.append(tahunan_opts[idx])

        # Get related items from filtered queryset for dynamic dropdowns
        periode_pengiriman_qs = filtered_qs.values_list(
            'id_periode_data__id_periode_pengiriman__periode_penyampaian',
            flat=True
        ).distinct()
        periode_pengiriman_options = []
        seen = set()
        for val in periode_pengiriman_qs:
            if val and val not in seen:
                seen.add(val)
                periode_pengiriman_options.append({'id': val, 'name': val})
        
        periode_penerimaan_qs = filtered_qs.values_list(
            'id_periode_data__id_periode_pengiriman__periode_penerimaan',
            flat=True
        ).distinct()
        periode_penerimaan_options = []
        periode_penerimaan_seen = set()
        for val in periode_penerimaan_qs:
            val = (val or '').strip()
            if val and val not in periode_penerimaan_seen:
                periode_penerimaan_seen.add(val)
                periode_penerimaan_options.append({'id': val, 'name': val})

        def _pic_options_filtered(tipe, qs):
            """Get PIC options filtered by the current queryset"""
            user_ids = qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE if tipe == PIC.TipePIC.P3DE else 
                TiketPIC.Role.PIDE if tipe == PIC.TipePIC.PIDE else 
                TiketPIC.Role.PMDE,
                tiketpic__active=True
            ).values_list('tiketpic__id_user_id', flat=True).distinct()
            
            vals = PIC.objects.filter(
                tipe=tipe,
                end_date__isnull=True,
                id_user_id__in=user_ids
            ).select_related('id_user').order_by('id_user__first_name', 'id_user__last_name', 'id_user__username')
            seen_users = set()
            data = []
            for v in vals:
                user = v.id_user
                if not user or user.id in seen_users:
                    continue
                seen_users.add(user.id)
                full_name = f"{user.first_name} {user.last_name}".strip()
                label = f"{user.username} - {full_name}" if full_name else user.username
                data.append({'id': str(user.id), 'name': label})
            return data

        pic_p3de_options = _pic_options_filtered(PIC.TipePIC.P3DE, filtered_qs)
        pic_pide_options = _pic_options_filtered(PIC.TipePIC.PIDE, filtered_qs)
        pic_pmde_options = _pic_options_filtered(PIC.TipePIC.PMDE, filtered_qs)

        # Get ILAP categories - filter by ALL selections EXCEPT kategori_ilap itself
        # Build from base_qs excluding the kategori_ilap self-filter
        kategori_ilap_filter_qs = base_qs
        if filter_nomor_tiket:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(tahun__in=int_years)
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(periode=int(pval))
                    except ValueError:
                        pass
        if filter_periode_penerimaan:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        if filter_pic_p3de:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_sub_jenis_data:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        if filter_ilap:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        if filter_jenis_data:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        if filter_kanwil:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                kategori_ilap_filter_qs = kategori_ilap_filter_qs.filter(status_tiket__in=int_statuses)
        
        kategori_ilap_qs = kategori_ilap_filter_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id_kategori',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__nama_kategori'
        ).distinct()
        kategori_ilap_options = []
        seen = set()
        for cat_id, cat_code, cat_name in kategori_ilap_qs:
            if cat_id and cat_id not in seen:
                seen.add(cat_id)
                kategori_ilap_options.append({
                    'id': str(cat_id), 
                    'name': f"{cat_code} - {cat_name}"
                })
        
        # Get ILAPs - filter by ALL selections EXCEPT ilap (to keep dropdown options while other filters narrow down)
        ilap_filter_qs = base_qs
        if filter_nomor_tiket:
            ilap_filter_qs = ilap_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                ilap_filter_qs = ilap_filter_qs.filter(tahun__in=int_years)
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        ilap_filter_qs = ilap_filter_qs.filter(periode=int(pval))
                    except ValueError:
                        pass
        if filter_periode_penerimaan:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        if filter_pic_p3de:
            ilap_filter_qs = ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            ilap_filter_qs = ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            ilap_filter_qs = ilap_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_kategori_ilap:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        if filter_sub_jenis_data:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        if filter_jenis_data:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        if filter_kanwil:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            ilap_filter_qs = ilap_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                ilap_filter_qs = ilap_filter_qs.filter(status_tiket__in=int_statuses)
        
        ilap_qs = ilap_filter_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_ilap',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap'
        ).distinct()
        ilap_options = []
        seen = set()
        for ilap_id, ilap_code, ilap_name in ilap_qs:
            if ilap_id and ilap_id not in seen:
                seen.add(ilap_id)
                ilap_options.append({
                    'id': str(ilap_id),
                    'name': f"{ilap_code} - {ilap_name}"
                })

        # Get Jenis Data and Sub Jenis Data - filter by ALL selections EXCEPT jenis_data and sub_jenis_data
        jenis_filter_qs = base_qs
        if filter_nomor_tiket:
            jenis_filter_qs = jenis_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                jenis_filter_qs = jenis_filter_qs.filter(tahun__in=int_years)
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        jenis_filter_qs = jenis_filter_qs.filter(periode=int(pval))
                    except ValueError:
                        pass
        if filter_periode_penerimaan:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        if filter_pic_p3de:
            jenis_filter_qs = jenis_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            jenis_filter_qs = jenis_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            jenis_filter_qs = jenis_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_kategori_ilap:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        if filter_ilap:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        if filter_kanwil:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            jenis_filter_qs = jenis_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        if filter_status:
            int_statuses = []
            for s in filter_status:
                try:
                    int_statuses.append(int(s))
                except ValueError:
                    pass
            if int_statuses:
                jenis_filter_qs = jenis_filter_qs.filter(status_tiket__in=int_statuses)
        
        jenis_options = []
        jenis_seen = set()
        sub_jenis_options = []
        sub_jenis_seen = set()
        
        jenis_qs = jenis_filter_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_jenis_data',
            'id_periode_data__id_sub_jenis_data_ilap__nama_jenis_data'
        ).distinct()
        
        for jenis_id, jenis_name in jenis_qs:
            if jenis_id and jenis_id not in jenis_seen:
                jenis_seen.add(jenis_id)
                jenis_options.append({'id': jenis_id, 'name': f"{jenis_id} - {jenis_name}"})
        
        sub_jenis_qs = jenis_filter_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data',
            'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data'
        ).distinct()
        
        for sub_jenis_id, sub_jenis_name in sub_jenis_qs:
            if sub_jenis_id and sub_jenis_id not in sub_jenis_seen:
                sub_jenis_seen.add(sub_jenis_id)
                sub_jenis_options.append({'id': sub_jenis_id, 'name': f"{sub_jenis_id} - {sub_jenis_name}"})

        # Get Kanwil from filtered queryset
        kanwil_qs = filtered_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__kode_kanwil',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__nama_kanwil'
        ).distinct()
        kanwil_options = []
        seen = set()
        for kanwil_id, kanwil_code, kanwil_name in kanwil_qs:
            if kanwil_id and kanwil_id not in seen:
                seen.add(kanwil_id)
                kanwil_options.append({
                    'id': str(kanwil_id),
                    'name': f"{kanwil_code} - {kanwil_name}"
                })

        # Get KPP from filtered queryset
        kpp_qs = filtered_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__kode_kpp',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__nama_kpp'
        ).distinct()
        kpp_options = []
        seen = set()
        for kpp_id, kpp_code, kpp_name in kpp_qs:
            if kpp_id and kpp_id not in seen:
                seen.add(kpp_id)
                kpp_options.append({
                    'id': str(kpp_id),
                    'name': f"{kpp_code} - {kpp_name}"
                })

        # Get Kategori Wilayah from filtered queryset
        kategori_wilayah_qs = filtered_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__deskripsi'
        ).distinct()
        kategori_wilayah_options = []
        seen = set()
        for wilayah_id, wilayah_desc in kategori_wilayah_qs:
            if wilayah_id and wilayah_id not in seen:
                seen.add(wilayah_id)
                kategori_wilayah_options.append({
                    'id': str(wilayah_id),
                    'name': wilayah_desc
                })

        # Get Jenis Tabel from filtered queryset
        jenis_tabel_qs = filtered_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id',
            'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi'
        ).distinct()
        jenis_tabel_options = []
        seen = set()
        for tabel_id, tabel_desc in jenis_tabel_qs:
            if tabel_id and tabel_id not in seen:
                seen.add(tabel_id)
                jenis_tabel_options.append({
                    'id': str(tabel_id),
                    'name': tabel_desc
                })

        # Get Dasar Hukum from filtered queryset
        dasar_hukum_qs = filtered_qs.values_list(
            'id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id',
            'id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__deskripsi'
        ).distinct()
        dasar_hukum_options = []
        seen = set()
        for hukum_id, hukum_desc in dasar_hukum_qs:
            if hukum_id and hukum_id not in seen:
                seen.add(hukum_id)
                dasar_hukum_options.append({
                    'id': str(hukum_id),
                    'name': hukum_desc
                })

        # Status options - filter by ALL selections EXCEPT status itself
        status_filter_qs = base_qs
        if filter_nomor_tiket:
            status_filter_qs = status_filter_qs.filter(nomor_tiket__in=filter_nomor_tiket)
        if filter_tahun:
            int_years = []
            for y in filter_tahun:
                try:
                    int_years.append(int(y))
                except ValueError:
                    pass
            if int_years:
                status_filter_qs = status_filter_qs.filter(tahun__in=int_years)
        if filter_periode:
            for pv in filter_periode:
                if ':' in pv:
                    ptype, pval = pv.split(':', 1)
                    try:
                        status_filter_qs = status_filter_qs.filter(periode=int(pval))
                    except ValueError:
                        pass
        if filter_periode_penerimaan:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan
            )
        if filter_pic_p3de:
            status_filter_qs = status_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de
            )
        if filter_pic_pide:
            status_filter_qs = status_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide
            )
        if filter_pic_pmde:
            status_filter_qs = status_filter_qs.filter(
                tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde
            )
        if filter_kategori_ilap:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap
            )
        if filter_ilap:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap
            )
        if filter_jenis_data:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data
            )
        if filter_sub_jenis_data:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data
            )
        if filter_kanwil:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil
            )
        if filter_kpp:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp
            )
        if filter_kategori_wilayah:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah
            )
        if filter_jenis_tabel:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel
            )
        if filter_dasar_hukum:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
            )
        if filter_periode_pengiriman:
            status_filter_qs = status_filter_qs.filter(
                id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman
            )
        
        # Get distinct status_tiket values from filtered data
        available_status_ids = set(
            status_filter_qs.values_list('status_tiket', flat=True).distinct()
        )
        status_options = [
            {'id': str(sid), 'name': STATUS_LABELS.get(sid, f'Status {sid}')}
            for sid in sorted(available_status_ids)
            if sid is not None
        ]

        return JsonResponse({
            'filter_options': {
                'nomor_tiket': nomor_options,
                'tahun': tahun_options,
                'periode': periode_options,
                'periode_penerimaan': periode_penerimaan_options,
                'pic_p3de': pic_p3de_options,
                'pic_pide': pic_pide_options,
                'pic_pmde': pic_pmde_options,
                'kategori_ilap': kategori_ilap_options,
                'ilap': ilap_options,
                'jenis_data': jenis_options,
                'sub_jenis_data': sub_jenis_options,
                'kanwil': kanwil_options,
                'kpp': kpp_options,
                'kategori_wilayah': kategori_wilayah_options,
                'jenis_tabel': jenis_tabel_options,
                'dasar_hukum': dasar_hukum_options,
                'periode_pengiriman': periode_pengiriman_options,
                'status': status_options,
            }
        })

    # Helper to split comma-separated multi-select values
    def _split(v):
        if not v:
            return []
        return [x.strip() for x in v.split(',') if x.strip()]

    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = base_qs
    records_total = qs.count()

    # Dropdown filters (monitoring-style) — support comma-separated multi-select
    filter_nomor_tiket = _split(request.GET.get('nomor_tiket', ''))
    filter_periode = request.GET.get('periode', '').strip()
    filter_periode_penerimaan = _split(request.GET.get('periode_penerimaan', ''))
    filter_pic_p3de = _split(request.GET.get('pic_p3de', ''))
    filter_pic_pide = _split(request.GET.get('pic_pide', ''))
    filter_pic_pmde = _split(request.GET.get('pic_pmde', ''))
    filter_kategori_ilap = _split(request.GET.get('kategori_ilap', ''))
    filter_ilap = _split(request.GET.get('ilap', ''))
    filter_jenis_data = _split(request.GET.get('jenis_data', ''))
    filter_sub_jenis_data = _split(request.GET.get('sub_jenis_data', ''))
    filter_kanwil = _split(request.GET.get('kanwil', ''))
    filter_kpp = _split(request.GET.get('kpp', ''))
    filter_kategori_wilayah = _split(request.GET.get('kategori_wilayah', ''))
    filter_jenis_tabel = _split(request.GET.get('jenis_tabel', ''))
    filter_dasar_hukum = _split(request.GET.get('dasar_hukum', ''))
    filter_periode_pengiriman = _split(request.GET.get('periode_pengiriman', ''))
    filter_tahun = _split(request.GET.get('tahun', ''))
    filter_status = _split(request.GET.get('status', ''))

    if filter_nomor_tiket:
        qs = qs.filter(nomor_tiket__in=filter_nomor_tiket)

    if filter_periode:
        try:
            periode_type = None
            periode_value = filter_periode
            if ':' in filter_periode:
                periode_type, periode_value = filter_periode.split(':', 1)
            qs = qs.filter(periode=int(periode_value))

            type_to_penerimaan = {
                'bulanan': 'Bulanan',
                'triwulanan': 'Triwulanan',
                'semester': 'Semester',
                'tahunan': 'Tahunan',
            }
            if periode_type in type_to_penerimaan:
                qs = qs.filter(id_periode_data__id_periode_pengiriman__periode_penerimaan=type_to_penerimaan[periode_type])
        except ValueError:
            qs = qs.none()

    if filter_periode_penerimaan:
        qs = qs.filter(id_periode_data__id_periode_pengiriman__periode_penerimaan__in=filter_periode_penerimaan)

    if filter_pic_p3de:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_p3de)

    if filter_pic_pide:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pide)

    if filter_pic_pmde:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id__in=filter_pic_pmde)

    if filter_kategori_ilap:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id__in=filter_kategori_ilap)

    if filter_ilap:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id__in=filter_ilap)

    if filter_jenis_data:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_jenis_data__in=filter_jenis_data)

    if filter_sub_jenis_data:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data__in=filter_sub_jenis_data)

    if filter_kanwil:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id__in=filter_kanwil)

    if filter_kpp:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id__in=filter_kpp)

    if filter_kategori_wilayah:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id__in=filter_kategori_wilayah)

    if filter_jenis_tabel:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id__in=filter_jenis_tabel)

    if filter_dasar_hukum:
        qs = qs.filter(
            id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id__in=filter_dasar_hukum
        )

    if filter_periode_pengiriman:
        qs = qs.filter(id_periode_data__id_periode_pengiriman__periode_penyampaian__in=filter_periode_pengiriman)

    if filter_tahun:
        int_years = []
        for y in filter_tahun:
            try:
                int_years.append(int(y))
            except ValueError:
                pass
        if int_years:
            qs = qs.filter(tahun__in=int_years)
        else:
            qs = qs.none()

    if filter_status:
        int_statuses = []
        for s in filter_status:
            try:
                int_statuses.append(int(s))
            except ValueError:
                pass
        if int_statuses:
            qs = qs.filter(status_tiket__in=int_statuses)
        else:
            qs = qs.none()

    qs = qs.distinct()

    records_filtered = qs.count()

    # ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')
    # Columns mapping for ordering to match DataTables columns:
    # 0:id, 1:nomor_tiket, 2:ILAP (kode), 3:Jenis Data (nama), 4:periode, 5:status_tiket
    columns = [
        'id',
        'nomor_tiket',
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
        'periode',
        'status_tiket'
    ]
    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = columns[idx] if idx < len(columns) else 'id'
            if order_dir == 'desc':
                col = '-' + col
            qs = qs.order_by(col)
        except Exception:
            qs = qs.order_by('id')
    else:
        qs = qs.order_by('id')

    qs_page = qs[start:start + length]

    data = []
    for obj in qs_page:
        # Get nama_ilap and nama_sub_jenis_data from related models
        nama_ilap = '-'
        kode_ilap = '-'
        nama_sub_jenis_data = '-'
        id_sub_jenis_data = '-'
        if obj.id_periode_data and obj.id_periode_data.id_sub_jenis_data_ilap:
            jenis_data_ilap = obj.id_periode_data.id_sub_jenis_data_ilap
            if jenis_data_ilap.id_ilap:
                kode_ilap = jenis_data_ilap.id_ilap.id_ilap
                nama_ilap = jenis_data_ilap.id_ilap.nama_ilap
            id_sub_jenis_data = jenis_data_ilap.id_sub_jenis_data
            nama_sub_jenis_data = jenis_data_ilap.nama_sub_jenis_data

        periode_formatted = _format_periode_tiket(obj)

        detail_btn = f"<a href='{reverse('tiket_detail', args=[obj.pk])}' class='btn btn-sm btn-info' title='View'><i class='feather-eye'></i></a>"
        
        actions_html = f"<div class='btn-group btn-group-sm' role='group'>{detail_btn}</div>"

        data.append({
            'id': obj.id,
            'nomor_tiket': obj.nomor_tiket or '-',
            'kode_ilap': kode_ilap,
            'nama_ilap': nama_ilap,
            'id_sub_jenis_data': id_sub_jenis_data,
            'nama_sub_jenis_data': nama_sub_jenis_data,
            'periode_formatted': periode_formatted,
            'status': STATUS_LABELS.get(obj.status_tiket, '-'),
            'status_ketersediaan_data': 'Ya' if obj.status_ketersediaan_data else 'Tidak',
            'actions': actions_html
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
