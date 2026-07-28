"""Allocation and formatting of `nomor_tanda_terima`.

The number is auto-generated and rendered read-only, but the browser still
posts it back, so it can be stale by the time it arrives: another user may
have taken it, or the user may have changed the date and moved the record
into a different year's series. `(nomor_tanda_terima, tahun_terima)` is
unique, so a stale value means an IntegrityError instead of a saved record.

Allocation therefore happens here, server-side, at save time. The posted
value is only ever a hint.
"""

from django.db.models import Max

from ..models.sequence_tanda_terima import SequenceTandaTerima
from ..models.tanda_terima_data import TandaTerimaData


NOMOR_PREFIX_WIDTH = 5
NOMOR_TEMPLATE = "{nomor}.TTD/PJ.1031/{tahun}"


def format_nomor_tanda_terima(nomor, tahun):
    """Render `nomor`/`tahun` as ``00001.TTD/PJ.1031/2026``."""
    return NOMOR_TEMPLATE.format(
        nomor=str(nomor).zfill(NOMOR_PREFIX_WIDTH),
        tahun=tahun,
    )


def parse_nomor_tanda_terima(value, expected_tahun=None):
    """Pull the sequence number out of a formatted string.

    Returns None when *value* is missing, unparseable, or belongs to a
    different year than *expected_tahun* — a number from the 2026 series
    means nothing in the 2025 one, so the caller should allocate a fresh
    one rather than carry it across.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        nomor = int(value.split('.')[0].strip())
    except (ValueError, IndexError, AttributeError):
        return None

    if expected_tahun is not None:
        try:
            tahun = int(value.rsplit('/', 1)[-1].strip())
        except (ValueError, IndexError, AttributeError):
            return None
        if tahun != int(expected_tahun):
            return None

    return nomor


def next_nomor_tanda_terima(tahun):
    """Next free sequence number for *tahun*.

    Continues from the highest number already recorded for the year. When
    the year has no records yet, an administrator-configured
    `SequenceTandaTerima` starting point is honoured, otherwise it starts
    at 1.
    """
    max_seq = TandaTerimaData.objects.filter(tahun_terima=tahun).aggregate(
        max_nomor=Max('nomor_tanda_terima')
    )['max_nomor'] or 0
    if max_seq > 0:
        return max_seq + 1

    seq_config = SequenceTandaTerima.objects.filter(tahun=tahun).first()
    if seq_config:
        return seq_config.nomor_terakhir + 1
    return 1


def allocate_nomor_tanda_terima(tahun, preferred=None, exclude_pk=None):
    """Return a sequence number that is free for *tahun*.

    Args:
        tahun: Year series to allocate within.
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
            tahun_terima=tahun, nomor_tanda_terima=preferred
        )
        if exclude_pk:
            taken = taken.exclude(pk=exclude_pk)
        if not taken.exists():
            return preferred

    return next_nomor_tanda_terima(tahun)
