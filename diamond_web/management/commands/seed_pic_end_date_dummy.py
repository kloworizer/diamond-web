"""Seed the scenario behind the "PIC sudah berakhir masih muncul" bug report.

The dev database has no PIC row with an ``end_date`` at all, so the rekam tiket
dropdown filtering cannot be exercised against it. This command builds a small,
self-contained ILAP with two sub jenis data:

* ``expired`` -- the dummy P3DE user's assignment ended yesterday, and somebody
  else has since taken over and is still active on it.
* ``kept``    -- the dummy P3DE user is still active, which keeps the ILAP
  itself visible to them.

Only ``kept`` may appear in the "Jenis Data ILAP" dropdown. Before the fix the
end_date window was checked against a second, unrelated ``pic`` join, so the
takeover PIC on ``expired`` kept it in the list too.

Idempotent: re-running updates the same records. Use ``--remove`` to delete
everything it created.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from diamond_web.models import (
    ILAP, JenisDataILAP, JenisTabel, KategoriILAP, KategoriWilayah,
    PIC, PeriodeJenisData, PeriodePengiriman, StatusData,
)

User = get_user_model()

ILAP_ID = 'ZZ999'
SUB_EXPIRED = 'ZZ9990101'
SUB_KEPT = 'ZZ9990202'
USER_EXPIRED = 'dummy_p3de_expired'
USER_TAKEOVER = 'dummy_p3de_takeover'
PASSWORD = 'dummy12345'


class Command(BaseCommand):
    help = "Seed a P3DE PIC whose assignment has ended, for rekam tiket dropdown testing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Delete the dummy records instead of creating them.',
        )

    def handle(self, *args, **options):
        if options['remove']:
            self._remove()
            return
        self._seed()

    @transaction.atomic
    def _seed(self):
        today = date.today()

        kategori, _ = KategoriILAP.objects.get_or_create(
            id_kategori='K1', defaults={'nama_kategori': 'Kementerian / Lembaga'}
        )
        wilayah, _ = KategoriWilayah.objects.get_or_create(deskripsi='Nasional')
        jenis_tabel, _ = JenisTabel.objects.get_or_create(deskripsi='Tabel Transaksi')
        status_data, _ = StatusData.objects.get_or_create(deskripsi='Data Tersedia')
        periode_pengiriman, _ = PeriodePengiriman.objects.get_or_create(
            periode_penyampaian='Bulanan', periode_penerimaan='Bulanan'
        )

        ilap, _ = ILAP.objects.get_or_create(
            id_ilap=ILAP_ID,
            defaults={
                'nama_ilap': 'ZZ Dummy ILAP - Uji PIC End Date',
                'id_kategori': kategori,
                'id_kategori_wilayah': wilayah,
            },
        )

        jenis_data = {}
        for sub_id, nama in (
            (SUB_EXPIRED, 'Sub Jenis Data - PIC Sudah Berakhir'),
            (SUB_KEPT, 'Sub Jenis Data - PIC Masih Aktif'),
        ):
            jd, _ = JenisDataILAP.objects.get_or_create(
                id_sub_jenis_data=sub_id,
                defaults={
                    'id_ilap': ilap,
                    'id_jenis_data': 'ZZ999',
                    'nama_jenis_data': 'Jenis Data Dummy Uji End Date',
                    'nama_sub_jenis_data': nama,
                    'nama_tabel_I': f'TABEL_I_{sub_id}',
                    'nama_tabel_U': f'TABEL_U_{sub_id}',
                    'id_jenis_tabel': jenis_tabel,
                    'id_status_data': status_data,
                },
            )
            jenis_data[sub_id] = jd
            PeriodeJenisData.objects.get_or_create(
                id_sub_jenis_data_ilap=jd,
                id_periode_pengiriman=periode_pengiriman,
                defaults={'start_date': today - timedelta(days=365), 'akhir_penyampaian': 31},
            )

        p3de_group, _ = Group.objects.get_or_create(name='user_p3de')
        users = {}
        for username in (USER_EXPIRED, USER_TAKEOVER):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': 'Dummy', 'last_name': username.split('_')[-1].title()},
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            user.groups.add(p3de_group)
            users[username] = user

        # The reporting user: ended on `expired`, still active on `kept`.
        self._set_pic(
            users[USER_EXPIRED], jenis_data[SUB_EXPIRED],
            start_date=today - timedelta(days=365),
            end_date=today - timedelta(days=1),
        )
        self._set_pic(
            users[USER_EXPIRED], jenis_data[SUB_KEPT],
            start_date=today - timedelta(days=365),
            end_date=None,
        )
        # The takeover: still active on `expired`.
        self._set_pic(
            users[USER_TAKEOVER], jenis_data[SUB_EXPIRED],
            start_date=today - timedelta(days=1),
            end_date=None,
        )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded ILAP {ILAP_ID} (pk={ilap.pk}).\n'
            f'  {USER_EXPIRED} / {PASSWORD}\n'
            f'    {SUB_EXPIRED}: P3DE ended {today - timedelta(days=1)}  -> must NOT appear\n'
            f'    {SUB_KEPT}: P3DE active            -> must appear\n'
            f'  {USER_TAKEOVER} is the active PIC on {SUB_EXPIRED}.'
        ))

    def _set_pic(self, user, jenis_data, start_date, end_date):
        """Create or update the single P3DE assignment for this user/jenis data."""
        pic, created = PIC.objects.update_or_create(
            tipe=PIC.TipePIC.P3DE,
            id_sub_jenis_data_ilap=jenis_data,
            id_user=user,
            defaults={'start_date': start_date, 'end_date': end_date},
        )
        return pic

    @transaction.atomic
    def _remove(self):
        PIC.objects.filter(
            id_sub_jenis_data_ilap__id_sub_jenis_data__in=[SUB_EXPIRED, SUB_KEPT]
        ).delete()
        PeriodeJenisData.objects.filter(
            id_sub_jenis_data_ilap__id_sub_jenis_data__in=[SUB_EXPIRED, SUB_KEPT]
        ).delete()
        JenisDataILAP.objects.filter(
            id_sub_jenis_data__in=[SUB_EXPIRED, SUB_KEPT]
        ).delete()
        ILAP.objects.filter(id_ilap=ILAP_ID).delete()
        User.objects.filter(username__in=[USER_EXPIRED, USER_TAKEOVER]).delete()
        self.stdout.write(self.style.SUCCESS('Dummy PIC end_date records removed.'))
