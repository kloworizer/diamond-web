"""Coding rules for Pemda (PD) and Provinsi (PV) sub jenis data.

A Pemda/Provinsi ILAP is coded ``<prefix><nomor:3>`` (``PD001``, ``PV012``) and
every jenis data it reports carries a 4-digit kode that is the same for every
pemda: ``<jenis:2><sub:2>``. So TDP, kode ``4101``, is::

    id_jenis_data     = PD001 + 41      -> PD00141
    id_sub_jenis_data = PD00141 + 01    -> PD0014101

Shared by the bulk PIC page and the jenis data generator so both read a kode
the same way.
"""
import re
from collections import Counter, defaultdict

from django.db.models import Q

PEMDA_PREFIXES = ('PD', 'PV')
SCOPE_PREFIXES = {
    'ALL': PEMDA_PREFIXES,
    'PD': ('PD',),
    'PV': ('PV',),
}
KODE_RE = re.compile(r'^\d{4}$')


def is_valid_kode(kode):
    """A 4-digit kode whose jenis and sub halves are both 01-99."""
    return bool(KODE_RE.match(kode or '')) and kode[:2] != '00' and kode[2:] != '00'


def pemda_filter(prefixes, field='id_sub_jenis_data'):
    q = Q()
    for prefix in prefixes:
        q |= Q(**{f'{field}__startswith': prefix})
    return q


def kode_ids(id_ilap, kode):
    """(id_jenis_data, id_sub_jenis_data) for an ILAP code and a 4-digit kode."""
    id_jenis_data = f'{id_ilap}{kode[:2]}'
    return id_jenis_data, f'{id_jenis_data}{kode[2:]}'


def jenis_data_for_kode(kode, scope='ALL'):
    """Every PD/PV `JenisDataILAP` carrying `kode`, within `scope`."""
    from ..models.jenis_data_ilap import JenisDataILAP

    return (
        JenisDataILAP.objects
        .filter(pemda_filter(SCOPE_PREFIXES[scope]), id_sub_jenis_data__endswith=kode)
        .select_related('id_ilap')
        .order_by('id_sub_jenis_data')
    )


def kode_options():
    """Every 4-digit kode found under PD/PV, with a label and per-prefix counts.

    Pemda name the same kode slightly differently, so the label is the most
    common name among its rows.
    """
    from ..models.jenis_data_ilap import JenisDataILAP

    names = defaultdict(Counter)
    counts = defaultdict(Counter)
    rows = JenisDataILAP.objects.filter(pemda_filter(PEMDA_PREFIXES)).values_list(
        'id_sub_jenis_data', 'nama_sub_jenis_data'
    )
    for code, nama in rows:
        kode = code[-4:]
        if not KODE_RE.match(kode):
            continue
        counts[kode][code[:2]] += 1
        names[kode][(nama or '').strip().upper()] += 1

    options = []
    for kode in sorted(counts):
        label = next((n for n, _ in names[kode].most_common() if n), '')
        options.append({
            'kode': kode,
            'nama': label,
            'PD': counts[kode]['PD'],
            'PV': counts[kode]['PV'],
        })
    return options
