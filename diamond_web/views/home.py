from django.shortcuts import render
from django.conf import settings
from django.db.models import (
    Count, F, Q, Exists, OuterRef, Max, Subquery, Value, Case, When, IntegerField,
)
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Concat, Coalesce, NullIf
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
from diamond_web.models.user_starred_tiket import UserStarredTiket
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.pic import PIC
from diamond_web.models.jenis_data_ilap import JenisDataILAP
from diamond_web.templatetags.auth_extras import format_periode_tiket
from diamond_web.constants.tiket_status import (
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUSES_SEBELUM_PENGENDALIAN_MUTU,
    STATUS_LABELS,
)
from diamond_web.constants.tiket_action_types import TiketActionType
from diamond_web.views.mixins import (
    is_kasi,
    is_kasi_p3de,
    is_kasi_pide,
    is_kasi_pmde,
    user_group_names,
)
from diamond_web.views.quality_control import jatuh_tempo_ids

# Filter buttons for the PMDE cards, keyed by the `data-urgency` value the
# button carries and the `count-<key>-<category>` span the template renders.

# Dalam Proses Pengendalian Mutu: days left until the deadline, the same
# thresholds the Quality Control page offers.
_JATUH_TEMPO_BUCKETS = {'lt10': 10, 'lt30': 30}

# Masih di P3DE & PIDE: which unit is still holding the tiket. P3DE records,
# researches and takes returns (1-3); PIDE receives and identifies (4-5).
_UNIT_BUCKETS = {
    'p3de': (STATUS_DIREKAM, STATUS_DITELITI, STATUS_DIKEMBALIKAN),
    'pide': (STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI),
}

# Join path from Tiket to the sub jenis data, and through it to the ILAP.
_SUB = 'id_periode_data__id_sub_jenis_data_ilap'

# Sortable columns per tiket category. DataTables sends the sorted column as a
# positional index, so each list must mirror -- index for index -- the column
# definitions getColumnsForCategory() hands the table in home.html. A column
# rendered on the page but missing here shifts every later index, which is how
# "Jml Baris Data Diterima" ended up sorting by nomor_tiket. Prioritas and Aksi
# are orderable:false and always sit last, so they need no entry.
_TIKET_ORDER_COLUMNS_DEFAULT = [
    'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data', 'tgl_terima_dip',
]

_TIKET_ORDER_COLUMNS = {
    'belum_rekam_backup_data': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'tgl_terima_dip',
    ],
    'belum_dibuat_tanda_terima': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'tgl_terima_dip',
    ],
    'belum_diteliti': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'tgl_terima_dip',
    ],
    'belum_dikirim_ke_pide': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'baris_lengkap', 'tgl_terima_dip',
    ],
    'pengembalian_seluruhnya_dari_pide': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'baris_lengkap', 'baris_tidak_lengkap', 'baris_cde',
        'tgl_terima_dip',
    ],
    'pengembalian_sebagian_dari_pide': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_diterima', 'baris_lengkap', 'baris_tidak_lengkap', 'baris_cde',
        'tgl_terima_dip',
    ],
    'belum_mulai_proses_identifikasi': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_lengkap', 'tgl_kirim_pide',
    ],
    'tiket_dikirim_ke_pide_tanpa_pic': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'tgl_kirim_pide',
    ],
    'dalam_proses_identifikasi': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_lengkap', 'baris_cde', 'tgl_rekam_pide',
    ],
    'dalam_proses_pengendalian_mutu': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'belum_qc', 'lolos_qc', 'tgl_transfer',
    ],
    'tiket_pengendalian_mutu_tanpa_pic': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'baris_i', 'jenis_tabel', 'tgl_transfer',
    ],
    'periode_tiket_null_p3de': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'status_tiket',
    ],
    'special_request': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'status_tiket', 'tgl_special_request',
    ],
    # Status earns a column here: it is the one category spanning more than one
    # unit, and which unit still holds a tiket is the point. jumlah_baris is
    # annotated onto the queryset in _build_tiket_base_qs, so it sorts directly
    # like any other column.
    'masih_di_p3de_pide': [
        'nomor_tiket', 'nama_ilap', 'nama_sub_jenis_data', 'periode_data',
        'jumlah_baris', 'status_tiket', 'tgl_terima_dip',
    ],
}

# Column name -> the ORM field(s) it orders by. Anything absent orders by a
# field of the same name on Tiket (or an annotation, for jumlah_baris).
_TIKET_ORDER_FIELDS = {
    'nama_ilap': (f'{_SUB}__id_ilap__nama_ilap',),
    'nama_sub_jenis_data': (f'{_SUB}__nama_sub_jenis_data',),
    'jenis_tabel': (f'{_SUB}__id_jenis_tabel__deskripsi',),
    # "Periode Data" displays as e.g. "Triwulan II 2026"; sorting that string
    # would order it alphabetically, so sort by the numbers behind it instead.
    'periode_data': ('tahun', 'periode'),
}

# Nullable baris/QC counters, which the table renders as 0. Ordering by the raw
# column would strand those rows at whichever end the backend puts NULLs (last
# on PostgreSQL, first on SQLite), so they sort on Coalesce(col, 0) instead and
# land where the 0 the user sees says they should.
_TIKET_ORDER_NULL_AS_ZERO = frozenset({
    'baris_lengkap', 'baris_tidak_lengkap', 'baris_i', 'baris_cde',
    'belum_qc', 'lolos_qc',
})


def _get_category_metrics(qs):
    """Count the tikets, distinct ILAPs and distinct jenis data of `qs`.

    All three are counted by the database in one pass. Counting the distinct
    values in Python instead means fetching one row per tiket over a four-table
    join, twice, to arrive at two integers.
    """
    if qs is None:
        return {'tickets': 0, 'ilaps': 0, 'jenis_datas': 0}
    row = qs.aggregate(
        tickets=Count('id', distinct=True),
        # NullIf keeps parity with the set comprehension this replaced, which
        # dropped every falsy value: 393 jenis_data_ilap rows carry an empty
        # nama_sub_jenis_data, and a bare Count would report them as one
        # distinct value rather than none.
        ilaps=Count(NullIf(f'{_SUB}__id_ilap__nama_ilap', Value('')), distinct=True),
        jenis_datas=Count(NullIf(f'{_SUB}__nama_sub_jenis_data', Value('')), distinct=True),
    )
    return {key: value or 0 for key, value in row.items()}

@login_required
def home(request):
    """Render the application home page.

    Context provided to template:
    - `is_p3de` (bool): whether the current authenticated user belongs to
      `user_p3de` or `kasi_p3de` group. Used to show P3DE-specific UI.
      `is_pide`/`is_pmde` work the same way for their units.
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
    # Read the user's groups once — every role flag below is answered from this
    # set rather than from a query of its own.
    groups = user_group_names(request.user)
    # expose user role membership for templates
    # Kasi supervise their unit, so they get the same home view as the unit's
    # users — but scoped to every tiket, not just their own.
    is_p3de = not groups.isdisjoint(['user_p3de', 'kasi_p3de'])
    is_pide = not groups.isdisjoint(['user_pide', 'kasi_pide'])
    is_pmde = not groups.isdisjoint(['user_pmde', 'kasi_pmde'])
    context['is_p3de'] = is_p3de
    context['is_pide'] = is_pide
    context['is_pmde'] = is_pmde
    context['is_kasi_p3de'] = is_kasi_p3de(request.user)
    context['is_kasi_pide'] = is_kasi_pide(request.user)
    context['is_kasi_pmde'] = is_kasi_pmde(request.user)
    # check admin group membership
    is_admin_p3de = 'admin_p3de' in groups
    is_admin_pide = 'admin_pide' in groups
    is_admin_pmde = 'admin_pmde' in groups
    context['is_admin_p3de'] = is_admin_p3de
    context['is_admin_pide'] = is_admin_pide
    context['is_admin_pmde'] = is_admin_pmde
    # compute task summary and category counts based on user role
    if is_p3de:
        context['tiket_summary'] = get_tiket_summary_for_user_p3de(request.user)
        p3de_tiket_ids = _get_p3de_tiket_ids(request.user)

        p3de_qs = _scoped(Tiket.objects.all(), p3de_tiket_ids)

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
                _scoped(
                    Tiket.objects.filter(
                        id_periode_data=OuterRef('id_periode_data'),
                        periode=OuterRef('periode'),
                        tahun=OuterRef('tahun'),
                    ),
                    p3de_tiket_ids,
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
        pide_tiket_ids = _get_pide_tiket_ids(request.user)

        pide_qs = _scoped(Tiket.objects.all(), pide_tiket_ids)
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
        pmde_tiket_ids = _get_pmde_tiket_ids(request.user)

        pmde_qs = _scoped(Tiket.objects.all(), pmde_tiket_ids)
        dalam_proses_pengendalian_mutu_qs = pmde_qs.filter(status_tiket=STATUS_PENGENDALIAN_MUTU)

        # Everything still upstream of PMDE, scoped the same way the card above
        # is: PMDE PICs are assigned when a tiket is recorded, not when it is
        # transferred (see rekam_tiket), so a pelaksana already has assignments
        # among these and sees the ones heading towards them. Kasi PMDE see the
        # whole seksi's queue, as everywhere else.
        masih_di_p3de_pide_qs = pmde_qs.filter(
            status_tiket__in=STATUSES_SEBELUM_PENGENDALIAN_MUTU
        )

        context['pmde_category_metrics'] = {
            'dalam_proses_pengendalian_mutu': _get_category_metrics(dalam_proses_pengendalian_mutu_qs),
            'masih_di_p3de_pide': _get_category_metrics(masih_di_p3de_pide_qs),
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
    # Special Request (Permintaan Khusus) — available to any user/kasi role.
    if is_p3de or is_pide or is_pmde:
        context['special_request_count'] = _scoped(
            Tiket.objects.filter(special_request=True),
            _get_special_request_tiket_ids(request.user),
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


def _scoped(qs, tiket_ids):
    """Narrow `qs` to `tiket_ids`, or leave it alone when there is no scope.

    The `_get_*_tiket_ids` helpers below return None for a supervisor, who sees
    every tiket. Filtering on "every id in the table" is not free — it compiles
    to `id IN (SELECT id FROM tiket)`, a subquery that removes no row but still
    has to be executed to prove it.
    """
    return qs if tiket_ids is None else qs.filter(id__in=tiket_ids)


def _get_p3de_tiket_ids(user):
    """Get the set of tiket IDs in the user's P3DE scope.

    Kasi P3DE supervise the whole unit, so they are unscoped and get None;
    other users get only the tikets for which they are an active P3DE PIC.
    """
    if is_kasi_p3de(user):
        return None
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.P3DE, active=True
    ).values_list('id_tiket', flat=True)


def _get_pide_tiket_ids(user):
    """Get the set of tiket IDs in the user's PIDE scope.

    Kasi PIDE supervise the whole unit, so they are unscoped and get None;
    other users get only the tikets for which they are an active PIDE PIC.
    """
    if is_kasi_pide(user):
        return None
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.PIDE, active=True
    ).values_list('id_tiket', flat=True)


def _get_pmde_tiket_ids(user):
    """Get the set of tiket IDs in the user's PMDE scope.

    Kasi PMDE supervise the whole unit, so they are unscoped and get None;
    other users get only the tikets for which they are an active PMDE PIC.
    """
    if is_kasi_pmde(user):
        return None
    return TiketPIC.objects.filter(
        id_user=user, role=TiketPIC.Role.PMDE, active=True
    ).values_list('id_tiket', flat=True)


def _get_special_request_tiket_ids(user):
    """Get the tiket IDs visible to the user for the Special Request category.

    Any kasi supervises the whole unit and is therefore unscoped (None); other
    users see only the tikets for which they hold an active PIC assignment
    (regardless of role).
    """
    if is_kasi(user):
        return None
    return TiketPIC.objects.filter(
        id_user=user, active=True
    ).values_list('id_tiket', flat=True)


def _build_tiket_base_qs(category, user):
    """Build the base Tiket queryset for a given category and user.

    Returns a queryset, or None if the user is not authorized for the category.
    """
    tiket_qs = Tiket.objects.select_related(
        'id_periode_data__id_sub_jenis_data_ilap__id_ilap',
        'id_periode_data__id_sub_jenis_data_ilap',
        'id_periode_data__id_sub_jenis_data_ilap__id_jenis_tabel',
        'id_periode_data__id_periode_pengiriman',
        'id_bentuk_data',
        'id_cara_penyampaian',
        'id_status_penelitian',
    )

    # Special Request category: tikets flagged special_request within the
    # user's visibility scope (kasi see all, others see their PIC tikets).
    if category == 'special_request':
        return _scoped(
            tiket_qs.filter(special_request=True),
            _get_special_request_tiket_ids(user),
        )

    # PMDE category: everything still upstream of quality control, scoped by the
    # same rule as Dalam Proses Pengendalian Mutu — the reader's own active PMDE
    # assignments, or the whole seksi for a kasi. Also gated on PMDE membership,
    # so the category stays out of the other units' home pages entirely.
    if category == 'masih_di_p3de_pide':
        if user_group_names(user).isdisjoint(['user_pmde', 'kasi_pmde']):
            return None
        # jumlah_baris mirrors sq.baris_data(): baris lengkap until
        # identification has actually split it into I/U/CDE/Res, baris I from
        # there on. Annotated (rather than computed in Python per row) so the
        # column can be sorted at the database like the others.
        return _scoped(
            tiket_qs.filter(
                status_tiket__in=STATUSES_SEBELUM_PENGENDALIAN_MUTU
            ).annotate(
                _split_total=(
                    Coalesce(F('baris_i'), 0) + Coalesce(F('baris_u'), 0)
                    + Coalesce(F('baris_cde'), 0) + Coalesce(F('baris_res'), 0)
                ),
            ).annotate(
                jumlah_baris=Case(
                    When(
                        Q(status_tiket__in=[STATUS_DIKIRIM_KE_PIDE, STATUS_IDENTIFIKASI])
                        & ~Q(_split_total=0),
                        then=Coalesce(F('baris_i'), Value(0)),
                    ),
                    default=Coalesce(F('baris_lengkap'), Value(0)),
                    output_field=IntegerField(),
                ),
            ),
            _get_pmde_tiket_ids(user),
        )

    # Admin category: periode_tiket_null_p3de - no user-specific PIC filter
    if category == 'periode_tiket_null_p3de':
        if 'admin_p3de' not in user_group_names(user):
            return None
        return tiket_qs.filter(tahun=2099)

    # Admin category: tickets in Pengendalian Mutu status without an active PMDE PIC
    if category == 'tiket_pengendalian_mutu_tanpa_pic':
        if 'admin_pmde' not in user_group_names(user):
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
        if 'admin_pide' not in user_group_names(user):
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
                    _scoped(
                        Tiket.objects.filter(
                            id_periode_data=OuterRef('id_periode_data'),
                            periode=OuterRef('periode'),
                            tahun=OuterRef('tahun'),
                        ),
                        _get_p3de_tiket_ids(user),
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
    return _scoped(tiket_qs, ids_func(user)).filter(extra_filter)


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
    try:
        draw = int(request.GET.get('draw', '1'))
    except (ValueError, TypeError):
        draw = 1
    try:
        start = int(request.GET.get('start', '0'))
    except (ValueError, TypeError):
        start = 0
    try:
        length = int(request.GET.get('length', '10'))
    except (ValueError, TypeError):
        length = 10
    category = request.GET.get('category', '')
    search_value = request.GET.get('search[value]', '')

    # Determine if this is a tiket-based category or a jenis_data_tanpa_pic category
    tiket_categories = {
        'belum_rekam_backup_data', 'belum_dibuat_tanda_terima', 'belum_diteliti',
        'belum_dikirim_ke_pide', 'pengembalian_seluruhnya_dari_pide',
        'pengembalian_sebagian_dari_pide', 'diklarifikasi',
        'belum_mulai_proses_identifikasi', 'dalam_proses_identifikasi',
        'dalam_proses_pengendalian_mutu', 'masih_di_p3de_pide',
        'periode_tiket_null_p3de',
        'tiket_pengendalian_mutu_tanpa_pic',
        'tiket_dikirim_ke_pide_tanpa_pic',
        'special_request',
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

    # Categories whose filter buttons are not the shared urgency triplet report
    # their own buckets here instead, keyed by the `data-urgency` value of the
    # button they belong to. The template renders one `count-<key>-<category>`
    # span per key, and the same key comes back as `age_group` when clicked.
    bucket_counts = {}

    ilap_list = []
    jenis_data_list = []

    if is_tiket_category:
        raw_ilap_list = list(qs.values_list('id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap', flat=True))
        ilap_list = sorted(list({i for i in raw_ilap_list if i}))
        total_ilap = len(ilap_list)

        raw_jenis_list = list(qs.values_list('id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data', flat=True))
        jenis_data_list = sorted(list({j for j in raw_jenis_list if j}))
        total_jenis_data = len(jenis_data_list)
                # Determine the correct date field for age tracking
        is_pide_belum_mulai = category in ('belum_mulai_proses_identifikasi', 'tiket_dikirim_ke_pide_tanpa_pic')
        is_pide_dalam_proses = category == 'dalam_proses_identifikasi'
        # The admin "tanpa PIC" card still measures how long a tiket has sat
        # since transfer; the main QC card measures how long it has left, which
        # is a different question and gets its own branch below.
        is_pmde_category = category == 'tiket_pengendalian_mutu_tanpa_pic'

        now = timezone.now()
        if category == 'dalam_proses_pengendalian_mutu':
            # Jatuh tempo, not age: the same thresholds the Quality Control page
            # offers, computed by the same function so the two cannot disagree
            # about when a tiket falls due.
            selected = request.GET.get('age_group')
            for key, limit in _JATUH_TEMPO_BUCKETS.items():
                bucket_counts[key] = len(jatuh_tempo_ids(qs, limit))
            bucket_counts['all'] = records_total
            if selected in _JATUH_TEMPO_BUCKETS:
                qs = qs.filter(
                    id__in=jatuh_tempo_ids(qs, _JATUH_TEMPO_BUCKETS[selected])
                )

        elif category == 'masih_di_p3de_pide':
            # Which unit still holds the tiket, which is the only split that
            # means anything across five statuses spanning two seksi.
            selected = request.GET.get('age_group')
            for key, statuses in _UNIT_BUCKETS.items():
                bucket_counts[key] = qs.filter(status_tiket__in=statuses).count()
            bucket_counts['all'] = records_total
            if selected in _UNIT_BUCKETS:
                qs = qs.filter(status_tiket__in=_UNIT_BUCKETS[selected])

        elif is_pide_belum_mulai:
            date_field = 'tgl_kirim_pide'
            # PIDE Belum Mulai SLA: 30 working days = 6 weeks = 42 calendar days
            cutoff_critical = now - timedelta(days=42)
            critical_count = qs.filter(**{f"{date_field}__lt": cutoff_critical}).count()
            warning_count = 0
            new_count = qs.filter(**{f"{date_field}__gte": cutoff_critical}).count()
            
            # Apply age_group filter
            age_group = request.GET.get('age_group')
            if age_group == 'critical':
                qs = qs.filter(**{f"{date_field}__lt": cutoff_critical})
            elif age_group == 'new':
                qs = qs.filter(**{f"{date_field}__gte": cutoff_critical})

        elif is_pide_dalam_proses:
            # PIDE Dalam Proses SLA: 30 working days = 42 calendar days from Tanggal Rekam PIDE (fallback to tgl_kirim_pide)
            qs = qs.annotate(effective_pide_date=Coalesce('tgl_rekam_pide', 'tgl_kirim_pide'))
            cutoff_critical = now - timedelta(days=42)
            critical_count = qs.filter(effective_pide_date__lt=cutoff_critical).count()
            warning_count = 0
            new_count = qs.filter(effective_pide_date__gte=cutoff_critical).count()
            
            # Apply age_group filter
            age_group = request.GET.get('age_group')
            if age_group == 'critical':
                qs = qs.filter(effective_pide_date__lt=cutoff_critical)
            elif age_group == 'new':
                qs = qs.filter(effective_pide_date__gte=cutoff_critical)

        elif is_pmde_category:
            date_field = 'tgl_transfer'
            # PMDE SLA: 85 working days = 17 weeks = 119 calendar days
            cutoff_critical = now - timedelta(days=119)
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
            date_field = 'tgl_terima_dip'
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

        # Apply priority filter for tiket categories
        if is_tiket_category:
            priority_only = request.GET.get('priority_only')
            if priority_only == '1':
                qs = qs.filter(id_jenis_prioritas_data__isnull=False)

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

    # Filter by Starred (Watchlist)
    starred_only = request.GET.get('starred_only') == 'true'
    if starred_only and is_tiket_category:
        from diamond_web.models.user_starred_tiket import UserStarredTiket
        starred_list = UserStarredTiket.objects.filter(id_user=request.user).values_list('nomor_tiket', flat=True)
        qs = qs.filter(nomor_tiket__in=starred_list)

    records_filtered = qs.count()

    # Ordering
    order_col_index = request.GET.get('order[0][column]')
    order_dir = request.GET.get('order[0][dir]', 'asc')

    if is_tiket_category:
        columns = _TIKET_ORDER_COLUMNS.get(category, _TIKET_ORDER_COLUMNS_DEFAULT)

        if order_col_index is not None:
            try:
                idx = int(order_col_index)
                col = columns[idx] if 0 <= idx < len(columns) else 'nomor_tiket'
                prefix = '-' if order_dir == 'desc' else ''
                if col in _TIKET_ORDER_NULL_AS_ZERO:
                    qs = qs.annotate(
                        _order_value=Coalesce(F(col), Value(0))
                    ).order_by(prefix + '_order_value')
                else:
                    fields = _TIKET_ORDER_FIELDS.get(col, (col,))
                    qs = qs.order_by(*(prefix + f for f in fields))
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

    if length < 0:
        qs_page = qs[start:]
    else:
        qs_page = qs[start:start + length]

    # Build data rows
    data = []
    for obj in qs_page:
        if is_tiket_category:
            nama_ilap = obj.id_periode_data.id_sub_jenis_data_ilap.id_ilap.nama_ilap
            nama_sub_jenis = obj.id_periode_data.id_sub_jenis_data_ilap.nama_sub_jenis_data
            nama_tabel_I = obj.id_periode_data.id_sub_jenis_data_ilap.nama_tabel_I or '-'
            jenis_tabel_obj = obj.id_periode_data.id_sub_jenis_data_ilap.id_jenis_tabel
            jenis_tabel = jenis_tabel_obj.deskripsi if jenis_tabel_obj else '-'
            view_url = reverse('tiket_detail', args=[obj.id])
            # Build action HTML — add quick-assign button for admin tiket_dikirim_ke_pide_tanpa_pic
            if category == 'tiket_dikirim_ke_pide_tan_pic' or category == 'tiket_dikirim_ke_pide_tanpa_pic':
                sub_jenis_id = obj.id_periode_data.id_sub_jenis_data_ilap_id
                sub_jenis_kode = obj.id_periode_data.id_sub_jenis_data_ilap.id_sub_jenis_data
                sub_jenis_nama_esc = nama_sub_jenis.replace('"', '&quot;').replace("'", '&#39;')
                nama_ilap_esc = nama_ilap.replace('"', '&quot;').replace("'", '&#39;')
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
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
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
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
            elif category == 'belum_diteliti':
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-warning text-white btn-quick-rekam-penelitian" '
                    f'data-tiket-id="{obj.id}" data-nomor-tiket="{obj.nomor_tiket}" title="Rekam Hasil Penelitian">'
                    f'<i class="feather-search"></i></button>'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
                    f'<i class="feather-eye"></i></a>'
                    f'</div>'
                )
            elif category == 'belum_rekam_backup_data':
                backup_url = reverse('backup_data_from_tiket_create', kwargs={'tiket_pk': obj.id})
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-warning text-white btn-home-ajax-modal" data-url="{backup_url}" data-target="#homeRekamBackupModal" data-tiket="{obj.nomor_tiket}" title="Rekam Backup Data">'
                    f'<i class="feather-save"></i></button>'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
                    f'<i class="feather-eye"></i></a>'
                    f'</div>'
                )
            elif category == 'belum_dibuat_tanda_terima':
                tanda_terima_url = reverse('tanda_terima_data_from_tiket_create', kwargs={'tiket_pk': obj.id})
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-info text-white btn-home-ajax-modal" data-url="{tanda_terima_url}" data-target="#homeTandaTerimaModal" data-tiket="{obj.nomor_tiket}" title="Buat Tanda Terima">'
                    f'<i class="feather-file-text"></i></button>'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
                    f'<i class="feather-eye"></i></a>'
                    f'</div>'
                )
            elif category == 'belum_mulai_proses_identifikasi':
                identifikasi_url = reverse('identifikasi_tiket', kwargs={'pk': obj.id})
                action_html = (
                    f'<div class="d-flex justify-content-center gap-1">'
                    f'<button type="button" class="btn btn-sm btn-info text-white btn-home-ajax-modal" data-url="{identifikasi_url}" data-target="#homeIdentifikasiModal" data-tiket="{obj.nomor_tiket}" title="Proses Identifikasi">'
                    f'<i class="feather-check-circle"></i></button>'
                    f'<a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank">'
                    f'<i class="feather-eye"></i></a>'
                    f'</div>'
                )
            else:
                action_html = f'<div class="d-flex justify-content-center gap-1"><a href="{view_url}" class="btn btn-sm btn-primary" title="Lihat" target="_blank"><i class="feather-eye"></i></a></div>'

            if category in ('belum_mulai_proses_identifikasi', 'tiket_dikirim_ke_pide_tanpa_pic'):
                date_val = obj.tgl_kirim_pide.strftime('%d-%m-%Y') if obj.tgl_kirim_pide else ''
                date_order = obj.tgl_kirim_pide.strftime('%Y-%m-%d') if obj.tgl_kirim_pide else ''
            elif category == 'dalam_proses_identifikasi':
                pide_dt = obj.tgl_rekam_pide or obj.tgl_kirim_pide
                date_val = pide_dt.strftime('%d-%m-%Y') if pide_dt else ''
                date_order = pide_dt.strftime('%Y-%m-%d') if pide_dt else ''
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
                    'periode_data': format_periode_tiket(obj) or '-',
                    'periode': obj.periode,
                    'tahun': obj.tahun,
                    'status_tiket': STATUS_LABELS.get(obj.status_tiket, ''),
                    'actions': action_html,
                })
            elif category == 'masih_di_p3de_pide':
                data.append({
                    'nomor_tiket': obj.nomor_tiket,
                    'nama_ilap': nama_ilap,
                    'nama_sub_jenis_data': nama_sub_jenis,
                    'periode_data': format_periode_tiket(obj) or '-',
                    'nama_tabel_I': nama_tabel_I,
                    # Same rule the Quality Control page uses for its P3DE/PIDE
                    # upstream sections (sq.baris_data): baris lengkap until
                    # identification has actually split it, baris I from there
                    # on. Computed as the `jumlah_baris` annotation so it can
                    # also be sorted at the database.
                    'jumlah_baris': obj.jumlah_baris,
                    'status_tiket': STATUS_LABELS.get(obj.status_tiket, ''),
                    'status_tiket_code': obj.status_tiket,
                    'tanggal': date_val,
                    'tanggal_order': date_order,
                    'is_prioritas': obj.id_jenis_prioritas_data_id is not None,
                    'actions': action_html,
                })
            elif category == 'special_request':
                data.append({
                    'nomor_tiket': obj.nomor_tiket,
                    'nama_ilap': nama_ilap,
                    'nama_sub_jenis_data': nama_sub_jenis,
                    'periode_data': format_periode_tiket(obj) or '-',
                    'status_tiket': STATUS_LABELS.get(obj.status_tiket, ''),
                    'tgl_special_request': (
                        obj.tgl_special_request.strftime('%d-%m-%Y') if obj.tgl_special_request else ''
                    ),
                    'tgl_special_request_order': (
                        obj.tgl_special_request.strftime('%Y-%m-%d') if obj.tgl_special_request else ''
                    ),
                    'actions': action_html,
                })
            else:
                data.append({
                    'nomor_tiket': obj.nomor_tiket,
                    'nama_ilap': nama_ilap,
                    'nama_sub_jenis_data': nama_sub_jenis,
                    'periode_data': format_periode_tiket(obj) or '-',
                    'nama_tabel_I': nama_tabel_I,
                    'jenis_tabel': jenis_tabel,
                    'baris_diterima': obj.baris_diterima or 0,
                    'baris_lengkap': obj.baris_lengkap or 0,
                    'baris_tidak_lengkap': obj.baris_tidak_lengkap or 0,
                    'baris_i': obj.baris_i or 0,
                    'baris_cde': obj.baris_cde or 0,
                    'belum_qc': obj.belum_qc or 0,
                    'lolos_qc': obj.lolos_qc or 0,
                    'tanggal': date_val,
                    'tanggal_order': date_order,
                    'is_prioritas': obj.id_jenis_prioritas_data_id is not None,
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
            'bucket_counts': bucket_counts,
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


@login_required
def toggle_starred_tiket(request):
    """Toggle bintang (watchlist) tiket menggunakan database UserStarredTiket."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    nomor_tiket = request.POST.get('nomor_tiket', '').strip()
    if not nomor_tiket:
        return JsonResponse({'error': 'nomor_tiket diperlukan'}, status=400)

    from diamond_web.models.user_starred_tiket import UserStarredTiket
    
    # Check if it exists in DB
    existing = UserStarredTiket.objects.filter(id_user=request.user, nomor_tiket=nomor_tiket).first()
    
    if existing:
        existing.delete()
        is_starred = False
    else:
        UserStarredTiket.objects.create(id_user=request.user, nomor_tiket=nomor_tiket)
        is_starred = True

    total = UserStarredTiket.objects.filter(id_user=request.user).count()

    return JsonResponse({
        'starred': is_starred,
        'nomor_tiket': nomor_tiket,
        'total': total,
    })

@login_required
@require_GET
def get_starred_tikets(request):
    """Ambil daftar nomor tiket yang dipantau (watchlist) beserta detailnya."""
    starred_records = UserStarredTiket.objects.filter(id_user=request.user).values_list('nomor_tiket', flat=True)
    starred = list(starred_records)
    
    details = []
    if starred:
        qs = Tiket.objects.filter(nomor_tiket__in=starred).select_related(
            'id_periode_data__id_sub_jenis_data_ilap__id_ilap'
        )
        for t in qs:
            try:
                nama_ilap = t.id_periode_data.id_sub_jenis_data_ilap.id_ilap.nama_ilap
                nama_sub_jenis_data = t.id_periode_data.id_sub_jenis_data_ilap.nama_sub_jenis_data
            except AttributeError:
                nama_ilap = "-"
                nama_sub_jenis_data = "-"
            
            details.append({
                'nomor_tiket': t.nomor_tiket,
                'ilap': nama_ilap,
                'jenis_data': nama_sub_jenis_data,
                'status': t.get_status_tiket_display(),
                'status_code': t.status_tiket,
                'url': reverse('tiket_detail', args=[t.id])
            })
        
        # Urutkan list berdasarkan kapan tiket di-assign ke pantauan (sesuai urutan `starred`)
        details.sort(key=lambda x: starred.index(x['nomor_tiket']))
            
    return JsonResponse({
        'starred': starred,
        'details': details,
        'total': len(starred)
    })