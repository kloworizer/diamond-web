"""Helpers for resolving the wilayah (Kanwil) an ILAP or Tiket belongs to.

Regional ILAP reach a Kanwil through two different shapes. ILAP with kategori
``PD`` (Pemerintah Daerah Kabupaten/Kota) map to a KPP, which in turn belongs
to a Kanwil. ILAP with kategori ``PV`` (Pemerintah Daerah Provinsi) have no
KPP counterpart at all and are mapped straight to a Kanwil — that is what the
``ILAPKPP.kpp`` flag distinguishes. Any query that goes "give me everything in
this Kanwil" therefore has to cover both paths, which is what these helpers do.
"""

from django.db.models import Q


ILAP_RELATION_PATH = 'ilap_kpp_relations'
TIKET_ILAP_PATH = 'id_periode_data__id_sub_jenis_data_ilap__id_ilap'
TIKET_RELATION_PATH = f'{TIKET_ILAP_PATH}__{ILAP_RELATION_PATH}'


def kanwil_q(kanwil_ids, prefix=ILAP_RELATION_PATH):
    """Q covering both the direct and the via-KPP Kanwil paths.

    Args:
        kanwil_ids: A single Kanwil primary key, or any iterable of them.
        prefix: Query path leading to the `ILAPKPP` relation from whatever
            model is being filtered.
    """
    if isinstance(kanwil_ids, (list, tuple, set, frozenset)):
        suffix, value = '__in', list(kanwil_ids)
    else:
        suffix, value = '', kanwil_ids
    return (
        Q(**{f'{prefix}__id_kanwil__id{suffix}': value})
        | Q(**{f'{prefix}__id_kpp__id_kanwil__id{suffix}': value})
    )


def ilap_in_kanwil_q(kanwil_ids, prefix=ILAP_RELATION_PATH):
    """Q object matching `ILAP` rows belonging to the given Kanwil id(s)."""
    return kanwil_q(kanwil_ids, prefix=prefix)


def tiket_in_kanwil_q(kanwil_ids, prefix=TIKET_RELATION_PATH):
    """Q object matching `Tiket` rows whose ILAP belongs to the Kanwil id(s)."""
    return kanwil_q(kanwil_ids, prefix=prefix)


def kanwil_value_paths(prefix=TIKET_RELATION_PATH):
    """Field paths yielding ``(id, kode, nama)`` of a Kanwil, per mapping shape.

    Returns a list of two triples — one for the direct mapping and one for
    the mapping through a KPP — so callers can union both result sets.
    """
    return [
        (
            f'{prefix}__id_kanwil__id',
            f'{prefix}__id_kanwil__kode_kanwil',
            f'{prefix}__id_kanwil__nama_kanwil',
        ),
        (
            f'{prefix}__id_kpp__id_kanwil__id',
            f'{prefix}__id_kpp__id_kanwil__kode_kanwil',
            f'{prefix}__id_kpp__id_kanwil__nama_kanwil',
        ),
    ]
