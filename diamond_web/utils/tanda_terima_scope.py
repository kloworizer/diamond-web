"""Scope helpers for Tanda Terima.

A tanda terima is recorded either per Kanwil (regional ILAP — kategori PV and
PD) or per ILAP (nasional/internasional), optionally narrowed to a single ND
Pengantar. Resolving "which tikets belong to this scope" is needed by the
form, by its AJAX endpoints and by the validation path, so it lives here.

Regional ILAP reach a Kanwil through two different shapes:
``ILAPKPP.id_kanwil`` when the ILAP has no KPP counterpart (kategori PV), and
``ILAPKPP.id_kpp.id_kanwil`` otherwise (kategori PD). Every query below covers
both.
"""

from django.db.models import Q

from ..constants.tiket_status import STATUS_DIKIRIM_KE_PIDE
from ..models.detil_tanda_terima import DetilTandaTerima
from ..models.ilap import ILAP
from ..models.tanda_terima_data import TandaTerimaData
from ..models.tiket import Tiket
from ..models.tiket_pic import TiketPIC
from .wilayah import TIKET_ILAP_PATH, ilap_in_kanwil_q, tiket_in_kanwil_q  # noqa: F401


LINGKUP_REGIONAL = 'regional'
LINGKUP_NASIONAL = 'nasional'
LINGKUP_CHOICES = [
    (LINGKUP_REGIONAL, 'Regional — per Kanwil'),
    (LINGKUP_NASIONAL, 'Nasional/Internasional — per ILAP'),
]

_TIKET_ILAP_PATH = TIKET_ILAP_PATH


def is_regional_ilap(ilap):
    """True when the ILAP is mapped to a wilayah (kategori PV or PD)."""
    if ilap is None:
        return False
    return ilap.ilap_kpp_relations.exists()


def regional_ilap_queryset():
    """ILAP that are mapped to a Kanwil, directly or through a KPP."""
    return ILAP.objects.filter(ilap_kpp_relations__isnull=False).distinct()


def nasional_ilap_queryset():
    """ILAP without any wilayah mapping — nasional/internasional."""
    return ILAP.objects.filter(ilap_kpp_relations__isnull=True)


def assigned_tiket_ids(kanwil_id=None, ilap_id=None, exclude_tanda_terima_id=None):
    """IDs of tikets already covered by an active tanda terima in this scope.

    A tiket blocked inside one Kanwil (or one ILAP) is still selectable from
    another scope, which mirrors how the per-ILAP rule worked before.
    """
    qs = DetilTandaTerima.objects.filter(id_tanda_terima__active=True)
    if kanwil_id:
        qs = qs.filter(id_tanda_terima__id_kanwil_id=kanwil_id)
    elif ilap_id:
        qs = qs.filter(id_tanda_terima__id_ilap_id=ilap_id)
    else:
        return set()

    if exclude_tanda_terima_id:
        qs = qs.exclude(id_tanda_terima_id=exclude_tanda_terima_id)
    return set(qs.values_list('id_tiket_id', flat=True))


def scoped_tiket_queryset(
    kanwil_id=None,
    ilap_id=None,
    nomor_nd_pengantar=None,
    user=None,
    exclude_tanda_terima_id=None,
    max_status=STATUS_DIKIRIM_KE_PIDE,
):
    """Tikets selectable for a tanda terima in the given scope.

    Args:
        kanwil_id: Kanwil primary key for the regional flow.
        ilap_id: ILAP primary key for the nasional/internasional flow.
        nomor_nd_pengantar: Optional exact ND Pengantar to narrow the result.
        user: When given and not an admin, restrict to tikets where the user
            is an active P3DE PIC.
        exclude_tanda_terima_id: Tanda terima being edited, whose own tikets
            must stay available.
        max_status: Upper (exclusive) bound on `status_tiket`.

    Returns:
        QuerySet of `Tiket`, empty when no scope is supplied.
    """
    if not kanwil_id and not ilap_id:
        return Tiket.objects.none()

    # `tanda_terima` is the authoritative "receipt already handled" marker. It
    # also covers tikets marked "Tidak Diterbitkan", which are flagged without
    # ever getting a DetilTandaTerima row and would otherwise stay listed.
    # Cancelling a tanda terima resets the flag, freeing the tiket again.
    qs = Tiket.objects.filter(status_tiket__lt=max_status, tanda_terima=False)
    if kanwil_id:
        qs = qs.filter(tiket_in_kanwil_q(kanwil_id))
    else:
        qs = qs.filter(**{f'{_TIKET_ILAP_PATH}_id': ilap_id})

    if nomor_nd_pengantar:
        qs = qs.filter(nomor_surat_pengantar=nomor_nd_pengantar)

    qs = qs.exclude(id__in=assigned_tiket_ids(
        kanwil_id=kanwil_id,
        ilap_id=ilap_id,
        exclude_tanda_terima_id=exclude_tanda_terima_id,
    ))

    if user is not None and not (user.is_superuser or user.groups.filter(name='admin').exists()):
        qs = qs.filter(
            tiketpic__id_user=user,
            tiketpic__active=True,
            tiketpic__role=TiketPIC.Role.P3DE,
        )

    return qs.distinct()


def nd_pengantar_options(**kwargs):
    """Distinct, sorted ND Pengantar numbers among the scoped tikets."""
    kwargs.pop('nomor_nd_pengantar', None)
    # `order_by()` clears Tiket's default ordering, which would otherwise be
    # added to the SELECT and defeat DISTINCT.
    values = (
        scoped_tiket_queryset(**kwargs)
        .exclude(nomor_surat_pengantar='')
        .order_by()
        .values_list('nomor_surat_pengantar', flat=True)
        .distinct()
    )
    return sorted({value for value in values if value})


def kanwil_ids_with_available_tiket(user=None, max_status=STATUS_DIKIRIM_KE_PIDE):
    """Kanwil primary keys that still have at least one selectable tiket."""
    qs = Tiket.objects.filter(status_tiket__lt=max_status, tanda_terima=False).exclude(
        id__in=DetilTandaTerima.objects.filter(
            id_tanda_terima__active=True,
            id_tanda_terima__id_kanwil__isnull=False,
        ).values_list('id_tiket_id', flat=True)
    )
    if user is not None and not (user.is_superuser or user.groups.filter(name='admin').exists()):
        qs = qs.filter(
            tiketpic__id_user=user,
            tiketpic__active=True,
            tiketpic__role=TiketPIC.Role.P3DE,
        )

    direct = qs.values_list(
        f'{_TIKET_ILAP_PATH}__ilap_kpp_relations__id_kanwil_id', flat=True
    )
    via_kpp = qs.values_list(
        f'{_TIKET_ILAP_PATH}__ilap_kpp_relations__id_kpp__id_kanwil_id', flat=True
    )
    return {pk for pk in list(direct) + list(via_kpp) if pk}


def tanda_terima_scope_kwargs(tanda_terima):
    """Scope kwargs describing an existing `TandaTerimaData` record."""
    if not isinstance(tanda_terima, TandaTerimaData):
        return {}
    return {
        'kanwil_id': tanda_terima.id_kanwil_id,
        'ilap_id': tanda_terima.id_ilap_id,
        'nomor_nd_pengantar': tanda_terima.nomor_nd_pengantar or None,
    }
