from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
)
from diamond_web.views.mixins import (
    is_kasi_p3de,
    is_kasi_pide,
    is_kasi_pmde,
    user_group_names,
)


def _scope(role, user, is_kasi):
    """Tikets `user` may act on in `role`, or None when they may act on none.

    A kasi supervises the whole unit and is left unscoped — filtering on every
    id in the table costs a subquery that removes nothing.
    """
    if is_kasi(user):
        return Tiket.objects.all()
    return Tiket.objects.filter(
        id__in=TiketPIC.objects.filter(
            id_user=user, role=role, active=True
        ).values_list('id_tiket', flat=True)
    )


def get_tiket_summary_for_user_p3de(user):
    """Return a compact summary of pending tiket actions for a P3DE user.

    Selects active ``TiketPIC`` records for the given user with role P3DE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Members of ``kasi_p3de`` supervise the whole unit, so their summary covers
    every tiket instead of only their own PIC assignments.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_p3de`` or
            ``kasi_p3de`` group the function returns a zeroed summary.

    Returns:
        dict: A dictionary with the following integer counts:

            - ``rekam_backup_data``: Number of assigned tickets missing backup
              data.
            - ``buat_tanda_terima``: Number of assigned tickets without a
              *tanda terima* (receipt).
            - ``rekam_hasil_penelitian``: Number of assigned tickets missing
              ``tgl_teliti``.
            - ``kirim_ke_pide``: Number of assigned tickets missing
              ``tgl_kirim_pide``.
    """
    empty = {
        'rekam_backup_data': 0,
        'buat_tanda_terima': 0,
        'rekam_hasil_penelitian': 0,
        'kirim_ke_pide': 0,
    }

    if not user or not getattr(user, 'is_authenticated', False):
        return empty
    if not is_kasi_p3de(user) and 'user_p3de' not in user_group_names(user):
        return empty
    tikets = _scope(TiketPIC.Role.P3DE, user, is_kasi_p3de)

    return {
        'rekam_backup_data': tikets.filter(backup=False).count(),
        'buat_tanda_terima': tikets.filter(tanda_terima=False).count(),
        'rekam_hasil_penelitian': tikets.filter(tgl_teliti__isnull=True).count(),
        'kirim_ke_pide': tikets.filter(tgl_kirim_pide__isnull=True).count(),
    }


def get_tiket_summary_for_user_pide(user):
    """Return a compact summary of pending tiket actions for a PIDE user.

    Selects active ``TiketPIC`` records for the given user with role PIDE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Members of ``kasi_pide`` supervise the whole unit, so their summary covers
    every tiket instead of only their own PIC assignments.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_pide`` or
            ``kasi_pide`` group the function returns a zeroed summary.

    Returns:
        dict: A dictionary with the following integer counts:

            - ``identifikasi_data``: Number of assigned tickets in
              ``STATUS_DIKIRIM_KE_PIDE`` status.
            - ``transfer_ke_pmde``: Number of assigned tickets ready to be
              transferred (status is ``STATUS_IDENTIFIKASI``).
    """
    empty = {
        'identifikasi_data': 0,
        'transfer_ke_pmde': 0,
    }

    if not user or not getattr(user, 'is_authenticated', False):
        return empty
    if not is_kasi_pide(user) and 'user_pide' not in user_group_names(user):
        return empty
    tikets = _scope(TiketPIC.Role.PIDE, user, is_kasi_pide)

    return {
        'identifikasi_data': tikets.filter(status_tiket=STATUS_DIKIRIM_KE_PIDE).count(),
        'transfer_ke_pmde': tikets.filter(status_tiket=STATUS_IDENTIFIKASI).count(),
    }


def get_tiket_summary_for_user_pmde(user):
    """Return a compact summary of pending tiket actions for a PMDE user.

    Selects active ``TiketPIC`` records for the given user with role PMDE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Members of ``kasi_pmde`` supervise the whole unit, so their summary covers
    every tiket instead of only their own PIC assignments.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_pmde`` or
            ``kasi_pmde`` group the function returns a zeroed summary.

    Returns:
        dict: A dictionary with the following integer counts:

            - ``pengendalian_mutu``: Number of assigned tickets in
              ``STATUS_PENGENDALIAN_MUTU`` status (Quality Control phase).
    """
    empty = {
        'pengendalian_mutu': 0,
    }

    if not user or not getattr(user, 'is_authenticated', False):
        return empty
    if not is_kasi_pmde(user) and 'user_pmde' not in user_group_names(user):
        return empty
    tikets = _scope(TiketPIC.Role.PMDE, user, is_kasi_pmde)

    return {
        'pengendalian_mutu': tikets.filter(status_tiket=STATUS_PENGENDALIAN_MUTU).count(),
    }
