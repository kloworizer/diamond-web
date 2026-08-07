"""Helpers for pointing a person's name at their PIC profil page.

A name shows up all over the app — the PIC block of a tiket, the log of actions
on it, the PIC list of a sub jenis data or a nama tabel, the PIC PMDE column of
quality control — and until now it was always a dead end: the reader learnt who
was responsible but nothing about what else that person holds. These helpers
turn every one of those names into the same link, so the pages agree on where a
name leads.

Not every name is a link, though. A Profil PIC page may only be opened by the
person it is about and by whoever supervises their seksi — see
:func:`can_view_pic_profil` — so a name the reader may not follow is printed as
plain text instead of as a link they would only bounce off. Every helper that
renders a name therefore has to be told who is doing the reading.

Two forms are offered because the pages render names two ways. Templates use the
``pic_name_link`` tag (see ``auth_extras``), which reads the viewer off the
request; the DataTables endpoints, which build HTML strings server-side, take
the finished anchor from :func:`pic_profil_link` and pass the viewer's
predicate from :func:`pic_profil_visibility` explicitly.
"""
from django.contrib.auth.models import User
from django.db.models import Q
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


def _supervised_staff_groups(group_names):
    """Return the staff groups a member of `group_names` supervises.

    Args:
        group_names (set): The group names the viewer belongs to.

    Returns:
        list: The ``user_*`` group names of every seksi the viewer is a kasi or
        an admin of; empty for someone who supervises nothing.
    """
    return [
        seksi['user_group'] for seksi in PDE_SEKSI
        if seksi['kasi_group'] in group_names or seksi['admin_group'] in group_names
    ]


def visible_profil_pic_users(viewer):
    """Return the users `viewer` may open the Profil PIC page of.

    The line of supervision, and nothing wider:

    * superusers and the global `admin` group reach anyone;
    * a kasi or an admin of a seksi reaches the staff of that seksi — kasi PMDE
      reaches the user PMDE, and so on — plus themselves;
    * everyone else reaches only themselves.

    This is the whole rule. It governs the page, the tiket endpoint behind it,
    the header search that finds people, and whether a name printed elsewhere in
    the app is rendered as a link at all.

    Args:
        viewer (User): The person doing the looking, possibly anonymous.

    Returns:
        QuerySet: The users they may open, empty for an anonymous request.
    """
    if not viewer or not getattr(viewer, 'is_authenticated', False):
        return User.objects.none()

    group_names = set(viewer.groups.values_list('name', flat=True))
    if viewer.is_superuser or 'admin' in group_names:
        return User.objects.all()

    supervised = _supervised_staff_groups(group_names)
    if supervised:
        # Their own account is added on purpose: a kasi is not usually a member
        # of the staff group they supervise, and they should still reach it.
        return User.objects.filter(
            Q(groups__name__in=supervised) | Q(pk=viewer.pk)
        ).distinct()

    return User.objects.filter(pk=viewer.pk)


def pic_profil_visibility(viewer):
    """Return a predicate answering :func:`visible_profil_pic_users` per user.

    Resolves the rule once and returns a callable, so a page printing a hundred
    names asks the database once rather than once per name. Callers that only
    have a single user to test can use :func:`can_view_pic_profil` instead.

    Args:
        viewer (User): The person doing the looking, possibly anonymous.

    Returns:
        callable: ``(user) -> bool``, false for ``None``.
    """
    if not viewer or not getattr(viewer, 'is_authenticated', False):
        return lambda user: False

    group_names = set(viewer.groups.values_list('name', flat=True))
    if viewer.is_superuser or 'admin' in group_names:
        return lambda user: user is not None

    supervised = _supervised_staff_groups(group_names)
    if not supervised:
        return lambda user: user is not None and user.pk == viewer.pk

    allowed = set(
        User.objects.filter(groups__name__in=supervised).values_list('pk', flat=True)
    )
    allowed.add(viewer.pk)
    return lambda user: user is not None and user.pk in allowed


def request_pic_profil_visibility(request):
    """Return :func:`pic_profil_visibility` for `request`, cached on it.

    For callers that render names one row at a time and have no obvious place to
    hold the predicate — a per-row serializer, a template tag. Resolving the rule
    costs a query, and a page of rows should pay it once.

    Args:
        request (HttpRequest): The current request, or ``None``.

    Returns:
        callable: ``(user) -> bool``; refuses everything when there is no
        request, which is what the Excel export path passes.
    """
    if request is None:
        return lambda user: False
    predicate = getattr(request, '_pic_profil_visibility', None)
    if predicate is None:
        predicate = pic_profil_visibility(request.user)
        request._pic_profil_visibility = predicate
    return predicate


def can_view_pic_profil(viewer, target):
    """Return True when `viewer` may open the Profil PIC page of `target`.

    The single-user form of :func:`visible_profil_pic_users`. Answered without a
    query when the two are the same person, which is the common case on a page
    someone reached from their own name.

    Args:
        viewer (User): The person doing the looking, possibly anonymous.
        target (User): The person whose page is wanted, or ``None``.

    Returns:
        bool: Whether the page may be opened.
    """
    if target is None or not viewer or not getattr(viewer, 'is_authenticated', False):
        return False
    if viewer.pk == target.pk:
        return True
    return visible_profil_pic_users(viewer).filter(pk=target.pk).exists()


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


def pic_profil_link(user, can_view, label=None,
                    css_class='text-primary text-decoration-none'):
    """Return `user`'s name, linked to their Profil PIC page when permitted.

    For the DataTables endpoints, which hand the browser finished HTML. Both the
    label and the URL are escaped here, so callers pass raw values.

    `can_view` is required rather than defaulted so that a new caller has to
    decide who is reading: a silent default would either strip every link or
    offer every reader a page most of them may not open.

    Args:
        user (User): The user to name, or ``None``.
        can_view (callable): The predicate from :func:`pic_profil_visibility`,
            built once for the request the rows are being rendered for.
        label (str, optional): Link text; defaults to :func:`pic_display_name`.
        css_class (str, optional): Classes of the anchor.

    Returns:
        str: The anchor when the viewer may open the page, otherwise the escaped
        name on its own — the row still says who is responsible either way.
    """
    text = escape(label if label is not None else pic_display_name(user))
    if user is None or not can_view(user):
        return text
    return (
        f'<a href="{escape(pic_profil_url(user))}" class="{escape(css_class)}">'
        f'{text}</a>'
    )
