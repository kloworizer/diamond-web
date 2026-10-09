"""Tests for the sync_tiket_kd_tahap management command."""
import threading
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
from diamond_web.utils.oracle_sync import OracleSyncConfigError
from diamond_web.utils.tiket_kd_tahap import nomor_tiket_oracle
from diamond_web.models.tiket_kd_tahap import TiketKdTahap
from diamond_web.views.sync_log_status import LOG_FILENAME_PATTERN, _get_type_display_name

from .conftest import TiketFactory

COMMAND = 'diamond_web.management.commands.sync_tiket_kd_tahap'
SERVICE = f'{COMMAND}.OracleDataSyncService'


@pytest.fixture(autouse=True)
def log_dir(tmp_path, monkeypatch):
    """Keep the run logs out of the real sync_logs/."""
    monkeypatch.setattr(f'{COMMAND}.SYNC_LOGS_DIR', str(tmp_path))
    return tmp_path


def _log(log_dir):
    """Name and content of the single log file a run wrote."""
    (path,) = log_dir.iterdir()
    return path.name, path.read_text(encoding='utf-8')


class FakeOracle:
    """Fake OracleDataSyncService for the command's parallel queries.

    *results* maps the NO_TIKET stored in Oracle -> [(kd_tahap, qc, jumlah), ...];
    an entry (kd_tahap, jumlah) has no QC flag (belum QC).
    *gagal* maps a table name -> the Exception its query raises, or a list of
    outcomes consumed one per attempt (an Exception, or None to succeed).
    Every connection gets its own cursor; `calls` records (sql, params).
    """

    def __init__(self, results, gagal=None):
        self.results = results
        self.gagal = {t: (list(v) if isinstance(v, list) else v) for t, v in (gagal or {}).items()}
        self.calls = []
        self.call_timeouts = []
        self._lock = threading.Lock()
        self.service = MagicMock()
        self.service._connect_oracle.side_effect = self._connect

    def _outcome(self, sql):
        with self._lock:
            for tabel, hasil in self.gagal.items():
                if f'.{tabel} ' in sql:
                    return hasil.pop(0) if isinstance(hasil, list) else hasil
        return None

    @contextmanager
    def _connect(self, _which):
        state = {}
        fake = self

        def _execute(sql, params):
            with fake._lock:
                fake.calls.append((sql, list(params)))
                fake.call_timeouts.append(conn.call_timeout)
            exc = fake._outcome(sql)
            if exc is not None:
                raise exc
            state['rows'] = [
                (nomor, *(entry if len(entry) == 3 else (entry[0], None, entry[1])))
                for nomor in params
                for entry in fake.results.get(nomor, [])
            ]

        cursor = MagicMock()
        cursor.execute.side_effect = _execute
        cursor.fetchall.side_effect = lambda: state['rows']

        @contextmanager
        def _cursor_cm():
            yield cursor

        conn = MagicMock()
        conn.call_timeout = 0
        conn.cursor.side_effect = _cursor_cm
        yield conn


def _run(results, gagal=None, **kwargs):
    oracle = FakeOracle(results, gagal)
    out = StringIO()
    with patch(SERVICE, return_value=oracle.service):
        call_command('sync_tiket_kd_tahap', stdout=out, **kwargs)
    return out.getvalue(), oracle


def _tiket(nomor, tahun=2025, status=STATUS_SELESAI, tabel='KPDE_CONTOH'):
    tiket = TiketFactory(
        nomor_tiket=nomor, status_tiket=status, tgl_terima_dip=datetime(tahun, 5, 1, 10, 0),
    )
    jdi = tiket.id_periode_data.id_sub_jenis_data_ilap
    jdi.nama_tabel_I = tabel
    jdi.save()
    return tiket


def _simpanan(tiket):
    """Stored rows: {kd_tahap: jumlah} for rows without QC, {(kd_tahap, qc): jumlah} otherwise."""
    return {
        kd if qc is None else (kd, qc): jumlah
        for kd, qc, jumlah in TiketKdTahap.objects.filter(id_tiket=tiket).values_list('kd_tahap', 'qc', 'jumlah_baris')
    }


def test_nomor_tiket_oracle_reverses_e_to_ei():
    assert nomor_tiket_oracle('EI1234567890ABCDE') == 'E1234567890ABCDE'
    assert nomor_tiket_oracle('A1234567890ABCDEF') == 'A1234567890ABCDEF'


@pytest.mark.django_db
def test_only_pengendalian_mutu_and_selesai_tikets_of_the_given_tahun_are_queried():
    selesai = _tiket('T0000000000000001')
    mutu = _tiket('T0000000000000004', status=STATUS_PENGENDALIAN_MUTU)
    lain_tahun = _tiket('T0000000000000002', tahun=2024)
    identifikasi = _tiket('T0000000000000003', status=STATUS_IDENTIFIKASI)

    _, oracle = _run({
        'T0000000000000001': [('1', 10), ('2', 5)],
        'T0000000000000002': [('1', 99)],
        'T0000000000000003': [('1', 99)],
        'T0000000000000004': [('3', 6)],
    }, tahun=2025)

    assert len(oracle.calls) == 1
    sql, params = oracle.calls[0]
    assert 'FROM BANKDATAPDE.KPDE_CONTOH t WHERE NO_TIKET IN (:1, :2)' in sql
    assert 'GROUP BY NO_TIKET, KD_TAHAP, QC' in sql
    assert sorted(params) == ['T0000000000000001', 'T0000000000000004']
    assert _simpanan(selesai) == {'1': 10, '2': 5}
    assert _simpanan(mutu) == {'3': 6}
    assert not TiketKdTahap.objects.filter(id_tiket__in=[lain_tahun, identifikasi]).exists()


@pytest.mark.django_db
def test_one_query_per_table_and_both_nomor_formats_are_summed():
    a = _tiket('EI1234567890ABCDE')
    b = _tiket('T0000000000000002')
    lain = _tiket('T0000000000000003', tabel='KPDE_LAIN')

    _, oracle = _run({
        'EI1234567890ABCDE': [('1', 4)],
        'E1234567890ABCDE': [('1', 6), ('2', 1)],
        'T0000000000000002': [('1', 3)],
        'T0000000000000003': [('9', 8)],
    }, tahun=2025)

    assert len(oracle.calls) == 2
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
    assert 'T0000000000000001 (BANKDATAPDE.KPDE_HILANG): query gagal setelah 1 percobaan: ORA-00942' in out


@pytest.mark.django_db
def test_dry_run_saves_nothing():
    tiket = _tiket('T0000000000000001')

    out, _ = _run({'T0000000000000001': [('1', 10)]}, tahun=2025, dry_run=True)

    assert not TiketKdTahap.objects.filter(id_tiket=tiket).exists()
    assert 'T0000000000000001: 1/(kosong)=10' in out


@pytest.mark.django_db
def test_schema_and_column_options_shape_the_query():
    _tiket('T0000000000000001')

    _, oracle = _run({}, tahun=2025, schema='LAIN', kolom_tiket='ID_TIKET')

    sql = oracle.calls[0][0]
    assert 'FROM LAIN.KPDE_CONTOH t WHERE ID_TIKET IN' in sql


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


@pytest.mark.django_db
def test_log_records_parameters_each_tiket_and_summary(log_dir):
    baru = _tiket('T0000000000000001')
    berubah = _tiket('T0000000000000002')
    sama = _tiket('T0000000000000003')
    dikosongkan = _tiket('T0000000000000004')
    TiketKdTahap.objects.create(id_tiket=berubah, kd_tahap='1', jumlah_baris=4)
    TiketKdTahap.objects.create(id_tiket=berubah, kd_tahap='2', jumlah_baris=9)
    TiketKdTahap.objects.create(id_tiket=sama, kd_tahap='1', jumlah_baris=6)
    TiketKdTahap.objects.create(id_tiket=dikosongkan, kd_tahap='1', jumlah_baris=1)

    out, _ = _run({
        'T0000000000000001': [('1', 10), ('2', 5)],
        'T0000000000000002': [('1', 7)],
        'T0000000000000003': [('1', 6)],
    }, tahun=2025)

    name, log = _log(log_dir)
    assert LOG_FILENAME_PATTERN.match(name).group(1) == 'kd_tahap_sync'
    assert f'Log: {log_dir / name}' in out
    assert 'Parameter: tahun=2025 tiket=- koneksi=secondary' in log
    assert 'Tiket ditemukan: 4 (Selesai=4)' in log
    assert 'Query BANKDATAPDE.KPDE_CONTOH: 4 tiket, 4 baris hasil (tiket berisi: 3)' in log
    assert f'BARU        tiket=T0000000000000001 id={baru.id} status=Selesai kd_tahap/qc 0->2 total_baris 0->15' in log
    assert 'kd_tahap/qc: 1/(kosong)=10, 2/(kosong)=5' in log
    assert 'BERUBAH     tiket=T0000000000000002' in log
    assert 'perubahan (2): 1/(kosong): 4->7, 2/(kosong): 9->-' in log
    assert 'SAMA        tiket=T0000000000000003' in log
    assert 'DIKOSONGKAN tiket=T0000000000000004' in log
    assert 'Status run            : SELESAI' in log
    assert 'Tiket BERUBAH         : 1' in log
    assert 'ERROR' not in log
    assert _simpanan(dikosongkan) == {}


@pytest.mark.django_db
def test_log_records_query_error_with_sql_and_traceback(log_dir):
    _tiket('T0000000000000001', tabel='KPDE_HILANG')
    _tiket('T0000000000000002')

    _run(
        {'T0000000000000002': [('1', 2)]},
        gagal={'KPDE_HILANG': Exception('ORA-00942: table or view does not exist')},
        tahun=2025,
    )

    _, log = _log(log_dir)
    assert 'ERROR Query BANKDATAPDE.KPDE_HILANG gagal' in log
    assert 'ERROR SQL: SELECT /*+ PARALLEL(t, 4) */ NO_TIKET, KD_TAHAP, QC, COUNT(*) FROM BANKDATAPDE.KPDE_HILANG t' in log
    assert 'ERROR Tiket: T0000000000000001' in log
    assert 'Traceback (most recent call last)' in log
    assert 'GAGAL       tiket=T0000000000000001' in log
    assert 'BARU        tiket=T0000000000000002' in log
    assert 'Status run            : SELESAI DENGAN ERROR' in log
    assert 'Tiket GAGAL           : 1' in log


@pytest.mark.django_db
def test_log_records_connection_failure(log_dir):
    _tiket('T0000000000000001')
    service = MagicMock()
    service._connect_oracle.side_effect = OracleSyncConfigError('ORA-12170: TNS:Connect timeout occurred')

    with patch(SERVICE, return_value=service), pytest.raises(CommandError):
        call_command('sync_tiket_kd_tahap', tahun=2025, stdout=StringIO(), stderr=StringIO())

    _, log = _log(log_dir)
    assert "Run dihentikan: Koneksi Oracle 'secondary' gagal: ORA-12170" in log
    assert 'Traceback (most recent call last)' in log
    assert 'Status run            : GAGAL' in log


@pytest.mark.django_db
def test_dry_run_writes_its_own_log_type(log_dir):
    _tiket('T0000000000000001')

    _run({'T0000000000000001': [('1', 10)]}, tahun=2025, dry_run=True)

    name, log = _log(log_dir)
    sync_type = LOG_FILENAME_PATTERN.match(name).group(1)
    assert sync_type == 'kd_tahap_sync_dryrun'
    assert _get_type_display_name(sync_type) == 'Sinkronisasi KD Tahap (Dry Run)'
    assert 'DRY-RUN' in log and 'BARU        tiket=T0000000000000001' in log


TIMEOUT = Exception('DPY-4011: the database or network closed the connection\nDPI-1067: call timeout of 900000 ms exceeded with ORA-3156')


@pytest.mark.django_db
def test_tables_run_in_parallel_with_their_own_connection_and_timeout():
    tikets = [_tiket(f'T00000000000000{i:02d}', tabel=f'KPDE_T{i}') for i in range(6)]
    mulai = threading.Barrier(3, timeout=5)

    oracle = FakeOracle({t.nomor_tiket: [('1', i + 1)] for i, t in enumerate(tikets)})
    asli = oracle._outcome

    def _outcome_bersamaan(sql):
        # The first three queries only proceed once three run at the same time.
        if len(oracle.calls) <= 3:
            mulai.wait()
        return asli(sql)

    oracle._outcome = _outcome_bersamaan
    with patch(SERVICE, return_value=oracle.service):
        call_command('sync_tiket_kd_tahap', tahun=2025, workers=3, timeout=120, stdout=StringIO())

    assert len(oracle.calls) == 6
    assert set(oracle.call_timeouts) == {120_000}
    assert [_simpanan(t) for t in tikets] == [{'1': i + 1} for i in range(6)]


@pytest.mark.django_db
def test_timeout_is_retried_and_others_still_succeed(log_dir):
    lambat = _tiket('T0000000000000001', tabel='KPDE_BESAR')
    ok = _tiket('T0000000000000002')

    out, oracle = _run(
        {'T0000000000000001': [('1', 5)], 'T0000000000000002': [('1', 2)]},
        gagal={'KPDE_BESAR': [TIMEOUT, None]},
        tahun=2025,
    )

    assert len(oracle.calls) == 3
    assert _simpanan(lambat) == {'1': 5}
    assert _simpanan(ok) == {'1': 2}
    assert 'BANKDATAPDE.KPDE_BESAR: TIMEOUT' in out and 'akan diulang' in out
    _, log = _log(log_dir)
    assert 'Query BANKDATAPDE.KPDE_BESAR gagal [TIMEOUT (melewati 3600 detik)] pada percobaan ke-1' in log
    assert 'percobaan ke-2' in log
    assert 'Status run            : SELESAI' in log
    assert 'Query Oracle          : 3 (timeout: 1)' in log


@pytest.mark.django_db
def test_table_still_failing_after_retries_is_listed_with_rerun_command(log_dir):
    lambat = _tiket('T0000000000000001', tabel='KPDE_BESAR')
    TiketKdTahap.objects.create(id_tiket=lambat, kd_tahap='1', jumlah_baris=4)
    ok = _tiket('T0000000000000002')

    out, oracle = _run(
        {'T0000000000000002': [('1', 2)]},
        gagal={'KPDE_BESAR': TIMEOUT},
        tahun=2025, retry=2,
    )

    assert len(oracle.calls) == 4  # KPDE_BESAR 3x, KPDE_CONTOH once
    assert _simpanan(lambat) == {'1': 4}
    assert _simpanan(ok) == {'1': 2}
    rerun = 'python manage.py sync_tiket_kd_tahap --tahun 2025 --tabel KPDE_BESAR --timeout 7200'
    assert rerun in out
    _, log = _log(log_dir)
    assert 'Tabel gagal (1):' in log
    assert '  - KPDE_BESAR: query melewati batas waktu 3600 detik' in log
    assert f'Ulangi tabel yang gagal dengan: {rerun}' in log
    assert 'query gagal setelah 3 percobaan' in log
    assert 'Status run            : SELESAI DENGAN ERROR' in log


@pytest.mark.django_db
def test_permanent_error_is_not_retried():
    _tiket('T0000000000000001', tabel='KPDE_HILANG')

    out, oracle = _run(
        {}, gagal={'KPDE_HILANG': Exception('ORA-00942: table or view does not exist')},
        tahun=2025, retry=3,
    )

    assert len(oracle.calls) == 1
    assert 'akan diulang' not in out


@pytest.mark.django_db
def test_tabel_option_only_reruns_the_given_tables():
    a = _tiket('T0000000000000001', tabel='KPDE_A')
    b = _tiket('T0000000000000002', tabel='KPDE_B')
    TiketKdTahap.objects.create(id_tiket=b, kd_tahap='1', jumlah_baris=9)

    out, oracle = _run(
        {'T0000000000000001': [('1', 5)], 'T0000000000000002': [('1', 1)]},
        tahun=2025, tabel='kpde_a',
    )

    assert [sql.split(' FROM ')[1].split()[0] for sql, _ in oracle.calls] == ['BANKDATAPDE.KPDE_A']
    assert _simpanan(a) == {'1': 5}
    assert _simpanan(b) == {'1': 9}
    assert 'Tiket Pengendalian Mutu & Selesai, tahun terima DIP 2025: 1' in out


def test_dropped_connection_counts_as_timeout_only_past_the_limit():
    from diamond_web.utils.tiket_kd_tahap import is_timeout

    putus = Exception('DPY-4011: the database or network closed the connection\nDPI-1080: connection was closed by ORA-03113')
    assert is_timeout(TIMEOUT)
    assert is_timeout(putus, durasi=3.2, batas=2)
    assert not is_timeout(putus, durasi=0.5, batas=2)
    assert not is_timeout(putus)


@pytest.mark.django_db
def test_rows_are_counted_per_kd_tahap_and_qc_flag(log_dir):
    tiket = _tiket('T0000000000000001')
    TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap='1', qc='P', jumlah_baris=4)

    _, oracle = _run({'T0000000000000001': [
        ('1', 'P', 7), ('1', 'X', 2), ('1', None, 3), ('2', ' F ', 1),
    ]}, tahun=2025, kolom_qc='FLAG_QC')

    assert 'SELECT /*+ PARALLEL(t, 4) */ NO_TIKET, KD_TAHAP, FLAG_QC, COUNT(*)' in oracle.calls[0][0]
    assert _simpanan(tiket) == {('1', 'P'): 7, ('1', 'X'): 2, '1': 3, ('2', 'F'): 1}
    _, log = _log(log_dir)
    assert 'kd_tahap/qc: 1/P=7, 1/X=2, 1/(kosong)=3, 2/F=1' in log
    assert 'perubahan (4): 1/P: 4->7, 1/X: -->2, 1/(kosong): -->3, 2/F: -->1' in log


@pytest.mark.django_db
def test_wide_qc_values_are_cut_and_their_counts_added():
    tiket = _tiket('T0000000000000001')
    panjang = 'Q' * 60

    _run({'T0000000000000001': [('1', panjang + 'A', 2), ('1', panjang + 'B', 3)]}, tahun=2025)

    assert _simpanan(tiket) == {('1', 'Q' * 50): 5}


@pytest.mark.django_db
def test_tiket_detail_sums_kd_tahap_over_qc_and_filters_by_qc_boxes(client):
    import json
    import re
    from django.urls import reverse
    from diamond_web.models import TiketPIC
    from .conftest import TiketPICFactory, UserFactory

    tiket = _tiket('T0000000000000001')
    tiket.sudah_qc, tiket.belum_qc = 96, 10
    tiket.qc_p, tiket.qc_x, tiket.qc_f, tiket.qc_c = 31, 45, 20, 0
    tiket.save()
    user = UserFactory()
    TiketPICFactory(id_tiket=tiket, id_user=user, role=TiketPIC.Role.PMDE, active=True)
    for kd, qc, jumlah in (('A1', 'P', 30), ('A1', 'F', 20), ('A1', None, 10), ('B2', 'X', 45), ('B2', 'p ', 1)):
        TiketKdTahap.objects.create(id_tiket=tiket, kd_tahap=kd, qc=qc, jumlah_baris=jumlah)
    client.force_login(user)

    html = client.get(reverse('tiket_detail', args=[tiket.pk])).content.decode()

    assert 'Jumlah Baris per KD Tahap<' in html
    tabel = html[html.index('id="kd-tahap-table"'):html.index('</table>', html.index('id="kd-tahap-table"'))]
    assert 'QC</th>' not in tabel  # QC filters the table, it is not a column
    # All QC: A1 = 30 + 20 + 10, B2 = 45 + 1.
    assert re.findall(r'font-monospace">([^<]+)</td>\s*<td class="text-end">([^<]+)<', tabel) == [('A1', '60'), ('B2', '46')]
    assert 'id="kd-tahap-total">106<' in tabel
    assert '>2 KD Tahap<' in html
    # The QC boxes of Status Quality Control are the filter: only flags with KD
    # Tahap rows (QC C has none), plus Belum QC for the rows without a flag.
    assert re.findall(r'data-kd-qc="([^"]*)"', html) == ['', 'P', 'X', 'F']
    assert 'kd-qc-chip' not in html
    assert 'id="kd-qc-filter-info"' in html
    assert re.search(r'qc-kolom-tidak-lolos"\s*>\s*<span class="meta-label">QC C</span>', html)
    data = json.loads(re.search(r'<script id="kd-tahap-data" type="application/json">(.*?)</script>', html).group(1))
    assert sorted(data) == sorted([['A1', 'P', 30], ['A1', 'F', 20], ['A1', '', 10], ['B2', 'X', 45], ['B2', 'P', 1]])
    assert '{#' not in html and '{%' not in html


def test_kd_tahap_per_kd_and_qc_flag():
    from diamond_web.views.tiket.detail import kd_tahap_per_kd, kd_tahap_qc_flag

    rows = [('B', 'N', 5), ('A', 'W', 5), (None, None, 7), ('A', 'P', 2), ('C', 'X', 1), ('B', None, 2)]
    assert kd_tahap_per_kd(rows) == [('A', 7), ('B', 7), (None, 7), ('C', 1)]
    assert [kd_tahap_qc_flag(q) for q in ('P', ' x ', None, '')] == ['P', 'X', '', '']


@pytest.mark.django_db
def test_parallel_hint_default_and_off():
    _tiket('T0000000000000001')

    _, oracle = _run({}, tahun=2025)
    assert oracle.calls[0][0].startswith('SELECT /*+ PARALLEL(t, 4) */ NO_TIKET, KD_TAHAP, QC, COUNT(*)')

    _, oracle = _run({}, tahun=2025, parallel=0)
    assert oracle.calls[0][0].startswith('SELECT NO_TIKET, KD_TAHAP, QC, COUNT(*) FROM BANKDATAPDE.KPDE_CONTOH t ')


def test_dpy_4024_is_a_timeout():
    from diamond_web.utils.tiket_kd_tahap import is_timeout

    assert is_timeout(Exception('DPY-4024: call timeout of 900000 ms exceeded'))


@pytest.mark.django_db
def test_tiket_option_processes_only_the_given_tikets(log_dir):
    a = _tiket('T0000000000000001')
    b = _tiket('T0000000000000002', tahun=2019)  # any year
    identifikasi = _tiket('T0000000000000003', status=STATUS_IDENTIFIKASI)
    lain = _tiket('T0000000000000004')

    out, oracle = _run(
        {t: [('1', 'P', 3)] for t in ('T0000000000000001', 'T0000000000000002', 'T0000000000000003', 'T0000000000000004')},
        tiket='T0000000000000001, T0000000000000002,T0000000000000003,T0000000000000009',
    )

    assert sorted(p for _, params in oracle.calls for p in params) == ['T0000000000000001', 'T0000000000000002']
    assert _simpanan(a) == {('1', 'P'): 3} and _simpanan(b) == {('1', 'P'): 3}
    assert not TiketKdTahap.objects.filter(id_tiket__in=[identifikasi, lain]).exists()
    assert 'Tiket Pengendalian Mutu & Selesai, 4 tiket yang diminta: 2' in out
    _, log = _log(log_dir)
    assert 'Parameter: tahun=None tiket=4 koneksi=secondary' in log
    assert '2 dari 4 tiket yang diminta dilewati' in log


@pytest.mark.django_db
def test_tahun_or_tiket_is_required():
    with pytest.raises(CommandError, match='--tahun atau --tiket'):
        call_command('sync_tiket_kd_tahap', stdout=StringIO(), stderr=StringIO())


@pytest.mark.django_db
def test_tiket_mode_rerun_command_lists_failed_tikets(log_dir):
    _tiket('T0000000000000001', tabel='KPDE_BESAR')
    _tiket('T0000000000000002')

    out, _ = _run(
        {'T0000000000000002': [('1', 2)]},
        gagal={'KPDE_BESAR': TIMEOUT},
        tiket='T0000000000000001,T0000000000000002', retry=0,
    )

    assert 'python manage.py sync_tiket_kd_tahap --tiket T0000000000000001 --timeout 7200' in out
