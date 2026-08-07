"""Profil PIC: one person, and everything they are the PIC of.

The catalogue pages read outwards from a thing — an ILAP, a sub jenis data, a
nama tabel — and each of them ends at a list of names. This page reads the other
way round, from the person towards the data they hold: which seksi they sit in,
which ILAPs they cover, which sub jenis data and bank data tables those cover in
turn, and which tikets landed on them. It is what every name in the app now
links to, so a reader who meets an unfamiliar PIC can find out what else that
person is responsible for without asking.

Unlike the catalogue pages it sits alongside, this one is scoped: a page about a
person is read by that person and by whoever supervises their seksi, and by
nobody else — see
:func:`~diamond_web.utils.pic_profil.visible_profil_pic_users` for the rule,
which governs the page, the tiket endpoint behind it, the header search that
finds people, and whether a name printed elsewhere is a link at all. Opening a
tiket from the list here still goes through `TiketDetailView`, which enforces
the PIC rules of its own.
"""
from datetime import date, datetime, time

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.dateformat import format as date_format
from django.utils.html import escape
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from ..constants.tiket_status import STATUS_BADGE_CLASSES, STATUS_LABELS
from ..models.pic import PIC
from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from ..utils import format_periode
from ..utils.pic_profil import (
    PDE_SEKSI,
    can_view_pic_profil,
    pic_display_name,
    seksi_label,
)

__all__ = [
    'ProfilPICDetailView',
    'build_seksi_directory',
    'profil_pic_tiket_data',
]


# The badge the peran column of the tiket table is shown with. Deliberately the
# three soft colours the rest of the app already uses for the three seksi, so a
# reader recognises them from the tiket detail page. TiketPIC records the role
# as an integer of its own, which is why this is keyed on Role, not on TipePIC.
ROLE_BADGE_CLASSES = {
    TiketPIC.Role.P3DE: 'bg-soft-primary text-primary',
    TiketPIC.Role.PIDE: 'bg-soft-info text-info',
    TiketPIC.Role.PMDE: 'bg-soft-warning text-warning',
}


def get_pic_user(username):
    """Return the User named `username`, or 404.

    Args:
        username (str): The username from the URL. Matched case-insensitively
            because it arrives from a URL a reader may have typed by hand.

    Returns:
        User: The matching user, with their groups preloaded.

    Raises:
        Http404: When no user carries that username.
    """
    user = User.objects.filter(
        username__iexact=username
    ).prefetch_related('groups').first()
    if user is None:
        raise Http404(f'Pengguna "{username}" tidak ditemukan.')
    return user


def build_seksi_directory():
    """Return the active staff of each PDE seksi, one entry per seksi.

    The three columns of the Profil PDE page, answering who works a seksi's
    queue. Two kinds of account are subtracted from the staff group:

    * superusers. They are members of all three staff groups so that they can
      act anywhere, so reading the staff group alone would put the same system
      account at the top of every column. Only the superuser flag is subtracted:
      somebody holding an admin role is a colleague who also administers the
      application, and belongs in the seksi they work in.
    * inactive accounts. A directory is a list of people to go to, and a
      disabled account is nobody to go to. Their Profil PIC page stays reachable
      from the tikets they used to hold, so the history is not lost.

    Returns:
        list: One dict per seksi, ``{'kode', 'label', 'users'}``, in the order
        the workflow moves through them; each user is ``{'user', 'nama'}``,
        sorted by the name the entry shows.
    """
    columns = []
    for seksi in PDE_SEKSI:
        users = User.objects.filter(
            groups__name=seksi['user_group'], is_active=True, is_superuser=False
        ).distinct()
        entries = [{'user': user, 'nama': pic_display_name(user)} for user in users]
        entries.sort(key=lambda entry: entry['nama'].lower())
        columns.append({
            'kode': seksi['kode'],
            'label': seksi['label'],
            'users': entries,
        })
    return columns


def get_viewable_pic_user(request, username):
    """Return the user named `username`, or refuse the request.

    Args:
        request (HttpRequest): The current request, whose user is the viewer.
        username (str): The username from the URL.

    Returns:
        User: The person the page is about.

    Raises:
        Http404: When no user carries that username.
        PermissionDenied: When the viewer may not open that person's profile.
    """
    pic_user = get_pic_user(username)
    if not can_view_pic_profil(request.user, pic_user):
        raise PermissionDenied(
            'Anda hanya dapat membuka profil PIC diri sendiri '
            'atau pegawai di seksi Anda.'
        )
    return pic_user


def build_penugasan_list(pic_user):
    """Return the PIC assignments of `pic_user`, newest first within each tipe.

    One entry per PIC row rather than per sub jenis data: a person is routinely
    reassigned to the same data after a gap, and each stretch is a fact of its
    own that the page has no business collapsing.

    Args:
        pic_user (User): The person whose assignments are wanted.

    The list itself is not rendered — the page shows the three collapsed views
    built from it below — but it is what they are all summarised from, so an
    assignment appears in each of them exactly once per stretch it covers.

    Returns:
        list: Dicts of ``{'jenis_data', 'ilap', 'tipe_label', 'aktif'}``, ordered
        by tipe and then by most recent start date.
    """
    pics = PIC.objects.filter(id_user=pic_user).select_related(
        'id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah'
    ).order_by('tipe', '-start_date')

    return [
        {
            'jenis_data': pic.id_sub_jenis_data_ilap,
            'ilap': pic.id_sub_jenis_data_ilap.id_ilap,
            'tipe_label': pic.get_tipe_display(),
            'aktif': pic.end_date is None,
        }
        for pic in pics
    ]


def summarise_ilap(penugasan_list):
    """Collapse `penugasan_list` to one entry per ILAP.

    A person holds several sub jenis data of the same ILAP, so listing the
    assignments would name one ILAP over and over. Each entry counts the sub
    jenis data behind it and reads as active when any one of them still is.

    Args:
        penugasan_list (list): Entries from :func:`build_penugasan_list`.

    Returns:
        list: Dicts of ``{'ilap', 'count', 'aktif'}``, active ILAPs first and
        then by name.
    """
    entries = {}
    for item in penugasan_list:
        ilap = item['ilap']
        if ilap is None:
            continue
        entry = entries.get(ilap.id_ilap)
        if entry is None:
            entry = entries[ilap.id_ilap] = {
                'ilap': ilap, 'jenis_data': set(), 'aktif': False
            }
        entry['jenis_data'].add(item['jenis_data'].pk)
        entry['aktif'] = entry['aktif'] or item['aktif']

    result = [
        {'ilap': e['ilap'], 'count': len(e['jenis_data']), 'aktif': e['aktif']}
        for e in entries.values()
    ]
    result.sort(key=lambda e: (not e['aktif'], e['ilap'].nama_ilap.lower()))
    return result


def summarise_jenis_data(penugasan_list):
    """Collapse `penugasan_list` to one entry per sub jenis data.

    The same sub jenis data appears once per stretch of assignment, and a person
    may hold it under more than one tipe, so each entry gathers the tipe labels
    it was held under and reads as active when any of those stretches is open.

    Args:
        penugasan_list (list): Entries from :func:`build_penugasan_list`.

    Returns:
        list: Dicts of ``{'jenis_data', 'ilap', 'tipe_labels', 'aktif'}``,
        active entries first and then by name.
    """
    entries = {}
    for item in penugasan_list:
        jenis_data = item['jenis_data']
        entry = entries.get(jenis_data.pk)
        if entry is None:
            entry = entries[jenis_data.pk] = {
                'jenis_data': jenis_data,
                'ilap': item['ilap'],
                'tipe_labels': [],
                'aktif': False,
            }
        if item['tipe_label'] not in entry['tipe_labels']:
            entry['tipe_labels'].append(item['tipe_label'])
        entry['aktif'] = entry['aktif'] or item['aktif']

    result = list(entries.values())
    result.sort(
        key=lambda e: (not e['aktif'], (e['jenis_data'].nama_sub_jenis_data or '').lower())
    )
    return result


# The three kategori wilayah an ILAP is filed under, listed in this order ahead
# of anything else the reference table grows, so the breakdown reads the same on
# every profile. A kategori not named here still appears, after these.
WILAYAH_ORDER = ('Nasional', 'Regional', 'Internasional')

# How recently a tiket must have arrived for the table it lands in to count as
# still being fed. Two years spans a full annual reporting cycle twice over, so
# a table that has missed both is genuinely dormant rather than merely late.
NAMA_TABEL_AKTIF_TAHUN = 2


def summarise_ilap_wilayah(ilap_list):
    """Break `ilap_list` down by the kategori wilayah of each ILAP.

    Args:
        ilap_list (list): Entries from :func:`summarise_ilap`.

    Every ILAP has a kategori wilayah — the column is NOT NULL — so there is no
    "uncategorised" bucket to fall back to.

    Returns:
        list: Dicts of ``{'label', 'count'}``, the kategori of
        :data:`WILAYAH_ORDER` first and any other kategori after them, by name.
        Kategori nobody holds are left out rather than shown as zero.
    """
    counts = {}
    for entry in ilap_list:
        label = entry['ilap'].id_kategori_wilayah.deskripsi
        counts[label] = counts.get(label, 0) + 1

    def sort_key(label):
        if label in WILAYAH_ORDER:
            return (0, WILAYAH_ORDER.index(label), '')
        return (1, 0, label.lower())

    return [
        {'label': label, 'count': counts[label]}
        for label in sorted(counts, key=sort_key)
    ]


def _years_ago(years):
    """Return the datetime `years` years before now, at the start of that day.

    Written out rather than done with a timedelta of 365 days so that a leap
    year does not quietly shift the boundary by a day; 29 February falls back to
    the 28th, which is the only date that has no counterpart in another year.
    """
    today = date.today()
    try:
        cutoff = today.replace(year=today.year - years)
    except ValueError:  # 29 February in a year whose counterpart has none
        cutoff = today.replace(year=today.year - years, day=28)
    return datetime.combine(cutoff, time.min)


def summarise_nama_tabel_aktivitas(nama_tabel_list):
    """Split `nama_tabel_list` into the tables still being fed and the dormant.

    A table counts as active when *any* tiket landing in it arrived within the
    last :data:`NAMA_TABEL_AKTIF_TAHUN` years — every sub jenis data feeding it,
    not only the ones this person is PIC of. Whether data still flows into a
    table is a property of the table, and it is the same question the nama tabel
    page these chips link to answers.

    A table with no tiket at all is counted as dormant: it has no recent tiket
    either, which is what the split is asking about.

    Args:
        nama_tabel_list (list): Entries from :func:`summarise_nama_tabel`.

    Returns:
        dict: ``{'aktif', 'tidak_aktif', 'tahun'}`` — the two counts and the
        number of years behind the split, so the template can name it.
    """
    names = [entry['nama_tabel'] for entry in nama_tabel_list]
    aktif = 0
    if names:
        aktif = len(set(
            Tiket.objects
            .filter(
                id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I__in=names,
                tgl_terima_dip__gte=_years_ago(NAMA_TABEL_AKTIF_TAHUN),
            )
            .values_list(
                'id_periode_data__id_sub_jenis_data_ilap__nama_tabel_I', flat=True
            )
        ))
    return {
        'aktif': aktif,
        'tidak_aktif': len(names) - aktif,
        'tahun': NAMA_TABEL_AKTIF_TAHUN,
    }


def summarise_tiket_status(pic_user):
    """Break the tikets of `pic_user` down by status, in workflow order.

    Counts distinct tikets, not assignments, so the rows add up to the headline
    total even for a tiket the person holds under two roles.

    Args:
        pic_user (User): The person whose tikets are counted.

    Returns:
        list: Dicts of ``{'label', 'count', 'dot_class'}``, ordered by status
        code — which is the order the workflow moves through them. Statuses with
        no tiket are left out.
    """
    rows = (
        TiketPIC.objects
        .filter(id_user=pic_user)
        .values('id_tiket__status_tiket')
        .annotate(total=Count('id_tiket', distinct=True))
    )
    counts = {row['id_tiket__status_tiket']: row['total'] for row in rows}

    return [
        {
            'label': STATUS_LABELS.get(status, f'Status {status}'),
            'count': counts[status],
            # The badge classes carry a text colour for the light badges; only
            # the background is wanted for a dot.
            'dot_class': STATUS_BADGE_CLASSES.get(status, 'bg-secondary').split()[0],
        }
        for status in sorted(counts)
    ]


def summarise_nama_tabel(penugasan_list):
    """Collapse `penugasan_list` to one entry per bank data table.

    A nama tabel is fed by many sub jenis data and a person is often PIC of
    several of them, so the name is counted once and carries how many of their
    sub jenis data land in it. Sub jenis data with no table recorded are left
    out: there is no table to name, and a blank chip leads nowhere.

    Args:
        penugasan_list (list): Entries from :func:`build_penugasan_list`.

    Returns:
        list: Dicts of ``{'nama_tabel', 'count', 'aktif'}``, active tables first
        and then by name.
    """
    entries = {}
    for item in penugasan_list:
        nama_tabel = (item['jenis_data'].nama_tabel_I or '').strip()
        if not nama_tabel:
            continue
        entry = entries.get(nama_tabel)
        if entry is None:
            entry = entries[nama_tabel] = {
                'nama_tabel': nama_tabel, 'jenis_data': set(), 'aktif': False
            }
        entry['jenis_data'].add(item['jenis_data'].pk)
        entry['aktif'] = entry['aktif'] or item['aktif']

    result = [
        {'nama_tabel': e['nama_tabel'], 'count': len(e['jenis_data']), 'aktif': e['aktif']}
        for e in entries.values()
    ]
    result.sort(key=lambda e: (not e['aktif'], e['nama_tabel'].lower()))
    return result


class ProfilPICDetailView(LoginRequiredMixin, TemplateView):
    """One person, with the seksi, ILAPs, sub jenis data and tabel they hold.

    Template: profil_pic/detail.html
    """
    template_name = 'profil_pic/detail.html'

    def get_context_data(self, **kwargs):
        """Assemble the person, their units and the four views of their work.

        Returns:
            dict: Template context containing:
                - pic_user (User): The person the page is about.
                - display_name (str), initials (str): Header identity.
                - seksi_list (list): Readable unit labels from their groups.
                - ilap_list, jenis_data_list, nama_tabel_list (list): The three
                  collapsed views of their assignments, one entry per thing
                  rather than per assignment.
                - tiket_total (int): Distinct tikets they are a PIC of. The rows
                  are loaded server-side by :func:`profil_pic_tiket_data`.
                - ilap_wilayah, nama_tabel_aktivitas, tiket_status: The
                  breakdowns shown under the matching summary tile.
        """
        context = super().get_context_data(**kwargs)
        pic_user = get_viewable_pic_user(self.request, self.kwargs['username'])
        penugasan_list = build_penugasan_list(pic_user)

        display_name = pic_display_name(pic_user)
        context['pic_user'] = pic_user
        context['display_name'] = display_name
        context['initials'] = ''.join(
            part[0] for part in display_name.split()[:2]
        ).upper() or display_name[:2].upper()

        context['seksi_list'] = [
            seksi_label(group.name) for group in pic_user.groups.all()
        ]

        context['ilap_list'] = summarise_ilap(penugasan_list)
        context['jenis_data_list'] = summarise_jenis_data(penugasan_list)
        context['nama_tabel_list'] = summarise_nama_tabel(penugasan_list)

        context['tiket_total'] = TiketPIC.objects.filter(
            id_user=pic_user
        ).values('id_tiket').distinct().count()

        # The breakdowns under the summary tiles. Each splits the tile above it
        # along the axis that tells a reader what kind of load this person
        # carries, rather than only how much of it.
        context['ilap_wilayah'] = summarise_ilap_wilayah(context['ilap_list'])
        context['nama_tabel_aktivitas'] = summarise_nama_tabel_aktivitas(
            context['nama_tabel_list']
        )
        context['tiket_status'] = summarise_tiket_status(pic_user)

        return context


# Columns of the tiket table the client may sort on. Peran and the aksi button
# are declared unsortable in the template instead: the first is a label read off
# an integer whose order means nothing to a reader, the second is not data.
TIKET_ORDER_COLUMNS = {
    0: 'id_tiket__nomor_tiket',
    1: 'id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap__nama_ilap',
    2: 'id_tiket__id_periode_data__id_sub_jenis_data_ilap__nama_sub_jenis_data',
    3: 'id_tiket__periode',
    4: 'id_tiket__tahun',
    6: 'id_tiket__status_tiket',
    7: 'id_tiket__tgl_terima_dip',
}


@login_required
@require_GET
def profil_pic_tiket_data(request, username):
    """Server-side DataTables endpoint for a person's tiket assignments.

    One row per TiketPIC record rather than per tiket: a person is occasionally
    PIC of the same tiket under two roles — handing it on and then taking it
    back — and each assignment is what the row is about, which is why it carries
    a peran of its own.

    Args:
        request (HttpRequest): The current request, carrying the DataTables
            ``draw``, ``start``, ``length``, ``search[value]`` and ``order``
            parameters.
        username (str): The username of the person the tikets belong to.

    Returns:
        JsonResponse: A JSON object with ``draw``, ``recordsTotal``,
        ``recordsFiltered`` and ``data`` (one dict per assignment row).

    Raises:
        PermissionDenied: When the viewer may not open that person's profile.
            Gated in its own right, not only through the page that draws it: the
            rows are the person's whole tiket load and this URL can be called
            directly.
    """
    pic_user = get_viewable_pic_user(request, username)

    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))
    search_value = request.GET.get('search[value]', '').strip()

    base_qs = TiketPIC.objects.filter(id_user=pic_user).select_related(
        'id_tiket__id_periode_data__id_periode_pengiriman',
        'id_tiket__id_periode_data__id_sub_jenis_data_ilap__id_ilap',
    )

    records_total = base_qs.count()

    if search_value:
        # status_tiket stores an integer, so the term is matched against the
        # labels first and the resulting codes are what the filter looks for.
        status_codes = [
            code for code, label in STATUS_LABELS.items()
            if search_value.lower() in label.lower()
        ]
        _sub = 'id_tiket__id_periode_data__id_sub_jenis_data_ilap'
        search_filter = (
            Q(id_tiket__nomor_tiket__icontains=search_value)
            | Q(**{f'{_sub}__nama_sub_jenis_data__icontains': search_value})
            | Q(**{f'{_sub}__id_ilap__nama_ilap__icontains': search_value})
        )
        if search_value.isdigit():
            search_filter |= (
                Q(id_tiket__tahun=int(search_value))
                | Q(id_tiket__periode=int(search_value))
            )
        if status_codes:
            search_filter |= Q(id_tiket__status_tiket__in=status_codes)
        base_qs = base_qs.filter(search_filter)

    records_filtered = base_qs.count()

    order_col_index = request.GET.get('order[0][column]')
    order_col = None
    if order_col_index is not None:
        try:
            order_col = TIKET_ORDER_COLUMNS.get(int(order_col_index))
        except (TypeError, ValueError):
            order_col = None
    if order_col:
        if request.GET.get('order[0][dir]', 'asc') == 'desc':
            order_col = f'-{order_col}'
        base_qs = base_qs.order_by(order_col)
    else:
        base_qs = base_qs.order_by('id_tiket__nomor_tiket')

    data = []
    for tiket_pic in base_qs[start:start + length]:
        tiket = tiket_pic.id_tiket
        sub_jenis_data = tiket.id_periode_data.id_sub_jenis_data_ilap
        ilap = sub_jenis_data.id_ilap
        periode_penerimaan = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
        status_label = STATUS_LABELS.get(tiket.status_tiket, '---')
        status_class = STATUS_BADGE_CLASSES.get(tiket.status_tiket, 'bg-secondary')
        role_label = TiketPIC.Role(tiket_pic.role).label if tiket_pic.role in TiketPIC.Role.values else str(tiket_pic.role)
        role_class = ROLE_BADGE_CLASSES.get(tiket_pic.role, 'bg-soft-secondary text-secondary')
        jenis_data_url = reverse(
            'jenis_data_ilap_profil', args=[sub_jenis_data.id_sub_jenis_data]
        )
        detail_url = reverse('tiket_detail', args=[tiket.pk])
        data.append({
            'nomor_tiket': escape(tiket.nomor_tiket),
            'nama_ilap': (
                f'<a href="{reverse("profil_ilap_detail", args=[ilap.id_ilap])}" '
                f'class="text-primary text-decoration-none">'
                f'<span class="text-muted small">{escape(ilap.id_ilap)}</span><br>'
                f'{escape(ilap.nama_ilap)}</a>'
            ) if ilap else '---',
            'sub_jenis_data': (
                f'<a href="{jenis_data_url}" class="text-primary text-decoration-none">'
                f'<span class="text-muted small">{escape(sub_jenis_data.id_sub_jenis_data)}</span>'
                f'<br>{escape(sub_jenis_data.nama_sub_jenis_data)}</a>'
            ),
            'periode': escape(format_periode(
                periode_penerimaan, tiket.periode, tiket.tahun, include_year=False
            )),
            'tahun': tiket.tahun,
            'peran': (
                f'<span class="badge {role_class}">{escape(role_label)}</span>'
                + ('' if tiket_pic.active
                   else ' <span class="badge bg-soft-secondary text-secondary">Nonaktif</span>')
            ),
            'status': f'<span class="badge {status_class}">{escape(status_label)}</span>',
            'tgl_terima_dip': (
                date_format(tiket.tgl_terima_dip, 'd M Y')
                if tiket.tgl_terima_dip else '---'
            ),
            'actions': (
                f'<a href="{detail_url}" class="btn btn-sm btn-primary" title="Detail Tiket">'
                f'<i class="feather-eye me-1"></i>Detail</a>'
            ),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'data': data,
    })
