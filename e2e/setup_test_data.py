"""
Set up an isolated test user + PIC assignments so a single user can drive the
whole tiket workflow (P3DE -> PIDE -> PMDE) through the real UI.

Why this is needed:
  diamond_web/views/tiket/detail.py computes user_is_active_pic_{p3de,pide,pmde}
  from BOTH an active TiketPIC assignment AND an active PIC-table record for the
  tiket's sub_jenis_data_ilap -- with NO superuser/admin override. So to see the
  P3DE/PIDE/PMDE action buttons as one user, that user must be an active PIC for
  all three roles on the chosen sub_jenis_data_ilap.

It also creates one account per Seksi P3DE / P3DER role (pw_user_p3der,
pw_kasi_p3der, pw_admin_p3der, pw_kasi_p3de, pw_admin_p3de) for
test_p3der_seksi.py. pw_user_p3der is made an active PIC P3DE on one Regional
sub jenis data, since a P3DER pelaksana only reaches the ILAP they are PIC of.

Idempotent: safe to run repeatedly.

Run:
  .venv/Scripts/python.exe e2e/setup_test_data.py
"""
import os
import sys
import django

# Ensure project root (parent of this e2e/ folder) is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Group  # noqa: E402
from diamond_web.models.pic import PIC  # noqa: E402
from diamond_web.models.periode_jenis_data import PeriodeJenisData  # noqa: E402

USERNAME = "pw_tester"
PASSWORD = "PwTest12345!"
# Groups mirror the existing `admin` account so every RBAC mixin passes.
GROUPS = [
    "admin", "admin_p3de", "admin_p3der", "admin_pide", "admin_pmde",
    "user_p3de", "user_p3der", "user_pide", "user_pmde",
]

# Single-role accounts for the Seksi P3DE / P3DER split (test_p3der_seksi.py).
SEKSI_ACCOUNTS = {
    "pw_user_p3der": "user_p3der",
    "pw_kasi_p3der": "kasi_p3der",
    "pw_admin_p3der": "admin_p3der",
    "pw_kasi_p3de": "kasi_p3de",
    "pw_admin_p3de": "admin_p3de",
}

U = get_user_model()


def main():
    user, created = U.objects.get_or_create(
        username=USERNAME,
        defaults={
            "is_superuser": True,
            "is_staff": True,
            "first_name": "Playwright",
            "last_name": "Tester",
        },
    )
    user.is_superuser = True
    user.is_staff = True
    user.set_password(PASSWORD)
    user.save()

    for gname in GROUPS:
        g, _ = Group.objects.get_or_create(name=gname)
        user.groups.add(g)

    print(f"User {'created' if created else 'updated'}: {USERNAME} (password set)")

    # Pick a sub_jenis_data_ilap that has an active PeriodeJenisData.
    pjd = (
        PeriodeJenisData.objects
        .select_related("id_sub_jenis_data_ilap__id_ilap")
        .filter(end_date__isnull=True)
        .first()
    )
    if pjd is None:
        print("ERROR: no active PeriodeJenisData found; cannot assign PICs.")
        sys.exit(1)

    sub = pjd.id_sub_jenis_data_ilap
    print(f"Chosen sub_jenis_data_ilap: {sub.id_sub_jenis_data} "
          f"(ILAP: {sub.id_ilap.nama_ilap}, ilap_id={sub.id_ilap_id})")

    for tipe in (PIC.TipePIC.P3DE, PIC.TipePIC.PIDE, PIC.TipePIC.PMDE):
        obj, made = PIC.objects.get_or_create(
            tipe=tipe,
            id_sub_jenis_data_ilap=sub,
            id_user=user,
            end_date__isnull=True,
            defaults={"start_date": date(2020, 1, 1), "end_date": None},
        )
        # get_or_create with end_date__isnull lookup can't set start_date on match;
        # ensure it's populated/active.
        obj.start_date = obj.start_date or date(2020, 1, 1)
        obj.end_date = None
        obj.save()
        print(f"  PIC {tipe}: {'created' if made else 'exists'} (id={obj.id})")

    setup_seksi_accounts()

    print("\nSETUP OK")
    print(f"LOGIN_USER={USERNAME}")
    print(f"LOGIN_PASS={PASSWORD}")
    print(f"ILAP_ID={sub.id_ilap_id}")
    print(f"SUB_JENIS={sub.id_sub_jenis_data}")


def setup_seksi_accounts():
    """One account per P3DE / P3DER role, plus a Regional PIC for pw_user_p3der."""
    for username, group in SEKSI_ACCOUNTS.items():
        user, _ = U.objects.get_or_create(
            username=username,
            defaults={"first_name": "Playwright", "last_name": group},
        )
        user.is_superuser = False
        user.is_staff = False
        user.set_password(PASSWORD)
        user.save()
        user.groups.set([Group.objects.get_or_create(name=group)[0]])
        print(f"Seksi account: {username} ({group})")

    pjd = (
        PeriodeJenisData.objects
        .select_related("id_sub_jenis_data_ilap__id_ilap")
        .filter(
            end_date__isnull=True,
            id_sub_jenis_data_ilap__id_ilap__id_kategori_wilayah__deskripsi__icontains="regional",
        )
        .order_by("id_sub_jenis_data_ilap__id_sub_jenis_data")
        .first()
    )
    if pjd is None:
        print("WARNING: no active Regional PeriodeJenisData; pw_user_p3der gets no PIC.")
        return
    sub = pjd.id_sub_jenis_data_ilap
    user = U.objects.get(username="pw_user_p3der")
    obj, made = PIC.objects.get_or_create(
        tipe=PIC.TipePIC.P3DE,
        id_sub_jenis_data_ilap=sub,
        id_user=user,
        end_date__isnull=True,
        defaults={"start_date": date(2020, 1, 1), "end_date": None},
    )
    print(f"  pw_user_p3der PIC P3DE on Regional {sub.id_sub_jenis_data} "
          f"(ILAP {sub.id_ilap.nama_ilap}): {'created' if made else 'exists'}")


if __name__ == "__main__":
    main()
