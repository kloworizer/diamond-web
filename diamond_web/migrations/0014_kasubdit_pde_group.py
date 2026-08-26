# Create the `kasubdit_pde` group.
#
# Kasubdit PDE supervises the three seksi. Membership carries no permission of
# its own: it is a navigation rule, read by `navbar.html` to hide the seksi and
# admin sections from a supervisor who reads the work rather than doing it.
# Members therefore also belong to a seksi group, which is what gives them the
# data scope behind Daftar Tiket and the pages above.
#
# Deliberately not added to the `admin` superuser that 0001 puts in every other
# group: the whole point of the group is to take menus away, and the superuser
# needs all of them.
#
# Forward is get_or_create because the group predates this migration on the
# production database — there it applies as a no-op. Reverse is a no-op for the
# same reason: it did not create that group, so it must not be the thing that
# drops it and takes every `auth_user_groups` row with it. Removing the group
# is a deliberate act, not the side effect of rolling a migration back.

from django.db import migrations


GROUP_NAME = "kasubdit_pde"


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name=GROUP_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('diamond_web', '0013_add_hot_path_indexes'),
    ]

    operations = [
        migrations.RunPython(create_group, migrations.RunPython.noop),
    ]
