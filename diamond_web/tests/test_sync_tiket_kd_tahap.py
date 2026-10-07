"""Tests for the sync_tiket_kd_tahap management command."""
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from diamond_web.constants.tiket_status import (
    STATUS_IDENTIFIKASI,
    STATUS_PENGENDALIAN_MUTU,
    STATUS_SELESAI,
)
from diamond_web.utils.tiket_kd_tahap import nomor_tiket_oracle
from diamond_web.models.tiket_kd_tahap import TiketKdTahap

from .conftest import TiketFactory

SERVICE = 'diamond_web.management.commands.sync_tiket_kd_tahap.OracleDataSyncService'


def _service(results, gagal=None):
    """Fake service whose cursor answers each execute() from *results*.

    *results* maps the NO_TIKET stored in Oracle → [(kd_tahap, jumlah), ...];
    *gagal* maps a table name → the Exception its query raises.
    """
    cursor = MagicMock()
    state = {}

    def _execute(sql, params):
        for tabel, exc in (gagal or {}).items():
            if f'.{tabel} ' in sql:
                raise exc
        state['rows'] = [
            (nomor, kd, jumlah)
            for nomor in params
            for kd, jumlah in results.get(nomor, [])
        ]

    cursor.execute.side_effect = _execute
    cursor.fetchall.side_effect = lambda: state['rows']

    @contextmanager
    def _cursor_cm():
        yield cursor

    conn = MagicMock()
    conn.cursor.side_effect = _cursor_cm

    @contextmanager
    def _connect(_which):
        yield conn

    service = MagicMock()
    service._connect_oracle.side_effect = _connect
    return service, cursor


def _run(results, gagal=None, **kwargs):
    service, cursor = _service(results, gagal)
    out = StringIO()
    with patch(SERVICE, return_value=service):
        call_command('sync_tiket_kd_tahap', stdout=out, **kwargs)
    return out.getvalue(), cursor


def _tiket(nomor, tahun=2025, status=STATUS_SELESAI, tabel='KPDE_CONTOH'):
    tiket = TiketFactory(
        nomor_tiket=nomor, status_tiket=status, tgl_terima_dip=datetime(tahun, 5, 1, 10, 0),
    )
    jdi = tiket.id_periode_data.id_sub_jenis_data_ilap
    jdi.nama_tabel_I = tabel
    jdi.save()
    return tiket


def _simpanan(tiket):
    return dict(
        TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'jumlah_baris')
    )


def test_nomor_tiket_oracle_reverses_e_to_ei():
    assert nomor_tiket_oracle('EI1234567890ABCDE') == 'E1234567890ABCDE'
    assert nomor_tiket_oracle('A1234567890ABCDEF') == 'A1234567890ABCDEF'


@pytest.mark.django_db
def test_only_pengendalian_mutu_and_selesai_tikets_of_the_given_tahun_are_queried():
    selesai = _tiket('T0000000000000001')
    mutu = _tiket('T0000000000000004', status=STATUS_PENGENDALIAN_MUTU)
    lain_tahun = _tiket('T0000000000000002', tahun=2024)
    identifikasi = _tiket('T0000000000000003', status=STATUS_IDENTIFIKASI)

    _, cursor = _run({
        'T0000000000000001': [('1', 10), ('2', 5)],
        'T0000000000000002': [('1', 99)],
        'T0000000000000003': [('1', 99)],
        'T0000000000000004': [('3', 6)],
    }, tahun=2025)

    assert cursor.execute.call_count == 1
    sql, params = cursor.execute.call_args.args
    assert 'FROM BANKDATAPDE.KPDE_CONTOH WHERE NO_TIKET IN (:1, :2)' in sql
    assert 'GROUP BY NO_TIKET, KD_TAHAP' in sql
    assert sorted(params) == ['T0000000000000001', 'T0000000000000004']
    assert _simpanan(selesai) == {'1': 10, '2': 5}
    assert _simpanan(mutu) == {'3': 6}
    assert not TiketKdTahap.objects.filter(id_tiket__in=[lain_tahun, identifikasi]).exists()


@pytest.mark.django_db
def test_one_query_per_table_and_both_nomor_formats_are_summed():
    a = _tiket('EI1234567890ABCDE')
    b = _tiket('T0000000000000002')
    lain = _tiket('T0000000000000003', tabel='KPDE_LAIN')

    _, cursor = _run({
        'EI1234567890ABCDE': [('1', 4)],
        'E1234567890ABCDE': [('1', 6), ('2', 1)],
        'T0000000000000002': [('1', 3)],
        'T0000000000000003': [('9', 8)],
    }, tahun=2025)

    assert cursor.execute.call_count == 2
    assert _simpanan(a) == {'1': 10, '2': 1}
    assert _simpanan(b) == {'1': 3}
    assert _simpanan(lain) == {'9': 8}


@pytest.mark.django_db
def test_rerun_replaces_previous_rows_and_clears_tikets_without_rows():
    tiket = _tiket('T0000000000000001')
    kosong = _tiket('T0000000000000002')
    TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='LAMA', jumlah_baris=1)
    TiketKdTahap.objects.create(id_tiket=kosong, kd_tahap='LAMA', jumlah_baris=1)

    _run({'T0000000000000001': [('1', 7), (None, 3)]}, tahun=2025)

    assert _simpanan(tiket) == {'1': 7, None: 3}
    assert _simpanan(kosong) == {}


@pytest.mark.django_db
def test_failed_table_keeps_old_rows_and_other_tables_still_run():
    gagal = _tiket('T0000000000000001', tabel='KPDE_HILANG')
    TiketKdTahap.objects.create(id_tiket=gagal, kd_tahap='1', jumlah_baris=4)
    ok = _tiket('T0000000000000003')

    out, _ = _run(
        {'T0000000000000001': [('1', 99)], 'T0000000000000003': [('1', 2)]},
        gagal={'KPDE_HILANG': Exception('ORA-00942: table or view does not exist')},
        tahun=2025,
    )

    assert _simpanan(gagal) == {'1': 4}
    assert _simpanan(ok) == {'1': 2}
    assert 'KPDE_HILANG (1 tiket): ORA-00942' in out


@pytest.mark.django_db
def test_dry_run_saves_nothing():
    tiket = _tiket('T0000000000000001')

    out, _ = _run({'T0000000000000001': [('1', 10)]}, tahun=2025, dry_run=True)

    assert not TiketKdTahap.objects.filter(id_tiket=tiket).exists()
    assert 'T0000000000000001: 1=10' in out


@pytest.mark.django_db
def test_schema_and_column_options_shape_the_query():
    _tiket('T0000000000000001')

    _, cursor = _run({}, tahun=2025, schema='LAIN', kolom_tiket='ID_TIKET')

    sql = cursor.execute.call_args.args[0]
    assert 'FROM LAIN.KPDE_CONTOH WHERE ID_TIKET IN' in sql


@pytest.mark.django_db
def test_unsafe_identifier_is_rejected():
    with pytest.raises(CommandError):
        call_command('sync_tiket_kd_tahap', tahun=2025, kolom_tiket='X; DROP TABLE T')


@pytest.mark.django_db
def test_tiket_detail_shows_kd_tahap_table(client):
    from django.urls import reverse
    from diamond_web.models import TiketPIC
    from .conftest import TiketPICFactory, UserFactory

    tiket = _tiket('T0000000000000001')
    user = UserFactory()
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)
    TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='B2', jumlah_baris=158607)
    TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='A1', jumlah_baris=3)
    TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap=None, jumlah_baris=10)
    client.force_login(user)

    html = client.get(reverse('tiket_detail', args=[tiket.pk])).content.decode()

    assert 'Jumlah Baris per KD Tahap' in html
    assert '3 KD Tahap' in html
    # Jumlah baris descending: B2 (158.607), empty (10), A1 (3).
    assert html.index('>B2<') < html.index('>-<') < html.index('>A1<')
    assert '158.607' in html and '158.620' in html  # one row and the total
    assert '{#' not in html and '{%' not in html


@pytest.mark.django_db
def test_tiket_detail_hides_kd_tahap_block_without_rows(client):
    from django.urls import reverse
    from diamond_web.models import TiketPIC
    from .conftest import TiketPICFactory, UserFactory

    tiket = _tiket('T0000000000000001')
    user = UserFactory()
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)
    client.force_login(user)

    html = client.get(reverse('tiket_detail', args=[tiket.pk])).content.decode()

    assert 'Jumlah Baris per KD Tahap' not in html
