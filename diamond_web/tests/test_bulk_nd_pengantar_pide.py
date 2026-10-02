"""P3DE: Generate ND Pengantar PIDE leaves out tikets taken back from PIDE."""

from datetime import datetime
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.urls import reverse

from diamond_web.constants.tiket_status import (
    STATUS_DIBATALKAN,
    STATUS_DIKEMBALIKAN,
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.tests.conftest import PeriodeJenisDataFactory, TiketFactory

URL_NAME = 'bulk_nd_pengantar_pide'
TGL_KIRIM = datetime(2026, 7, 10, 14, 14)


@pytest.fixture
def tikets(db):
    periode = PeriodeJenisDataFactory()

    def make(status):
        return TiketFactory(
            id_periode_data=periode, status_tiket=status,
            tgl_kirim_pide=TGL_KIRIM, tanda_terima=True,
        )

    return {
        'dikirim': make(STATUS_DIKIRIM_KE_PIDE),
        'identifikasi': make(STATUS_IDENTIFIKASI),
        'pengendalian_mutu': make(STATUS_PENGENDALIAN_MUTU),
        'selesai': make(STATUS_SELESAI),
        # Dikembalikan manually by PIDE: the tiket is cancelled.
        'dibatalkan': make(STATUS_DIBATALKAN),
        # Dikembalikan by the Oracle sync (Aturan 4): back at P3DE.
        'dikembalikan': make(STATUS_DIKEMBALIKAN),
        'ilap': periode.id_sub_jenis_data_ilap.id_ilap,
    }


@pytest.mark.django_db
@pytest.mark.parametrize('ilap', ['semua', 'own'])
def test_listing_leaves_out_tikets_taken_back(client, authenticated_user, tikets, ilap):
    client.force_login(authenticated_user)
    ilap_id = 'semua' if ilap == 'semua' else str(tikets['ilap'].pk)
    resp = client.get(reverse(URL_NAME), {'ilap_id': ilap_id, 'tanggal_kirim_pide': '2026-07-10'})

    listed = {t.pk for t in resp.context['tickets']}
    assert listed == {
        tikets[k].pk for k in ('dikirim', 'identifikasi', 'pengendalian_mutu', 'selesai')
    }


@pytest.mark.django_db
def test_generate_ignores_tikets_taken_back(client, authenticated_user, tikets):
    """A stale form that still posts a cancelled tiket must not get it into the document."""
    client.force_login(authenticated_user)
    with patch(
        'diamond_web.views.bulk_document_generation._generate_docx_for_tickets',
        return_value=HttpResponse('ok'),
    ) as generate:
        client.post(reverse(URL_NAME), {
            'ilap_id': 'semua',
            'tanggal_kirim_pide': '2026-07-10',
            'ticket_ids': [str(tikets[k].pk) for k in ('dikirim', 'dibatalkan', 'dikembalikan')],
        })

    selected = generate.call_args.args[0]
    assert [t.pk for t in selected] == [tikets['dikirim'].pk]


@pytest.mark.django_db
def test_generate_with_only_taken_back_tikets_warns(client, authenticated_user, tikets):
    client.force_login(authenticated_user)
    resp = client.post(reverse(URL_NAME), {
        'ilap_id': 'semua',
        'tanggal_kirim_pide': '2026-07-10',
        'ticket_ids': [str(tikets['dibatalkan'].pk)],
    })
    assert resp.status_code == 302
