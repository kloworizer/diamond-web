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


def format_number_with_separator(value):
    """Format a number with thousand separator using dot as per Indonesian convention.
    
    Converts numbers like 1000 to 1.000, 1000000 to 1.000.000, etc.
    
    Args:
        value: An integer, float, or None to format.
        
    Returns:
        Formatted string with thousand separators (using dot), or '-' for None/invalid.
    """
    if value is None or value == '-':
        return '-'
    try:
        return f"{int(value):,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return str(value)


def _to_roman_numeral(num):
    """Convert an integer to Roman numeral representation.
    
    Supports numbers 1-3999. Used for formatting periods like Semester I, Triwulan II, etc.
    
    Args:
        num: Integer to convert (1-3999).
        
    Returns:
        Roman numeral string (e.g., 'I', 'II', 'III', 'IV', 'V', etc.).
    """
    val = [
        1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,
        1
    ]
    syms = [
        'M', 'CM', 'D', 'CD',
        'C', 'XC', 'L', 'XL',
        'X', 'IX', 'V', 'IV',
        'I'
    ]
    roman_num = ''
    i = 0
    num = int(num)
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num


def format_periode(deskripsi_periode, periode, tahun, include_year=True):
    """Format period description into human-readable date range string.

    Converts numeric periodo values and descriptions into readable format.
    Supports Indonesian period types with Roman numerals for semester, triwulan, and kuartal.
    
    Examples:
        - (Bulanan, 3, 2026) -> 'Maret 2026'
        - (Bulanan, 3, 2026, include_year=False) -> 'Maret'
        - (Semester, 2, 2026) -> 'Semester II 2026'
        - (Semester, 2, 2026, include_year=False) -> 'Semester II'
        - (Triwulan, 3, 2026) -> 'Triwulan III 2026'
        - (Mingguan, 5, 2026) -> 'Minggu 5 2026'

    Args:
        deskripsi_periode (str): Period type (Harian, Mingguan, Bulanan, 
            Semester, Triwulanan, Kuartal, etc.)
        periode (int): Numeric period value (day, week, month number, etc.)
        tahun (int): Year value
        include_year (bool): Whether to include the year in the output (default: True)

    Returns:
        str: Human-readable period string
    """
    bulan_names = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ]
    
    year_suffix = f" {tahun}" if include_year else ""
    
    if deskripsi_periode == 'Harian':
        return f'Hari {periode}{year_suffix}'
    elif deskripsi_periode == 'Mingguan':
        return f'Minggu {periode}{year_suffix}'
    elif deskripsi_periode == '2 Mingguan':
        return f'2 Minggu {periode}{year_suffix}'
    elif deskripsi_periode == 'Bulanan':
        if 1 <= periode <= 12:
            return f'{bulan_names[periode - 1]}{year_suffix}'
        return f'Bulan {periode}{year_suffix}'
    elif deskripsi_periode == 'Triwulanan':
        roman = _to_roman_numeral(periode)
        return f'Triwulan {roman}{year_suffix}'
    elif deskripsi_periode == 'Kuartal':
        roman = _to_roman_numeral(periode)
        return f'Kuartal {roman}{year_suffix}'
    elif deskripsi_periode == 'Semester':
        roman = _to_roman_numeral(periode)
        return f'Semester {roman}{year_suffix}'
    elif deskripsi_periode == 'Tahunan':
        return str(tahun)
    else:
        return f'{periode}{year_suffix}'
