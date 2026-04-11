"""Tests to cover remaining small gaps in simple CRUD view files.

Covers:
- except Exception: pass in list view delete toast handlers (via mock.patch)
- except ValueError: pass in datatables column ID search handlers
- Additional missing lines in various view files
"""
import json
import pytest
from unittest.mock import patch
from urllib.parse import quote_plus
from django.urls import reverse
from django.contrib.auth.models import Group

from .conftest import (
    UserFactory, BentukDataFactory, CaraPenyampaianFactory, DasarHukumFactory,
    KanwilFactory, KPPFactory, StatusDataFactory, MediaBackupFactory,
    KategoriWilayahFactory, KlasifikasiJenisDataFactory, JenisTabelFactory,
    JenisDataILAPFactory, ILAPFactory, KategoriILAPFactory,
)


@pytest.fixture
def p3de_admin(db):
    user = UserFactory()
    grp, _ = Group.objects.get_or_create(name='admin_p3de')
    user.groups.add(grp)
    return user


@pytest.fixture
def admin_user(db):
    user = UserFactory(is_staff=True, is_superuser=True)
    grp, _ = Group.objects.get_or_create(name='admin')
    user.groups.add(grp)
    return user


# ─── LIST VIEW EXCEPTION HANDLERS ────────────────────────────────────────────
# Lines like 26-27, 36-37 in bentuk_data.py etc. are "except Exception: pass"
# blocks. We use mock.patch to make unquote_plus raise an exception.

@pytest.mark.django_db
class TestListViewExceptionHandlers:
    """Cover except Exception: pass blocks in list view delete toast handlers."""

    def _get_toast_url(self, url_name, obj_name='Test'):
        return reverse(url_name), {'deleted': '1', 'name': quote_plus(obj_name)}

    def test_bentuk_data_list_exception_in_toast(self, client, p3de_admin):
        """Lines 26-27: bentuk_data list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.bentuk_data.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('bentuk_data_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_cara_penyampaian_list_exception_in_toast(self, client, p3de_admin):
        """Lines 26-27: cara_penyampaian list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.cara_penyampaian.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('cara_penyampaian_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_media_backup_list_exception_in_toast(self, client, p3de_admin):
        """Lines 26-27: media_backup list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.media_backup.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('media_backup_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_status_penelitian_list_exception_in_toast(self, client, p3de_admin):
        """Lines 26-27: status_penelitian list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.status_penelitian.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('status_penelitian_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_dasar_hukum_list_exception_in_toast(self, client, p3de_admin):
        """Lines 36-37: dasar_hukum list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.dasar_hukum.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('dasar_hukum_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_kanwil_list_exception_in_toast(self, client, p3de_admin):
        """Lines 27-28: kanwil list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.kanwil.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('kanwil_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_kpp_list_exception_in_toast(self, client, p3de_admin):
        """Lines 27-28: kpp list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.kpp.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('kpp_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_status_data_list_exception_in_toast(self, client, p3de_admin):
        """Lines 36-37: status_data list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.status_data.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('status_data_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_kategori_wilayah_list_exception_in_toast(self, client, p3de_admin):
        """Lines 36-37: kategori_wilayah list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.kategori_wilayah.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('kategori_wilayah_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_klasifikasi_jenis_data_list_exception_in_toast(self, client, p3de_admin):
        """Lines 36-37: klasifikasi_jenis_data list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.klasifikasi_jenis_data.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('klasifikasi_jenis_data_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_periode_pengiriman_list_exception_in_toast(self, client, p3de_admin):
        """Lines 36-37: periode_pengiriman list view - except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.periode_pengiriman.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('periode_pengiriman_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_ilap_list_exception_in_toast(self, client, p3de_admin):
        """ilap lines 38-39: except Exception: pass in ILAPListView."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.ilap.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('ilap_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200


# ─── DATATABLES ValueError HANDLERS ─────────────────────────────────────────
# Lines like 121-122 in bentuk_data.py (except ValueError: pass in column ID search)

@pytest.mark.django_db
class TestDatatablesValueErrorHandlers:
    """Cover except ValueError: pass in datatables column ID search."""

    def test_bentuk_data_datatables_invalid_id_search(self, client, p3de_admin):
        """Lines 121-122: bentuk_data_data - non-numeric ID in column search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('bentuk_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',  # Invalid ID → ValueError
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['draw'] == 1

    def test_cara_penyampaian_datatables_invalid_id_search(self, client, p3de_admin):
        """cara_penyampaian_data - non-numeric ID in column search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('cara_penyampaian_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_media_backup_datatables_invalid_id_search(self, client, p3de_admin):
        """media_backup_data - non-numeric ID in column search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('media_backup_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_penelitian_datatables_invalid_id_search(self, client, p3de_admin):
        """status_penelitian_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_penelitian_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_dasar_hukum_datatables_invalid_id_search(self, client, p3de_admin):
        """dasar_hukum_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('dasar_hukum_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_data_datatables_invalid_id_search(self, client, p3de_admin):
        """status_data_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_kategori_wilayah_datatables_invalid_id_search(self, client, p3de_admin):
        """kategori_wilayah_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('kategori_wilayah_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_klasifikasi_jenis_data_datatables_invalid_id_search(self, client, p3de_admin):
        """klasifikasi_jenis_data_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('klasifikasi_jenis_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_periode_pengiriman_datatables_invalid_id_search(self, client, p3de_admin):
        """periode_pengiriman_data - non-numeric ID search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('periode_pengiriman_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_jenis_tabel_datatables_exception_ordering(self, client, p3de_admin):
        """jenis_tabel_data line 97 - exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('jenis_tabel_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',  # Should trigger except
        })
        assert resp.status_code == 200


# ─── ADDITIONAL MISSING LINES ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestAdditionalMissingLines:
    """Cover additional missing lines in various view files."""

    def test_kanwil_datatables_invalid_ordering(self, client, p3de_admin):
        """kanwil line 127: except Exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('kanwil_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_kpp_datatables_invalid_ordering(self, client, p3de_admin):
        """kpp line ~96: similar exception in datatables."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('kpp_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_dasar_hukum_datatables_invalid_ordering(self, client, p3de_admin):
        """dasar_hukum line 116: except Exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('dasar_hukum_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_data_datatables_invalid_ordering(self, client, p3de_admin):
        """status_data line 116: except Exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_data_datatables_desc_ordering(self, client, p3de_admin, db):
        """status_data datatables with desc ordering (extra branch)."""
        StatusDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_status_data_no_delete_to_cover_non_ajax_success_message(self, client, p3de_admin, db):
        """status_data lines 157-158 (dasar_hukum too): the delete non-ajax result."""
        obj = StatusDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        # SafeDeleteMixin.delete() is called - test non-AJAX path (lines 175-176 in status_data.py)
        resp = client.post(reverse('status_data_delete', args=[pk]))
        assert resp.status_code == 200

    def test_dasar_hukum_datatables_desc_ordering(self, client, p3de_admin, db):
        """dasar_hukum datatables with desc ordering."""
        DasarHukumFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('dasar_hukum_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_media_backup_datatables_invalid_ordering(self, client, p3de_admin):
        """media_backup datatables - exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('media_backup_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_media_backup_datatables_desc_ordering(self, client, p3de_admin, db):
        """Lines 139-140: media_backup datatables desc ordering."""
        MediaBackupFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('media_backup_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_kategori_wilayah_datatables_invalid_ordering(self, client, p3de_admin):
        """kategori_wilayah line 115: exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('kategori_wilayah_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_klasifikasi_jenis_data_datatables_invalid_ordering(self, client, p3de_admin):
        """klasifikasi_jenis_data line 116: exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('klasifikasi_jenis_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_klasifikasi_jenis_data_datatables_desc_ordering(self, client, p3de_admin, db):
        """klasifikasi_jenis_data line 158: datatables with desc ordering."""
        KlasifikasiJenisDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('klasifikasi_jenis_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_periode_pengiriman_datatables_invalid_ordering(self, client, p3de_admin):
        """periode_pengiriman line 116: exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('periode_pengiriman_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_penelitian_datatables_invalid_ordering(self, client, p3de_admin):
        """status_penelitian: exception in ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_penelitian_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_status_penelitian_datatables_desc_ordering(self, client, p3de_admin, db):
        """status_penelitian lines 119-120: datatables with desc ordering."""
        from .conftest import StatusPenelitianFactory
        StatusPenelitianFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_penelitian_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_ilap_datatables_invalid_id_search(self, client, p3de_admin):
        """ilap lines 38-39: except ValueError in ILAP ID column search."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_ilap_datatables_invalid_ordering(self, client, p3de_admin):
        """ilap line 115: except in ILAP ordering."""
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'not_a_number',
        })
        assert resp.status_code == 200

    def test_ilap_datatables_desc_ordering(self, client, p3de_admin, db):
        """ilap line 119: with desc ordering."""
        ILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '0', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200

    def test_ilap_datatables_column3_search(self, client, p3de_admin, db):
        """ilap line 115: 3rd column search (id_kategori)."""
        obj = ILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': ['', '', str(obj.id_kategori.id_kategori)],
        })
        assert resp.status_code == 200

    def test_ilap_datatables_column5_search(self, client, p3de_admin, db):
        """ilap line 119: 5th column search (id_kpp)."""
        obj = ILAPFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'columns_search[]': ['', '', '', '', obj.id_kpp.nama_kpp if obj.id_kpp else 'test'],
        })
        assert resp.status_code == 200

    def test_monitoring_sorting_valueerror(self, client, db):
        """monitoring lines 453-454: except (ValueError, IndexError): pass."""
        # Create a user with user_p3de group (monitoring is accessible to user_p3de)
        user = UserFactory()
        grp, _ = Group.objects.get_or_create(name='user_p3de')
        user.groups.add(grp)
        client.force_login(user)
        resp = client.get(reverse('monitoring_penyampaian_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': 'abc',  # non-numeric → ValueError in int('abc')
            'order[0][dir]': 'asc',
        })
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_ilap_delete_ajax_post(self, client, p3de_admin, db):
        """ilap line 252: AJAX POST delete response in ILAPDeleteView.delete()."""
        obj = ILAPFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        resp = client.post(
            reverse('ilap_delete', args=[pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_kategori_ilap_list_exception_in_toast(self, client, p3de_admin):
        """kategori_ilap lines 34-35: except Exception: pass."""
        client.force_login(p3de_admin)
        with patch('diamond_web.views.kategori_ilap.unquote_plus', side_effect=Exception('forced')):
            resp = client.get(reverse('kategori_ilap_list'), {'deleted': '1', 'name': 'Test'})
        assert resp.status_code == 200

    def test_mixins_line_110(self, client, p3de_admin):
        """mixins.py line 110: AjaxFormMixin.form_invalid with AJAX."""
        # AjaxFormMixin.form_invalid returns JSON for AJAX requests - hit the form_invalid path
        # In a create view, submit invalid form with AJAX
        client.force_login(p3de_admin)
        resp = client.post(
            reverse('bentuk_data_create'),
            data={'deskripsi': ''},  # Empty = invalid
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        # form_invalid is called → should return JSON with form errors
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data or 'errors' in data or 'error' in data


# ─── STATUS DATA MISSING LINES 157-158, 175-176 ─────────────────────────────

@pytest.mark.django_db
class TestStatusDataMissingLines:
    """Cover missing lines in status_data.py."""

    def test_status_data_update_desc_ordering(self, client, p3de_admin, db):
        """Lines 157-158: status_data datatables desc ordering + non-empty data."""
        StatusDataFactory()
        StatusDataFactory()
        client.force_login(p3de_admin)
        resp = client.get(reverse('status_data_data'), {
            'draw': '1', 'start': '0', 'length': '10',
            'order[0][column]': '1', 'order[0][dir]': 'desc',
        })
        assert resp.status_code == 200
        assert resp.json()['draw'] == 1

    def test_ilap_delete_ajax_get(self, client, p3de_admin, db):
        """ilap lines 242-244: AJAX GET branch in ILAPDeleteView.get()."""
        obj = ILAPFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        resp = client.get(reverse('ilap_delete', args=[pk]), {'ajax': '1'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'html' in data

    def test_dasar_hukum_delete_non_ajax_success_message(self, client, p3de_admin, db):
        """dasar_hukum lines 157-158: non-AJAX delete success message branch."""
        obj = DasarHukumFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        # POST without AJAX header → SafeDeleteMixin handles, returns messages.success
        resp = client.post(reverse('dasar_hukum_delete', args=[pk]))
        assert resp.status_code == 200

    def test_dasar_hukum_delete_ajax_post(self, client, p3de_admin, db):
        """dasar_hukum line 116: AJAX POST delete response."""
        obj = DasarHukumFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        resp = client.post(
            reverse('dasar_hukum_delete', args=[pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True

    def test_status_data_delete_ajax_post(self, client, p3de_admin, db):
        """status_data line 116: AJAX POST delete response."""
        obj = StatusDataFactory()
        pk = obj.pk
        client.force_login(p3de_admin)
        resp = client.post(
            reverse('status_data_delete', args=[pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('success') is True
