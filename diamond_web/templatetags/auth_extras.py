from django import template
from diamond_web.utils import format_periode

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    if user.is_authenticated:
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