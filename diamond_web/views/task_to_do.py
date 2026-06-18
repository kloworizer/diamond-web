from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.constants.tiket_status import (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
)


def get_tiket_summary_for_user_p3de(user):
    """Return a compact summary of pending tiket actions for a P3DE user.

    Selects active ``TiketPIC`` records for the given user with role P3DE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_p3de`` group the
            function returns a zeroed summary.

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
    if not user.groups.filter(name='user_p3de').exists():
        return empty

    p3de_pic = TiketPIC.objects.filter(id_user=user, role=TiketPIC.Role.P3DE, active=True)
    tiket_ids = p3de_pic.values_list('id_tiket', flat=True)

    return {
        'rekam_backup_data': Tiket.objects.filter(id__in=tiket_ids, backup=False).count(),
        'buat_tanda_terima': Tiket.objects.filter(id__in=tiket_ids, tanda_terima=False).count(),
        'rekam_hasil_penelitian': Tiket.objects.filter(id__in=tiket_ids, tgl_teliti__isnull=True).count(),
        'kirim_ke_pide': Tiket.objects.filter(id__in=tiket_ids, tgl_kirim_pide__isnull=True).count(),
    }


def get_tiket_summary_for_user_pide(user):
    """Return a compact summary of pending tiket actions for a PIDE user.

    Selects active ``TiketPIC`` records for the given user with role PIDE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_pide`` group the
            function returns a zeroed summary.

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
    if not user.groups.filter(name='user_pide').exists():
        return empty

    pide_pic = TiketPIC.objects.filter(id_user=user, role=TiketPIC.Role.PIDE, active=True)
    tiket_ids = pide_pic.values_list('id_tiket', flat=True)

    return {
        'identifikasi_data': Tiket.objects.filter(id__in=tiket_ids, status_tiket=STATUS_DIKIRIM_KE_PIDE).count(),
        'transfer_ke_pmde': Tiket.objects.filter(id__in=tiket_ids, status_tiket=STATUS_IDENTIFIKASI).count(),
    }


def get_tiket_summary_for_user_pmde(user):
    """Return a compact summary of pending tiket actions for a PMDE user.

    Selects active ``TiketPIC`` records for the given user with role PMDE to
    determine the relevant set of ticket IDs, then executes simple
    ``Tiket.objects.filter(...).count()`` queries for each metric.

    Args:
        user: A Django ``User`` instance (or falsy).  If the user is not
            authenticated or is not a member of the ``user_pmde`` group the
            function returns a zeroed summary.

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
    if not user.groups.filter(name='user_pmde').exists():
        return empty

    pmde_pic = TiketPIC.objects.filter(id_user=user, role=TiketPIC.Role.PMDE, active=True)
    tiket_ids = pmde_pic.values_list('id_tiket', flat=True)

    return {
        'pengendalian_mutu': Tiket.objects.filter(id__in=tiket_ids, status_tiket=STATUS_PENGENDALIAN_MUTU).count(),
    }
