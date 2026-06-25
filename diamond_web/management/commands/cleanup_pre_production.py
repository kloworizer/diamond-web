"""
Management command to clean up pre-production tiket data.

Purpose:
    Deletes all Tiket records where old_db=False, along with their related
    records (TiketPIC, TiketAction, KirimPideTemp, DetilTandaTerima,
    BackupData). This ensures only tickets synced/migrated from the old
    database (old_db=True) remain before going to production.

Scheduled to run via Celery Beat on July 1, 2026 at 00:00 WIB.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from diamond_web.models.tiket import Tiket
from diamond_web.models.tiket_pic import TiketPIC
from diamond_web.models.tiket_action import TiketAction
from diamond_web.models.kirim_pide_temp import KirimPideTemp
from diamond_web.models.detil_tanda_terima import DetilTandaTerima
from diamond_web.models.backup_data import BackupData

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Hapus semua data tiket dengan old_db=False beserta relasinya"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Hitung jumlah record yang akan dihapus tanpa benar-benar menghapus',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        # Get all Tiket IDs where old_db=False
        tiket_ids = list(
            Tiket.objects.filter(old_db=False).values_list('id', flat=True)
        )
        total_tiket = len(tiket_ids)

        if total_tiket == 0:
            self.stdout.write(self.style.SUCCESS(
                "Tidak ada tiket dengan old_db=False untuk dibersihkan."
            ))
            return

        self.stdout.write(f"Ditemukan {total_tiket} tiket dengan old_db=False.")

        # Count related records for reporting
        counts = {
            'TiketPIC': TiketPIC.objects.filter(id_tiket__in=tiket_ids).count(),
            'TiketAction': TiketAction.objects.filter(id_tiket__in=tiket_ids).count(),
            'KirimPideTemp': KirimPideTemp.objects.filter(id_tiket__in=tiket_ids).count(),
            'DetilTandaTerima': DetilTandaTerima.objects.filter(id_tiket__in=tiket_ids).count(),
            'BackupData': BackupData.objects.filter(id_tiket__in=tiket_ids).count(),
        }

        total_related = sum(counts.values())

        self.stdout.write("Record terkait yang akan dihapus:")
        for model_name, count in counts.items():
            self.stdout.write(f"  - {model_name}: {count}")
        self.stdout.write(f"  - Tiket: {total_tiket}")
        self.stdout.write(f"  Total: {total_tiket + total_related} records")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "Dry-run mode: tidak ada perubahan yang dilakukan."
            ))
            return

        # Perform deletion inside a transaction
        with transaction.atomic():
            # Order matters: delete child records before parent
            self.stdout.write("Menghapus TiketPIC...")
            deleted, _ = TiketPIC.objects.filter(id_tiket__in=tiket_ids).delete()
            self.stdout.write(f"  -> {deleted} TiketPIC dihapus")

            self.stdout.write("Menghapus TiketAction...")
            deleted, _ = TiketAction.objects.filter(id_tiket__in=tiket_ids).delete()
            self.stdout.write(f"  -> {deleted} TiketAction dihapus")

            self.stdout.write("Menghapus KirimPideTemp...")
            deleted, _ = KirimPideTemp.objects.filter(id_tiket__in=tiket_ids).delete()
            self.stdout.write(f"  -> {deleted} KirimPideTemp dihapus")

            self.stdout.write("Menghapus DetilTandaTerima...")
            deleted, _ = DetilTandaTerima.objects.filter(id_tiket__in=tiket_ids).delete()
            self.stdout.write(f"  -> {deleted} DetilTandaTerima dihapus")

            self.stdout.write("Menghapus BackupData...")
            deleted, _ = BackupData.objects.filter(id_tiket__in=tiket_ids).delete()
            self.stdout.write(f"  -> {deleted} BackupData dihapus")

            # Finally delete the Tiket records
            self.stdout.write("Menghapus Tiket (old_db=False)...")
            deleted, _ = Tiket.objects.filter(old_db=False).delete()
            self.stdout.write(f"  -> {deleted} Tiket dihapus")

        self.stdout.write(self.style.SUCCESS(
            "Pembersihan data pre-produksi selesai. "
            f"{total_tiket} tiket (old_db=False) dan {total_related} record terkait telah dihapus."
        ))
