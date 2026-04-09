# Default DOCX Templates

This directory contains default DOCX template files that are committed to git as examples and defaults for the application.

## Purpose

These templates are used as the default templates for document generation in the P3DE data collection workflow. When users upload custom templates, they override these defaults.

## Contents

The directory contains 11 template files for the following document types:

1. **tanda_terima_nasional_internasional.docx** - Receipt document for national/international ILAP
2. **tanda_terima_regional.docx** - Receipt document for regional ILAP
3. **lampiran_tanda_terima_nasional_internasional.docx** - Attachment for national/international receipt
4. **lampiran_tanda_terima_regional.docx** - Attachment for regional receipt
5. **register_penerimaan_data.docx** - Data receipt register
6. **nd_pengantar_pide.docx** - Covering letter to PIDE
7. **surat_klarifikasi.docx** - Clarification letter
8. **surat_pkdi_nasional_internasional_lengkap.docx** - PKDI letter (complete data) - national/international
9. **surat_pkdi_nasional_internasional_sebagian.docx** - PKDI letter (partial data) - national/international
10. **surat_pkdi_regional_lengkap.docx** - PKDI letter (complete data) - regional
11. **surat_pkdi_regional_sebagian.docx** - PKDI letter (partial data) - regional

## Usage

### Loading Templates

To load these default templates into the database on first setup:

```bash
python manage.py load_default_templates
```

This command will:
- Create DocxTemplate records for each template if they don't already exist
- Load the DOCX files into the media folder via Django's FileField
- Mark all templates as active by default

### Resetting Templates

To reset existing templates and reload from fixtures:

```bash
python manage.py load_default_templates --reset
```

This will delete all existing templates and reload them from the fixtures directory.

### Template Variables

All templates support the following placeholder variables:

- `{{nomor_tiket}}` - Ticket number
- `{{nomor_tanda_terima}}` - Receipt number
- `{{diterima_dari}}` - Received from (sender)
- `{{nama_kantor}}` - Office/institution name
- `{{nomor_surat_pengantar}}` - Letter number
- `{{tanggal_surat_pengantar}}` - Letter date
- `{{tanggal_penerimaan}}` - Reception date
- `{{nama_ilap}}` - ILAP name
- `{{jenis_data}}` - Data type
- `{{periode_data}}` - Data period
- `{{bentuk_data}}` - Data format/form
- `{{tanggal_terima_dip}}` - Reception date at DIP
- `{{cara_penyampaian}}` - Delivery method
- `{{nama_pic_p3de}}` - P3DE PIC name
- `{{nama_pic}}` - PIC name
- `{{email_pic}}` - PIC email
- `{{telepon_pic}}` - PIC phone
- `{{nama_tabel}}` - Table name
- `{{jumlah_record}}` - Record count
- `{{ukuran_file}}` - File size

These placeholders will be automatically replaced with actual values when documents are generated.

## Customizing Templates

To customize these templates:

1. Edit the DOCX files directly (they are standard Microsoft Word files)
2. Keep the placeholder variables intact (format: `{{variable_name}}`)
3. Save the files back to this directory
4. The changes will be reflected the next time `load_default_templates` is run

## Why These Are in Git

These templates are committed to the repository because they:
- Serve as defaults for new installations
- Document the expected structure of DOCX templates
- Provide examples of how to create custom templates
- Ensure consistency across deployments

The actual user-uploaded templates are stored in `diamond_web/media/` which is NOT committed to git.
