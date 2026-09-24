"""Template Dokumen: each seksi's admins manage only their own templates."""

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from diamond_web.models.docx_template import DocxTemplate
from diamond_web.tests.conftest import UserFactory


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)


def _user(*groups):
    user = UserFactory()
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _template(jenis_dokumen):
    template = DocxTemplate(nama_template=f'T {jenis_dokumen}', jenis_dokumen=jenis_dokumen, active=True)
    template.file_template.save(f'{jenis_dokumen}.docx', ContentFile(b'PK fake'), save=True)
    return template


@pytest.fixture
def templates(db):
    return {
        'p3de': _template('nd_pengantar_pide'),
        'pmde': _template('nd_pengantar_pdi'),
    }


def _listed(client):
    resp = client.get(reverse('docx_template_data'), {'draw': 1, 'start': 0, 'length': 50})
    assert resp.status_code == 200
    return {row['jenis_dokumen'] for row in resp.json()['data']}


@pytest.mark.django_db
class TestJenisDokumenForUser:
    def test_admin_p3de_owns_everything_but_pmde_types(self):
        allowed = DocxTemplate.jenis_dokumen_for_user(_user('admin_p3de'))
        assert 'nd_pengantar_pide' in allowed
        assert 'nd_pengantar_pdi' not in allowed

    def test_admin_pmde_owns_only_pmde_types(self):
        assert DocxTemplate.jenis_dokumen_for_user(_user('admin_pmde')) == {'nd_pengantar_pdi'}

    def test_admin_owns_all(self):
        assert len(DocxTemplate.jenis_dokumen_for_user(_user('admin'))) == len(DocxTemplate.DOCUMENT_TYPE_CHOICES)

    def test_user_pmde_owns_none(self):
        assert DocxTemplate.jenis_dokumen_for_user(_user('user_pmde')) == set()


@pytest.mark.django_db
class TestScopedViews:
    def test_list_data_scoped_per_seksi(self, client, templates):
        client.force_login(_user('admin_pmde'))
        assert _listed(client) == {'ND Pengantar ke PDI'}

        client.force_login(_user('admin_p3de'))
        assert _listed(client) == {'ND Pengantar ke PIDE'}

        client.force_login(_user('admin'))
        assert _listed(client) == {'ND Pengantar ke PDI', 'ND Pengantar ke PIDE'}

    def test_admin_pmde_can_edit_own_template(self, client, templates):
        client.force_login(_user('admin_pmde'))
        url = reverse('docx_template_update', kwargs={'pk': templates['pmde'].pk})
        assert client.get(url).status_code == 200
        resp = client.post(url, {
            'nama_template': 'ND PDI baru',
            'jenis_dokumen': 'nd_pengantar_pdi',
            'active': 'on',
        })
        assert resp.status_code in (200, 302)
        templates['pmde'].refresh_from_db()
        assert templates['pmde'].nama_template == 'ND PDI baru'

    @pytest.mark.parametrize('view', ['docx_template_update', 'docx_template_delete', 'docx_template_download'])
    def test_other_seksi_template_is_not_found(self, client, templates, view):
        client.force_login(_user('admin_pmde'))
        assert client.get(reverse(view, kwargs={'pk': templates['p3de'].pk})).status_code == 404

        client.force_login(_user('admin_p3de'))
        assert client.get(reverse(view, kwargs={'pk': templates['pmde'].pk})).status_code == 404

    def test_admin_pmde_cannot_delete_p3de_template(self, client, templates):
        client.force_login(_user('admin_pmde'))
        resp = client.post(reverse('docx_template_delete', kwargs={'pk': templates['p3de'].pk}))
        assert resp.status_code == 404
        assert DocxTemplate.objects.filter(pk=templates['p3de'].pk).exists()

    def test_create_form_offers_only_own_jenis_dokumen(self, client, db):
        client.force_login(_user('admin_pmde'))
        resp = client.get(reverse('docx_template_create'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        html = resp.json()['html'] if resp['Content-Type'].startswith('application/json') else resp.content.decode()
        assert 'value="nd_pengantar_pdi"' in html
        assert 'value="nd_pengantar_pide"' not in html

    def test_admin_pmde_cannot_create_p3de_template(self, client, db):
        client.force_login(_user('admin_pmde'))
        client.post(reverse('docx_template_create'), {
            'nama_template': 'Selundupan',
            'jenis_dokumen': 'nd_pengantar_pide',
            'file_template': SimpleUploadedFile('x.docx', b'PK fake'),
            'active': 'on',
        })
        assert not DocxTemplate.objects.filter(nama_template='Selundupan').exists()

    def test_user_pmde_is_forbidden(self, client, db):
        client.force_login(_user('user_pmde'))
        assert client.get(reverse('docx_template_list')).status_code == 403
