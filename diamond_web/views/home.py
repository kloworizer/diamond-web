from django.shortcuts import render
from django.conf import settings
from django.db.models import F, Q, Exists, OuterRef, Max, Subquery
from django.contrib.auth.models import Group
from django.contrib.auth.decorators import login_required
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
    # compute task summary based on user role
    if is_p3de:
        context['tiket_summary'] = get_tiket_summary_for_user_p3de(request.user)
        # Get tikets for P3DE user with specific categories
        p3de_pic = TiketPIC.objects.filter(id_user=request.user, role=TiketPIC.Role.P3DE, active=True)
        tiket_ids = p3de_pic.values_list('id_tiket', flat=True)
        
        # Get tikets for each category
        context['p3de_tiket_categories'] = {
            'belum_rekam_backup_data': Tiket.objects.filter(
                id__in=tiket_ids, 
                status_tiket=STATUS_DIREKAM, 
                backup=False
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'belum_dibuat_tanda_terima': Tiket.objects.filter(
                id__in=tiket_ids, 
                status_tiket=STATUS_DIREKAM, 
                tanda_terima=False
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'belum_diteliti': Tiket.objects.filter(
                id__in=tiket_ids, 
                status_tiket=STATUS_DIREKAM, 
                backup=True, 
                tanda_terima=True
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'belum_dikirim_ke_pide': Tiket.objects.filter(
                id__in=tiket_ids, 
                status_tiket=STATUS_DITELITI,
                baris_lengkap__gt=0
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'pengembalian_seluruhnya_dari_pide': Tiket.objects.filter(
                id__in=tiket_ids
            ).filter(
                Exists(TiketAction.objects.filter(
                    id_tiket=OuterRef('pk'),
                    action=TiketActionType.DIKEMBALIKAN
                ))
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'pengembalian_sebagian_dari_pide': Tiket.objects.filter(
                id__in=tiket_ids,
                baris_cde__gt=0
            ).exclude(
                baris_cde=F('baris_lengkap')
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'diklarifikasi': Tiket.objects.filter(
                id__in=tiket_ids,
                penyampaian=Subquery(
                    Tiket.objects.filter(
                        id_periode_data=OuterRef('id_periode_data'),
                        periode=OuterRef('periode'),
                        tahun=OuterRef('tahun'),
                        id__in=tiket_ids,
                    ).values('id_periode_data', 'periode', 'tahun')
                    .annotate(max_penyampaian=Max('penyampaian'))
                    .values('max_penyampaian')[:1]
                )
            ).filter(
                ~Q(id_status_penelitian=1) | Q(baris_cde__gt=0)
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian',
                'id_status_penelitian'
            ).order_by('-id'),
        }
        # Admin: Jenis Data ILAP without active P3DE PIC
        if is_admin_p3de:
            context['p3de_jenis_data_tanpa_pic'] = JenisDataILAP.objects.filter(
                ~Exists(PIC.objects.filter(
                    id_sub_jenis_data_ilap=OuterRef('pk'),
                    tipe=PIC.TipePIC.P3DE,
                    end_date__isnull=True
                ))
            ).select_related('id_ilap').order_by('id_sub_jenis_data')
            # Admin: Tiket with Tahun=2099 (null periode/tahun data from migration)
            context['p3de_tiket_periode_null'] = Tiket.objects.filter(
                tahun=2099
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id')
    if is_pide:
        context['tiket_summary_pide'] = get_tiket_summary_for_user_pide(request.user)
        pide_pic = TiketPIC.objects.filter(id_user=request.user, role=TiketPIC.Role.PIDE, active=True)
        pide_tiket_ids = pide_pic.values_list('id_tiket', flat=True)

        context['pide_tiket_categories'] = {
            'belum_mulai_proses_identifikasi': Tiket.objects.filter(
                id__in=pide_tiket_ids,
                status_tiket=STATUS_DIKIRIM_KE_PIDE
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
            'dalam_proses_identifikasi': Tiket.objects.filter(
                id__in=pide_tiket_ids,
                status_tiket=STATUS_IDENTIFIKASI
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
        }
        # Admin: Jenis Data ILAP without active PIDE PIC
        if is_admin_pide:
            context['pide_jenis_data_tanpa_pic'] = JenisDataILAP.objects.filter(
            ~Exists(PIC.objects.filter(
                id_sub_jenis_data_ilap=OuterRef('pk'),
                tipe=PIC.TipePIC.PIDE,
                end_date__isnull=True
            ))
        ).select_related('id_ilap').order_by('id_sub_jenis_data')
    if is_pmde:
        context['tiket_summary_pmde'] = get_tiket_summary_for_user_pmde(request.user)
        pmde_pic = TiketPIC.objects.filter(id_user=request.user, role=TiketPIC.Role.PMDE, active=True)
        pmde_tiket_ids = pmde_pic.values_list('id_tiket', flat=True)

        context['pmde_tiket_categories'] = {
            'dalam_proses_pengendalian_mutu': Tiket.objects.filter(
                id__in=pmde_tiket_ids,
                status_tiket=STATUS_PENGENDALIAN_MUTU
            ).select_related(
                'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
                'id_periode_data__id_sub_jenis_data_ilap',
                'id_bentuk_data',
                'id_cara_penyampaian'
            ).order_by('-id'),
        }
        # Admin: Jenis Data ILAP without active PMDE PIC
        if is_admin_pmde:
            context['pmde_jenis_data_tanpa_pic'] = JenisDataILAP.objects.filter(
            ~Exists(PIC.objects.filter(
                id_sub_jenis_data_ilap=OuterRef('pk'),
                tipe=PIC.TipePIC.PMDE,
                end_date__isnull=True
            ))
        ).select_related('id_ilap').order_by('id_sub_jenis_data')
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