import os
import re
import markdown
from django.shortcuts import render
from django.conf import settings
from django.http import Http404

DOCS_DIR = os.path.join(settings.BASE_DIR, 'docs')
README_PATH = os.path.join(settings.BASE_DIR, 'readme.md')

# Mapping of filename to display title
DOC_TITLES = {
    'readme.md': 'README — Diamond System Overview',
    'PRODUCTION_SETUP.md': 'Production Setup Guide',
    'API_DOCUMENTATION.md': 'API Documentation',
    'models_erd.md': 'Model ER Diagram',
    'DEPLOYMENT_CHECKLIST.md': 'Deployment Checklist',
    'SECURITY.md': 'Security Documentation',
    'HANDOVER_DOCUMENT.md': 'Project Handover Document',
    'CONTRIBUTING.md': 'Contributing Guidelines',
    'CHANGELOG.md': 'Changelog & Release Notes',
    'ORACLE_SETUP.md': 'Oracle Database Setup Guide',
    'status_tiket_flow.md': 'Diagram Alur Status Tiket',
    'TEMPLATES_SETUP.md': 'Default Templates Setup Guide',
}

# Ordered list of docs for the index page
DOC_ORDER = [
    'readme.md',
    'PRODUCTION_SETUP.md',
    'API_DOCUMENTATION.md',
    'models_erd.md',
    'DEPLOYMENT_CHECKLIST.md',
    'SECURITY.md',
    'HANDOVER_DOCUMENT.md',
    'CONTRIBUTING.md',
    'CHANGELOG.md',
    'ORACLE_SETUP.md',
    'status_tiket_flow.md',
    'TEMPLATES_SETUP.md',
]


def get_docs_list():
    """Return a list of doc metadata dictionaries."""
    docs = []
    for filename in DOC_ORDER:
        if filename == 'readme.md':
            filepath = README_PATH
        else:
            filepath = os.path.join(DOCS_DIR, filename)
        if os.path.exists(filepath):
            docs.append({
                'filename': filename,
                'title': DOC_TITLES.get(filename, filename.replace('.md', '').replace('_', ' ').title()),
                'slug': filename.replace('.md', ''),
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

    # Get page title
    docs = get_docs_list()
    doc_titles = {d['slug']: d['title'] for d in docs}
    page_title = doc_titles.get(slug, slug.replace('-', ' ').title())

    context = {
        'html_content': html_content,
        'page_title': page_title,
        'slug': slug,
        'docs': docs,
    }
    return render(request, 'docs/detail.html', context)
