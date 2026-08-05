"""A rejected Tanda Terima must say why it was rejected.

The tiket table in the form is rebuilt by AJAX on every render, so a submit
that fails validation used to come back looking untouched: the chronology check
in `clean()` raised a non-field error, the template rendered no non-field block,
and the user saw the form again with nothing created and nothing explained.
"""
import datetime
import json

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from diamond_web.forms.tanda_terima_data import TandaTerimaDataForm
from diamond_web.models.ilap_kpp import ILAPKPP
from diamond_web.models.tanda_terima_data import TandaTerimaData
from diamond_web.utils import lift_time_above
from diamond_web.tests.conftest import (
    ILAPFactory, JenisDataILAPFactory, KanwilFactory, KPPFactory,
    PeriodeJenisDataFactory, TiketFactory,
)


def regional_tiket(kanwil, via_kpp=False, tgl_terima_dip=None):
    """A tiket whose ILAP is mapped to `kanwil`, directly or through a KPP."""
    ilap = ILAPFactory()
    if via_kpp:
        ILAPKPP.objects.create(id_ilap=ilap, kpp=True, id_kpp=KPPFactory(id_kanwil=kanwil))
    else:
        ILAPKPP.objects.create(id_ilap=ilap, kpp=False, id_kanwil=kanwil)
    periode = PeriodeJenisDataFactory(id_sub_jenis_data_ilap=JenisDataILAPFactory(id_ilap=ilap))
    return TiketFactory(
        id_periode_data=periode,
        status_tiket=1,
        tanda_terima=False,
        tgl_terima_dip=tgl_terima_dip or (timezone.now() - datetime.timedelta(days=10)),
    )


def post_data(kanwil, tikets, tanggal):
    return {
        'tanggal_tanda_terima': tanggal.isoformat(),
        'lingkup': 'regional',
        'id_kanwil': str(kanwil.pk),
        'id_ilap': '',
        'nomor_nd_pengantar': '',
        'tiket_ids': [str(t.pk) for t in tikets],
        'nomor_tanda_terima': '',
    }


@pytest.mark.django_db
class TestRegionalCreateReportsRejection:
    """A Kanwil-scoped create that fails validation must render its reason."""

    def test_backdated_receipt_renders_the_reason(self, client, admin_user):
        kanwil = KanwilFactory()
        tiket = regional_tiket(kanwil, tgl_terima_dip=timezone.now())

        client.force_login(admin_user)
        resp = client.post(
            reverse('tanda_terima_data_create'),
            post_data(kanwil, [tiket], timezone.now().date() - datetime.timedelta(days=3)),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = json.loads(resp.content)
        assert payload['success'] is False
        assert TandaTerimaData.objects.count() == 0
        # The whole point: the rejected form explains itself
        assert 'tidak boleh sebelum Tanggal Terima DIP' in payload['html']
        assert tiket.nomor_tiket in payload['html']

    def test_valid_regional_receipt_is_created(self, client, admin_user):
        kanwil = KanwilFactory()
        tiket = regional_tiket(kanwil)

        client.force_login(admin_user)
        resp = client.post(
            reverse('tanda_terima_data_create'),
            post_data(kanwil, [tiket], timezone.now().date()),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        payload = json.loads(resp.content)
        assert payload['success'] is True, payload
        tanda_terima = TandaTerimaData.objects.get()
        assert tanda_terima.id_kanwil_id == kanwil.pk
        assert tanda_terima.id_ilap_id is None

    def test_rejected_submit_keeps_the_tiket_selection(self, client, admin_user):
        """The table is refetched on render, so the choice rides on the form."""
        kanwil = KanwilFactory()
        late = regional_tiket(kanwil, tgl_terima_dip=timezone.now())
        early = regional_tiket(kanwil, via_kpp=True)

        client.force_login(admin_user)
        resp = client.post(
            reverse('tanda_terima_data_create'),
            post_data(kanwil, [late, early], timezone.now().date() - datetime.timedelta(days=3)),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        html = json.loads(resp.content)['html']
        assert f'data-preselected="{late.pk},{early.pk}"' in html


@pytest.mark.django_db
class TestChronologyErrorPlacement:
    """The clash is reported on the date field, and names every offender."""

    def test_error_lands_on_the_date_field(self, admin_user):
        kanwil = KanwilFactory()
        tiket = regional_tiket(kanwil, tgl_terima_dip=timezone.now())

        form = TandaTerimaDataForm(
            data=post_data(kanwil, [tiket], timezone.now().date() - datetime.timedelta(days=3)),
            user=admin_user,
        )
        assert not form.is_valid()
        assert 'tanggal_tanda_terima' in form.errors
        assert form.non_field_errors() == []

    def test_every_conflicting_tiket_is_named(self, admin_user):
        """A Kanwil pools many ILAP, so several tikets can clash at once."""
        kanwil = KanwilFactory()
        first = regional_tiket(kanwil, tgl_terima_dip=timezone.now())
        second = regional_tiket(kanwil, via_kpp=True, tgl_terima_dip=timezone.now())

        form = TandaTerimaDataForm(
            data=post_data(kanwil, [first, second],
                           timezone.now().date() - datetime.timedelta(days=3)),
            user=admin_user,
        )
        assert not form.is_valid()
        message = str(form.errors['tanggal_tanda_terima'])
        assert first.nomor_tiket in message
        assert second.nomor_tiket in message


class TestLiftTimeAbove:
    """The date-only picker borrows the submit time; only that gets adjusted."""

    def test_same_day_shortfall_is_lifted_past_the_floor(self):
        floor = datetime.datetime(2026, 8, 5, 14, 30)
        value = datetime.datetime(2026, 8, 5, 9, 0)

        lifted = lift_time_above(value, floor)
        assert lifted == datetime.datetime(2026, 8, 5, 14, 31)
        assert lifted.date() == value.date()

    def test_value_already_past_the_floor_is_untouched(self):
        floor = datetime.datetime(2026, 8, 5, 9, 0)
        value = datetime.datetime(2026, 8, 5, 14, 30)

        assert lift_time_above(value, floor) == value

    def test_earlier_day_is_left_for_the_caller_to_reject(self):
        floor = datetime.datetime(2026, 8, 5, 14, 30)
        value = datetime.datetime(2026, 8, 2, 23, 0)

        assert lift_time_above(value, floor) == value

    def test_later_day_is_untouched(self):
        floor = datetime.datetime(2026, 8, 5, 23, 30)
        value = datetime.datetime(2026, 8, 7, 1, 0)

        assert lift_time_above(value, floor) == value

    def test_lift_never_rolls_over_into_the_next_day(self):
        floor = datetime.datetime(2026, 8, 5, 23, 59, 30)
        value = datetime.datetime(2026, 8, 5, 8, 0)

        lifted = lift_time_above(value, floor)
        assert lifted.date() == datetime.date(2026, 8, 5)
        assert lifted >= floor

    def test_none_passthrough(self):
        assert lift_time_above(None, datetime.datetime(2026, 8, 5)) is None
        assert lift_time_above(datetime.datetime(2026, 8, 5), None) == datetime.datetime(2026, 8, 5)


@pytest.mark.django_db
class TestSameDayReceiptIsAccepted:
    """Picking the DIP receipt's own day must work whatever the clock says."""

    def test_same_day_receipt_saves_at_or_after_tgl_terima_dip(self, client, admin_user):
        kanwil = KanwilFactory()
        # Late in the day, so the submit-time stamp almost certainly falls short
        dip = datetime.datetime.combine(
            timezone.now().date(), datetime.time(23, 59, 0)
        )
        tiket = regional_tiket(kanwil, tgl_terima_dip=dip)

        client.force_login(admin_user)
        resp = client.post(
            reverse('tanda_terima_data_create'),
            post_data(kanwil, [tiket], timezone.now().date()),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        assert json.loads(resp.content)['success'] is True
        tanda_terima = TandaTerimaData.objects.get()
        assert tanda_terima.tanggal_tanda_terima.date() == timezone.now().date()
        assert tanda_terima.tanggal_tanda_terima >= dip

    def test_lift_clears_the_latest_of_several_tikets(self, admin_user):
        kanwil = KanwilFactory()
        today = timezone.now().date()
        earlier = regional_tiket(
            kanwil, tgl_terima_dip=datetime.datetime.combine(today, datetime.time(23, 58))
        )
        latest = regional_tiket(
            kanwil, via_kpp=True,
            tgl_terima_dip=datetime.datetime.combine(today, datetime.time(23, 59)),
        )

        form = TandaTerimaDataForm(
            data=post_data(kanwil, [earlier, latest], today), user=admin_user
        )
        assert form.is_valid(), form.errors
        tanggal = form.cleaned_data['tanggal_tanda_terima']
        assert tanggal >= latest.tgl_terima_dip
        assert tanggal.date() == today

    def test_earlier_day_is_still_rejected(self, admin_user):
        """The lift must not paper over a genuinely backdated receipt."""
        kanwil = KanwilFactory()
        tiket = regional_tiket(kanwil, tgl_terima_dip=timezone.now())

        form = TandaTerimaDataForm(
            data=post_data(kanwil, [tiket],
                           timezone.now().date() - datetime.timedelta(days=1)),
            user=admin_user,
        )
        assert not form.is_valid()
        assert 'sebelum Tanggal Terima DIP' in str(form.errors)


@pytest.mark.django_db
class TestNonFieldErrorsAreRendered:
    """Catch-all: no form-wide error may render invisibly again."""

    def test_template_renders_non_field_errors(self, admin_user):
        kanwil = KanwilFactory()
        tiket = regional_tiket(kanwil)

        form = TandaTerimaDataForm(
            data=post_data(kanwil, [tiket], timezone.now().date()), user=admin_user
        )
        form.is_valid()
        form.add_error(None, 'Galat tingkat formulir untuk diuji.')

        html = render_to_string('tanda_terima_data/form.html', {'form': form})
        assert 'Galat tingkat formulir untuk diuji.' in html
