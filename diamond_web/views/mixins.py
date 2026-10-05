from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.db.models import Q
from django.utils import timezone
from ..models.tiket_pic import TiketPIC


class AjaxLoginRequiredMixin(LoginRequiredMixin):
    """Extend ``LoginRequiredMixin`` to return a proper 401 JSON response
    for AJAX (``X-Requested-With: XMLHttpRequest``) requests.

    Django's default ``LoginRequiredMixin`` always returns a 302 redirect to
    the login page, even for AJAX requests.  This causes the front-end fetch
    wrapper to receive a 302 \u2192 HTML redirect body instead of a JSON
    response, which in turn makes "modal gagal muat form" appear when the
    session has expired mid-page.

    By returning **401** for AJAX calls, the global fetch wrapper in
    ``base.html`` can correctly detect session expiry (401 = unauthenticated)
    and trigger the session-expired UI instead of silently failing.
    """

    def handle_no_permission(self):
        """Return 401 JSON for AJAX requests; redirect for regular page loads.

        Returns:
            JsonResponse: 401 with ``{\"error\": \"Sesi telah berakhir. Silakan login kembali.\"}``
            for AJAX requests.
            HttpResponseRedirect: Redirect to the login page for non-AJAX
            requests (standard Django behaviour).
        """
        request = getattr(self, 'request', None)
        if request is not None and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'error': 'Sesi telah berakhir. Silakan login kembali.'},
                status=401
            )
        return super().handle_no_permission()

class AdminRequiredMixin(UserPassesTestMixin):
    """Require membership in the `admin` group.

    Use this mixin on class-based views to restrict access to users who
    belong to the `admin` group. It delegates to Django's
    `UserPassesTestMixin` and implements `test_func`.
    """
    raise_exception = True

    def test_func(self):
        return self.request.user.groups.filter(name='admin').exists()


class AdminAnyRequiredMixin(UserPassesTestMixin):
    """Require membership in any admin group (admin, admin_p3de, admin_p3der, admin_pide, admin_pmde).

    Use this mixin on base class-based views that should be accessible to any
    administrator. This provides a safety layer for base views that might be
    accessed directly, ensuring that only admin-level users can access them.
    Subclasses can further restrict to specific admin roles via more specific
    mixins (e.g., AdminP3DERequiredMixin for P3DE-only views).
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to any admin group.

        Returns:
            bool: True if the user is a member of the ``admin``,
            ``admin_p3de``, ``admin_p3der``, ``admin_pide``, or ``admin_pmde`` group.
        """
        return self.request.user.groups.filter(
            name__in=['admin', *P3DE_ADMIN_GROUPS, 'admin_pide', 'admin_pmde']
        ).exists()


class AdminP3DERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin`, `admin_p3de` or `admin_p3der`.

    Intended for views that should be accessible by central admins and the
    administrators of either P3DE seksi (P3DE and P3DER), such as the shared
    reference data. Views that touch per-ILAP rows narrow further by seksi.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to ``admin``, ``admin_p3de`` or ``admin_p3der``.

        Returns:
            bool: True if the user is a member of one of those groups.
        """
        return self.request.user.groups.filter(name__in=['admin', *P3DE_ADMIN_GROUPS]).exists()


class AdminPIDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `admin_pide` groups.

    Use this for views that should be reachable by global admins and PIDE
    administrators.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to the ``admin`` or ``admin_pide`` group.

        Returns:
            bool: True if the user is a member of either group.
        """
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide']).exists()


class AdminPMDERequiredMixin(UserPassesTestMixin):
    """Require membership in the ``admin`` or ``admin_pmde`` groups.

    Use this mixin for views that should be accessible by global admins and
    PMDE administrators.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to the ``admin`` or ``admin_pmde`` group.

        Returns:
            bool: True if the user is a member of either group.
        """
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde']).exists()


class UserP3DERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or one of the P3DE / P3DER groups.

    This mixin is used when both administrative and regular P3DE users
    should be allowed access. If the request is AJAX and the user lacks
    permission, a JSON 403 response is returned to keep the client-side
    flow simple; otherwise the standard `handle_no_permission` path is
    taken.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to an allowed group.

        Allowed groups are ``admin`` and the admin, user and kasi groups of
        both P3DE seksi (``*_p3de`` and ``*_p3der``).

        Returns:
            bool: True if the user is a member of one of the allowed groups.
        """
        return self.request.user.groups.filter(name__in=['admin', *P3DE_GROUPS]).exists()

    def handle_no_permission(self):
        """Handle unauthorized access for P3DE users.

        Returns a JSON 403 response for AJAX requests; otherwise falls back
        to the standard ``handle_no_permission`` behavior.

        Returns:
            JsonResponse or HttpResponse: A JSON 403 response for AJAX
            requests, or the result of the parent ``handle_no_permission``.
        """
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class UserPIDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `user_pide` groups.

    Similar to `UserP3DERequiredMixin` but for PIDE users. Returns a JSON
    403 for AJAX requests when permission is denied, otherwise falls back
    to the standard `handle_no_permission` behavior.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to an allowed group.

        Allowed groups are ``admin``, ``admin_pide``, ``user_pide``, and ``kasi_pide``.

        Returns:
            bool: True if the user is a member of one of the allowed groups.
        """
        return self.request.user.groups.filter(name__in=['admin', 'admin_pide', 'user_pide', 'kasi_pide']).exists()

    def handle_no_permission(self):
        """Handle unauthorized access for PIDE users.

        Returns a JSON 403 response for AJAX requests; otherwise falls back
        to the standard ``handle_no_permission`` behavior.

        Returns:
            JsonResponse or HttpResponse: A JSON 403 response for AJAX
            requests, or the result of the parent ``handle_no_permission``.
        """
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class UserPMDERequiredMixin(UserPassesTestMixin):
    """Require membership in `admin` or `user_pmde` groups.

    Similar to `UserP3DERequiredMixin` but for PMDE users. Returns a JSON
    403 for AJAX requests when permission is denied, otherwise falls back
    to the standard `handle_no_permission` behavior.
    """
    raise_exception = True

    def test_func(self):
        """Check whether the current user belongs to an allowed group.

        Allowed groups are ``admin``, ``admin_pmde``, ``user_pmde``, and ``kasi_pmde``.

        Returns:
            bool: True if the user is a member of one of the allowed groups.
        """
        return self.request.user.groups.filter(name__in=['admin', 'admin_pmde', 'user_pmde', 'kasi_pmde']).exists()

    def handle_no_permission(self):
        """Handle unauthorized access for PMDE users.

        Returns a JSON 403 response for AJAX requests; otherwise falls back
        to the standard ``handle_no_permission`` behavior.

        Returns:
            JsonResponse or HttpResponse: A JSON 403 response for AJAX
            requests, or the result of the parent ``handle_no_permission``.
        """
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": "Forbidden"}, status=403)
        return super().handle_no_permission()


class ActiveTiketPICRequiredMixin(UserPassesTestMixin):
    """Allow access to admins or active PICs assigned to a tiket.

    This mixin resolves the tiket instance either from `self.object` or by
    calling `get_object()`. Administrators and superusers are always
    allowed. For other users, the method verifies that the user has an
    active `TiketPIC` assignment for the tiket with one of the allowed
    roles (P3DE, PIDE, PMDE).
    """
    def test_func(self):
        """Check whether the current user can access a tiket.

        Superusers and ``admin`` group members are always allowed. Other
        authenticated users must have an active ``TiketPIC`` assignment
        for the tiket with one of the allowed roles (P3DE, PIDE, PMDE).

        Returns:
            bool: True if the user is permitted to access the tiket.
        """
        user = self.request.user
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True
        tiket = getattr(self, 'object', None)
        if tiket is None:
            try:
                tiket = self.get_object()
            except Exception:
                return False
        return TiketPIC.objects.filter(
            id_tiket=tiket,
            id_user=user,
            active=True,
            role__in=[TiketPIC.Role.P3DE, TiketPIC.Role.PIDE, TiketPIC.Role.PMDE]
        ).exists()


class ActiveTiketPICRequiredForEditMixin(UserPassesTestMixin):
    """Require active PIC assignment to allow edit operations on tiket-related objects.

    The mixin supports views where the tiket primary key may be provided via
    `kwargs['tiket_pk']`, `self.tiket_pk`, or resolved from the view's
    `get_object()` result. Superusers and `admin` group members are
    always permitted. When the permission check fails during an AJAX
    request, a JSON 403 response is returned; otherwise an HTTP 403 is
    raised.
    """
    def test_func(self):
        """Check whether the current user is an active PIC for edit operations.

        Superusers and ``admin`` group members are always permitted. For
        other authenticated users, the method resolves the tiket primary
        key from ``kwargs``, a class attribute, or the view's object, and
        verifies an active ``TiketPIC`` assignment exists.

        Returns:
            bool: True if the user has edit permission on the tiket.
        """
        user = self.request.user
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True
        
        # Get tiket from kwargs or object
        tiket_pk = self.kwargs.get('tiket_pk') or getattr(self, 'tiket_pk', None)
        if tiket_pk is None:
            # Try to get from object
            try:
                obj = self.get_object()
                if hasattr(obj, 'id_tiket'):
                    tiket_pk = obj.id_tiket.pk
                elif hasattr(obj, 'id_tiket_id'):
                    tiket_pk = obj.id_tiket_id
            except Exception:
                return False
        
        if tiket_pk is None:
            return False
        
        from ..models.tiket import Tiket
        try:
            tiket = Tiket.objects.get(pk=tiket_pk)
            return TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=user,
                active=True
            ).exists()
        except Tiket.DoesNotExist:
            return False
    
    def handle_no_permission(self):
        """Handle unauthorized access for tiket edit operations.

        Returns a JSON 403 response with an Indonesian-language message
        for AJAX requests; otherwise returns an HTTP 403 Forbidden response.

        Returns:
            JsonResponse or HttpResponseForbidden: A JSON 403 for AJAX
            requests, or an HTTP 403 Forbidden response.
        """
        from django.http import HttpResponseForbidden
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "message": "Anda bukan PIC aktif untuk tiket ini."}, 
                status=403
            )
        return HttpResponseForbidden("Anda bukan PIC aktif untuk tiket ini.")


class ActiveTiketP3DERequiredForEditMixin(UserPassesTestMixin):
    """Require active P3DE PIC assignment for edit operations.

    Similar to `ActiveTiketPICRequiredForEditMixin` but restricts to PICs
    whose `role` is specifically `P3DE`. The admins and kasi of a P3DE seksi
    are exempt, for the tikets of their own seksi only.
    """
    def test_func(self):
        """Check whether the current user is an active P3DE PIC for edit operations.

        Superusers and ``admin`` group members are always permitted, and the
        admins and kasi of a P3DE seksi on the tikets of that seksi. For
        other authenticated users, the method resolves the tiket and
        verifies an active ``TiketPIC`` assignment with role ``P3DE``.

        Returns:
            bool: True if the user is an active P3DE PIC for the tiket.
        """
        user = self.request.user
        if user.is_authenticated and (user.is_superuser or user.groups.filter(name='admin').exists()):
            return True
        # The admins and kasi of a seksi are exempt on that seksi's tikets.
        supervised = p3de_seksi_of_user(user, 'admin', 'kasi')

        # Get tiket from kwargs or object
        tiket_pk = self.kwargs.get('tiket_pk') or getattr(self, 'tiket_pk', None)
        if tiket_pk is None:
            try:
                obj = self.get_object()
                if hasattr(obj, 'id_tiket'):
                    tiket_pk = obj.id_tiket.pk
                elif hasattr(obj, 'id_tiket_id'):
                    tiket_pk = obj.id_tiket_id
                elif hasattr(obj, 'pk'):
                    tiket_pk = obj.pk
            except Exception:
                return False

        if tiket_pk is None:
            return False

        from ..models.tiket import Tiket
        from ..models.tiket_pic import TiketPIC
        try:
            tiket = Tiket.objects.get(pk=tiket_pk)
            if supervised and p3de_seksi_of(tiket) in supervised:
                return True
            return TiketPIC.objects.filter(
                id_tiket=tiket,
                id_user=user,
                active=True,
                role=TiketPIC.Role.P3DE
            ).exists()
        except Tiket.DoesNotExist:
            return False

    def handle_no_permission(self):
        """Handle unauthorized access for P3DE PIC edit operations.

        Returns a JSON 403 response with an Indonesian-language message
        for AJAX requests; otherwise returns an HTTP 403 Forbidden response.

        Returns:
            JsonResponse or HttpResponseForbidden: A JSON 403 for AJAX
            requests, or an HTTP 403 Forbidden response.
        """
        request = getattr(self, "request", None)
        if request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "message": "Anda bukan PIC P3DE aktif untuk tiket ini."}, 
                status=403
            )
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Anda bukan PIC P3DE aktif untuk tiket ini.")


# Seksi P3DE was split in two. Both seksi run the same stage of the workflow —
# rekam, tanda terima, penelitian, kirim ke PIDE — so a PIC or TiketPIC of
# either still carries the `P3DE` tipe/role. What tells them apart is the ILAP:
# a Regional ILAP belongs to Seksi P3DER, a Nasional or Internasional one to
# Seksi P3DE. Each seksi has its own admin, user and kasi group.
SEKSI_P3DE = 'P3DE'
SEKSI_P3DER = 'P3DER'
P3DE_SEKSI_GROUPS = {
    SEKSI_P3DE: {'admin': 'admin_p3de', 'user': 'user_p3de', 'kasi': 'kasi_p3de'},
    SEKSI_P3DER: {'admin': 'admin_p3der', 'user': 'user_p3der', 'kasi': 'kasi_p3der'},
}
ALL_P3DE_SEKSI = frozenset(P3DE_SEKSI_GROUPS)
P3DE_ADMIN_GROUPS = ('admin_p3de', 'admin_p3der')
P3DE_USER_GROUPS = ('user_p3de', 'user_p3der')
P3DE_KASI_GROUPS = ('kasi_p3de', 'kasi_p3der')
P3DE_GROUPS = P3DE_ADMIN_GROUPS + P3DE_USER_GROUPS + P3DE_KASI_GROUPS

KASI_GROUPS = ['kasi_p3de', 'kasi_p3der', 'kasi_pide', 'kasi_pmde']

# The kategori wilayah whose ILAP go to Seksi P3DER. Matched as a substring,
# case-insensitively, the way `ILAPForm` recognises a Regional ILAP.
WILAYAH_REGIONAL = 'regional'

# Lookup prefixes from a model to its ILAP, for `p3de_wilayah_q`.
TIKET_ILAP_PATH = 'id_periode_data__id_sub_jenis_data_ilap__id_ilap__'
JENIS_DATA_ILAP_PATH = 'id_ilap__'
# For every model with an `id_sub_jenis_data_ilap` FK: PIC, PeriodeJenisData.
SUB_JENIS_ILAP_PATH = 'id_sub_jenis_data_ilap__id_ilap__'


def user_group_names(user):
    """Return the names of every group `user` belongs to, as a frozenset.

    The membership is read once and memoized on the `User` instance. A single
    request asks the same question many times over — the home page alone
    resolves nine role flags before it runs a query of its own, and every
    class-based view's `test_func` adds another — and each call was previously
    its own join against `auth_user_groups`.

    The cache lives on the request's `User` instance, so it is discarded when
    the request ends and a group change takes effect on the next one.

    Returns:
        frozenset: The user's group names, empty for anonymous users.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return frozenset()
    names = getattr(user, '_group_names_cache', None)
    if names is None:
        names = frozenset(user.groups.values_list('name', flat=True))
        try:
            user._group_names_cache = names
        except AttributeError:
            # Not every caller passes a real model instance; skip the cache
            # rather than fail when the attribute cannot be set.
            pass
    return names


def _in_group(user, *names):
    """Return True when `user` is authenticated and belongs to any of `names`."""
    return not user_group_names(user).isdisjoint(names)


def is_regional_wilayah(kategori_wilayah):
    """Return True when `kategori_wilayah` (a model or its deskripsi) is Regional."""
    return WILAYAH_REGIONAL in str(kategori_wilayah or '').lower()


def _ilap_of(obj):
    """Return the ILAP behind a Tiket, PIC, JenisDataILAP or ILAP, or None."""
    if obj is None:
        return None
    if hasattr(obj, 'id_kategori_wilayah_id'):
        return obj
    if hasattr(obj, 'id_periode_data_id'):
        return obj.id_periode_data.id_sub_jenis_data_ilap.id_ilap
    if hasattr(obj, 'id_sub_jenis_data_ilap_id'):
        return obj.id_sub_jenis_data_ilap.id_ilap
    if hasattr(obj, 'id_ilap_id'):
        return obj.id_ilap
    return None


def p3de_seksi_of(obj):
    """Return the seksi (`SEKSI_P3DE` or `SEKSI_P3DER`) that handles `obj`.

    `obj` is a Tiket, PIC, JenisDataILAP or ILAP: Regional ILAP belong to
    P3DER, every other kategori wilayah to P3DE. None when `obj` resolves to no
    ILAP.
    """
    ilap = _ilap_of(obj)
    if ilap is None:
        return None
    return SEKSI_P3DER if is_regional_wilayah(ilap.id_kategori_wilayah) else SEKSI_P3DE


def p3de_seksi_of_user(user, *ranks):
    """Return the P3DE seksi `user` belongs to, as a frozenset.

    Args:
        user (User): The user to test.
        *ranks (str): Any of ``'admin'``, ``'user'``, ``'kasi'`` — only groups
            of those ranks count. Every rank counts when none is given.

    Returns:
        frozenset: Subset of ``{SEKSI_P3DE, SEKSI_P3DER}``. Superusers and the
        global ``admin`` group oversee both seksi.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return frozenset()
    if user.is_superuser or _in_group(user, 'admin'):
        return ALL_P3DE_SEKSI
    ranks = ranks or ('admin', 'user', 'kasi')
    names = user_group_names(user)
    return frozenset(
        seksi for seksi, groups in P3DE_SEKSI_GROUPS.items()
        if any(groups[rank] in names for rank in ranks)
    )


def p3de_wilayah_q(seksi, ilap_path=''):
    """Return a Q matching the rows whose ILAP belongs to one of `seksi`.

    Args:
        seksi (iterable): P3DE seksi, e.g. from :func:`p3de_seksi_of_user`.
        ilap_path (str): Lookup prefix from the queried model to its ILAP, e.g.
            :data:`TIKET_ILAP_PATH`; empty when querying ILAP itself.

    Returns:
        Q: Matches everything for both seksi and nothing for none.
    """
    seksi = frozenset(seksi)
    regional = Q(**{f'{ilap_path}id_kategori_wilayah__deskripsi__icontains': WILAYAH_REGIONAL})
    if seksi >= ALL_P3DE_SEKSI:
        return Q()
    if SEKSI_P3DER in seksi:
        return regional
    if SEKSI_P3DE in seksi:
        return ~regional
    return Q(pk__in=[])


def p3de_admin_wilayah_q(user, ilap_path=''):
    """Return a Q narrowing an administrator's per-ILAP rows to their P3DE seksi.

    An `admin_p3de` sees the Nasional/Internasional ILAP, an `admin_p3der` the
    Regional ones. Superusers, the global `admin` group and anyone holding no
    P3DE admin group are not narrowed (``Q()``).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return Q()
    if user.is_superuser or _in_group(user, 'admin'):
        return Q()
    seksi = p3de_seksi_of_user(user, 'admin')
    return p3de_wilayah_q(seksi, ilap_path) if seksi else Q()


def p3de_user_groups_for(seksi):
    """Return the ``user_*`` group names of `seksi`, in seksi order."""
    return [P3DE_SEKSI_GROUPS[s]['user'] for s in P3DE_SEKSI_GROUPS if s in seksi]


def p3de_seksi_label(seksi):
    """Return a display label for a set of P3DE seksi, e.g. ``"P3DE / P3DER"``."""
    return ' / '.join(s for s in P3DE_SEKSI_GROUPS if s in seksi) or SEKSI_P3DE


def _p3de_rank_covers(user, rank, target):
    """True when `user` holds a P3DE `rank` group, for `target`'s seksi if given."""
    seksi = p3de_seksi_of_user(user, rank)
    if target is None or not seksi:
        return bool(seksi)
    return p3de_seksi_of(target) in seksi


def is_admin_p3de(user, target=None):
    """Return True for users who administer P3DE tikets.

    Covers superusers, the global `admin` group and the seksi admin groups
    (`admin_p3de`, `admin_p3der`). P3DE administrators are not bound to the PIC
    assignments of a tiket: they may open any tiket of their seksi and correct
    its isian at any point in the workflow.

    Args:
        user (User): The user to test.
        target (optional): A Tiket, PIC, JenisDataILAP or ILAP. When given, a
            seksi admin only counts for targets of their own seksi — admin P3DE
            for Nasional/Internasional ILAP, admin P3DER for Regional ones.
    """
    return _p3de_rank_covers(user, 'admin', target)


def is_admin_pmde(user):
    """Return True for users who administer PMDE tikets.

    Covers superusers, the global `admin` group and the `admin_pmde` group —
    the same set every other Admin PMDE menu admits.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    return _in_group(user, 'admin', 'admin_pmde')


def tiket_pic_roles_managed_by(user, tiket=None):
    """Return the `TiketPIC.Role` values `user` may manage on a tiket page.

    Mirrors the PIC menu: each seksi admin manages its own role (`admin_p3de`
    / `admin_p3der` -> P3DE, `admin_pide` -> PIDE, `admin_pmde` -> PMDE);
    superusers and the global `admin` group manage all three. Returned in role
    order. When `tiket` is given, a P3DE seksi admin only manages the P3DE role
    on the tikets of their own seksi (see :func:`is_admin_p3de`).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    if user.is_superuser or _in_group(user, 'admin'):
        return list(TiketPIC.Role)
    roles = []
    if is_admin_p3de(user, tiket):
        roles.append(TiketPIC.Role.P3DE)
    if _in_group(user, 'admin_pide'):
        roles.append(TiketPIC.Role.PIDE)
    if _in_group(user, 'admin_pmde'):
        roles.append(TiketPIC.Role.PMDE)
    return roles


def is_kasi_p3de(user, target=None):
    """Return True when `user` belongs to a P3DE kasi group (`kasi_p3de`, `kasi_p3der`).

    When `target` (a Tiket, PIC, JenisDataILAP or ILAP) is given, the kasi only
    counts for targets of their own seksi — see :func:`p3de_seksi_of`.
    """
    return _p3de_rank_covers(user, 'kasi', target)


def is_kasi_pide(user):
    """Return True when `user` belongs to the `kasi_pide` supervisor group."""
    return _in_group(user, 'kasi_pide')


def is_kasi_pmde(user):
    """Return True when `user` belongs to the `kasi_pmde` supervisor group."""
    return _in_group(user, 'kasi_pmde')


def is_kasi(user):
    """Return True when `user` belongs to any kasi (supervisor) group.

    Kasi are not admins, but they supervise their unit and are therefore not
    limited to the tikets where they are the active PIC.
    """
    return _in_group(user, *KASI_GROUPS)


def can_view_any_tiket(user):
    """Return True when `user` may open the detail page of any tiket.

    Covers superusers, the global `admin` group, the PIDE and PMDE
    administrators and the PIDE and PMDE kasi. The admins and kasi of a P3DE
    seksi are not among them: they see the tikets of their own seksi only, see
    :func:`can_open_tiket`. Viewing is all this grants: the workflow actions
    stay gated behind an active TiketPIC assignment, and editing the isian
    stays with `is_admin_p3de`.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user.is_superuser or _in_group(
        user, 'admin', 'admin_pide', 'admin_pmde', 'kasi_pide', 'kasi_pmde'
    )


def supervised_tiket_q(user):
    """Return the tikets `user` sees by supervision rather than as their PIC.

    Returns:
        None when `user` sees every tiket (superusers, the global `admin`
        group, kasi PIDE and kasi PMDE); a Q over the tikets of their seksi for
        a kasi P3DE / P3DER; ``Q(pk__in=[])`` for everyone else.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return Q(pk__in=[])
    if user.is_superuser or _in_group(user, 'admin', 'kasi_pide', 'kasi_pmde'):
        return None
    seksi = p3de_seksi_of_user(user, 'kasi')
    if seksi >= ALL_P3DE_SEKSI:
        return None
    return p3de_wilayah_q(seksi, TIKET_ILAP_PATH)


def can_open_tiket(user, tiket):
    """Return True when `user` may open `tiket`'s detail page.

    Granted to:
    - everyone covered by `can_view_any_tiket` (admins and kasi);
    - the admins and kasi of the P3DE seksi that handles the tiket's ILAP;
    - anyone with a `TiketPIC` row on the tiket, active or not, so a PIC
      handed over keeps reading the tikets they worked;
    - the current PIC of the tiket's sub jenis data (a `PIC` row with no
      `end_date`, any tipe), who may never have been put on the tiket because
      a handover only reaches tikets that are still open.

    Viewing is all this grants: the workflow actions stay gated behind an
    active `TiketPIC` on the tiket itself.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if can_view_any_tiket(user):
        return True
    if is_admin_p3de(user, tiket) or is_kasi_p3de(user, tiket):
        return True
    if TiketPIC.objects.filter(id_tiket=tiket, id_user=user).exists():
        return True
    from ..models.pic import PIC
    return PIC.objects.filter(
        id_user=user,
        id_sub_jenis_data_ilap_id=tiket.id_periode_data.id_sub_jenis_data_ilap_id,
        end_date__isnull=True,
    ).exists()


def has_active_tiket_pic(user):
    """Return True if `user` has any active `TiketPIC` assignments.

    Returns a boolean and is safe to call with `None` or anonymous users.
    """
    if not user or not user.is_authenticated:
        return False
    return TiketPIC.objects.filter(id_user=user, active=True).exists()


def get_active_p3de_ilap_ids(user):
    """Return ILAP IDs where `user` is an active P3DE PIC.

    The helper restricts PIC assignments to the P3DE `tipe`, ensures the
    assignment `start_date` is in the past, and that `end_date` is either
    null or in the future. Returns a list of distinct ILAP primary keys.
    """
    if not user or not user.is_authenticated:
        return []
    
    from datetime import datetime
    from django.db.models import Q
    from ..models.pic import PIC
    
    today = datetime.now().date()
    
    # Get ILAPs where user is assigned as P3DE PIC with active date range
    return PIC.objects.filter(
        tipe=PIC.TipePIC.P3DE,
        id_user=user,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).values_list(
        'id_sub_jenis_data_ilap__id_ilap_id',
        flat=True
    ).distinct()


def get_active_p3de_jenis_data_ilap_ids(user):
    """Return JenisDataILAP IDs where `user` is an active P3DE PIC.

    Active means `start_date` is in the past and `end_date` is null or in
    the future. Returns a list of distinct JenisDataILAP primary keys.
    """
    if not user or not user.is_authenticated:
        return []

    from datetime import datetime
    from django.db.models import Q
    from ..models.pic import PIC

    today = datetime.now().date()

    return PIC.objects.filter(
        tipe=PIC.TipePIC.P3DE,
        id_user=user,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).values_list(
        'id_sub_jenis_data_ilap_id',
        flat=True
    ).distinct()


def is_active_ilap_pic(user, ilap):
    """Return True when `user` is an active PIC on any jenis data of `ilap`.

    Every tipe counts (P3DE, PIDE and PMDE), and active means the assignment
    has started and has not ended yet — the same window
    :func:`get_active_p3de_ilap_ids` applies.

    Args:
        user (User): The user to test.
        ilap (ILAP): The ILAP whose jenis data are checked.

    Returns:
        bool: True when at least one active assignment exists.
    """
    if not user or not user.is_authenticated:
        return False

    from datetime import datetime
    from django.db.models import Q
    from ..models.pic import PIC

    today = datetime.now().date()

    return PIC.objects.filter(
        id_sub_jenis_data_ilap__id_ilap=ilap,
        id_user=user,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).exists()


def can_view_ilap_kontak(user, ilap):
    """Return True when `user` may see the PIC and contact details of `ilap`.

    The profil ILAP pages themselves are open to every logged in user, but
    the institution's contact person is not: it belongs to the people who
    correspond with the ILAP. The admins and kasi of the P3DE seksi that
    handles the ILAP (P3DE for Nasional/Internasional, P3DER for Regional)
    oversee that correspondence, so they always see it. Everyone else needs an
    active PIC assignment on at least one of the ILAP's jenis data — including
    kasi PIDE and kasi PMDE, who supervise the processing of the data rather
    than the correspondence with its source.
    """
    if is_admin_p3de(user, ilap) or is_kasi_p3de(user, ilap):
        return True
    return is_active_ilap_pic(user, ilap)


def can_access_tiket_list(user):
    """Return True when `user` should be allowed to view tiket listings.

    Rules applied:
    - Superusers and any admin group members (admin, admin_p3de, admin_p3der, admin_pide, admin_pmde) are always allowed.
    - Members of any kasi group (kasi_p3de, kasi_p3der, kasi_pide, kasi_pmde) are allowed.
    - Members of `user_p3de`, `user_p3der`, `user_pide`, or `user_pmde`
      groups are allowed.
    - Otherwise, the user must have at least one `TiketPIC` record.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name__in=['admin', *P3DE_ADMIN_GROUPS, 'admin_pide', 'admin_pmde']).exists():
        return True
    if is_kasi(user):
        return True
    if user.groups.filter(name__in=[*P3DE_USER_GROUPS, 'user_pide', 'user_pmde']).exists():
        return True
    return TiketPIC.objects.filter(id_user=user).exists()


class ActiveTiketPICListRequiredMixin(UserPassesTestMixin):
    """Require admin/superuser or any active `TiketPIC` assignment.

    Use this mixin for list views where any active PIC should be allowed to
    access tiket lists for their assignments.
    """
    def test_func(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.groups.filter(name='admin').exists():
            return True
        return TiketPIC.objects.filter(id_user=user, active=True).exists()


class UserFormKwargsMixin:
    """Add the current request user to form `kwargs`.

    Views that need the `user` in their form constructors can mix this in
    so forms receive `kwargs['user'] = request.user` automatically.
    """
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class AjaxFormMixin:
    """Provide consistent AJAX handling for Create/Update views.

    Behavior summary:
    - If the request contains the `ajax` GET parameter the view will
      return rendered form HTML (for client-side injection) instead of a
      full page.
    - On successful form submission for AJAX requests the mixin returns
      a JSON payload containing `success: true` and optionally
      `redirect` pointing to the success URL. The mixin also registers
      the configured `success_message` in Django messages so the client
      sees the toast after a full navigation.
    - Non-AJAX flows remain compatible with standard Django CBV
      behavior.
    """

    ajax_param = "ajax"
    success_message = ""

    def is_ajax(self):
        """Determine whether the current request is an AJAX request.

        Checks for the ``X-Requested-With`` header set to
        ``XMLHttpRequest``.

        Returns:
            bool: True if the request is an AJAX request.
        """
        request = getattr(self, "request", None)
        return request is not None and request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def render_form_html(self, form):
        """Render the form template to an HTML string (used for AJAX)."""
        return render_to_string(
            self.template_name,
            self.get_context_data(form=form),
            request=self.request,
        )

    def render_form_response(self, form):
        """Return either a JSON html payload (when `?ajax=1`) or full response."""
        if self.request.GET.get(self.ajax_param):
            return JsonResponse({"html": self.render_form_html(form)})
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """Save valid form and return JSON redirect for AJAX clients.

        The method also registers `success_message` into Django messages so
        that client-side toasts can be rendered after a redirect.
        """
        self._apply_audit_fields(form)
        self.object = form.save()
        self.after_save(form)
        message = self.get_success_message(form)
        if self.is_ajax():
            # For AJAX requests, return the message in the JSON response
            # so the client can display it directly without redirecting.
            payload = {"success": True}
            if message:
                payload["message"] = message
            try:
                redirect_url = self.get_success_url()
            except Exception:
                redirect_url = getattr(self, 'success_url', None)
            if redirect_url:
                payload["redirect"] = redirect_url
            return JsonResponse(payload)
        if message:
            messages.success(self.request, message)
        return super().form_valid(form)

    def after_save(self, form):  # noqa: ARG002
        """Hook run right after `form.save()`, before the success message is
        built. Override for follow-up writes that the message should report."""

    def form_invalid(self, form):
        """Return form HTML for AJAX invalid submissions, otherwise default."""
        if self.is_ajax():
            return JsonResponse({"success": False, "html": self.render_form_html(form)})
        return super().form_invalid(form)

    def get_success_message(self, form):  # noqa: ARG002 - form kept for parity with Django patterns
        """Format and return the success message for this view.

        The method intentionally accepts `form` for signature parity with
        other patterns but does not require it.
        """
        if not self.success_message:
            return ""
        try:
            return self.success_message.format(object=self.object)
        except Exception:
            return self.success_message

    def _apply_audit_fields(self, form):
        """Stamp audit fields on the model instance when supported.

        Sets ``create_date`` and ``create_by`` only when the instance is
        newly created (i.e., these fields are not yet populated). Always
        updates ``update_date`` and ``update_by`` if the model has those
        fields. Truncates the username to a maximum of 9 characters.

        Args:
            form: The bound form whose ``instance`` will be stamped.
        """
        instance = form.instance
        today = timezone.now().date()
        username = (getattr(self.request.user, 'username', '') or '')[:9]

        if hasattr(instance, 'create_date') and not getattr(instance, 'create_date', None):
            instance.create_date = today
        if hasattr(instance, 'create_by') and not getattr(instance, 'create_by', None):
            instance.create_by = username
        if hasattr(instance, 'update_date'):
            instance.update_date = today
        if hasattr(instance, 'update_by'):
            instance.update_by = username

class SafeDeleteMixin:
    """Mixin to handle deletion errors gracefully.

    Catches ProtectedError and other deletion-related exceptions and returns
    user-friendly error messages instead of generic 500 errors. Works with
    both AJAX and standard form submissions.
    """
    
    def delete(self, request, *args, **kwargs):
        """Override delete to catch ``ProtectedError`` and other deletion exceptions.

        Attempts to delete the view's object and handles three outcomes:

        1. Success: returns a JSON response with ``success: True`` and a
           success message (or sets a Django messages success notification).
        2. ``ProtectedError``: returns a JSON error response describing the
           related objects that prevent deletion.
        3. Any other exception: returns a generic error response.

        Args:
            request: The current HTTP request.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            JsonResponse: A JSON payload indicating success or failure.
        """
        from django.db.models.deletion import ProtectedError
        
        self.object = self.get_object()
        object_name = str(self.object)
        
        try:
            self.object.delete()
            # Success path
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': self.get_delete_success_message(object_name)
                })
            messages.success(request, self.get_delete_success_message(object_name))
            return JsonResponse({'success': True, 'redirect': self.get_success_url()})
        
        except ProtectedError as e:
            # Get the model name that is preventing deletion
            related_models = []
            if hasattr(e, 'protected_objects'):
                for obj in e.protected_objects:
                    related_models.append(obj._meta.verbose_name_plural)
            
            error_message = self.get_protected_error_message(object_name, related_models)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                }, status=400)
            
            messages.error(request, error_message)
            return JsonResponse({'success': False, 'message': error_message}, status=400)
        
        except Exception as e:
            error_message = self.get_general_error_message(str(e))
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                }, status=400)
            
            messages.error(request, error_message)
            return JsonResponse({'success': False, 'message': error_message}, status=400)
    
    def get_delete_success_message(self, object_name):
        """Generate a success message after a successful deletion.

        Args:
            object_name (str): The string representation of the deleted object.

        Returns:
            str: A formatted success message in Indonesian indicating the
            object was successfully deleted.
        """
        model_name = self.model._meta.verbose_name
        return f'{model_name} "{object_name}" berhasil dihapus.'
    
    def get_protected_error_message(self, object_name, related_models):
        """Generate an error message when deletion is blocked by a ``ProtectedError``.

        Args:
            object_name (str): The string representation of the object
                being deleted.
            related_models (list): A list of verbose plural names of
                related models that prevent deletion.

        Returns:
            str: A formatted error message in Indonesian indicating the
            object cannot be deleted because it is still referenced.
        """
        model_name = self.model._meta.verbose_name
        if related_models:
            related_text = ', '.join(related_models)
            return f'Tidak dapat menghapus {model_name} "{object_name}" karena masih digunakan oleh {related_text}. Silakan hapus referensi tersebut terlebih dahulu.'
        return f'Tidak dapat menghapus {model_name} "{object_name}" karena masih digunakan di tempat lain. Silakan hapus referensi tersebut terlebih dahulu.'
    
    def get_general_error_message(self, error_detail):
        """Generate a generic error message for unexpected deletion failures.

        Args:
            error_detail (str): The string representation of the caught
                exception, used for logging or debugging.

        Returns:
            str: A generic error message in Indonesian.
        """
        return 'Gagal menghapus data. Silakan periksa apakah data masih digunakan di tempat lain.'