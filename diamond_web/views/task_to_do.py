from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC


def get_tiket_summary_for_user(user):
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
