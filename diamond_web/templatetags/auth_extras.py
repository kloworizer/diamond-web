from django import template
from diamond_web.utils import format_periode
from diamond_web.utils.pic_profil import pic_profil_url as _pic_profil_url

register = template.Library()


@register.filter(name='pic_profil_url')
def pic_profil_url(user):
    """Return the Profil PIC URL of `user`, or an empty string when there is none.

    Lets a template link a name it already has the User for, without repeating
    the ``{% url %}`` call and the username lookup at every one of the dozen
    places a PIC name is printed.

    Args:
        user: A `User` instance, or ``None``.

    Returns:
        str: The URL, or ``''`` so ``{% if %}`` can fall back to plain text.
    """
    return _pic_profil_url(user) or ''

@register.filter(name='has_group')
def has_group(user, group_name):
    if user is not None and user.is_authenticated:
        return user.groups.filter(name=group_name).exists()
    return False
@register.filter(name='get_item')
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, '---')
    return '---'

@register.filter(name='format_periode_tiket')
def format_periode_tiket(tiket, include_year=True):
    """Format a Tiket object's periode using format_periode from utils.
    
    Uses tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
    as the period description (e.g., 'Triwulanan', 'Bulanan').
    
    Args:
        tiket: A Tiket model instance.
        include_year: If True (default), includes the year in output.
        
    Returns:
        Formatted period string like 'Triwulan II' or 'Triwulan II 2026'.
    """
    try:
        deskripsi = tiket.id_periode_data.id_periode_pengiriman.periode_penerimaan
    except AttributeError:
        deskripsi = ''
    return format_periode(deskripsi, tiket.periode, tiket.tahun, include_year=include_year)