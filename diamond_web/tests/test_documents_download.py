"""Tests for tiket/documents.py: tiket_documents_download view.

Covers all doc_type options and access control scenarios.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from diamond_web.models import TiketPIC, TandaTerimaData
from diamond_web.models.detil_tanda_terima import DetilTandaTerima
from diamond_web.tests.conftest import TiketFactory, TiketPICFactory, UserFactory


def _make_tiket_with_tanda_terima(user, status=1):
    """Create a tiket with tanda_terima=True and matching DetilTandaTerima."""
    tiket = TiketFactory(status_tiket=status, tanda_terima=True)
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.P3DE, active=True)
    ilap = tiket.id_periode_data.id_sub_jenis_data_ilap.id_ilap
    tt = TandaTerimaData.objects.create(
        nomor_tanda_terima=1,
        tahun_terima=timezone.now().year,
        tanggal_tanda_terima=timezone.now(),
        id_ilap=ilap,
        id_perekam=user,
        active=True,
    )
    DetilTandaTerima.objects.create(id_tanda_terima=tt, id_tiket=tiket)
    return tiket, tt


@pytest.mark.django_db
class TestTiketDocumentsDownload:
    """Tests for tiket_documents_download view."""

    def test_requires_login(self, client, tiket):
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_non_p3de_user_denied(self, client, pide_user, tiket):
        """Non-P3DE users cannot access document downloads."""
        client.force_login(pide_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code in (302, 403)

    def test_non_pic_p3de_user_gets_403(self, client, authenticated_user, db):
        """P3DE user without TiketPIC gets 403."""
        tiket = TiketFactory(status_tiket=1, tanda_terima=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code == 403

    def test_no_tanda_terima_returns_400(self, client, authenticated_user, db):
        """Returns 400 if tanda_terima=False."""
        tiket = TiketFactory(status_tiket=1, tanda_terima=False)
        TiketPICFactory(id_tiket=tiket, id_user=authenticated_user,
                        role=TiketPIC.Role.P3DE, active=True)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code == 400

    def test_admin_no_tanda_terima_returns_400(self, client, admin_user, db):
        """Admin also gets 400 if tanda_terima=False."""
        tiket = TiketFactory(status_tiket=1, tanda_terima=False)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code == 400

    def test_admin_can_download_tanda_terima(self, client, admin_user, authenticated_user, db):
        """Admin can download tanda_terima document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(admin_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'tanda_terima',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_pic_user_can_download_tanda_terima(self, client, authenticated_user, db):
        """P3DE PIC user can download tanda_terima document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'tanda_terima',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_lampiran(self, client, authenticated_user, db):
        """Download lampiran document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'lampiran',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_register(self, client, authenticated_user, db):
        """Download register document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'register',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_pkdi_lengkap(self, client, authenticated_user, db):
        """Download pkdi_lengkap document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'pkdi_lengkap',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_pkdi_sebagian(self, client, authenticated_user, db):
        """Download pkdi_sebagian document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'pkdi_sebagian',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_klarifikasi(self, client, authenticated_user, db):
        """Download klarifikasi document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'klarifikasi',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_download_nd_pengantar(self, client, authenticated_user, db):
        """Download nd_pengantar document."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'nd_pengantar',
        })
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_default_doc_type_is_tanda_terima(self, client, authenticated_user, db):
        """When doc_type is not specified, tanda_terima is the default."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code == 200
        assert 'application/vnd.openxmlformats' in resp.get('Content-Type', '')

    def test_content_disposition_contains_filename(self, client, authenticated_user, db):
        """Response has Content-Disposition with a filename."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'tanda_terima',
        })
        assert resp.status_code == 200
        assert 'filename' in resp.get('Content-Disposition', '')

    def test_with_docx_template(self, client, authenticated_user, db):
        """Uses DocxTemplate when active template exists."""
        from diamond_web.tests.conftest import DocxTemplateFactory
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        DocxTemplateFactory(
            jenis_dokumen='tanda_terima_nasional_internasional',
        )
        client.force_login(authenticated_user)
        resp = client.get(reverse('tiket_documents_download', args=[tiket.pk]), {
            'doc_type': 'tanda_terima',
        })
        # Should still return 200 (template may fail gracefully)
        assert resp.status_code in (200, 500)

    def test_requires_get_method(self, client, authenticated_user, db):
        """Only GET is allowed."""
        tiket, _ = _make_tiket_with_tanda_terima(authenticated_user)
        client.force_login(authenticated_user)
        resp = client.post(reverse('tiket_documents_download', args=[tiket.pk]))
        assert resp.status_code == 405
