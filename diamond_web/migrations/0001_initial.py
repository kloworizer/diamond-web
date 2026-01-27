# Generated squashed initial migration - Create groups and superuser

from django.db import migrations


def create_groups_and_superuser(apps, schema_editor):
    """
    Creates all groups and a superuser 'admin' with password 'admin'.
    Groups created: admin, admin_p3de, admin_pide, admin_pmde, kasi_p3de, kasi_pide, user_p3de, user_pide, user_pmde
    """
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    # Groups to create
    group_names = [
        "admin",
        "admin_p3de",
        "admin_pide",
        "admin_pmde",
        "kasi_p3de",
        "kasi_pide",
        "user_p3de",
        "user_pide",
        "user_pmde",
    ]

    for name in group_names:
        Group.objects.get_or_create(name=name)

    # Create admin superuser if not exists
    if not User.objects.filter(username="admin").exists():
        admin_user = User.objects.create_superuser("admin", "admin@diamond.pde", "admin")
    else:
        admin_user = User.objects.get(username="admin")
    
    # Add admin user to all groups
    admin_user.groups.set(Group.objects.filter(name__in=group_names))


def delete_groups_and_superuser(apps, schema_editor):
    """Removes all groups and the admin superuser."""
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    group_names = [
        "admin",
        "admin_p3de",
        "admin_pide",
        "admin_pmde",
        "kasi_p3de",
        "kasi_pide",
        "user_p3de",
        "user_pide",
        "user_pmde",
    ]

    Group.objects.filter(name__in=group_names).delete()
    User.objects.filter(username="admin").delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_groups_and_superuser, reverse_code=delete_groups_and_superuser),
    ]
