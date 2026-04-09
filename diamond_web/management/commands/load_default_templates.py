"""Django management command to load default DOCX templates from fixtures."""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from pathlib import Path
from diamond_web.models.docx_template import DocxTemplate


class Command(BaseCommand):
    help = 'Load default DOCX templates from fixtures directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing templates before loading',
        )

    def handle(self, *args, **options):
        fixtures_dir = Path(__file__).resolve().parent.parent.parent.parent / 'diamond_web' / 'fixtures' / 'default_templates'

        if not fixtures_dir.exists():
            self.stdout.write(self.style.ERROR(f'Fixtures directory not found: {fixtures_dir}'))
            return

        # Map template files to jenis_dokumen
        template_mapping = {
            'tanda_terima_nasional_internasional.docx': 'tanda_terima_nasional_internasional',
            'tanda_terima_regional.docx': 'tanda_terima_regional',
            'lampiran_tanda_terima_nasional_internasional.docx': 'lampiran_tanda_terima_nasional_internasional',
            'lampiran_tanda_terima_regional.docx': 'lampiran_tanda_terima_regional',
            'register_penerimaan_data.docx': 'register_penerimaan_data',
            'nd_pengantar_pide.docx': 'nd_pengantar_pide',
            'surat_klarifikasi.docx': 'surat_klarifikasi',
            'surat_pkdi_nasional_internasional_lengkap.docx': 'surat_pkdi_nasional_internasional_lengkap',
            'surat_pkdi_nasional_internasional_sebagian.docx': 'surat_pkdi_nasional_internasional_sebagian',
            'surat_pkdi_regional_lengkap.docx': 'surat_pkdi_regional_lengkap',
            'surat_pkdi_regional_sebagian.docx': 'surat_pkdi_regional_sebagian',
        }

        if options.get('reset'):
            count = DocxTemplate.objects.count()
            DocxTemplate.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing templates'))

        loaded = 0
        skipped = 0

        for filename, jenis_dokumen in template_mapping.items():
            file_path = fixtures_dir / filename

            if not file_path.exists():
                self.stdout.write(self.style.WARNING(f'Template file not found: {filename}'))
                continue

            # Check if template already exists
            template, created = DocxTemplate.objects.get_or_create(
                jenis_dokumen=jenis_dokumen,
                defaults={
                    'nama_template': jenis_dokumen.replace('_', ' ').title(),
                    'active': True,
                }
            )

            # Load the file
            if created or not template.file_template:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                    template.file_template.save(filename, ContentFile(file_content), save=True)
                    loaded += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Loaded: {jenis_dokumen}'))
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'⊘ Skipped (already exists): {jenis_dokumen}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Done! Loaded {loaded} templates, skipped {skipped}'))
