# Generated seed migration - Create users for groups

from django.db import migrations
import random
import string


def seed_users(apps, schema_editor):
    """
    Create users for groups: user_p3de, user_pide, user_pmde
    Username: 9 digit random number
    Name: Indonesian name
    Email: @diamond.pde
    """
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    # Indonesian names for users
    indonesian_names = [
        "Ahmad Wijaya",
        "Budi Santoso",
        "Citra Dewi",
        "Dwi Purwanto",
        "Eka Prasetya",
        "Farhan Hidayat",
        "Gitawati Handini",
        "Hendra Kusuma",
        "Irwan Setiawan",
        "Joko Bambang",
        "Krisna Murti",
        "Lestari Nugraheni",
        "Mahmud Jamal",
        "Nining Suryani",
        "Oka Wardana",
        "Putri Handayani",
        "Quirino Samsudin",
        "Rina Sugiarti",
        "Setya Budiman",
        "Tri Haryanto",
        "Umi Kulsum",
        "Vicky Mandala",
        "Wulan Safitri",
        "Xenia Wijaya",
        "Yani Suryono",
        "Zainul Abidin",
    ]

    groups_to_create = [
        ("user_p3de", 3),
        ("user_pide", 3),
        ("user_pmde", 3),
    ]

    user_count = 0

    for group_name, num_users in groups_to_create:
        group = Group.objects.get(name=group_name)

        for i in range(num_users):
            # Generate random 9-digit username
            username = ''.join([str(random.randint(0, 9)) for _ in range(9)])

            # Make sure username is unique
            while User.objects.filter(username=username).exists():
                username = ''.join([str(random.randint(0, 9)) for _ in range(9)])

            # Get Indonesian name
            name = indonesian_names[user_count % len(indonesian_names)]

            # Create email
            email = f"{username}@diamond.pde"

            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=name.split()[0] if len(name.split()) > 0 else name,
                last_name=name.split()[1] if len(name.split()) > 1 else "",
            )

            # Assign user to group
            user.groups.add(group)

            user_count += 1


def unseed_users(apps, schema_editor):
    """Remove all users from user_p3de, user_pide, user_pmde groups."""
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    group_names = ["user_p3de", "user_pide", "user_pmde"]
    groups = Group.objects.filter(name__in=group_names)

    # Get all users in these groups
    users_to_delete = User.objects.filter(groups__in=groups).exclude(
        groups__name__in=["admin", "admin_p3de", "admin_pide", "admin_pmde"]
    ).distinct()

    # Delete users that only belong to these groups
    for user in users_to_delete:
        if user.groups.count() <= 1:
            user.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diamond_web", "0011_seed_periode_jenis_data"),
    ]

    operations = [
        migrations.RunPython(seed_users, reverse_code=unseed_users),
    ]
