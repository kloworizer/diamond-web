"""Helpers for pointing a person's name at their PIC profil page.

A name shows up all over the app — the PIC block of a tiket, the log of actions
on it, the PIC list of a sub jenis data or a nama tabel, the PIC PMDE column of
quality control — and until now it was always a dead end: the reader learnt who
was responsible but nothing about what else that person holds. These helpers
turn every one of those names into the same link, so the pages agree on where a
name leads.

Two forms are offered because the pages render names two ways. Templates take
the URL from the ``pic_profil_url`` filter (see ``auth_extras``) and write their
own markup; the DataTables endpoints, which build HTML strings server-side, take
the finished anchor from :func:`pic_profil_link`.
"""
from django.urls import reverse
from django.utils.html import escape


# Group names carry the unit and the rank in one string, which is right for a
# permission check and wrong on a profile page. The labels below are what a
# reader is told instead; a group absent from the map is shown as recorded, so
# a new group does not disappear from the page before anyone names it here.
SEKSI_LABELS = {
    'admin': 'Administrator',
    'admin_p3de': 'Admin P3DE',
    'admin_pide': 'Admin PIDE',
    'admin_pmde': 'Admin PMDE',
    'kasi_p3de': 'Kepala Seksi P3DE',
    'kasi_pide': 'Kepala Seksi PIDE',
    'kasi_pmde': 'Kepala Seksi PMDE',
    'user_p3de': 'Seksi P3DE',
    'user_pide': 'Seksi PIDE',
    'user_pmde': 'Seksi PMDE',
}


# The three seksi of PDE, in the order the workflow moves a tiket through them.
# Each names the groups that stand in the three relations to it: the staff who
# work in it, the kasi who supervises it, and the admin who administers it. The
# staff directory reads the first, the search visibility rule reads all three.
PDE_SEKSI = (
    {
        'kode': 'P3DE',
        'label': 'Seksi P3DE',
        'user_group': 'user_p3de',
        'kasi_group': 'kasi_p3de',
        'admin_group': 'admin_p3de',
    },
    {
        'kode': 'PIDE',
        'label': 'Seksi PIDE',
        'user_group': 'user_pide',
        'kasi_group': 'kasi_pide',
        'admin_group': 'admin_pide',
    },
    {
        'kode': 'PMDE',
        'label': 'Seksi PMDE',
        'user_group': 'user_pmde',
        'kasi_group': 'kasi_pmde',
        'admin_group': 'admin_pmde',
    },
)

# The groups that administer the application rather than work a seksi's queue.
# An administrator is routinely a member of the staff groups as well — the
# `admin` account of this deployment is in all three — so membership of a staff
# group alone does not make someone staff, and the directory subtracts these.
ADMIN_GROUPS = ('admin',) + tuple(seksi['admin_group'] for seksi in PDE_SEKSI)


def seksi_label(group_name):
    """Return the readable unit label of `group_name`.

    Args:
        group_name (str): A Django group name, e.g. ``user_pide``.

    Returns:
        str: The label from :data:`SEKSI_LABELS`, or `group_name` itself when
        the group is not one of the known units.
    """
    return SEKSI_LABELS.get(group_name, group_name)


def pic_display_name(user):
    """Return the name to show for `user`.

    Args:
        user (User): The user to name, or ``None``.

    Returns:
        str: Full name when one is recorded, the username otherwise, and an
        empty string for ``None`` — callers rendering a missing PIC decide for
        themselves what stands in its place.
    """
    if user is None:
        return ''
    return (user.get_full_name() or '').strip() or user.username


def pic_profil_url(user):
    """Return the profil PIC URL of `user`, or ``None`` when there is no user.

    Keyed by username rather than by primary key: the profil pages of this app
    are all reached by the business identifier of the thing they describe, and
    a username is what a reader recognises in a URL they copied out of a chat.

    Args:
        user (User): The user to link to, ``None``, or an anonymous user — the
            navbar renders on every page, including the ones served before
            anybody has logged in.

    Returns:
        str|None: The URL, or ``None`` so templates can fall back to plain text.
    """
    # An AnonymousUser has a blank username, which the URL pattern would refuse
    # to reverse; there is no profile behind it either way.
    if user is None or not getattr(user, 'username', ''):
        return None
    return reverse('profil_pic_detail', args=[user.username])


def pic_profil_link(user, label=None, css_class='text-primary text-decoration-none'):
    """Return an escaped anchor to the profil PIC page of `user`.

    For the DataTables endpoints, which hand the browser finished HTML. Both
    the label and the URL are escaped here, so callers pass raw values.

    Args:
        user (User): The user to link to, or ``None``.
        label (str, optional): Link text; defaults to :func:`pic_display_name`.
        css_class (str, optional): Classes of the anchor.

    Returns:
        str: The anchor, or the escaped label alone when `user` is ``None`` —
        a row without a PIC still shows whatever the caller wanted to say.
    """
    text = escape(label if label is not None else pic_display_name(user))
    if user is None:
        return text
    return (
        f'<a href="{escape(pic_profil_url(user))}" class="{escape(css_class)}">'
        f'{text}</a>'
    )
