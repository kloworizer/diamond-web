"""Utility functions and helpers for the diamond_web application."""

from datetime import datetime
from django.core.exceptions import ValidationError


def validate_not_future_datetime(value, field_label="Tanggal/waktu"):
    """Raise ``ValidationError`` if *value* is a future datetime.

    Compares *value* against the current local server time using
    ``datetime.now()``.  Because the project has ``USE_TZ = False``, all
    datetime values in the database are stored as-is in GMT+7 (the server
    timezone), so a plain ``datetime.now()`` comparison is correct.

    Args:
        value: A :class:`datetime` object to validate.  ``None`` is
            accepted and returned unchanged (let the field's own
            ``required`` validation handle missing values).
        field_label: Human-readable field name used in the error message.

    Returns:
        The original *value* when it does not exceed the current time.

    Raises:
        ValidationError: When *value* is strictly greater than
            ``datetime.now()``.
    """
    if value is None:
        return value
    now = datetime.now()
    if value > now:
        raise ValidationError(
            f"{field_label} tidak boleh lebih dari waktu saat ini "
            f"({now.strftime('%d-%m-%Y %H:%M')})."
        )
    return value
