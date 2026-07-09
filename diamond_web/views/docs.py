import os
import re
import markdown
from django.shortcuts import render
from django.conf import settings
from django.http import Http404

DOCS_DIR = os.path.join(settings.BASE_DIR, 'docs')
README_PATH = os.path.join(settings.BASE_DIR, 'readme.md')

# Mapping of filename to display title (Bahasa Indonesia)
DOC_TITLES = {
    'readme.md': 'README — Gambaran Umum Sistem Diamond',
    'PRODUCTION_SETUP.md': 'Panduan Setup Produksi',
    'API_DOCUMENTATION.md': 'Dokumentasi API',
    'models_erd.md': 'Diagram ERD Model',
    'SECURITY.md': 'Dokumentasi Keamanan',
    'HANDOVER_DOCUMENT.md': 'Dokumen Serah Terima Proyek',
    'CONTRIBUTING.md': 'Panduan Kontribusi',
    'CHANGELOG.md': 'Catatan Rilis & Perubahan',
    'ORACLE_SETUP.md': 'Panduan Setup Database Oracle',
    'status_tiket_flow.md': 'Diagram Alur Status Tiket',
    'TEMPLATES_SETUP.md': 'Panduan Setup Template Default',
    'RBAC_MATRIX.md': 'Matriks RBAC & Hak Akses Menu',
    'DATA_MIGRATION_DEV_PHASE.md': 'Panduan Migrasi Data',
    'SYNC_TIKET_UPDATE_RULES.md': 'Aturan Sinkronisasi Status Tiket (Oracle Sync)',
}

# Phase grouping for documentation (Bahasa Indonesia)
DOC_GROUPS = {
    'Pendahuluan': [
        'readme.md',
    ],
    'Fase Desain': [
        'models_erd.md',
        'status_tiket_flow.md',
        'RBAC_MATRIX.md',
    ],
    'Fase Pengembangan': [
        'API_DOCUMENTATION.md',
        'CONTRIBUTING.md',
        'SECURITY.md',
        'CHANGELOG.md',
        'DATA_MIGRATION_DEV_PHASE.md',
        'SYNC_TIKET_UPDATE_RULES.md',
    ],
    'Fase Produksi': [
        'PRODUCTION_SETUP.md',
        'ORACLE_SETUP.md',
        'TEMPLATES_SETUP.md',
        'HANDOVER_DOCUMENT.md',
    ],
}


def get_docs_list():
    """Return a list of doc metadata dictionaries grouped by phase."""
    docs = []
    for group_name, filenames in DOC_GROUPS.items():
        group_docs = []
        for filename in filenames:
            if filename == 'readme.md':
                filepath = README_PATH
            else:
                filepath = os.path.join(DOCS_DIR, filename)
            if os.path.exists(filepath):
                group_docs.append({
                    'filename': filename,
                    'title': DOC_TITLES.get(filename, filename.replace('.md', '').replace('_', ' ').title()),
                    'slug': filename.replace('.md', ''),
                })
        docs.append({
            'group': group_name,
            'docs': group_docs,
        })
    return docs


def docs_index(request):
    """List all available documentation files."""
    docs = get_docs_list()
    return render(request, 'docs/index.html', {'docs': docs})


def docs_detail(request, slug):
    """Render a single markdown file as HTML."""
    filename = f'{slug}.md'

    if filename == 'readme.md':
        filepath = README_PATH
    else:
        filepath = os.path.join(DOCS_DIR, filename)

    if not os.path.exists(filepath):
        raise Http404(f"Document '{filename}' not found.")

    with open(filepath, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Pre-process Mermaid code blocks: convert ```mermaid to raw HTML
    # so that codehilite doesn't try to syntax-highlight them.
    # This renders them as <pre class="mermaid"> blocks for Mermaid.js.
    def replace_mermaid(match):
        code = match.group(1).strip()
        # Escape HTML entities inside the mermaid code
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<pre class="mermaid">{code}</pre>'

    md_content = re.sub(
        r'```mermaid\s*\n(.*?)```',
        replace_mermaid,
        md_content,
        flags=re.DOTALL
    )

    # Configure markdown with extensions
    md_extensions = [
        'markdown.extensions.extra',       # Tables, fenced code, etc.
        'markdown.extensions.codehilite',  # Syntax highlighting (uses Pygments)
        'markdown.extensions.toc',          # Table of contents
        'markdown.extensions.nl2br',        # Newline to <br>
        'markdown.extensions.sane_lists',   # Sane lists
    ]

    html_content = markdown.markdown(md_content, extensions=md_extensions)

    # Get page title from grouped docs
    docs = get_docs_list()
    doc_titles = {}
    for group in docs:
        for d in group['docs']:
            doc_titles[d['slug']] = d['title']
    page_title = doc_titles.get(slug, slug.replace('-', ' ').title())

    context = {
        'html_content': html_content,
        'page_title': page_title,
        'slug': slug,
        'docs': docs,
    }
    return render(request, 'docs/detail.html', context)
