# Default Templates Setup - Implementation Guide

## Overview

The application now uses **version-controlled default templates** committed to git, while still allowing users to upload custom templates to the `media/` folder.

## Architecture

```
Project Root
├── diamond_web/
│   ├── fixtures/
│   │   └── default_templates/          ← COMMITTED TO GIT (examples)
│   │       ├── *.docx (11 templates)
│   │       └── README.md
│   └── media/
│       └── docx_templates/            ← IGNORED BY GIT (user uploads)
│           └── (FileField storage)
├── .gitignore                          ← Updated to allow fixtures
```

## File Structure

### Fixtures (Version Controlled)
**Location:** `diamond_web/fixtures/default_templates/`

Contains 11 default DOCX template files:
- Template files are committed to git
- Used as examples and defaults on first setup
- Read-only reference for developers
- Can be edited and committed for template improvements

### Media (User Uploads - Not Version Controlled)  
**Location:** `diamond_web/media/docx_templates/`

Contains user-uploaded templates stored via Django FileField:
- All files here are ignored by git (as per `.gitignore`)
- Automatically organized by date (`YYYYMMDD/` subdirectories)
- Generated/uploaded files live here
- Production data stays local to each deployment

## .gitignore Configuration

```ignore
media/                                    # Ignore all media files
# But allow default templates in fixtures
!diamond_web/fixtures/default_templates/ # Exception: allow fixtures
!diamond_web/fixtures/default_templates/*.docx
```

This allows:
- ✓ Template DOCX files in `fixtures/` to be committed
- ✓ README.md in `fixtures/` to be committed
- ✗ All files in `media/` to be ignored

## Setup Process

### First Time Setup

1. Clone the repository (fixtures templates are already included)
2. Run migrations
3. Load default templates into database:

```bash
python manage.py load_default_templates
```

This command:
- Reads templates from `diamond_web/fixtures/default_templates/`
- Creates DocxTemplate records in database
- Copies files to `diamond_web/media/docx_templates/` via FileField
- Marks all templates as active

### Workflow

**On First Setup:**
```
fixtures/default_templates/*.docx
           ↓ (via load_default_templates command)
        Database (DocxTemplate records)
           ↓ (FileField saves)
media/docx_templates/*.docx
           ↓ (used for document generation)
      Generated documents
```

**When User Uploads Custom Template:**
```
User uploads via UI
           ↓
        Database (DocxTemplate record)
           ↓
media/docx_templates/*.docx (automatically saved)
           ↓ (used for document generation)
      Generated documents
```

## Template Management Commands

### Load Default Templates

```bash
# Load templates (skip if already exist)
python manage.py load_default_templates

# Reset and reload (deletes all, loads fresh)
python manage.py load_default_templates --reset
```

## User Workflow

### Admin Users

1. **View templates:** Go to "Kelola Template Dokumen" menu
2. **Upload custom:** Use the form to upload new templates
3. **Edit:** Update template content directly in UI
4. **Delete:** Remove custom templates
5. **Download:** Download any template to verify content

### Document Generation

The system automatically:
1. Detects document type requested
2. Checks region type (Regional vs Nasional/Internasional) from tiket
3. Selects appropriate template from database
4. Fills placeholders with tiket data
5. Returns generated DOCX file

## Development Workflow

### Improving Templates

1. Edit `.docx` files in `diamond_web/fixtures/default_templates/`
2. Keep placeholder variables intact: `{{variable_name}}`
3. Test in development
4. Commit changes to git

### For Reviewers
- Template changes are visible in git history
- Can see exactly what changed in templates
- Template quality is part of code review

## Database Reset Scenario

If database is reset but templates aren't:

```bash
# Reload default templates from fixtures
python manage.py load_default_templates --reset

# This restores:
# - All 11 DocxTemplate records
# - All 11 DOCX files in media folder
# - All templates marked as active
```

## Benefits

✓ **Version Control:** Templates are tracked in git like code  
✓ **Reproducibility:** New deployments automatically get default templates  
✓ **User Customization:** Users can still upload/manage custom templates  
✓ **Separation:** Development changes (fixtures) separate from user data (media)  
✓ **Consistency:** All deployments start with same template quality  
✓ **Documentation:** README explains template system to developers  

## Migration Notes

The migration from old system:
1. ✓ Deleted unused folders (old docx_templates/, templates/uploads/)
2. ✓ Kept current templates in media/ (active/used)
3. ✓ Copied templates to fixtures/ (for version control)
4. ✓ Updated .gitignore to allow fixtures but not media
5. ✓ Created management command for setup

No database changes needed - existing DocxTemplate records remain intact.
