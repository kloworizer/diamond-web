"""Regression tests: an expired P3DE PIC must not keep seeing its sub jenis data.

Both the "Jenis Data ILAP" dropdown (TiketForm) and the AJAX endpoint that
feeds it (ILAPPeriodeDataAPIView) restrict non-admin users to the sub jenis
data where they are an *active* P3DE PIC. The activeness window is
``start_date <= today`` and ``end_date IS NULL OR end_date >= today``.

The end_date half used to live in a chained ``.filter()`` call, which makes
Django join the ``pic`` table a second time -- so the date window was checked
against an unrelated PIC row (any user, any tipe) instead of the user's own
assignment. A P3DE user whose assignment had ended still saw the sub jenis
data as long as *somebody* was still an active PIC on it.
"""
import json
import pytest
from datetime import date, timedelta

from django.contrib.auth.models import Group
from django.urls import reverse

from diamond_web.forms.tiket import TiketForm
from diamond_web.tests.conftest import (
    ILAPFactory, JenisDataILAPFactory, PICFactory, PeriodePengirimanFactory,
    UserFactory,
)
from diamond_web.models.periode_jenis_data import PeriodeJenisData


@pytest.fixture
def expired_p3de_setup(db, authenticated_user):
    """One ILAP, two sub jenis data, as reported by the user.

    The user is still an active P3DE PIC on ``kept`` -- so the ILAP itself
    stays visible and the coarse ILAP-level access check passes -- but their
    assignment on ``expired`` ended yesterday. Only ``expired`` must drop out.

    A second, still-active PIC (a different user) sits on ``expired`` too:
    that is the row the buggy second join used to match the date window
    against.
    """
    today = date.today()
    ilap = ILAPFactory()
    expired = JenisDataILAPFactory(id_ilap=ilap)
    kept = JenisDataILAPFactory(id_ilap=ilap)

    # The reporting user: assignment on `expired` has already ended...
    PICFactory(
        tipe='P3DE',
        id_sub_jenis_data_ilap=expired,
        id_user=authenticated_user,
        start_date=today - timedelta(days=365),
        end_date=today - timedelta(days=1),
    )
    # ...but they are still active on `kept`, so the ILAP remains theirs.
    PICFactory(
        tipe='P3DE',
        id_sub_jenis_data_ilap=kept,
        id_user=authenticated_user,
        start_date=today - timedelta(days=365),
        end_date=None,
    )
    # Somebody else took over `expired` and is still active on it.
    PICFactory(
        tipe='P3DE',
        id_sub_jenis_data_ilap=expired,
        id_user=UserFactory(),
        start_date=today - timedelta(days=1),
        end_date=None,
    )

    periode_pengiriman = PeriodePengirimanFactory()
    expired_periode = PeriodeJenisData.objects.create(
        id_sub_jenis_data_ilap=expired,
        id_periode_pengiriman=periode_pengiriman,
        start_date=today - timedelta(days=365),
        akhir_penyampaian=30,
    )
    kept_periode = PeriodeJenisData.objects.create(
        id_sub_jenis_data_ilap=kept,
        id_periode_pengiriman=periode_pengiriman,
        start_date=today - timedelta(days=365),
        akhir_penyampaian=30,
    )
    return ilap, expired, expired_periode, kept_periode


@pytest.mark.django_db
class TestExpiredP3DEPICExcluded:
    """The dropdown and its AJAX feed must both drop the ended assignment."""

    def test_api_excludes_sub_jenis_data_of_expired_pic(
        self, client, authenticated_user, expired_p3de_setup
    ):
        ilap, _, expired_periode, kept_periode = expired_p3de_setup
        client.force_login(authenticated_user)

        resp = client.get(reverse('api_ilap_periode_jenis_data', args=[ilap.pk]))

        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        returned = {row['id'] for row in data['data']}
        assert expired_periode.pk not in returned
        assert returned == {kept_periode.pk}

    def test_form_dropdown_excludes_sub_jenis_data_of_expired_pic(
        self, authenticated_user, expired_p3de_setup
    ):
        ilap, _, expired_periode, kept_periode = expired_p3de_setup

        form = TiketForm(data={'id_ilap': str(ilap.pk)}, user=authenticated_user)

        returned = {pd.pk for pd in form.fields['id_periode_data'].queryset}
        assert expired_periode.pk not in returned
        assert returned == {kept_periode.pk}

    def test_expired_pic_with_end_date_today_still_active(
        self, client, authenticated_user, expired_p3de_setup
    ):
        """end_date == today is the last valid day, not an expiry."""
        ilap, expired, expired_periode, kept_periode = expired_p3de_setup
        PICFactory(
            tipe='P3DE',
            id_sub_jenis_data_ilap=expired,
            id_user=authenticated_user,
            start_date=date.today() - timedelta(days=5),
            end_date=date.today(),
        )
        client.force_login(authenticated_user)

        resp = client.get(reverse('api_ilap_periode_jenis_data', args=[ilap.pk]))

        data = json.loads(resp.content)
        returned = {row['id'] for row in data['data']}
        assert returned == {expired_periode.pk, kept_periode.pk}

    def test_pic_of_other_tipe_does_not_grant_access(
        self, client, expired_p3de_setup
    ):
        """An active PIDE assignment must not stand in for a P3DE one."""
        ilap, expired, expired_periode, kept_periode = expired_p3de_setup
        pide_user = UserFactory()
        pide_user.groups.add(Group.objects.get_or_create(name='user_p3de')[0])
        PICFactory(
            tipe='PIDE',
            id_sub_jenis_data_ilap=expired,
            id_user=pide_user,
            start_date=date.today() - timedelta(days=10),
            end_date=None,
        )
        client.force_login(pide_user)

        resp = client.get(reverse('api_ilap_periode_jenis_data', args=[ilap.pk]))

        data = json.loads(resp.content)
        assert data['data'] == []
