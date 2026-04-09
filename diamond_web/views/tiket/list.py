"""Tiket list view - shared across all workflow steps."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

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

    # Return dynamic filter options for dropdowns
    if request.GET.get('get_filter_options'):
        nomor_options = []
        nomor_seen = set()
        for n in base_qs.order_by('id').values_list('nomor_tiket', flat=True):
            if not n or n in nomor_seen:
                continue
            nomor_seen.add(n)
            nomor_options.append({'id': n, 'name': n})

        tahun_options = []
        tahun_seen = set()
        for y in PeriodeJenisData.objects.order_by('id').values_list('start_date__year', flat=True):
            if y is None:
                continue
            y_str = str(y)
            if y_str in tahun_seen:
                continue
            tahun_seen.add(y_str)
            tahun_options.append({'id': y_str, 'name': y_str})

        periode_options = []
        bulan_names = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
        for idx, nama in enumerate(bulan_names, start=1):
            periode_options.append({'id': f'bulanan:{idx}', 'name': nama})
        for idx in range(1, 5):
            periode_options.append({'id': f'triwulanan:{idx}', 'name': f'Triwulan {idx}'})
        for idx in range(1, 3):
            periode_options.append({'id': f'semester:{idx}', 'name': f'Semester {idx}'})
        periode_options.append({'id': 'tahunan:1', 'name': 'Tahunan'})

        periode_pengiriman_options = [
            {'id': p.periode_penyampaian, 'name': p.periode_penyampaian}
            for p in PeriodePengiriman.objects.all().order_by('id')
            if p.periode_penyampaian
        ]
        periode_penerimaan_options = []
        periode_penerimaan_seen = set()
        for p in PeriodePengiriman.objects.all().order_by('id'):
            val = (p.periode_penerimaan or '').strip()
            if not val or val in periode_penerimaan_seen:
                continue
            periode_penerimaan_seen.add(val)
            periode_penerimaan_options.append({'id': val, 'name': val})

        def _pic_options(tipe):
            vals = PIC.objects.filter(
                tipe=tipe,
                end_date__isnull=True
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

        pic_p3de_options = _pic_options(PIC.TipePIC.P3DE)
        pic_pide_options = _pic_options(PIC.TipePIC.PIDE)
        pic_pmde_options = _pic_options(PIC.TipePIC.PMDE)

        kategori_ilap_options = [
            {'id': str(o.id), 'name': f"{o.id_kategori} - {o.nama_kategori}"}
            for o in KategoriILAP.objects.all().order_by('id')
        ]
        ilap_options = [
            {'id': str(o.id), 'name': f"{o.id_ilap} - {o.nama_ilap}"}
            for o in ILAP.objects.all().order_by('id')
        ]

        jenis_options = []
        jenis_seen = set()
        sub_jenis_options = []
        sub_jenis_seen = set()
        for o in JenisDataILAP.objects.all().order_by('id'):
            if o.id_jenis_data and o.id_jenis_data not in jenis_seen:
                jenis_seen.add(o.id_jenis_data)
                jenis_options.append({'id': o.id_jenis_data, 'name': f"{o.id_jenis_data} - {o.nama_jenis_data}"})
            if o.id_sub_jenis_data and o.id_sub_jenis_data not in sub_jenis_seen:
                sub_jenis_seen.add(o.id_sub_jenis_data)
                sub_jenis_options.append({'id': o.id_sub_jenis_data, 'name': f"{o.id_sub_jenis_data} - {o.nama_sub_jenis_data}"})

        kanwil_options = [
            {'id': str(o.id), 'name': f"{o.kode_kanwil} - {o.nama_kanwil}"}
            for o in Kanwil.objects.all().order_by('kode_kanwil')
        ]
        kpp_options = [
            {'id': str(o.id), 'name': f"{o.kode_kpp} - {o.nama_kpp}"}
            for o in KPP.objects.all().order_by('kode_kpp')
        ]
        kategori_wilayah_options = [
            {'id': str(o.id), 'name': o.deskripsi}
            for o in KategoriWilayah.objects.all().order_by('id')
        ]
        jenis_tabel_options = [
            {'id': str(o.id), 'name': o.deskripsi}
            for o in JenisTabel.objects.all().order_by('id')
        ]
        dasar_hukum_options = [
            {'id': str(o.id), 'name': o.deskripsi}
            for o in DasarHukum.objects.all().order_by('id')
        ]

        status_options = [
            {'id': str(sid), 'name': label}
            for sid, label in sorted(STATUS_LABELS.items(), key=lambda x: x[0])
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

    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))

    qs = base_qs
    records_total = qs.count()

    # Dropdown filters (monitoring-style)
    filter_nomor_tiket = request.GET.get('nomor_tiket', '').strip()
    filter_periode = request.GET.get('periode', '').strip()
    filter_periode_penerimaan = request.GET.get('periode_penerimaan', '').strip()
    filter_pic_p3de = request.GET.get('pic_p3de', '').strip()
    filter_pic_pide = request.GET.get('pic_pide', '').strip()
    filter_pic_pmde = request.GET.get('pic_pmde', '').strip()
    filter_kategori_ilap = request.GET.get('kategori_ilap', '').strip()
    filter_ilap = request.GET.get('ilap', '').strip()
    filter_jenis_data = request.GET.get('jenis_data', '').strip()
    filter_sub_jenis_data = request.GET.get('sub_jenis_data', '').strip()
    filter_kanwil = request.GET.get('kanwil', '').strip()
    filter_kpp = request.GET.get('kpp', '').strip()
    filter_kategori_wilayah = request.GET.get('kategori_wilayah', '').strip()
    filter_jenis_tabel = request.GET.get('jenis_tabel', '').strip()
    filter_dasar_hukum = request.GET.get('dasar_hukum', '').strip()
    filter_periode_pengiriman = request.GET.get('periode_pengiriman', '').strip()
    filter_terlambat = request.GET.get('terlambat', '').strip()
    filter_tahun = request.GET.get('tahun', '').strip()
    filter_status = request.GET.get('status', '').strip()

    if filter_nomor_tiket:
        qs = qs.filter(nomor_tiket=filter_nomor_tiket)

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
        qs = qs.filter(id_periode_data__id_periode_pengiriman__periode_penerimaan__iexact=filter_periode_penerimaan)

    if filter_pic_p3de:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.P3DE, tiketpic__active=True, tiketpic__id_user_id=filter_pic_p3de)

    if filter_pic_pide:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.PIDE, tiketpic__active=True, tiketpic__id_user_id=filter_pic_pide)

    if filter_pic_pmde:
        qs = qs.filter(tiketpic__role=TiketPIC.Role.PMDE, tiketpic__active=True, tiketpic__id_user_id=filter_pic_pmde)

    if filter_kategori_ilap:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori__id=filter_kategori_ilap)

    if filter_ilap:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id=filter_ilap)

    if filter_jenis_data:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_jenis_data=filter_jenis_data)

    if filter_sub_jenis_data:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_sub_jenis_data=filter_sub_jenis_data)

    if filter_kanwil:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id_kanwil__id=filter_kanwil)

    if filter_kpp:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kpp__id=filter_kpp)

    if filter_kategori_wilayah:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__id=filter_kategori_wilayah)

    if filter_jenis_tabel:
        qs = qs.filter(id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__id=filter_jenis_tabel)

    if filter_dasar_hukum:
        qs = qs.filter(
            id_periode_data__id_sub_jenis_data_ilap__klasifikasijenisdata__id_klasifikasi_tabel__id=filter_dasar_hukum
        )

    if filter_periode_pengiriman:
        qs = qs.filter(id_periode_data__id_periode_pengiriman__periode_penyampaian=filter_periode_pengiriman)

    if filter_tahun:
        try:
            qs = qs.filter(tahun=int(filter_tahun))
        except ValueError:
            qs = qs.none()

    if filter_status:
        try:
            qs = qs.filter(status_tiket=int(filter_status))
        except ValueError:
            qs = qs.none()

    if filter_terlambat in ('Ya', 'Tidak'):
        now = timezone.now()
        late_ids = []
        not_late_ids = []
        qs_for_late = qs.select_related('id_durasi_jatuh_tempo_pide')
        for obj in qs_for_late:
            is_late = False
            if obj.tgl_terima_dip and obj.id_durasi_jatuh_tempo_pide and obj.id_durasi_jatuh_tempo_pide.durasi is not None:
                deadline = obj.tgl_terima_dip + timedelta(days=obj.id_durasi_jatuh_tempo_pide.durasi)
                is_late = now > deadline
            if is_late:
                late_ids.append(obj.id)
            else:
                not_late_ids.append(obj.id)

        qs = qs.filter(id__in=late_ids if filter_terlambat == 'Ya' else not_late_ids)

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

        detail_btn = f"<a href='{reverse('tiket_detail', args=[obj.pk])}' class='btn btn-sm btn-info' title='View'><i class='ri-eye-line'></i></a>"
        
        # Only show download button to P3DE users
        if _is_p3de_user(request.user):
            if obj.tanda_terima:
                download_btn = f"<button type='button' onclick='downloadTiketDocs({obj.pk})' class='btn btn-sm btn-success' title='Generate Dokumen'><i class='ri-file-pdf-line'></i></button>"
            else:
                download_btn = "<button type='button' class='btn btn-sm btn-success' title='Tanda terima belum dibuat' disabled><i class='ri-file-pdf-line'></i></button>"
        else:
            download_btn = ""  # Hide button entirely for non-P3DE users
        
        actions_html = f"<div class='btn-group btn-group-sm'>{detail_btn}{download_btn}</div>"

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
