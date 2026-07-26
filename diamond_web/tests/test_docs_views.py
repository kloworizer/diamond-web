"""Tests for views/docs.py (docs_index + docs_detail)."""
import pytest
from django.urls import reverse

from diamond_web.views.docs import DOC_GROUPS, get_docs_list


@pytest.mark.django_db
class TestGetDocsList:
    def test_returns_all_groups(self):
        docs = get_docs_list()
        group_names = [g['group'] for g in docs]
        assert group_names == list(DOC_GROUPS.keys())

    def test_readme_group_has_readme_entry(self):
        docs = get_docs_list()
        pendahuluan = next(g for g in docs if g['group'] == 'Pendahuluan')
        assert len(pendahuluan['docs']) == 1
        assert pendahuluan['docs'][0]['filename'] == 'readme.md'
        assert pendahuluan['docs'][0]['slug'] == 'readme'

    def test_known_title_used(self):
        docs = get_docs_list()
        design = next(g for g in docs if g['group'] == 'Fase Desain')
        titles = {d['filename']: d['title'] for d in design['docs']}
        assert titles['models_erd.md'] == 'Diagram ERD Model'

    def test_missing_file_excluded(self, tmp_path, monkeypatch):
        """A DOC_GROUPS entry whose file doesn't exist on disk is skipped."""
        import diamond_web.views.docs as docs_module
        monkeypatch.setattr(docs_module, 'DOCS_DIR', str(tmp_path))
        docs = docs_module.get_docs_list()
        design = next(g for g in docs if g['group'] == 'Fase Desain')
        # None of the Fase Desain files exist in the empty tmp_path.
        assert design['docs'] == []


@pytest.mark.django_db
class TestDocsIndex:
    def test_get_success(self, client):
        resp = client.get(reverse('docs_index'))
        assert resp.status_code == 200
        assert 'docs' in resp.context


@pytest.mark.django_db
class TestDocsDetail:
    def test_readme_renders(self, client):
        resp = client.get(reverse('docs_detail', kwargs={'slug': 'readme'}))
        assert resp.status_code == 200
        assert resp.context['slug'] == 'readme'
        assert 'html_content' in resp.context
        assert resp.context['page_title'] == 'README — Gambaran Umum Sistem Diamond'

    def test_known_doc_renders_with_known_title(self, client):
        resp = client.get(reverse('docs_detail', kwargs={'slug': 'SECURITY'}))
        assert resp.status_code == 200
        assert resp.context['page_title'] == 'Dokumentasi Keamanan'

    def test_unknown_slug_returns_404(self, client):
        resp = client.get(reverse('docs_detail', kwargs={'slug': 'does-not-exist'}))
        assert resp.status_code == 404

    def test_mermaid_block_converted_to_pre_tag(self, client, tmp_path, monkeypatch):
        import diamond_web.views.docs as docs_module
        doc_file = tmp_path / 'MERMAID_TEST.md'
        doc_file.write_text(
            "# Title\n\n```mermaid\ngraph TD;\n  A-->B;\n```\n\nEnd.",
            encoding='utf-8',
        )
        monkeypatch.setattr(docs_module, 'DOCS_DIR', str(tmp_path))
        resp = client.get(reverse('docs_detail', kwargs={'slug': 'MERMAID_TEST'}))
        assert resp.status_code == 200
        assert '<pre class="mermaid">' in resp.context['html_content']
        assert 'graph TD;' in resp.context['html_content']

    def test_unmapped_slug_uses_title_cased_fallback(self, client, tmp_path, monkeypatch):
        import diamond_web.views.docs as docs_module
        doc_file = tmp_path / 'some-custom-doc.md'
        doc_file.write_text("content", encoding='utf-8')
        monkeypatch.setattr(docs_module, 'DOCS_DIR', str(tmp_path))
        resp = client.get(reverse('docs_detail', kwargs={'slug': 'some-custom-doc'}))
        assert resp.status_code == 200
        assert resp.context['page_title'] == 'Some Custom Doc'
