"""Seksi P3DE / P3DER: each seksi sees and manages the ILAP of its own wilayah.

Seksi P3DE handles the Nasional and Internasional ILAP, Seksi P3DER the Regional
ones. Both run the same stage of the workflow, so PIC and TiketPIC keep the
`P3DE` tipe; the split is by group (`*_p3de` vs `*_p3der`) and by the ILAP's
kategori wilayah. This scenario drives the real UI as one account per role and
checks:

- the menus and labels name the viewer's seksi;
- the row counts behind Daftar Tiket and the PIC P3DE list match the database
  for that seksi exactly (not merely "fewer than everything");
- a kasi / admin of one seksi is refused the other seksi's tiket;
- the PIC P3DE form only offers the admin's own seksi, and the server refuses
  a user of the other seksi even when the browser is made to submit one.

Accounts come from setup_test_data.py (pw_user_p3der, pw_kasi_p3der,
pw_admin_p3der, pw_kasi_p3de, pw_admin_p3de). The DB truth is read through the
ORM, so DJANGO_SETTINGS_MODULE must point at the same database the server under
test uses.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import helpers as H

PASSWORD = H.PASS
REGIONAL = "regional"


def _orm():
    """Set Django up once, on the database the server under test uses."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    import django
    django.setup()
    from django.contrib.auth.models import User
    from django.db.models import Q
    from diamond_web.models.ilap import ILAP
    from diamond_web.models.jenis_data_ilap import JenisDataILAP
    from diamond_web.models.pic import PIC
    from diamond_web.models.tiket import Tiket
    from diamond_web.models.tiket_pic import TiketPIC

    reg = "id_kategori_wilayah__deskripsi__icontains"
    return {
        "User": User, "Q": Q, "ILAP": ILAP, "JenisDataILAP": JenisDataILAP,
        "PIC": PIC, "Tiket": Tiket, "TiketPIC": TiketPIC,
        "tiket_reg": {f"id_periode_data__id_sub_jenis_data_ilap__id_ilap__{reg}": REGIONAL},
        "pic_reg": {f"id_sub_jenis_data_ilap__id_ilap__{reg}": REGIONAL},
        "jd_reg": {f"id_ilap__{reg}": REGIONAL},
        "ilap_reg": {reg: REGIONAL},
    }


def _records_total(page, url_part, navigate):
    """Run `navigate()` and return the first DataTables `recordsTotal` from `url_part`."""
    with page.expect_response(lambda r: url_part in r.url and "draw=" in r.url, timeout=30000) as info:
        navigate()
    return info.value.json()["recordsTotal"]


def _nav_texts(page, selector):
    return page.eval_on_selector_all(selector, "els => els.map(e => e.textContent.trim())")


def _check(rep, sc, step, ok, detail=""):
    (rep.ok if ok else rep.fail)(sc, step, detail)
    return ok


def user_p3der(page, rep, db):
    sc = "p3der_user"
    H.login(page, "pw_user_p3der", PASSWORD)
    user = db["User"].objects.get(username="pw_user_p3der")

    page.goto(f"{H.BASE_URL}/")
    captions = _nav_texts(page, ".nxl-caption label")
    _check(rep, sc, "navbar caption names P3DER", captions == ["P3DER"], f"{captions}")
    pic_entries = [t for t in _nav_texts(page, ".nxl-navbar .nxl-mtext") if t.startswith("PIC")]
    _check(rep, sc, "navbar PIC entry is 'PIC P3DER'", pic_entries == ["PIC P3DER"], f"{pic_entries}")
    roles = _nav_texts(page, ".role-section-header small")
    _check(rep, sc, "home sidebar says 'Pelaksana P3DER'", roles == ["Pelaksana P3DER"], f"{roles}")

    # Rekam form: every ILAP offered is Regional and one the user is PIC of.
    page.goto(f"{H.BASE_URL}/tiket/rekam/")
    page.wait_for_selector("#id_ilap", state="attached")
    offered = set(page.eval_on_selector(
        "#id_ilap", "s => [...s.options].filter(o => o.value).map(o => +o.value)"))
    expected = set(db["ILAP"].objects.filter(
        jenisdatailap__pic__tipe="P3DE", jenisdatailap__pic__id_user=user,
        jenisdatailap__pic__end_date__isnull=True,
    ).values_list("id", flat=True))
    non_regional = db["ILAP"].objects.filter(id__in=offered).exclude(**db["ilap_reg"]).count()
    _check(rep, sc, "rekam: ILAP dropdown = own Regional PIC ILAP",
           offered == expected and non_regional == 0 and offered,
           f"offered={sorted(offered)} expected={sorted(expected)} non_regional={non_regional}")

    # Daftar Tiket: own TiketPIC only.
    got = _records_total(page, "/tiket/data/", lambda: page.goto(f"{H.BASE_URL}/tiket/"))
    want = db["Tiket"].objects.filter(tiketpic__id_user=user).distinct().count()
    _check(rep, sc, "Daftar Tiket recordsTotal = own TiketPIC", got == want, f"got={got} want={want}")

    # PIC P3DE list: the Regional rows only.
    got = _records_total(page, "/pic-p3de/data/", lambda: page.goto(f"{H.BASE_URL}/pic/?tab=p3de"))
    want = db["PIC"].objects.filter(tipe="P3DE", **db["pic_reg"]).count()
    _check(rep, sc, "PIC P3DE list recordsTotal = Regional PIC P3DE", got == want, f"got={got} want={want}")
    tab = page.text_content("#tab-p3de").strip()
    _check(rep, sc, "PIC tab reads 'PIC P3DER'", tab == "PIC P3DER", tab)
    H.shot(page, f"{sc}_pic_list")

    # Profil PDE directory: P3DER is its own column.
    page.goto(f"{H.BASE_URL}/profil-ilap/")
    titles = [t.split("\n")[0].strip() for t in _nav_texts(page, ".seksi-card .card-header")]
    _check(rep, sc, "Profil PDE lists four seksi",
           [t.split()[0] + " " + t.split()[1] for t in titles] == ["Seksi P3DE", "Seksi P3DER", "Seksi PIDE", "Seksi PMDE"],
           f"{titles}")
    in_p3der = page.eval_on_selector_all(
        ".seksi-card", "cards => cards.filter(c => c.querySelector('.card-header').textContent.includes('Seksi P3DER'))"
        ".map(c => c.textContent.includes('@pw_user_p3der'))")
    _check(rep, sc, "pw_user_p3der listed under Seksi P3DER", in_p3der == [True], f"{in_p3der}")
    H.shot(page, f"{sc}_profil_pde")


def _kasi(page, rep, db, username, regional):
    sc = username.replace("pw_", "")
    H.login(page, username, PASSWORD)
    tikets = db["Tiket"].objects.filter(**db["tiket_reg"]) if regional \
        else db["Tiket"].objects.exclude(**db["tiket_reg"])
    got = _records_total(page, "/tiket/data/", lambda: page.goto(f"{H.BASE_URL}/tiket/"))
    want = tikets.count()
    _check(rep, sc, f"Daftar Tiket recordsTotal = {'Regional' if regional else 'Nasional+Internasional'} tikets",
           got == want, f"got={got} want={want} (all={db['Tiket'].objects.count()})")

    own = tikets.order_by("id").first()
    other = (db["Tiket"].objects.exclude(**db["tiket_reg"]) if regional
             else db["Tiket"].objects.filter(**db["tiket_reg"])).order_by("id").first()
    resp = page.goto(f"{H.BASE_URL}/tiket/{own.pk}/")
    crumb = page.text_content(".breadcrumb li:nth-child(2)").strip() if resp.status == 200 else ""
    seksi = "P3DER" if regional else "P3DE"
    _check(rep, sc, "opens own seksi tiket", resp.status == 200 and crumb == seksi,
           f"tiket {own.pk} status={resp.status} breadcrumb={crumb!r}")
    resp = page.goto(f"{H.BASE_URL}/tiket/{other.pk}/")
    _check(rep, sc, "refused the other seksi's tiket", resp.status == 403, f"tiket {other.pk} status={resp.status}")

    page.goto(f"{H.BASE_URL}/")
    captions = _nav_texts(page, ".nxl-caption label")
    _check(rep, sc, f"navbar caption names {seksi}", captions == [seksi], f"{captions}")
    roles = _nav_texts(page, ".role-section-header small")
    _check(rep, sc, f"home sidebar says 'Kepala Seksi {seksi}'", roles == [f"Kepala Seksi {seksi}"], f"{roles}")


def kasi_p3der(page, rep, db):
    _kasi(page, rep, db, "pw_kasi_p3der", regional=True)


def kasi_p3de(page, rep, db):
    _kasi(page, rep, db, "pw_kasi_p3de", regional=False)


def _open_pic_create(page):
    page.goto(f"{H.BASE_URL}/pic/?tab=p3de")
    page.wait_for_selector("#pane-p3de [data-action='create']")
    page.click("#pane-p3de [data-action='create']")
    page.wait_for_selector("#crudModal #id_id_user", state="attached")
    page.wait_for_selector("#crudModal.show")


def _admin(page, rep, db, username, regional):
    sc = username.replace("pw_", "")
    seksi = "P3DER" if regional else "P3DE"
    other_user_group = "user_p3de" if regional else "user_p3der"
    own_user_group = "user_p3der" if regional else "user_p3de"
    H.login(page, username, PASSWORD)

    page.goto(f"{H.BASE_URL}/")
    # A seksi admin also gets the seksi's own section, as admin_p3de always has.
    captions = _nav_texts(page, ".nxl-caption label")
    _check(rep, sc, f"navbar captions '{seksi}' + 'Admin {seksi}'",
           captions == [seksi, f"Admin {seksi}"], f"{captions}")

    _open_pic_create(page)
    bulk = page.locator("#pane-p3de a[href*='bulk-pemda']").count()
    _check(rep, sc, f"Bulk PD/PV button {'shown' if regional else 'hidden'}", bulk == (1 if regional else 0), f"count={bulk}")

    subs = set(page.eval_on_selector(
        "#id_id_sub_jenis_data_ilap", "s => [...s.options].filter(o => o.value).map(o => +o.value)"))
    jd = db["JenisDataILAP"].objects
    want_subs = set((jd.filter(**db["jd_reg"]) if regional else jd.exclude(**db["jd_reg"])).values_list("id", flat=True))
    _check(rep, sc, f"PIC form: sub jenis data = {seksi} ILAP only", subs == want_subs,
           f"offered={len(subs)} want={len(want_subs)} diff={len(subs ^ want_subs)}")
    users = set(page.eval_on_selector(
        "#id_id_user", "s => [...s.options].filter(o => o.value).map(o => +o.value)"))
    want_users = set(db["User"].objects.filter(groups__name=own_user_group).values_list("id", flat=True))
    _check(rep, sc, f"PIC form: users = {own_user_group} only", users == want_users,
           f"offered={len(users)} want={len(want_users)}")

    # Make the browser submit a user of the other seksi; the server must refuse.
    # For a seksi admin that user is not even a valid choice of the field.
    outsider = db["User"].objects.filter(groups__name=other_user_group).exclude(
        groups__name=own_user_group).order_by("id").first()
    body, errors, before, after = _forge_pic_submit(page, db, outsider.pk, min(subs))
    _check(rep, sc, f"server refuses a {other_user_group} user",
           body.get("success") is False and after == before and errors,
           f"success={body.get('success')} rows {before}->{after} errors={errors}")
    H.shot(page, f"{sc}_pic_form_rejected")
    H.force_close_modal(page, "crudModal")

    # Bulk PD/PV page itself.
    resp = page.goto(f"{H.BASE_URL}/pic/bulk-pemda/")
    _check(rep, sc, f"Bulk PD/PV page {'opens' if regional else 'refused'}",
           resp.status == (200 if regional else 403), f"status={resp.status}")

    # Detail of the other seksi's tiket is refused; own seksi offers Ubah Isian.
    tikets = db["Tiket"].objects
    own = (tikets.filter(**db["tiket_reg"]) if regional else tikets.exclude(**db["tiket_reg"])) \
        .filter(status_tiket__gt=1).order_by("id").first()
    other = (tikets.exclude(**db["tiket_reg"]) if regional else tikets.filter(**db["tiket_reg"])).order_by("id").first()
    resp = page.goto(f"{H.BASE_URL}/tiket/{own.pk}/")
    edit = page.locator("[data-bs-target='#editTiketModal']").count() if resp.status == 200 else 0
    _check(rep, sc, "own seksi tiket (past Direkam) offers Ubah Isian Tiket", resp.status == 200 and edit > 0,
           f"tiket {own.pk} status_tiket={own.status_tiket} http={resp.status} edit_buttons={edit}")
    resp = page.goto(f"{H.BASE_URL}/tiket/{other.pk}/")
    _check(rep, sc, "refused the other seksi's tiket", resp.status == 403, f"tiket {other.pk} status={resp.status}")


def _forge_pic_submit(page, db, user_pk, sub_pk):
    """Submit the open PIC P3DE form with `user_pk` / `sub_pk`, whatever it offers.

    Returns (json body, visible error texts, PIC rows before, after).
    """
    before = db["PIC"].objects.count()
    page.evaluate(
        """([userPk, subPk]) => {
            const u = document.getElementById('id_id_user');
            if (![...u.options].some(o => o.value === String(userPk))) u.add(new Option('forged', userPk));
            $('#id_id_user').val(String(userPk)).trigger('change');
            $('#id_id_sub_jenis_data_ilap').val(String(subPk)).trigger('change');
        }""",
        [user_pk, sub_pk],
    )
    page.evaluate("""() => {
        const el = document.querySelector('#crudModal input[name="start_date"]');
        if (el._flatpickr) el._flatpickr.setDate('2026-01-01', true); else el.value = '2026-01-01';
    }""")
    with page.expect_response(lambda r: "/pic-p3de/create/" in r.url and r.request.method == "POST") as info:
        page.click("#crudModal button[type='submit']")
    body = info.value.json()
    try:
        page.wait_for_function(
            "() => [...document.querySelectorAll('#modalContent .invalid-feedback, #modalContent .errorlist')]"
            ".some(e => e.textContent.trim())", timeout=10000)
    except Exception:
        pass
    errors = [t for t in page.eval_on_selector_all(
        "#modalContent .invalid-feedback, #modalContent .errorlist",
        "els => els.map(e => e.textContent.trim())") if t]
    return body, errors, before, db["PIC"].objects.count()


def global_admin_seksi_rule(page, rep, db):
    """A global admin is offered both seksi's users, so the per-ILAP rule decides.

    Pick a Regional sub jenis data and a Seksi P3DE user: the form must say the
    ILAP belongs to Seksi P3DER, and write nothing.
    """
    sc = "admin_global_pic_rule"
    H.login(page)
    _open_pic_create(page)
    users = set(page.eval_on_selector(
        "#id_id_user", "s => [...s.options].filter(o => o.value).map(o => +o.value)"))
    p3de_user = db["User"].objects.filter(groups__name="user_p3de").exclude(
        groups__name="user_p3der").exclude(is_superuser=True).order_by("id").first()
    p3der_user = db["User"].objects.get(username="pw_user_p3der")
    _check(rep, sc, "both seksi's users offered", {p3de_user.pk, p3der_user.pk} <= users,
           f"offered={len(users)}")
    regional_sub = db["JenisDataILAP"].objects.filter(**db["jd_reg"]).order_by("id").first()
    body, errors, before, after = _forge_pic_submit(page, db, p3de_user.pk, regional_sub.pk)
    _check(rep, sc, "Regional sub jenis + user_p3de refused with the seksi message",
           body.get("success") is False and after == before and any("Seksi P3DER" in e for e in errors),
           f"success={body.get('success')} rows {before}->{after} errors={errors}")
    H.shot(page, f"{sc}_rejected")
    H.force_close_modal(page, "crudModal")


def admin_p3der(page, rep, db):
    _admin(page, rep, db, "pw_admin_p3der", regional=True)


def admin_p3de(page, rep, db):
    _admin(page, rep, db, "pw_admin_p3de", regional=False)


def run(page, rep):
    db = _orm()
    for fn in (user_p3der, kasi_p3der, kasi_p3de, admin_p3der, admin_p3de, global_admin_seksi_rule):
        try:
            fn(page, rep, db)
        except Exception as e:
            H.shot(page, f"{fn.__name__}_EXCEPTION")
            rep.fail(fn.__name__, "exception", str(e))
    # Leave the session on the default account so later scenarios are unaffected.
    H.login(page)


if __name__ == "__main__":
    rep = H.Reporter()
    with H.browser_page(headless=os.environ.get("E2E_HEADFUL") != "1") as page:
        run(page, rep)
    rep.write()
