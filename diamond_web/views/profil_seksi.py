"""Ringkasan Seksi: every person of one PDE seksi, and how much each holds.

The Profil PDE page names the staff of the three seksi; this page, reached from
the name of a seksi there, puts their workload side by side — the tiles of the
Profil PIC page, one row per person. The figures are counted exactly as those
tiles count them, so following a name from a row lands on a page that agrees
with it: every PIC assignment the person has held, ended ones included, and
every tiket they are a PIC of under any role.

One figure the Profil PIC page does not show is added: how many distinct nama
tabel the person's prioritas sub jenis data land in, prioritas being a
``JenisPrioritasData`` row whose ``tahun`` is the current year.

A row per person is a Profil PIC page per person, so the page follows the same
line of supervision — see
:func:`~diamond_web.utils.pic_profil.can_view_ringkasan_seksi`.
"""
from collections import defaultdict
from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404
from django.views.generic import TemplateView

from ..constants.tiket_status import STATUS_BADGE_CLASSES, STATUS_LABELS
from ..models.jenis_prioritas_data import JenisPrioritasData
from ..models.pic import PIC
from ..models.tiket_pic import TiketPIC
from ..utils.pic_profil import can_view_ringkasan_seksi, get_pde_seksi
from .profil_pic import WILAYAH_ORDER, build_seksi_staff

__all__ = [
    'ProfilSeksiDetailView',
    'build_ringkasan_seksi',
]


def _prioritas_sub_ids(sub_ids, tahun):
    """Return the sub jenis data of `sub_ids` that are prioritas in `tahun`.

    Read off ``JenisPrioritasData.tahun``, the year the prioritas was set for:
    the question here is which data is prioritas this year, not whether one
    particular tiket arrived inside a window, which is what
    :mod:`diamond_web.utils.jenis_prioritas` answers.

    Args:
        sub_ids (iterable): JenisDataILAP primary keys.
        tahun (int): The year asked about.

    Returns:
        set: The prioritas ones among `sub_ids`.
    """
    sub_ids = list(sub_ids)
    if not sub_ids:
        return set()
    return set(
        JenisPrioritasData.objects
        .filter(tahun=str(tahun), id_sub_jenis_data_ilap__in=sub_ids)
        .values_list('id_sub_jenis_data_ilap', flat=True)
    )


def _figures(ilap, subs, prioritas, tabel_of_sub, status_counts):
    """Return the figures of one row from the sets behind it.

    Shared by the person rows and the seksi total, so the two are counted the
    same way; the total is simply handed the union of every person's sets.

    Args:
        ilap (dict): ``{id_ilap: kategori wilayah}`` of the ILAPs held.
        subs (set): The sub jenis data held.
        prioritas (set): The sub jenis data prioritas this year.
        tabel_of_sub (dict): ``{sub jenis data: nama tabel}``, blank for none.
        status_counts (dict): ``{status_tiket: distinct tikets}``.

    Returns:
        dict: The figures described in :func:`build_ringkasan_seksi`.
    """
    subs_prioritas = subs & prioritas
    wilayah = list(ilap.values())
    return {
        'ilap': len(ilap),
        'ilap_wilayah': [wilayah.count(label) for label in WILAYAH_ORDER],
        'jenis_data': len(subs),
        'nama_tabel': len({tabel_of_sub[s] for s in subs} - {''}),
        'nama_tabel_prioritas': len({tabel_of_sub[s] for s in subs_prioritas} - {''}),
        # A tiket's status is one value, so the per-status counts — each of
        # distinct tikets — sum to the distinct total without a query of its own.
        'tiket': sum(status_counts.values()),
        'tiket_status': [status_counts.get(status, 0) for status in STATUS_LABELS],
    }


def build_ringkasan_seksi(entries, tahun=None):
    """Count the workload of each person in `entries`, and of them together.

    A handful of queries for the whole seksi rather than a Profil PIC page's
    worth per person: the PIC rows, the prioritas rows behind them, and the
    tiket counts per status — per person, and once more across the seksi.

    Args:
        entries (list): ``{'user', 'nama'}`` dicts from
            :func:`~diamond_web.views.profil_pic.build_seksi_staff`, in the
            order the rows are wanted.
        tahun (int, optional): The year prioritas is counted for; defaults to
            the current year.

    Returns:
        tuple: ``(rows, total)``. `rows` holds one dict per entry, in the same
        order, with ``user``, ``nama``, ``ilap`` (the total), ``ilap_wilayah``
        (counts in :data:`~diamond_web.views.profil_pic.WILAYAH_ORDER` order),
        ``jenis_data``, ``nama_tabel``, ``nama_tabel_prioritas``, ``tiket`` (the total) and ``tiket_status``
        (counts in :data:`STATUS_LABELS` order, zeros included). `total` holds
        the same figures for the seksi as a whole, each thing counted once
        however many of its people hold it — which is why it is not the sum of
        the rows.
    """
    tahun = tahun or date.today().year
    user_ids = [entry['user'].pk for entry in entries]

    pic_rows = (
        PIC.objects
        .filter(id_user__in=user_ids)
        .values_list(
            'id_user',
            'id_sub_jenis_data_ilap',
            'id_sub_jenis_data_ilap__nama_tabel_I',
            'id_sub_jenis_data_ilap__id_ilap',
            'id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__deskripsi',
        )
    )
    jenis_data = defaultdict(set)
    ilap = defaultdict(dict)
    tabel_of_sub = {}
    for user_id, sub_id, nama_tabel, ilap_id, wilayah in pic_rows:
        jenis_data[user_id].add(sub_id)
        tabel_of_sub[sub_id] = (nama_tabel or '').strip()
        if ilap_id is not None:
            ilap[user_id][ilap_id] = wilayah

    prioritas = _prioritas_sub_ids(tabel_of_sub, tahun)

    tiket_pics = TiketPIC.objects.filter(id_user__in=user_ids)
    tiket_counts = defaultdict(dict)
    for row in (
        tiket_pics
        .values('id_user', 'id_tiket__status_tiket')
        .annotate(total=Count('id_tiket', distinct=True))
    ):
        tiket_counts[row['id_user']][row['id_tiket__status_tiket']] = row['total']

    rows = []
    for entry in entries:
        user_id = entry['user'].pk
        rows.append({
            'user': entry['user'],
            'nama': entry['nama'],
            **_figures(
                ilap[user_id], jenis_data[user_id], prioritas,
                tabel_of_sub, tiket_counts[user_id],
            ),
        })

    seksi_ilap = {}
    for per_user in ilap.values():
        seksi_ilap.update(per_user)
    seksi_status = {
        row['id_tiket__status_tiket']: row['total']
        for row in (
            tiket_pics
            .values('id_tiket__status_tiket')
            .annotate(total=Count('id_tiket', distinct=True))
        )
    }
    total = _figures(
        seksi_ilap, set(tabel_of_sub), prioritas, tabel_of_sub, seksi_status
    )
    return rows, total


class ProfilSeksiDetailView(LoginRequiredMixin, TemplateView):
    """One PDE seksi, with one row of workload figures per person in it.

    Template: profil_seksi/detail.html
    """
    template_name = 'profil_seksi/detail.html'

    def get_context_data(self, **kwargs):
        """Assemble the seksi and the rows of its table.

        Returns:
            dict: Template context containing:
                - seksi (dict): The :data:`PDE_SEKSI` entry.
                - tahun (int): The year prioritas is counted for.
                - rows (list), total (dict): From :func:`build_ringkasan_seksi`,
                  the rows by name.
                - wilayah_labels (tuple): The ILAP sub-column headers.
                - status_columns (list): ``{'lines', 'label', 'dot_class'}`` per
                  tiket status, in workflow order.

        Raises:
            Http404: When the kode names no seksi.
            PermissionDenied: When the viewer does not supervise the seksi.
        """
        context = super().get_context_data(**kwargs)
        seksi = get_pde_seksi(self.kwargs['kode'])
        if seksi is None:
            raise Http404(f'Seksi "{self.kwargs["kode"]}" tidak ditemukan.')
        if not can_view_ringkasan_seksi(self.request.user, seksi):
            raise PermissionDenied(
                'Ringkasan seksi hanya dapat dibuka oleh kepala seksi, '
                'admin seksi tersebut, atau administrator.'
            )

        tahun = date.today().year
        context['seksi'] = seksi
        context['tahun'] = tahun
        context['rows'], context['total'] = build_ringkasan_seksi(
            build_seksi_staff(seksi), tahun
        )
        context['wilayah_labels'] = WILAYAH_ORDER
        # Split after the first word, so a status name takes two short lines in
        # its header rather than holding a narrow column open to its full width.
        context['status_columns'] = [
            {
                'lines': label.split(' ', 1),
                'label': label,
                'dot_class': STATUS_BADGE_CLASSES.get(status, 'bg-secondary').split()[0],
            }
            for status, label in STATUS_LABELS.items()
        ]
        return context
