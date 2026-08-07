from django import template
from django.utils.html import format_html

from diamond_web.utils import format_periode
from diamond_web.utils.pic_profil import (
    pic_display_name,
    pic_profil_url as _pic_profil_url,
    request_pic_profil_visibility,
)

register = template.Library()


def _visibility(context):
    """Return the viewer's Profil PIC predicate for the request being rendered.

    A page prints a name in many places — the PIC block, the whole action log, a
    directory column — and the rule costs a query, so it is resolved once per
    request rather than once per name.
    """
    return request_pic_profil_visibility(context.get('request'))


@register.simple_tag(takes_context=True)
def pic_name_link(context, user, label=None,
                  css_class='text-primary text-decoration-none'):
    """Render a PIC's name, linked to their profile when the viewer may open it.

    A Profil PIC page is readable by the person it is about and by whoever
    supervises their seksi. This tag is how a template prints a name without
    having to know that: the reader who may follow the name gets a link, and the
    reader who may not gets the same name as plain text rather than a link that
    would only refuse them.

    Args:
        user: A `User` instance, or ``None``.
        label (str, optional): Text to show; defaults to the user's full name,
            falling back to their username.
        css_class (str, optional): Classes of the anchor.

    Returns:
        str: Escaped HTML — an anchor, or the bare name.
    """
    text = label if label is not None else pic_display_name(user)
    url = _pic_profil_url(user) if user is not None else None
    if not url or not _visibility(context)(user):
        return text
    return format_html(
        '<a href="{}" class="{}" title="Lihat profil PIC">{}</a>',
        url, css_class, text,
    )


@register.simple_tag(takes_context=True)
def can_view_pic_profil(context, user):
    """Return whether the viewer may open `user`'s Profil PIC page.

    For the few places that need the answer without rendering the name — a
    directory entry whose whole card is the link, for instance.
    """
    return _visibility(context)(user)


@register.filter(name='pic_profil_url')
def pic_profil_url(user):
    """Return the Profil PIC URL of `user`, or ``''`` when there is none.

    Builds the URL and nothing else — it does **not** ask whether the viewer may
    open that page. Use it only where the target is the viewer themselves, such
    as the navbar's own-profile link, which is always permitted. Anywhere a
    template prints somebody else's name, use ``pic_name_link``, which asks.

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