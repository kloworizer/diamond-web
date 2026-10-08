"""Allocation and formatting of `nomor_tanda_terima`.

The number is auto-generated and rendered read-only, but the browser still
posts it back, so it can be stale by the time it arrives: another user may
have taken it, or the user may have changed the date and moved the record
into a different year's series. `(nomor_tanda_terima, tahun_terima)` is
unique, so a stale value means an IntegrityError instead of a saved record.

Allocation therefore happens here, server-side, at save time. The posted
value is only ever a hint.

Seksi P3DE and Seksi P3DER keep separate series, each with its own kode in
the number (PJ.1031 / PJ.1032) and its own counter per year. Which seksi a
tanda terima belongs to follows its scope — see :func:`seksi_tanda_terima`.
"""

from django.db.models import Max

from ..models.sequence_tanda_terima import SequenceTandaTerima
from ..models.tanda_terima_data import TandaTerimaData


NOMOR_PREFIX_WIDTH = 5
NOMOR_TEMPLATE = "{nomor}.TTD/{kode}/{tahun}"
SEKSI_P3DE = TandaTerimaData.Seksi.P3DE
SEKSI_P3DER = TandaTerimaData.Seksi.P3DER
KODE_SEKSI = {
    SEKSI_P3DE: 'PJ.1031',
    SEKSI_P3DER: 'PJ.1032',
}


def seksi_tanda_terima(kanwil=None, ilap=None):
    """Return the seksi whose series a tanda terima with this scope belongs to.

    A Kanwil-scoped (regional) tanda terima pools Regional ILAP, so it is
    Seksi P3DER's. An ILAP-scoped one follows the ILAP's kategori wilayah:
    Regional -> P3DER, Nasional / Internasional -> P3DE.

    Args:
        kanwil: The Kanwil (or its pk), when the scope is regional.
        ilap: The ILAP (or its pk), when the scope is per ILAP.
    """
    from ..models.ilap import ILAP
    from ..views.mixins import SEKSI_P3DER as MIXIN_P3DER, p3de_seksi_of

    if kanwil:
        return SEKSI_P3DER
    if ilap is not None and not isinstance(ilap, ILAP):
        ilap = ILAP.objects.select_related('id_kategori_wilayah').filter(pk=ilap).first()
    if ilap is not None and p3de_seksi_of(ilap) == MIXIN_P3DER:
        return SEKSI_P3DER
    return SEKSI_P3DE


def format_nomor_tanda_terima(nomor, tahun, seksi=SEKSI_P3DE):
    """Render `nomor`/`tahun` as ``00001.TTD/PJ.1031/2026`` (P3DE) or ``…/PJ.1032/…`` (P3DER)."""
    return NOMOR_TEMPLATE.format(
        nomor=str(nomor).zfill(NOMOR_PREFIX_WIDTH),
        kode=KODE_SEKSI.get(seksi, KODE_SEKSI[SEKSI_P3DE]),
        tahun=tahun,
    )


def parse_nomor_tanda_terima(value, expected_tahun=None, expected_seksi=None):
    """Pull the sequence number out of a formatted string.

    Returns None when *value* is missing, unparseable, belongs to a
    different year than *expected_tahun*, or carries another seksi's kode
    than *expected_seksi* — a number from the 2026 series means nothing in
    the 2025 one, nor one from PJ.1031 in PJ.1032, so the caller should
    allocate a fresh one rather than carry it across.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        nomor = int(value.split('.')[0].strip())
    except (ValueError, IndexError, AttributeError):
        return None

    if expected_seksi is not None and f'/{KODE_SEKSI[expected_seksi]}/' not in value:
        return None

    if expected_tahun is not None:
        try:
            tahun = int(value.rsplit('/', 1)[-1].strip())
        except (ValueError, IndexError, AttributeError):
            return None
        if tahun != int(expected_tahun):
            return None

    return nomor


def next_nomor_tanda_terima(tahun, seksi=SEKSI_P3DE):
    """Next free sequence number for *tahun* in *seksi*'s series.

    Continues from the highest number already recorded for the seksi and
    year. When there are no records yet, an administrator-configured
    `SequenceTandaTerima` starting point is honoured, otherwise it starts
    at 1.
    """
    max_seq = TandaTerimaData.objects.filter(seksi=seksi, tahun_terima=tahun).aggregate(
        max_nomor=Max('nomor_tanda_terima')
    )['max_nomor'] or 0
    if max_seq > 0:
        return max_seq + 1

    seq_config = SequenceTandaTerima.objects.filter(seksi=seksi, tahun=tahun).first()
    if seq_config:
        return seq_config.nomor_terakhir + 1
    return 1


def allocate_nomor_tanda_terima(tahun, preferred=None, exclude_pk=None, seksi=SEKSI_P3DE):
    """Return a sequence number that is free for *tahun* in *seksi*'s series.

    Args:
        tahun: Year series to allocate within.
        seksi: Seksi series to allocate within (P3DE or P3DER).
        preferred: Number requested by the caller (parsed from the posted
            string). Honoured when it is still free, which keeps
            deliberately chosen numbers and gap-filling working.
        exclude_pk: Existing record to ignore when checking, so re-saving a
            record does not collide with itself.

    Returns:
        int: `preferred` when available, otherwise the next free number.
    """
    if preferred is not None and preferred > 0:
        taken = TandaTerimaData.objects.filter(
            seksi=seksi, tahun_terima=tahun, nomor_tanda_terima=preferred
        )
        if exclude_pk:
            taken = taken.exclude(pk=exclude_pk)
        if not taken.exists():
            return preferred

    return next_nomor_tanda_terima(tahun, seksi)
