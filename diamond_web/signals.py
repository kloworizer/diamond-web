from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.contrib import messages

from .models.nama_tabel_jenis_data import NamaTabelJenisData

@receiver(user_logged_in)
def display_login_success_message(sender, request, user, **kwargs):
    # Only add message if messages middleware is installed
    # This handles cases like test clients that don't process middleware
    if hasattr(request, '_messages'):
        # Get user's full name or fall back to username
        full_name = user.get_full_name().strip() if user.get_full_name() else user.username
        messages.success(request, f"Selamat datang, {full_name}!")


def _mirror_nama_tabel_ke_induk(jenis_data_id):
    """Rewrite a jenis data's cache columns from its utama table name.

    `JenisDataILAP.nama_tabel_I` and `nama_tabel_U` are a denormalised copy of
    the utama `NamaTabelJenisData` row. Every report filter, export column and
    detail page reads those columns instead of traversing the relation, because
    traversing it fans the query out to one row per table name — a silently
    wrong count rather than an error. So the copy has to be rewritten whenever
    the utama row is saved, replaced or removed.

    Uses `.update()` rather than `.save()`: it touches only the two columns and
    does not re-enter any JenisDataILAP save handling.
    """
    from .models.jenis_data_ilap import JenisDataILAP

    utama = (
        NamaTabelJenisData.objects
        .filter(id_jenis_data_ilap_id=jenis_data_id, utama=True)
        .first()
    )
    JenisDataILAP.objects.filter(id=jenis_data_id).update(
        nama_tabel_I=utama.nama_tabel_I if utama else "",
        nama_tabel_U=utama.nama_tabel_U if utama else "",
    )


@receiver(post_save, sender=NamaTabelJenisData)
def sync_nama_tabel_cache_on_save(sender, instance, **kwargs):
    _mirror_nama_tabel_ke_induk(instance.id_jenis_data_ilap_id)


@receiver(post_delete, sender=NamaTabelJenisData)
def sync_nama_tabel_cache_on_delete(sender, instance, **kwargs):
    # Also fires while a JenisDataILAP cascade-deletes its table names, where
    # the parent is already gone and the update simply matches nothing.
    _mirror_nama_tabel_ke_induk(instance.id_jenis_data_ilap_id)