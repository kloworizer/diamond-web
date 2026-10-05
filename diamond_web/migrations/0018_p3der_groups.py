# Create the Seksi P3DER groups and a placeholder Kepala Seksi P3DER account.
#
# Seksi P3DE was split in two: P3DE keeps the Nasional and Internasional ILAP,
# the new P3DER takes the Regional ones. Both run the same stage of the
# workflow, so no table changes — the seksi is told apart by the user's group
# and the ILAP's kategori wilayah (see `diamond_web.views.mixins`).
#
# The `admin` superuser joins the new groups, as 0001 put it in every seksi
# group it created.
#
# The kasi account is a placeholder: its username is `kasi_p3der` and it has no
# usable password, so nobody can log in with it until an administrator sets one
# (and, usually, renames it to the kasi's NIP) through Django Admin.
#
# Moving staff from user_p3de to user_p3der is not done here; it is done by hand
# per person.
#
# Reverse is a no-op, for the reason given in 0014: by the time anyone rolls
# this back, people may have been put in these groups, and dropping a group
# takes every one of those memberships with it.

from django.contrib.auth.hashers import make_password
from django.db import migrations


GROUP_NAMES = ("admin_p3der", "user_p3der", "kasi_p3der")
KASI_USERNAME = "kasi_p3der"


def create_groups_and_kasi(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    groups = [Group.objects.get_or_create(name=name)[0] for name in GROUP_NAMES]

    admin_user = User.objects.filter(username="admin").first()
    if admin_user is not None:
        admin_user.groups.add(*groups)

    kasi, _ = User.objects.get_or_create(
        username=KASI_USERNAME,
        defaults={
            "first_name": "Kepala Seksi",
            "last_name": "P3DER",
            "password": make_password(None),
            "is_active": True,
        },
    )
    kasi.groups.add(Group.objects.get(name="kasi_p3der"))


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("diamond_web", "0017_nd_pengantar_pdi_template"),
    ]

    operations = [
        migrations.RunPython(create_groups_and_kasi, migrations.RunPython.noop),
    ]
