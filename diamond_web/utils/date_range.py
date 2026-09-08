"""Reading the value a filter panel's date range picker sends.

The picker hands both ends of a range over in a single parameter, written
``"<start>..<end>"`` in ISO dates — so a filter that is a range rather than a
choice still travels as one value, and can sit in the same filter registries,
query strings and shareable URLs as the dropdowns beside it.

Either half may be left empty, which leaves that end of the range open.
"""

from datetime import datetime


def parse_iso_date(value):
    """Read one ISO date (``YYYY-MM-DD``), or None if missing or malformed."""
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_date_range(raw):
    """Read a ``"<start>..<end>"`` value into a `(start, end)` pair of dates.

    An unreadable half is dropped rather than matching nothing: a malformed
    date is a broken request, not a request for no rows.
    """
    start, _, end = (raw or '').partition('..')
    return parse_iso_date(start), parse_iso_date(end)


def filter_date_range(qs, field, bounds):
    """Narrow `qs` to rows whose `field` falls within `bounds`, inclusive.

    Compared on the date alone, so the last day of a range is included whatever
    time of day the timestamp carries.
    """
    start, end = bounds
    if start:
        qs = qs.filter(**{f'{field}__date__gte': start})
    if end:
        qs = qs.filter(**{f'{field}__date__lte': end})
    return qs
