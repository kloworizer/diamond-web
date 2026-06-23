"""Quality Control page - PMDE User Quality Control view.

This module provides a simple page for PMDE users to view and monitor
tickets that are in the quality control process (status = Pengendalian Mutu).
Displays a DataTable with comprehensive columns including ILAP info, PIC,
deadline calculations, and QC progress.
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q, Value
from django.db.models.functions import Cast
from django.db.models import (
    DateField, IntegerField, Subquery, OuterRef,
    Exists
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import date

from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..models.klasifikasi_jenis_data import KlasifikasiJenisData
from ..models.durasi_jatuh_tempo import DurasiJatuhTempo
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..constants.tiket_status import STATUS_PENGENDALIAN_MUTU


def _is_pmde_user(user):
    """Check if user is PMDE user or admin."""
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['user_pmde', 'admin', 'admin_pmde']
    ).exists()


class QualityControlView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Display Quality Control page for PMDE users.

    Shows a DataTable of tickets assigned to the current PMDE user that
    are in the quality control process (status = Pengendalian Mutu).

    Template: quality_control/list.html
    """
    template_name = 'quality_control/list.html'

    def test_func(self):
        """Verify user is PMDE user or admin."""
        return _is_pmde_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


@login_required
@user_passes_test(_is_pmde_user)
@require_http_methods(["POST", "GET"])
@csrf_protect
def quality_control_data(request):
    """DataTables server-side endpoint for Quality Control page."""
    params = request.POST if request.method == 'POST' else request.GET

    draw = int(params.get('draw', '1'))
    start = int(params.get('start', '0'))
    length = int(params.get('length', '10'))

    # Get the PMDE-assigned ticket IDs for the current user
    pmde_pic = TiketPIC.objects.filter(
        id_user=request.user, role=TiketPIC.Role.PMDE, active=True
    )
    pmde_tiket_ids = pmde_pic.values_list('id_tiket', flat=True)

    # Subquery: active durasi for each ticket's sub_jenis_data & tgl_transfer range
    durasi_subq = DurasiJatuhTempo.objects.filter(
        id_sub_jenis_data=OuterRef('id_periode_data__id_sub_jenis_data_ilap'),
        seksi__name='user_pmde',
        start_date__lte=Cast(OuterRef('tgl_transfer'), DateField()),
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=Cast(OuterRef('tgl_transfer'), DateField()))
    ).order_by('-start_date').values('durasi')[:1]

    # Base query with date annotations for sorting
    tikets = Tiket.objects.filter(
        id__in=pmde_tiket_ids,
        status_tiket=STATUS_PENGENDALIAN_MUTU
    ).select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel',
    ).prefetch_related(
        'tiketpic_set',
    ).annotate(
        tgl_transfer_date=Cast('tgl_transfer', DateField()),
        tgl_rematch_date=Cast('tgl_rematch', DateField()),
        # Active durasi for sorting deadline / jatuh tempo
        active_durasi=Coalesce(
            Subquery(durasi_subq, output_field=IntegerField()),
            Value(0)
        ),
    ).annotate(
        # Prioritas: check if tgl_terima_dip falls within JenisPrioritasData range
        is_prioritas=Exists(
            JenisPrioritasData.objects.filter(
                id_sub_jenis_data_ilap=OuterRef('id_periode_data__id_sub_jenis_data_ilap'),
                start_date__lte=Cast(OuterRef('tgl_terima_dip'), DateField()),
                end_date__gte=Cast(OuterRef('tgl_terima_dip'), DateField()),
            )
        ),
    )

    # ---- Column search ----
    columns_search = params.getlist('columns_search[]') or params.getlist('columns_search')
    if columns_search:
        if len(columns_search) > 0 and columns_search[0]:
            tikets = tikets.filter(id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I__icontains=columns_search[0])
        if len(columns_search) > 2 and columns_search[2]:
            tikets = tikets.filter(nomor_tiket__icontains=columns_search[2])
        if len(columns_search) > 3 and columns_search[3]:
            tikets = tikets.filter(id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=columns_search[3])
        if len(columns_search) > 4 and columns_search[4]:
            tikets = tikets.filter(id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=columns_search[4])
        if len(columns_search) > 5 and columns_search[5]:
            tikets = tikets.filter(id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi__icontains=columns_search[5])
        if len(columns_search) > 8 and columns_search[8]:
            tikets = tikets.filter(tgl_transfer__icontains=columns_search[8])
        if len(columns_search) > 9 and columns_search[9]:
            tikets = tikets.filter(tgl_rematch__icontains=columns_search[9])
        if len(columns_search) > 10 and columns_search[10]:
            search_val = columns_search[10].lower()
            prioritas_qs = JenisPrioritasData.objects.filter(
                id_sub_jenis_data_ilap=OuterRef('id_periode_data__id_sub_jenis_data_ilap'),
                start_date__lte=Cast(OuterRef('tgl_terima_dip'), DateField()),
                end_date__gte=Cast(OuterRef('tgl_terima_dip'), DateField()),
            )
            if search_val in ('ya', 'y'):
                tikets = tikets.filter(Exists(prioritas_qs))
            elif search_val in ('tidak', 't', 'tdk'):
                tikets = tikets.filter(~Exists(prioritas_qs))
        if len(columns_search) > 12 and columns_search[12]:
            tikets = tikets.filter(baris_i__icontains=columns_search[12])
        if len(columns_search) > 13 and columns_search[13]:
            tikets = tikets.filter(sudah_qc__icontains=columns_search[13])
        if len(columns_search) > 14 and columns_search[14]:
            tikets = tikets.filter(belum_qc__icontains=columns_search[14])

    records_filtered = tikets.count()

    # ---- Server-side sorting ----
    order_map = {
        0: 'id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I',
        1: 'id',
        2: 'nomor_tiket',
        3: 'id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap',
        4: 'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
        5: 'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel__deskripsi',
        6: 'id',
        7: 'tgl_transfer_date',
        8: 'tgl_transfer_date',
        9: 'tgl_rematch_date',
        10: 'tgl_transfer_date',
        11: 'is_prioritas',
        12: 'baris_i',
        13: 'sudah_qc',
        14: 'belum_qc',
    }

    # Read sort column and direction from DataTables params
    order_col_index = params.get('order[0][column]')
    order_dir = params.get('order[0][dir]', 'asc')

    if order_col_index is not None:
        try:
            idx = int(order_col_index)
            col = order_map.get(idx, 'id')
            if order_dir == 'desc':
                col = '-' + col
            tikets = tikets.order_by(col)
        except (ValueError, TypeError):
            tikets = tikets.order_by('-id')
    else:
        tikets = tikets.order_by('-id')

    # Pagination
    tikets = tikets[start:start + length]

    # Build response data
    data = []
    for tiket in tikets:
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        ilap = sub_jenis_data.id_ilap
        jenis_tabel = sub_jenis_data.id_jenis_tabel

        # Get PIC PMDE name
        pic_pmde_name = ''
        pic_pmde = tiket.tiketpic_set.filter(role=TiketPIC.Role.PMDE, active=True).first()
        if pic_pmde and pic_pmde.id_user:
            pic_pmde_name = pic_pmde.id_user.get_full_name() or pic_pmde.id_user.username

        # Get klasifikasi (kategori from dasar_hukum) via KlasifikasiJenisData
        klasifikasi_list = KlasifikasiJenisData.objects.filter(
            id_sub_jenis_data=sub_jenis_data
        ).select_related('id_klasifikasi_tabel')
        kategori_list = [k.id_klasifikasi_tabel.kategori for k in klasifikasi_list if k.id_klasifikasi_tabel]
        kategori_str = ', '.join(kategori_list) if kategori_list else '-'

        # Lookup active DurasiJatuhTempo for PMDE where tgl_transfer falls in range
        deadline = '-'
        jatuh_tempo = '-'
        if tiket.tgl_transfer:
            tgl_transfer_date = tiket.tgl_transfer.date() if hasattr(tiket.tgl_transfer, 'date') else tiket.tgl_transfer
            aktif_durasi = DurasiJatuhTempo.objects.filter(
                id_sub_jenis_data=sub_jenis_data,
                seksi__name='user_pmde',
                start_date__lte=tgl_transfer_date,
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=tgl_transfer_date)
            ).order_by('-start_date').first()
        else:
            aktif_durasi = None

        if aktif_durasi and aktif_durasi.durasi:
            if tiket.tgl_transfer:
                try:
                    deadline_date = tiket.tgl_transfer + timezone.timedelta(days=aktif_durasi.durasi)
                    deadline = deadline_date.strftime('%d/%m/%Y')
                    sisa_hari = (deadline_date.date() - date.today()).days if hasattr(deadline_date, 'date') else (deadline_date - date.today()).days
                    jatuh_tempo = f'{sisa_hari} hari'
                except Exception:
                    deadline = '-'
                    jatuh_tempo = '-'

        # Compute sort-friendly values for orthogonal DataTable sorting
        deadline_sort_iso = deadline_date.strftime('%Y-%m-%d') if deadline != '-' and 'deadline_date' in locals() else ''
        tgl_transfer_sort = tiket.tgl_transfer.strftime('%Y-%m-%d') if tiket.tgl_transfer else ''
        tgl_rematch_sort = tiket.tgl_rematch.strftime('%Y-%m-%d') if tiket.tgl_rematch else ''
        sisa_hari_val = str(sisa_hari) if 'sisa_hari' in locals() else ''
        # Numeric days remaining for frontend row coloring (None = unknown)
        jatuh_tempo_days = locals().get('sisa_hari', None)

        row = {
            'nama_tabel': sub_jenis_data.nama_tabel_I or '',
            'pic_pmde': pic_pmde_name,
            'nomor_tiket': tiket.nomor_tiket,
            'nama_ilap': ilap.nama_ilap if ilap else '',
            'sub_jenis_data': sub_jenis_data.nama_sub_jenis_data or '',
            'jenis_tabel': jenis_tabel.deskripsi if jenis_tabel else '',
            'klasifikasi': kategori_str,
            'deadline': {'display': deadline, 'sort': deadline_sort_iso},
            'tgl_transfer': {'display': tiket.tgl_transfer.strftime('%d/%m/%Y') if tiket.tgl_transfer else '-', 'sort': tgl_transfer_sort},
            'tgl_rematch': {'display': tiket.tgl_rematch.strftime('%d/%m/%Y') if tiket.tgl_rematch else '-', 'sort': tgl_rematch_sort},
            'jatuh_tempo': {'display': jatuh_tempo, 'sort': sisa_hari_val},
            'prioritas': 'Ya' if tiket.is_prioritas else 'Tidak',
            'jml_baris_i': tiket.baris_i or 0,
            'jml_selesai': tiket.sudah_qc or 0,
            'jml_progress': tiket.belum_qc or 0,
            'sisa_hari': jatuh_tempo_days,  # numeric for frontend row coloring
            'action': f'<a href="{reverse("tiket_detail", args=[tiket.id])}" class="btn btn-sm btn-primary" title="Lihat Detail"><i class="feather-eye"></i></a>',
        }
        data.append(row)

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_filtered,
        'recordsFiltered': records_filtered,
        'data': data
    })
