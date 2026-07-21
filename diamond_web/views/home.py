from django.shortcuts import render
from django.conf import settings
from django.db.models import F, Q, Exists, OuterRef, Max, Subquery, Value
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Concat
from django.contrib.auth.models import Group, User
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

def _get_category_metrics(qs):
    if qs is None:
        return {'tickets': 0, 'ilaps': 0, 'jenis_datas': 0}
    tickets = qs.count()
    ilaps = qs.values('id_periode_data__id_sub_jenis_data_ilap__id_ilap').distinct().count() if tickets > 0 else 0
    jenis_datas = qs.values('id_periode_data__id_sub_jenis_data_ilap').distinct().count() if tickets > 0 else 0
    return {
        'tickets': tickets,
        'ilaps': ilaps,
        'jenis_datas': jenis_datas,
    }

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

        p3de_qs = Tiket.objects.filter(id__in=p3de_tiket_ids)

        belum_rekam_backup_data_qs = p3de_qs.filter(status_tiket=STATUS_DIREKAM, backup=False)
        belum_dibuat_tanda_terima_qs = p3de_qs.filter(status_tiket=STATUS_DIREKAM, tanda_terima=False)
        belum_diteliti_qs = p3de_qs.filter(status_tiket=STATUS_DIREKAM, backup=True, tanda_terima=True)
        belum_dikirim_ke_pide_qs = p3de_qs.filter(status_tiket=STATUS_DITELITI, baris_lengkap__gt=0)
        pengembalian_seluruhnya_dari_pide_qs = p3de_qs.filter(
            Exists(TiketAction.objects.filter(
                id_tiket=OuterRef('pk'),
                action=TiketActionType.DIKEMBALIKAN
            ))
        )
        pengembalian_sebagian_dari_pide_qs = p3de_qs.filter(baris_cde__gt=0).exclude(baris_cde=F('baris_lengkap'))
        
        diklarifikasi_qs = p3de_qs.filter(
            penyampaian=Subquery(
                Tiket.objects.filter(
                    id_periode_data=OuterRef('id_periode_data'),
                    periode=OuterRef('periode'),
                    tahun=OuterRef('tahun'),
                    id__in=p3de_tiket_ids,
                ).values('id_periode_data', 'periode', 'tahun')
                .annotate(max_penyampaian=Max('penyampaian'))
                .values('max_penyampaian')[:1]
            ),
            status_tiket__gt=STATUS_DITELITI
        ).filter(~Q(id_status_penelitian=1) | Q(baris_cde__gt=0))

        context['p3de_category_metrics'] = {
            'belum_rekam_backup_data': _get_category_metrics(belum_rekam_backup_data_qs),
            'belum_dibuat_tanda_terima': _get_category_metrics(belum_dibuat_tanda_terima_qs),
            'belum_diteliti': _get_category_metrics(belum_diteliti_qs),
            'belum_dikirim_ke_pide': _get_category_metrics(belum_dikirim_ke_pide_qs),
            'pengembalian_seluruhnya_dari_pide': _get_category_metrics(pengembalian_seluruhnya_dari_pide_qs),
            'pengembalian_sebagian_dari_pide': _get_category_metrics(pengembalian_sebagian_dari_pide_qs),
            'diklarifikasi': _get_category_metrics(diklarifikasi_qs),
        }

        context['p3de_category_counts'] = {
            k: v['tickets'] for k, v in context['p3de_category_metrics'].items()
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

        pide_qs = Tiket.objects.filter(id__in=pide_tiket_ids)
        belum_mulai_proses_identifikasi_qs = pide_qs.filter(status_tiket=STATUS_DIKIRIM_KE_PIDE)
        dalam_proses_identifikasi_qs = pide_qs.filter(status_tiket=STATUS_IDENTIFIKASI)

        context['pide_category_metrics'] = {
            'belum_mulai_proses_identifikasi': _get_category_metrics(belum_mulai_proses_identifikasi_qs),
            'dalam_proses_identifikasi': _get_category_metrics(dalam_proses_identifikasi_qs),
        }

        context['pide_category_counts'] = {
            k: v['tickets'] for k, v in context['pide_category_metrics'].items()
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
            # Admin: Tickets in Dikirim ke PIDE status without an active PIDE PIC
            context['pide_tiket_dikirim_ke_pide_tanpa_pic_count'] = Tiket.objects.filter(
                status_tiket=STATUS_DIKIRIM_KE_PIDE
            ).filter(
                ~Exists(TiketPIC.objects.filter(
                    id_tiket=OuterRef('pk'),
                    role=TiketPIC.Role.PIDE,
                    active=True
                ))
            ).count()
    if is_pmde:
        context['tiket_summary_pmde'] = get_tiket_summary_for_user_pmde(request.user)
        pmde_tiket_ids = TiketPIC.objects.filter(
            id_user=request.user, role=TiketPIC.Role.PMDE, active=True
        ).values_list('id_tiket', flat=True)

        pmde_qs = Tiket.objects.filter(id__in=pmde_tiket_ids)
        dalam_proses_pengendalian_mutu_qs = pmde_qs.filter(status_tiket=STATUS_PENGENDALIAN_MUTU)

        context['pmde_category_metrics'] = {
            'dalam_proses_pengendalian_mutu': _get_category_metrics(dalam_proses_pengendalian_mutu_qs),
        }

        context['pmde_category_counts'] = {
            k: v['tickets'] for k, v in context['pmde_category_metrics'].items()
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
            # Admin: Tickets in Pengendalian Mutu status without an active PMDE PIC
            context['pmde_tiket_pengendalian_mutu_tanpa_pic_count'] = Tiket.objects.filter(
                status_tiket=STATUS_PENGENDALIAN_MUTU
            ).filter(
                ~Exists(TiketPIC.objects.filter(
                    id_tiket=OuterRef('pk'),
                    role=TiketPIC.Role.PMDE,
                    active=True
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

    # Admin category: tickets in Pengendalian Mutu status without an active PMDE PIC
    if category == 'tiket_pengendalian_mutu_tanpa_pic':
        if not user.groups.filter(name='admin_pmde').exists():
            return None
        return tiket_qs.filter(
            status_tiket=STATUS_PENGENDALIAN_MUTU
        ).filter(
            ~Exists(TiketPIC.objects.filter(
                id_tiket=OuterRef('pk'),
                role=TiketPIC.Role.PMDE,
                active=True
            ))
        )

    # Admin category: tickets in Dikirim ke PIDE status without an active PIDE PIC
    if category == 'tiket_dikirim_ke_pide_tanpa_pic':
        if not user.groups.filter(name='admin_pide').exists():
            return None
        return tiket_qs.filter(
            status_tiket=STATUS_DIKIRIM_KE_PIDE
        ).filter(
            ~Exists(TiketPIC.objects.filter(
                id_tiket=OuterRef('pk'),
                role=TiketPIC.Role.PIDE,
                active=True
            ))
        )

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
            ) & (~Q(id_status_penelitian=1) | Q(baris_cde__gt=0)) & Q(status_tiket__gt=STATUS_DITELITI)
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
        'tiket_pengendalian_mutu_tanpa_pic',
        'tiket_dikirim_ke_pide_tanpa_pic',
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

    # Calculate summary metrics (Total Tiket, Jumlah ILAP, Jenis Data) on base category QS
    total_tiket = records_total
    total_ilap = 0
    total_jenis_data = 0
    
    # Age group breakdown summary
    critical_count = 0
    warning_count = 0
    new_count = 0
    
    ilap_list = []
    jenis_data_list = []

    if is_tiket_category:
        total_ilap = qs.values('id_periode_data__id_sub_jenis_data_ilap__id_ilap').distinct().count()
        total_jenis_data = qs.values('id_periode_data__id_sub_jenis_data_ilap__id_jenis_data').distinct().count()
        
        # Get actual distinct names
        ilap_list = list(qs.values_list('id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap', flat=True).distinct())
        jenis_data_list = list(qs.values_list('id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data', flat=True).distinct())
                # Determine the correct date field for age tracking
        is_pide_category = category in ('belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi', 'tiket_dikirim_ke_pide_tanpa_pic')
        is_pmde_category = category in ('dalam_proses_pengendalian_mutu', 'tiket_pengendalian_mutu_tanpa_pic')

        if is_pide_category:
            date_field = 'tgl_kirim_pide'
        elif is_pmde_category:
            date_field = 'tgl_transfer'
        else:
            date_field = 'tgl_terima_dip'
            
        now = timezone.now()
        if is_pide_category:
            # PIDE SLA: 45 working days = 9 weeks = 63 calendar days
            cutoff_critical = now - timedelta(days=63)
            critical_count = qs.filter(**{f"{date_field}__lt": cutoff_critical}).count()
            warning_count = 0
            new_count = qs.filter(**{f"{date_field}__gte": cutoff_critical}).count()
            
            # Apply age_group filter
            age_group = request.GET.get('age_group')
            if age_group == 'critical':
                qs = qs.filter(**{f"{date_field}__lt": cutoff_critical})
            elif age_group == 'new':
                qs = qs.filter(**{f"{date_field}__gte": cutoff_critical})
        elif is_pmde_category:
            # PMDE SLA: 90 calendar days
            cutoff_critical = now - timedelta(days=90)
            critical_count = qs.filter(**{f"{date_field}__lt": cutoff_critical}).count()
            warning_count = 0
            new_count = qs.filter(**{f"{date_field}__gte": cutoff_critical}).count()
            
            # Apply age_group filter
            age_group = request.GET.get('age_group')
            if age_group == 'critical':
                qs = qs.filter(**{f"{date_field}__lt": cutoff_critical})
            elif age_group == 'new':
                qs = qs.filter(**{f"{date_field}__gte": cutoff_critical})
        else:
            # Default P3DE limits (critical: >7 days, warning: 3-7 days, new: <3 days)
            cutoff_critical = now - timedelta(days=7)
            cutoff_warning = now - timedelta(days=3)
            
            critical_count = qs.filter(**{f"{date_field}__lt": cutoff_critical}).count()
            warning_count = qs.filter(**{f"{date_field}__range": (cutoff_critical, cutoff_warning)}).count()
            new_count = qs.filter(**{f"{date_field}__gte": cutoff_warning}).count()
            
            # Apply age_group filter
            age_group = request.GET.get('age_group')
            if age_group == 'critical':
                qs = qs.filter(**{f"{date_field}__lt": cutoff_critical})
            elif age_group == 'warning':
                qs = qs.filter(**{f"{date_field}__range": (cutoff_critical, cutoff_warning)})
            elif age_group == 'new':
                qs = qs.filter(**{f"{date_field}__gte": cutoff_warning})

    elif is_jenis_data_category:
        total_ilap = qs.values('id_ilap').distinct().count()
        total_jenis_data = records_total
        
        ilap_list = list(qs.values_list('id_ilap__nama_ilap', flat=True).distinct())
        jenis_data_list = list(qs.values_list('nama_sub_jenis_data', flat=True).distinct())

    ilap_list = sorted(list(set(n for n in ilap_list if n)))
    jenis_data_list = sorted(list(set(n for n in jenis_data_list if n)))

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
        if category in ('belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi', 'tiket_dikirim_ke_pide_tanpa_pic'):
            columns = ['nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'tgl_kirim_pide']
        elif category in ('dalam_proses_pengendalian_mutu', 'tiket_pengendalian_mutu_tanpa_pic'):
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
            nama_tabel_I = obj.id_periode_data.id_sub_jenis_data_ilap.nama_tabel_I or '-'
            view_url = reverse('tiket_detail', args=[obj.id])
            # Build action HTML — add quick-assign button for admin tiket_dikirim_ke_pide_tanpa_pic
            if category == 'tiket_dikirim_ke_pide_tan_pic' or category == 'tiket_dikirim_ke_pide_tanpa_pic':
                sub_jenis_id = obj.id_periode_data.id_sub_jenis_data_ilap_id
                sub_jenis_kode = obj.id_periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data
                sub_jenis_nama_esc = nama_sub_jenis.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat">'
                    f'<i class="feather-eye"></i></a> '
                    f'<button type="button" class="btn btn-sm btn-success btn-quick-assign-pide" '
                    f'data-subjenis-id="{sub_jenis_id}" '
                    f'data-subjenis-kode="{sub_jenis_kode}" '
                    f'data-subjenis-nama="{sub_jenis_nama_esc}" '
                    f'data-ilap="{nama_ilap_esc}" '
                    f'title="Assign PIC PIDE">'
                    f'<i class="feather-user-plus"></i></button>'
                    f'</div>'
                )
            elif category == 'tiket_pengendalian_mutu_tanpa_pic' or category == 'tiket_pengendalian_mutu_tan_pic':
                sub_jenis_id = obj.id_periode_data.id_sub_jenis_data_ilap_id
                sub_jenis_kode = obj.id_periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data
                sub_jenis_nama_esc = nama_sub_jenis.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat">'
                    f'<i class="feather-eye"></i></a> '
                    f'<button type="button" class="btn btn-sm btn-success btn-quick-assign-pmde" '
                    f'data-subjenis-id="{sub_jenis_id}" '
                    f'data-subjenis-kode="{sub_jenis_kode}" '
                    f'data-subjenis-nama="{sub_jenis_nama_esc}" '
                    f'data-ilap="{nama_ilap_esc}" '
                    f'title="Assign PIC PMDE">'
                    f'<i class="feather-user-plus"></i></button>'
                    f'</div>'
                )
            else:
                action_html = f'<div class="d-flex justify-content-center gap-1"><a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat"><i class="feather-eye"></i></a></div>'

            if category in ('belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi', 'tiket_dikirim_ke_pide_tanpa_pic'):
                date_val = obj.tgl_kirim_pide.strftime('%d-%m-%Y') if obj.tgl_kirim_pide else ''
                date_order = obj.tgl_kirim_pide.strftime('%Y-%m-%d') if obj.tgl_kirim_pide else ''
            elif category in ('dalam_proses_pengendalian_mutu', 'tiket_pengendalian_mutu_tanpa_pic'):
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
                    'nama_tabel_I': nama_tabel_I,
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
                    'nama_tabel_I': nama_tabel_I,
                    'tanggal': date_val,
                    'tanggal_order': date_order,
                    'actions': action_html,
                })
        elif is_jenis_data_category:
            action_html = ''
            if category == 'jenis_data_tanpa_pic_p3de':
                sub_jenis_id = obj.pk
                sub_jenis_kode = obj.id_sub_jenis_data
                sub_jenis_nama_esc = obj.nama_sub_jenis_data.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = obj.id_ilap.nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-success btn-quick-assign-p3de" '
                    f'data-subjenis-id="{sub_jenis_id}" '
                    f'data-subjenis-kode="{sub_jenis_kode}" '
                    f'data-subjenis-nama="{sub_jenis_nama_esc}" '
                    f'data-ilap="{nama_ilap_esc}" '
                    f'title="Assign PIC P3DE">'
                    f'<i class="feather-user-plus"></i></button>'
                    f'</div>'
                )
            elif category == 'jenis_data_tanpa_pic_pide':
                sub_jenis_id = obj.pk
                sub_jenis_kode = obj.id_sub_jenis_data
                sub_jenis_nama_esc = obj.nama_sub_jenis_data.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = obj.id_ilap.nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-success btn-quick-assign-pide" '
                    f'data-subjenis-id="{sub_jenis_id}" '
                    f'data-subjenis-kode="{sub_jenis_kode}" '
                    f'data-subjenis-nama="{sub_jenis_nama_esc}" '
                    f'data-ilap="{nama_ilap_esc}" '
                    f'title="Assign PIC PIDE">'
                    f'<i class="feather-user-plus"></i></button>'
                    f'</div>'
                )
            elif category == 'jenis_data_tanpa_pic_pmde':
                sub_jenis_id = obj.pk
                sub_jenis_kode = obj.id_sub_jenis_data
                sub_jenis_nama_esc = obj.nama_sub_jenis_data.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = obj.id_ilap.nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-success btn-quick-assign-pmde" '
                    f'data-subjenis-id="{sub_jenis_id}" '
                    f'data-subjenis-kode="{sub_jenis_kode}" '
                    f'data-subjenis-nama="{sub_jenis_nama_esc}" '
                    f'data-ilap="{nama_ilap_esc}" '
                    f'title="Assign PIC PMDE">'
                    f'<i class="feather-user-plus"></i></button>'
                    f'</div>'
                )

            data.append({
                'id_sub_jenis_data': obj.id_sub_jenis_data,
                'nama_ilap': obj.id_ilap.nama_ilap,
                'nama_jenis_data': obj.nama_jenis_data,
                'nama_sub_jenis_data': obj.nama_sub_jenis_data,
                'nama_tabel_I': obj.nama_tabel_I or '-',
                'actions': action_html,
            })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
        'summary': {
            'total_tiket': total_tiket,
            'total_ilap': total_ilap,
            'total_jenis_data': total_jenis_data,
            'ilap_list': ilap_list,
            'jenis_data_list': jenis_data_list,
            'critical_count': critical_count,
            'warning_count': warning_count,
            'new_count': new_count,
        }
    })


@login_required
@require_GET
def home_pic_pide_users(request):
    """Return JSON list of user_pide members for the quick-assign PIC PIDE modal.

    Only accessible to admin_pide group members.
    """
    if not request.user.groups.filter(name='admin_pide').exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    users = User.objects.filter(groups__name='user_pide').order_by('first_name', 'last_name')
    data = [
        {
            'id': u.id,
            'label': f"{u.first_name} {u.last_name} ({u.username})".strip() or u.username
        }
        for u in users
    ]
    return JsonResponse({'users': data})


@login_required
@require_GET
def home_pic_p3de_users(request):
    """Return JSON list of user_p3de members for the quick-assign PIC P3DE modal.

    Only accessible to admin_p3de group members.
    """
    if not request.user.groups.filter(name='admin_p3de').exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    users = User.objects.filter(groups__name='user_p3de').order_by('first_name', 'last_name')
    data = [
        {
            'id': u.id,
            'label': f"{u.first_name} {u.last_name} ({u.username})".strip() or u.username
        }
        for u in users
    ]
    return JsonResponse({'users': data})


@login_required
@require_GET
def home_pic_pmde_users(request):
    """Return JSON list of user_pmde members for the quick-assign PIC PMDE modal.

    Only accessible to admin_pmde group members.
    """
    if not request.user.groups.filter(name='admin_pmde').exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    users = User.objects.filter(groups__name='user_pmde').order_by('first_name', 'last_name')
    data = [
        {
            'id': u.id,
            'label': f"{u.first_name} {u.last_name} ({u.username})".strip() or u.username
        }
        for u in users
    ]
    return JsonResponse({'users': data})