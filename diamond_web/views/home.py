from django.shortcuts import render
from django.conf import settings
from django.db.models import F, Q, Exists, OuterRef, Max, Subquery, Value
from django.db.models.functions import Concat
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET
from diamond_web.views.task_to_do import (
    get_tiket_summary_for_user_p3de,
    get_tiket_summary_for_user_pide,
    get_tiket_summary_for_user_pmde,
)
from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.pic import PIC
from diamond_web.models.jenis_data_ilap import JenisDataILAP
from diamond_web.constants.tiket_status import (
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_LABELS,
)
from diamond_web.constants.tiket_action_types import TiketActionType

@login_required
def home(request):
    """Render the application home page.

    Context provided to template:
    - `is_p3de` (bool): whether the current authenticated user belongs to
      `user_p3de` group. Used to show P3DE-specific UI.
    - `tiket_summary` (dict): when `is_p3de` is True, contains counts of
      actionable tiket items for the logged-in P3DE (uses
      `get_tiket_summary_for_user`). Example keys: `rekam_backup_data`,
      `buat_tanda_terima`, `rekam_hasil_penelitian`, `kirim_ke_pide`.
    - `p3de_tiket_categories` (dict): when `is_p3de` is True, contains filtered
      lists of tikets by category for the P3DE user.
    - `debug_user_groups` (dict): only present when `settings.DEBUG` is
      True; includes three admin groups and their member lists for UI
      debugging.

    Usage: GET request; returns rendered `home.html` with the above context.
    """
    context = {}
    # expose user role membership for templates
    is_p3de = False
    is_pide = False
    is_pmde = False
    if request.user.is_authenticated:
        is_p3de = request.user.groups.filter(name='user_p3de').exists()
        is_pide = request.user.groups.filter(name='user_pide').exists()
        is_pmde = request.user.groups.filter(name='user_pmde').exists()
    context['is_p3de'] = is_p3de
    context['is_pide'] = is_pide
    context['is_pmde'] = is_pmde
    # check admin group membership
    is_admin_p3de = request.user.groups.filter(name='admin_p3de').exists()
    is_admin_pide = request.user.groups.filter(name='admin_pide').exists()
    is_admin_pmde = request.user.groups.filter(name='admin_pmde').exists()
    context['is_admin_p3de'] = is_admin_p3de
    context['is_admin_pide'] = is_admin_pide
    context['is_admin_pmde'] = is_admin_pmde
    # compute task summary and category counts based on user role
    if is_p3de:
        context['tiket_summary'] = get_tiket_summary_for_user_p3de(request.user)
        p3de_tiket_ids = TiketPIC.objects.filter(
            id_user=request.user, role=TiketPIC.Role.P3DE, active=True
        ).values_list('id_tiket', flat=True)

        context['p3de_category_counts'] = {
            'belum_rekam_backup_data': Tiket.objects.filter(
                id__in=p3de_tiket_ids, status_tiket=STATUS_DIREKAM, backup=False
            ).count(),
            'belum_dibuat_tanda_terima': Tiket.objects.filter(
                id__in=p3de_tiket_ids, status_tiket=STATUS_DIREKAM, tanda_terima=False
            ).count(),
            'belum_diteliti': Tiket.objects.filter(
                id__in=p3de_tiket_ids, status_tiket=STATUS_DIREKAM, backup=True, tanda_terima=True
            ).count(),
            'belum_dikirim_ke_pide': Tiket.objects.filter(
                id__in=p3de_tiket_ids, status_tiket=STATUS_DITELITI, baris_lengkap__gt=0
            ).count(),
            'pengembalian_seluruhnya_dari_pide': Tiket.objects.filter(
                id__in=p3de_tiket_ids
            ).filter(
                Exists(TiketAction.objects.filter(
                    id_tiket=OuterRef('pk'),
                    action=TiketActionType.DIKEMBALIKAN
                ))
            ).count(),
            'pengembalian_sebagian_dari_pide': Tiket.objects.filter(
                id__in=p3de_tiket_ids, baris_cde__gt=0
            ).exclude(baris_cde=F('baris_lengkap')).count(),
            'diklarifikasi': Tiket.objects.filter(
                id__in=p3de_tiket_ids,
                penyampaian=Subquery(
                    Tiket.objects.filter(
                        id_periode_data=OuterRef('id_periode_data'),
                        periode=OuterRef('periode'),
                        tahun=OuterRef('tahun'),
                        id__in=p3de_tiket_ids,
                    ).values('id_periode_data', 'periode', 'tahun')
                    .annotate(max_penyampaian=Max('penyampaian'))
                    .values('max_penyampaian')[:1]
                )
            ).filter(~Q(id_status_penelitian=1) | Q(baris_cde__gt=0)).count(),
        }
        # Admin: Jenis Data ILAP without active P3DE PIC
        if is_admin_p3de:
            context['p3de_jenis_data_tanpa_pic_count'] = JenisDataILAP.objects.filter(
                ~Exists(PIC.objects.filter(
                    id_sub_jenis_data_ilap=OuterRef('pk'),
                    tipe=PIC.TipePIC.P3DE,
                    end_date__isnull=True
                ))
            ).count()
            context['p3de_tiket_periode_null_count'] = Tiket.objects.filter(
                tahun=2099
            ).count()
    if is_pide:
        context['tiket_summary_pide'] = get_tiket_summary_for_user_pide(request.user)
        pide_tiket_ids = TiketPIC.objects.filter(
            id_user=request.user, role=TiketPIC.Role.PIDE, active=True
        ).values_list('id_tiket', flat=True)

        context['pide_category_counts'] = {
            'belum_mulai_proses_identifikasi': Tiket.objects.filter(
                id__in=pide_tiket_ids, status_tiket=STATUS_DIKIRIM_KE_PIDE
            ).count(),
            'dalam_proses_identifikasi': Tiket.objects.filter(
                id__in=pide_tiket_ids, status_tiket=STATUS_IDENTIFIKASI
            ).count(),
        }
        # Admin: Jenis Data ILAP without active PIDE PIC
        if is_admin_pide:
            context['pide_jenis_data_tanpa_pic_count'] = JenisDataILAP.objects.filter(
                ~Exists(PIC.objects.filter(
                    id_sub_jenis_data_ilap=OuterRef('pk'),
                    tipe=PIC.TipePIC.PIDE,
                    end_date__isnull=True
                ))
            ).count()
    if is_pmde:
        context['tiket_summary_pmde'] = get_tiket_summary_for_user_pmde(request.user)
        pmde_tiket_ids = TiketPIC.objects.filter(
            id_user=request.user, role=TiketPIC.Role.PMDE, active=True
        ).values_list('id_tiket', flat=True)

        context['pmde_category_counts'] = {
            'dalam_proses_pengendalian_mutu': Tiket.objects.filter(
                id__in=pmde_tiket_ids, status_tiket=STATUS_PENGENDALIAN_MUTU
            ).count(),
        }
        # Admin: Jenis Data ILAP without active PMDE PIC
        if is_admin_pmde:
            context['pmde_jenis_data_tanpa_pic_count'] = JenisDataILAP.objects.filter(
                ~Exists(PIC.objects.filter(
                    id_sub_jenis_data_ilap=OuterRef('pk'),
                    tipe=PIC.TipePIC.PMDE,
                    end_date__isnull=True
                ))
            ).count()
    if settings.DEBUG:
        groups = Group.objects.filter(name__in=['user_p3de', 'user_pide', 'user_pmde']).prefetch_related('user_set')
        debug_groups = {}
        for group in groups:
            users = group.user_set.all().order_by('username')
            debug_groups[group.name] = [
                {
                    'username': user.username,
                    'full_name': user.get_full_name() or '-'
                }
                for user in users
            ]
        context['debug_user_groups'] = debug_groups
    return render(request, 'home.html', context)


def _get_p3de_tiket_ids(user):
    """Get the set of tiket IDs for which the user is an active P3DE PIC."""
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.P3DE, active=True
    ).values_list('id_tiket', flat=True)


def _get_pide_tiket_ids(user):
    """Get the set of tiket IDs for which the user is an active PIDE PIC."""
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.PIDE, active=True
    ).values_list('id_tiket', flat=True)


def _get_pmde_tiket_ids(user):
    """Get the set of tiket IDs for which the user is an active PMDE PIC."""
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.PMDE, active=True
    ).values_list('id_tiket', flat=True)


def _build_tiket_base_qs(category, user):
    """Build the base Tiket queryset for a given category and user.

    Returns a queryset, or None if the user is not authorized for the category.
    """
    tiket_qs = Tiket.objects.select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap',
        'id_bentuk_data',
        'id_cara_penyampaian',
        'id_status_penelitian',
    )

    # Admin category: periode_tiket_null_p3de - no user-specific PIC filter
    if category == 'periode_tiket_null_p3de':
        if not user.groups.filter(name='admin_p3de').exists():
            return None
        return tiket_qs.filter(tahun=2099)

    # Map each category to (ids_func, extra_filter)
    category_map = {
        # P3DE categories
        'belum_rekam_backup_data': (
            _get_p3de_tiket_ids,
            Q(status_tiket=STATUS_DIREKAM, backup=False)
        ),
        'belum_dibuat_tanda_terima': (
            _get_p3de_tiket_ids,
            Q(status_tiket=STATUS_DIREKAM, tanda_terima=False)
        ),
        'belum_diteliti': (
            _get_p3de_tiket_ids,
            Q(status_tiket=STATUS_DIREKAM, backup=True, tanda_terima=True)
        ),
        'belum_dikirim_ke_pide': (
            _get_p3de_tiket_ids,
            Q(status_tiket=STATUS_DITELITI, baris_lengkap__gt=0)
        ),
        'pengembalian_seluruhnya_dari_pide': (
            _get_p3de_tiket_ids,
            Exists(TiketAction.objects.filter(
                id_tiket=OuterRef('pk'),
                action=TiketActionType.DIKEMBALIKAN
            ))
        ),
        'pengembalian_sebagian_dari_pide': (
            _get_p3de_tiket_ids,
            Q(baris_cde__gt=0) & ~Q(baris_cde=F('baris_lengkap'))
        ),
        'diklarifikasi': (
            _get_p3de_tiket_ids,
            Q(
                penyampaian=Subquery(
                    Tiket.objects.filter(
                        id_periode_data=OuterRef('id_periode_data'),
                        periode=OuterRef('periode'),
                        tahun=OuterRef('tahun'),
                        id__in=_get_p3de_tiket_ids(user),
                    ).values('id_periode_data', 'periode', 'tahun')
                    .annotate(max_penyampaian=Max('penyampaian'))
                    .values('max_penyampaian')[:1]
                )
            ) & (~Q(id_status_penelitian=1) | Q(baris_cde__gt=0))
        ),
        # PIDE categories
        'belum_mulai_proses_identifikasi': (
            _get_pide_tiket_ids,
            Q(status_tiket=STATUS_DIKIRIM_KE_PIDE)
        ),
        'dalam_proses_identifikasi': (
            _get_pide_tiket_ids,
            Q(status_tiket=STATUS_IDENTIFIKASI)
        ),
        # PMDE categories
        'dalam_proses_pengendalian_mutu': (
            _get_pmde_tiket_ids,
            Q(status_tiket=STATUS_PENGENDALIAN_MUTU)
        ),
    }

    entry = category_map.get(category)
    if entry is None:
        return None

    ids_func, extra_filter = entry
    tiket_ids = ids_func(user)
    tiket_qs = tiket_qs.filter(id__in=tiket_ids).filter(extra_filter)

    return tiket_qs


def _build_jenis_data_tanpa_pic_qs(category, user):
    """Build the base JenisDataILAP queryset for admin 'jenis_data_tanpa_pic' views."""
    if category == 'jenis_data_tanpa_pic_p3de':
        if not user.groups.filter(name='admin_p3de').exists():
            return None
        pic_type = PIC.TipePIC.P3DE
    elif category == 'jenis_data_tanpa_pic_pide':
        if not user.groups.filter(name='admin_pide').exists():
            return None
        pic_type = PIC.TipePIC.PIDE
    elif category == 'jenis_data_tanpa_pic_pmde':
        if not user.groups.filter(name='admin_pmde').exists():
            return None
        pic_type = PIC.TipePIC.PMDE
    else:
        return None

    return JenisDataILAP.objects.filter(
        ~Exists(PIC.objects.filter(
            id_sub_jenis_data_ilap=OuterRef('pk'),
            tipe=pic_type,
            end_date__isnull=True
        ))
    ).select_related('id_ilap')


@login_required
@require_GET
def home_data(request):
    """Server-side DataTables endpoint for home page tiket categories.

    GET Parameters:
    - draw: DataTables draw counter
    - start, length: paging offset and page size
    - category: the category key (e.g. 'belum_rekam_backup_data')
    - search[value]: global search term
    - order[0][column], order[0][dir]: ordering

    Returns JSON with draw, recordsTotal, recordsFiltered, data.
    """
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))
    category = request.GET.get('category', '')
    search_value = request.GET.get('search[value]', '')

    # Determine if this is a tiket-based category or a jenis_data_tanpa_pic category
    tiket_categories = {
        'belum_rekam_backup_data', 'belum_dibuat_tanda_terima', 'belum_diteliti',
        'belum_dikirim_ke_pide', 'pengembalian_seluruhnya_dari_pide',
        'pengembalian_sebagian_dari_pide', 'diklarifikasi',
        'belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi',
        'dalam_proses_pengendalian_mutu', 'periode_tiket_null_p3de',
    }
    jenis_data_categories = {
        'jenis_data_tanpa_pic_p3de', 'jenis_data_tanpa_pic_pide', 'jenis_data_tanpa_pic_pmde',
    }

    is_tiket_category = category in tiket_categories
    is_jenis_data_category = category in jenis_data_categories

    if is_tiket_category:
        qs = _build_tiket_base_qs(category, request.user)
    elif is_jenis_data_category:
        qs = _build_jenis_data_tanpa_pic_qs(category, request.user)
    else:
        return JsonResponse({'error': 'Invalid category'}, status=400)

    if qs is None:
        return JsonResponse({'error': 'Access denied or invalid category'}, status=403)

    records_total = qs.count()

    # Global search for tiket categories
    if search_value and is_tiket_category:
        qs = qs.filter(
            Q(nomor_tiket__icontains=search_value) |
            Q(id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap__icontains=search_value) |
            Q(id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data__icontains=search_value)
        )

    # Global search for jenis_data categories
    if search_value and is_jenis_data_category:
        qs = qs.filter(
            Q(id_sub_jenis_data__icontains=search_value) |
            Q(id_ilap__nama_ilap__icontains=search_value) |
            Q(nama_jenis_data__icontains=search_value) |
            Q(nama_sub_jenis_data__icontains=search_value)
        )

    records_filtered = qs.count()

    # Ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')

    if is_tiket_category:
        columns = ['nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'tgl_terima_dip']
        if category in ('belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi'):
            columns = ['nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'tgl_kirim_pide']
        elif category == 'dalam_proses_pengendalian_mutu':
            columns = ['nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'tgl_transfer']
        elif category == 'periode_tiket_null_p3de':
            columns = ['nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode', 'tahun', 'status_tiket']

        if order_col_index is not None:
            try:
                idx = int(order_col_index)
                col = columns[idx] if idx < len(columns) else 'nomor_tiket'
                if col == 'nama_ilap':
                    col = 'id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap'
                elif col == 'nama_sub_jenis_data':
                    col = 'id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data'
                elif col == 'tgl_terima_dip':
                    col = 'tgl_terima_dip'
                elif col == 'tgl_kirim_pide':
                    col = 'tgl_kirim_pide'
                elif col == 'tgl_transfer':
                    col = 'tgl_transfer'
                if order_dir == 'desc':
                    col = '-' + col
                qs = qs.order_by(col)
            except Exception:
                qs = qs.order_by('-id')
        else:
            qs = qs.order_by('-id')
    elif is_jenis_data_category:
        columns = ['id_sub_jenis_data', 'nama_ilap', 'nama_jenis_data', 'nama_sub_jenis_data']
        if order_col_index is not None:
            try:
                idx = int(order_col_index)
                col = columns[idx] if idx < len(columns) else 'id_sub_jenis_data'
                if col == 'nama_ilap':
                    col = 'id_ilap__nama_ilap'
                if order_dir == 'desc':
                    col = '-' + col
                qs = qs.order_by(col)
            except Exception:
                qs = qs.order_by('id_sub_jenis_data')
        else:
            qs = qs.order_by('id_sub_jenis_data')

    qs_page = qs[start:start + length]

    # Build data rows
    data = []
    for obj in qs_page:
        if is_tiket_category:
            nama_ilap = obj.id_periode_data.id_sub_jenis_data_ilap.id_ilap.nama_ilap
            nama_sub_jenis = obj.id_periode_data.id_sub_jenis_data_ilap.nama_sub_jenis_data
            view_url = reverse('tiket_detail', args=[obj.id])
            action_html = f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat"><i class="feather-eye"></i></a>'

            if category in ('belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi'):
                date_val = obj.tgl_kirim_pide.strftime('%d-%m-%Y') if obj.tgl_kirim_pide else ''
                date_order = obj.tgl_kirim_pide.strftime('%Y-%m-%d') if obj.tgl_kirim_pide else ''
            elif category == 'dalam_proses_pengendalian_mutu':
                date_val = obj.tgl_transfer.strftime('%d-%m-%Y') if obj.tgl_transfer else ''
                date_order = obj.tgl_transfer.strftime('%Y-%m-%d') if obj.tgl_transfer else ''
            else:
                date_val = obj.tgl_terima_dip.strftime('%d-%m-%Y') if obj.tgl_terima_dip else ''
                date_order = obj.tgl_terima_dip.strftime('%Y-%m-%d') if obj.tgl_terima_dip else ''

            if category == 'periode_tiket_null_p3de':
                data.append({
                    'nomor_tiket': obj.nomor_tiket,
                    'nama_ilap': nama_ilap,
                    'nama_sub_jenis_data': nama_sub_jenis,
                    'periode': obj.periode,
                    'tahun': obj.tahun,
                    'status_tiket': STATUS_LABELS.get(obj.status_tiket, ''),
                    'actions': action_html,
                })
            else:
                data.append({
                    'nomor_tiket': obj.nomor_tiket,
                    'nama_ilap': nama_ilap,
                    'nama_sub_jenis_data': nama_sub_jenis,
                    'tanggal': date_val,
                    'tanggal_order': date_order,
                    'actions': action_html,
                })
        elif is_jenis_data_category:
            data.append({
                'id_sub_jenis_data': obj.id_sub_jenis_data,
                'nama_ilap': obj.id_ilap.nama_ilap,
                'nama_jenis_data': obj.nama_jenis_data,
                'nama_sub_jenis_data': obj.nama_sub_jenis_data,
            })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })