"""Tests for the durasi jatuh tempo rule table and the generate it drives.

The durasi Generate Otomatis writes used to be constants in the view (prioritas
45, non prioritas 85, PMDE only). They are now rows in
``AturanDurasiJatuhTempo``, resolved per Sub Jenis Data per year, so a seksi can
change its prioritas durasi from 45 to 35 next year without a code change, and a
Sub Jenis Data with its own rate (Bea dan Cukai, 14 days) keeps it as a stated
rule rather than as a row nothing happens to touch.

Three things are worth pinning down: that the most specific rule wins, that a
year with no rule is skipped rather than guessed, and that PIDE now generates
through the very same machinery as PMDE.
"""
from datetime import date

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.models.aturan_durasi_jatuh_tempo import AturanDurasiJatuhTempo
from diamond_web.models.durasi_jatuh_tempo import DurasiJatuhTempo

from .conftest import (
    ILAPFactory,
    JenisDataILAPFactory,
    JenisPrioritasDataFactory,
    UserFactory,
)

TAHUN = 2025


@pytest.fixture(autouse=True)
def tabel_aturan_kosong(db):
    """Migrasi 0016 mengisi aturan awal supaya perilaku produksi tidak berubah.

    Test di berkas ini menyatakan aturannya sendiri, jadi tabelnya dikosongkan
    lebih dulu — kalau tidak, aturan hasil seed ikut terbaca dan hasilnya
    bergantung pada tahun berapa test dijalankan.
    """
    AturanDurasiJatuhTempo.objects.all().delete()


@pytest.fixture
def seksi_pmde(db):
    return Group.objects.get_or_create(name='user_pmde')[0]


@pytest.fixture
def seksi_pide(db):
    return Group.objects.get_or_create(name='user_pide')[0]


@pytest.fixture
def ilap(db):
    return ILAPFactory(nama_ilap='Direktorat Jenderal Bea dan Cukai')


@pytest.fixture
def sub_jenis(ilap):
    return JenisDataILAPFactory(id_ilap=ilap, id_sub_jenis_data='KM0180101')


def _aturan(seksi, tahun=TAHUN, prioritas=45, non_prioritas=85, **scope):
    return AturanDurasiJatuhTempo.objects.create(
        seksi=seksi, tahun=tahun,
        durasi_prioritas=prioritas, durasi_non_prioritas=non_prioritas,
        **scope,
    )


def _jadikan_prioritas(sub_jenis, tahun=TAHUN):
    return JenisPrioritasDataFactory(
        id_sub_jenis_data_ilap=sub_jenis, tahun=str(tahun),
        start_date=date(tahun, 1, 1), end_date=date(tahun, 12, 31),
    )


# --------------------------------------------------------------------------- #
# Resolusi aturan                                                             #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestResolve:

    def _resolve(self, seksi, sub_jenis, is_prioritas, tahun=TAHUN):
        index = AturanDurasiJatuhTempo.index_for(seksi)
        return AturanDurasiJatuhTempo.resolve(
            index, sub_jenis.pk, sub_jenis.id_ilap_id, tahun, is_prioritas
        )

    def test_the_general_rule_applies_when_there_is_no_exception(
        self, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde)
        assert self._resolve(seksi_pmde, sub_jenis, True) == 45
        assert self._resolve(seksi_pmde, sub_jenis, False) == 85

    def test_a_sub_jenis_data_rule_beats_the_general_one(self, seksi_pmde, sub_jenis):
        _aturan(seksi_pmde)
        _aturan(seksi_pmde, prioritas=14, id_sub_jenis_data=sub_jenis)
        assert self._resolve(seksi_pmde, sub_jenis, True) == 14

    def test_an_ilap_rule_beats_the_general_one(self, seksi_pmde, sub_jenis, ilap):
        _aturan(seksi_pmde)
        _aturan(seksi_pmde, prioritas=20, id_ilap=ilap)
        assert self._resolve(seksi_pmde, sub_jenis, True) == 20

    def test_a_sub_jenis_data_rule_beats_its_own_ilap_rule(
        self, seksi_pmde, sub_jenis, ilap
    ):
        """Bea dan Cukai is exactly this case: some of its sub jenis data are 14
        while the rest of the ILAP stays on the general 45."""
        _aturan(seksi_pmde)
        _aturan(seksi_pmde, prioritas=20, id_ilap=ilap)
        _aturan(seksi_pmde, prioritas=14, id_sub_jenis_data=sub_jenis)

        assert self._resolve(seksi_pmde, sub_jenis, True) == 14
        lain = JenisDataILAPFactory(id_ilap=ilap)
        assert self._resolve(seksi_pmde, lain, True) == 20

    def test_a_year_without_a_rule_resolves_to_none(self, seksi_pmde, sub_jenis):
        _aturan(seksi_pmde, tahun=2025)
        assert self._resolve(seksi_pmde, sub_jenis, True, tahun=2026) is None

    def test_rules_of_another_seksi_are_invisible(self, seksi_pmde, seksi_pide, sub_jenis):
        _aturan(seksi_pide, prioritas=35, non_prioritas=90)
        assert self._resolve(seksi_pmde, sub_jenis, True) is None

    def test_the_durasi_can_differ_per_year(self, seksi_pmde, sub_jenis):
        """Yang jadi alasan tabel ini ada: 2026 = 45, 2027 = 35."""
        _aturan(seksi_pmde, tahun=2026, prioritas=45)
        _aturan(seksi_pmde, tahun=2027, prioritas=35)
        assert self._resolve(seksi_pmde, sub_jenis, True, tahun=2026) == 45
        assert self._resolve(seksi_pmde, sub_jenis, True, tahun=2027) == 35


# --------------------------------------------------------------------------- #
# Generate Otomatis                                                           #
# --------------------------------------------------------------------------- #

@pytest.fixture
def admin_pmde(db):
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name='admin_pmde')[0])
    return user


@pytest.fixture
def admin_pide(db):
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name='admin_pide')[0])
    return user


@pytest.mark.django_db
class TestGeneratePMDE:

    def _generate(self, client, user):
        client.force_login(user)
        return client.post(reverse('durasi_jatuh_tempo_pmde_generate'))

    def test_writes_the_durasi_the_rule_says(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde, prioritas=45, non_prioritas=85)
        _jadikan_prioritas(sub_jenis)

        assert self._generate(client, admin_pmde).status_code == 200

        row = DurasiJatuhTempo.objects.get(
            seksi=seksi_pmde, id_sub_jenis_data=sub_jenis, start_date=date(TAHUN, 1, 1)
        )
        assert row.durasi == 45
        assert row.end_date == date(TAHUN, 12, 31)

    def test_a_sub_jenis_data_exception_is_honoured(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde)
        _aturan(seksi_pmde, prioritas=14, id_sub_jenis_data=sub_jenis)
        _jadikan_prioritas(sub_jenis)

        self._generate(client, admin_pmde)

        assert DurasiJatuhTempo.objects.get(
            seksi=seksi_pmde, id_sub_jenis_data=sub_jenis
        ).durasi == 14

    def test_a_non_prioritas_year_takes_the_other_number(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde)
        self._generate(client, admin_pmde)
        assert DurasiJatuhTempo.objects.get(
            seksi=seksi_pmde, id_sub_jenis_data=sub_jenis
        ).durasi == 85

    def test_a_year_without_a_rule_is_not_generated(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        """No rule means no basis for a number — the year is left alone rather
        than filled with a guess."""
        _aturan(seksi_pmde, tahun=2025)

        self._generate(client, admin_pmde)

        tahun_ditulis = set(
            DurasiJatuhTempo.objects.filter(seksi=seksi_pmde)
            .values_list('start_date__year', flat=True)
        )
        assert tahun_ditulis == {2025}

    def test_without_any_rule_nothing_is_written_and_it_says_so(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        resp = self._generate(client, admin_pmde)
        assert resp.status_code == 400
        assert 'Aturan Durasi Jatuh Tempo' in resp.json()['message']
        assert not DurasiJatuhTempo.objects.exists()

    def test_an_existing_row_is_never_overwritten(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        """The durasi 14 rows survived precisely because generate only inserts.
        That must stay true."""
        _aturan(seksi_pmde)
        manual = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sub_jenis, seksi=seksi_pmde, durasi=14,
            start_date=date(TAHUN, 1, 1), end_date=date(TAHUN, 12, 31),
        )

        self._generate(client, admin_pmde)

        manual.refresh_from_db()
        assert manual.durasi == 14


@pytest.mark.django_db
class TestGeneratePIDE:
    """PIDE now has the same feature, driven by the same engine."""

    def test_pide_generates_from_its_own_rule(
        self, client, admin_pide, seksi_pide, sub_jenis
    ):
        _aturan(seksi_pide, prioritas=35, non_prioritas=90)
        _jadikan_prioritas(sub_jenis)

        client.force_login(admin_pide)
        resp = client.post(reverse('durasi_jatuh_tempo_pide_generate'))

        assert resp.status_code == 200
        assert DurasiJatuhTempo.objects.get(
            seksi=seksi_pide, id_sub_jenis_data=sub_jenis
        ).durasi == 35

    def test_pide_and_pmde_do_not_read_each_others_rules(
        self, client, admin_pide, seksi_pide, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde, prioritas=45, non_prioritas=85)
        _aturan(seksi_pide, prioritas=35, non_prioritas=90)

        client.force_login(admin_pide)
        client.post(reverse('durasi_jatuh_tempo_pide_generate'))

        assert DurasiJatuhTempo.objects.filter(seksi=seksi_pide).exists()
        assert not DurasiJatuhTempo.objects.filter(seksi=seksi_pmde).exists()
        assert DurasiJatuhTempo.objects.get(seksi=seksi_pide).durasi == 90

    def test_preview_reports_the_years_it_would_cover(
        self, client, admin_pide, seksi_pide, sub_jenis
    ):
        _aturan(seksi_pide, tahun=2025, prioritas=35, non_prioritas=90)
        _aturan(seksi_pide, tahun=2026, prioritas=35, non_prioritas=90)

        client.force_login(admin_pide)
        payload = client.get(
            reverse('durasi_jatuh_tempo_pide_generate_preview')
        ).json()

        assert payload['success'] is True
        assert payload['tahun_tersedia'] == [2025, 2026]
        assert payload['total_rows'] == 2

    def test_a_pmde_admin_cannot_drive_the_pide_generate(
        self, client, admin_pmde, seksi_pide, sub_jenis
    ):
        """These endpoints use @user_passes_test, which redirects rather than
        raising 403 — the same as the PMDE ones next to them."""
        _aturan(seksi_pide, prioritas=35, non_prioritas=90)
        client.force_login(admin_pmde)

        resp = client.post(reverse('durasi_jatuh_tempo_pide_generate'))

        assert resp.status_code == 302
        assert not DurasiJatuhTempo.objects.exists()


# --------------------------------------------------------------------------- #
# Sinkronkan Prioritas                                                        #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestPrioritasSync:

    def test_a_row_moves_to_the_prioritas_durasi_when_it_becomes_prioritas(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        _aturan(seksi_pmde)
        row = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sub_jenis, seksi=seksi_pmde, durasi=85,
            start_date=date(TAHUN, 1, 1), end_date=date(TAHUN, 12, 31),
        )
        _jadikan_prioritas(sub_jenis)

        client.force_login(admin_pmde)
        client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))

        row.refresh_from_db()
        assert row.durasi == 45

    def test_a_hand_set_durasi_is_left_alone(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        """30 is neither number this Sub Jenis Data's rule allows, so it was set
        deliberately and must survive."""
        _aturan(seksi_pmde)
        row = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sub_jenis, seksi=seksi_pmde, durasi=30,
            start_date=date(TAHUN, 1, 1), end_date=date(TAHUN, 12, 31),
        )
        _jadikan_prioritas(sub_jenis)

        client.force_login(admin_pmde)
        client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))

        row.refresh_from_db()
        assert row.durasi == 30

    def test_an_exception_row_keeps_its_own_number(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        """The old code compared against one global 45/85 pair, so a 14 row was
        only safe by accident. Now 14 is what its own rule says, and the sync
        confirms it rather than overwriting it."""
        _aturan(seksi_pmde)
        _aturan(seksi_pmde, prioritas=14, id_sub_jenis_data=sub_jenis)
        row = DurasiJatuhTempo.objects.create(
            id_sub_jenis_data=sub_jenis, seksi=seksi_pmde, durasi=14,
            start_date=date(TAHUN, 1, 1), end_date=date(TAHUN, 12, 31),
        )
        _jadikan_prioritas(sub_jenis)

        client.force_login(admin_pmde)
        client.post(reverse('durasi_jatuh_tempo_pmde_prioritas_sync'))

        row.refresh_from_db()
        assert row.durasi == 14


# --------------------------------------------------------------------------- #
# Menu aturan                                                                 #
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestMenuAturan:

    @pytest.mark.parametrize('group_name', ['admin', 'admin_pide', 'admin_pmde'])
    def test_every_admin_seksi_can_open_it(self, client, db, group_name):
        user = UserFactory()
        user.groups.add(Group.objects.get_or_create(name=group_name)[0])
        client.force_login(user)

        assert client.get(reverse('aturan_durasi_jatuh_tempo_list')).status_code == 200
        assert client.get(reverse('aturan_durasi_jatuh_tempo_data')).status_code == 200

    def test_a_plain_user_cannot(self, client, db):
        user = UserFactory()
        user.groups.add(Group.objects.get_or_create(name='user_pmde')[0])
        client.force_login(user)
        assert client.get(reverse('aturan_durasi_jatuh_tempo_list')).status_code == 403

    def test_a_duplicate_rule_is_rejected_with_a_clear_message(
        self, client, admin_pmde, seksi_pmde
    ):
        _aturan(seksi_pmde)
        client.force_login(admin_pmde)

        resp = client.post(
            reverse('aturan_durasi_jatuh_tempo_create'),
            {
                'seksi': seksi_pmde.pk, 'tahun': TAHUN,
                'durasi_prioritas': 40, 'durasi_non_prioritas': 80,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        assert AturanDurasiJatuhTempo.objects.count() == 1
        assert 'sudah ada' in resp.content.decode()

    def test_a_sub_jenis_data_from_another_ilap_is_rejected(
        self, client, admin_pmde, seksi_pmde, sub_jenis
    ):
        client.force_login(admin_pmde)
        ilap_lain = ILAPFactory()

        resp = client.post(
            reverse('aturan_durasi_jatuh_tempo_create'),
            {
                'seksi': seksi_pmde.pk, 'tahun': TAHUN,
                'durasi_prioritas': 14, 'durasi_non_prioritas': 85,
                'id_ilap': ilap_lain.pk, 'id_sub_jenis_data': sub_jenis.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        assert AturanDurasiJatuhTempo.objects.count() == 0
        assert 'bukan milik ILAP' in resp.content.decode()
