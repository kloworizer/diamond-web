"""Filtering a timestamp column by the stretch of time a filter panel asks for.

Two shapes of question, both over the same column: a range picker, which hands
both ends over in a single parameter written ``"<start>..<end>"`` in ISO dates —
so a filter that is a range rather than a choice still travels as one value, and
sits in the same filter registries, query strings and shareable URLs as the
dropdowns beside it — and a plain list of years.

Either half of a range may be left empty, which leaves that end open.

Both are turned into half-open comparisons against the bare column
(``>= start of day``, ``< start of the day after``) rather than the ``__date``
and ``__year`` lookups that read more naturally: those wrap the column in a
function, which costs the index on it. On the tiket list — 48k rows, seven
querysets rebuilt on every dropdown change — that is the difference between
~0.2s per queryset and none.
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Q


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

    Both ends are whole days: the last day of a range is included whatever time
    of day its timestamp carries, since the upper bound is the start of the day
    after it.
    """
    start, end = bounds
    if start:
        qs = qs.filter(**{f'{field}__gte': datetime.combine(start, time.min)})
    if end:
        qs = qs.filter(**{f'{field}__lt': datetime.combine(end + timedelta(days=1), time.min)})
    return qs


def parse_years(values):
    """The years among `values`, dropping anything that is not a usable one.

    A year outside what a date can hold is dropped along with the non-numeric
    input, so the caller only ever sees years it can build a span from.
    """
    years = []
    for value in values:
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        if date.min.year <= year < date.max.year:
            years.append(year)
    return years


def filter_years(qs, field, years):
    """Narrow `qs` to rows whose `field` falls in one of `years`.

    `years` must already be parsed — see `parse_years` — and non-empty: an empty
    list adds no clause and so returns `qs` untouched, which is *not* what a
    year filter nothing could be read from should match. That case is the
    caller's to decide, and both panels answer it with `qs.none()`, the way
    their own year dropdowns already do.
    """
    spans = Q()
    for year in years:
        spans |= Q(**{
            f'{field}__gte': datetime(year, 1, 1),
            f'{field}__lt': datetime(year + 1, 1, 1),
        })
    return qs.filter(spans) if years else qs
