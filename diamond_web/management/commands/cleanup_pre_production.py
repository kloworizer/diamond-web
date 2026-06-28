"""
Management command to clean up pre-production tiket data.

Purpose:
    Performs comprehensive cleanup of test data entered during the testing
    period before going to production:
      1. Truncates all BackupData, TandaTerimaData, DetilTandaTerima records
      2. Deletes TiketAction rows except for action type 301 (PIC Ditambahkan)
      3. Deletes all Tiket records where old_db=False, along with related
         records (TiketPIC, KirimPideTemp, etc.)

    This ensures only tickets synced/migrated from the old database
    (old_db=True) remain, and any user test entries are fully removed.

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
from diamond_web.models.tanda_terima_data import TandaTerimaData

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Bersihkan semua data testing (pre-produksi): hapus tiket old_db=False, truncate data testing, hapus TiketAction selain PIC Ditambahkan"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Hitung jumlah record yang akan dihapus tanpa benar-benar menghapus',
        )
        parser.add_argument(
            '--skip-test-data',
            action='store_true',
            help='Lewati pembersihan data testing (BackupData, TandaTerimaData, DetilTandaTerima, TiketAction)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        skip_test_data = options.get('skip_test_data', False)

        # ================================================================
        # PHASE 1: Cleanup data testing (BackupData, TandaTerimaData,
        #           DetilTandaTerima, TiketAction)
        # ================================================================
        test_data_counts = {}
        if not skip_test_data:
            test_data_counts = {
                'BackupData (semua)': BackupData.objects.count(),
                'TandaTerimaData (semua)': TandaTerimaData.objects.count(),
                'DetilTandaTerima (semua)': DetilTandaTerima.objects.count(),
                'TiketAction (selain action=301)': TiketAction.objects.exclude(action=301).count(),
            }
            total_test_data = sum(test_data_counts.values())

            if total_test_data > 0:
                self.stdout.write("=" * 50)
                self.stdout.write("PHASE 1: Pembersihan data testing")
                self.stdout.write("=" * 50)
                self.stdout.write("Record testing yang akan dibersihkan:")
                for model_name, count in test_data_counts.items():
                    self.stdout.write(f"  - {model_name}: {count}")
                self.stdout.write(f"  Total data testing: {total_test_data} records")

                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        "  [DRY-RUN] Tidak ada perubahan yang dilakukan."
                    ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "Tidak ada data testing untuk dibersihkan."
                ))
        else:
            self.stdout.write(self.style.WARNING(
                "PHASE 1 dilewati (--skip-test-data)."
            ))

        # ================================================================
        # PHASE 2: Hapus Tiket dengan old_db=False
        # ================================================================
        # Get all Tiket IDs where old_db=False
        tiket_ids = list(
            Tiket.objects.filter(old_db=False).values_list('id', flat=True)
        )
        total_tiket = len(tiket_ids)

        if total_tiket > 0:
            # Count related records for reporting
            old_db_counts = {
                'TiketPIC': TiketPIC.objects.filter(id_tiket__in=tiket_ids).count(),
                'TiketAction': TiketAction.objects.filter(id_tiket__in=tiket_ids).count(),
                'KirimPideTemp': KirimPideTemp.objects.filter(id_tiket__in=tiket_ids).count(),
            }

            self.stdout.write("\n" + "=" * 50)
            self.stdout.write(f"PHASE 2: Hapus {total_tiket} tiket dengan old_db=False")
            self.stdout.write("=" * 50)
            self.stdout.write("Record terkait yang akan dihapus:")
            for model_name, count in old_db_counts.items():
                self.stdout.write(f"  - {model_name}: {count}")
            self.stdout.write(f"  - Tiket: {total_tiket}")
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nTidak ada tiket dengan old_db=False untuk dibersihkan."
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\nDry-run mode: tidak ada perubahan yang dilakukan."
            ))
            return

        # Perform deletion inside a transaction
        with transaction.atomic():
            # ---- PHASE 1: Cleanup data testing ----
            if not skip_test_data and total_test_data > 0:
                self.stdout.write("\n--- Phase 1: Membersihkan data testing ---")

                # Order matters: DetilTandaTerima references TandaTerimaData and Tiket
                self.stdout.write("Menghapus DetilTandaTerima (semua)...")
                deleted, _ = DetilTandaTerima.objects.all().delete()
                self.stdout.write(f"  -> {deleted} DetilTandaTerima dihapus")

                self.stdout.write("Menghapus TandaTerimaData (semua)...")
                deleted, _ = TandaTerimaData.objects.all().delete()
                self.stdout.write(f"  -> {deleted} TandaTerimaData dihapus")

                self.stdout.write("Menghapus BackupData (semua)...")
                deleted, _ = BackupData.objects.all().delete()
                self.stdout.write(f"  -> {deleted} BackupData dihapus")

                self.stdout.write("Menghapus TiketAction (kecuali action=301)...")
                deleted, _ = TiketAction.objects.exclude(action=301).delete()
                self.stdout.write(f"  -> {deleted} TiketAction dihapus")

            # ---- PHASE 2: Hapus Tiket old_db=False ----
            if total_tiket > 0:
                self.stdout.write("\n--- Phase 2: Menghapus tiket old_db=False ---")

                self.stdout.write("Menghapus TiketPIC...")
                deleted, _ = TiketPIC.objects.filter(id_tiket__in=tiket_ids).delete()
                self.stdout.write(f"  -> {deleted} TiketPIC dihapus")

                self.stdout.write("Menghapus TiketAction (old_db=False)...")
                deleted, _ = TiketAction.objects.filter(id_tiket__in=tiket_ids).delete()
                self.stdout.write(f"  -> {deleted} TiketAction dihapus")

                self.stdout.write("Menghapus KirimPideTemp...")
                deleted, _ = KirimPideTemp.objects.filter(id_tiket__in=tiket_ids).delete()
                self.stdout.write(f"  -> {deleted} KirimPideTemp dihapus")

                # Tiket dengan old_db=False
                self.stdout.write("Menghapus Tiket (old_db=False)...")
                deleted, _ = Tiket.objects.filter(old_db=False).delete()
                self.stdout.write(f"  -> {deleted} Tiket dihapus")

        # ---- Summary ----
        phase1_msg = ""
        if not skip_test_data:
            phase1_msg = f", {total_test_data} data testing dibersihkan"
        phase2_msg = ""
        if total_tiket > 0:
            phase2_msg = f", {total_tiket} tiket (old_db=False) dihapus"

        self.stdout.write(self.style.SUCCESS(
            "\nPembersihan pre-produksi selesai!" + phase1_msg + phase2_msg
        ))
