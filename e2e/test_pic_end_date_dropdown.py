"""Rekam tiket: a P3DE PIC whose assignment has ended must lose the sub jenis data.

Bug report: "user p3de that pic in that sub jenis data but have end date still
have that sub jenis data in the dropdown".

The "Jenis Data ILAP" dropdown on /tiket/rekam/ is filled by an AJAX call to
/api/ilap/<pk>/periode-jenis-data/ once an ILAP is picked. Both that endpoint
and the form's own queryset used to check the PIC date window in a *chained*
.filter(), which makes Django join `pic` a second time -- so "is this
assignment still active?" was answered by an unrelated PIC row (any user, any
tipe). A P3DE user whose assignment had ended kept seeing the sub jenis data as
long as somebody else was still active on it.

Requires the dummy fixture:
    python manage.py seed_pic_end_date_dummy

which builds one ILAP with two sub jenis data, where `dummy_p3de_expired` is
ended on one and still active on the other -- the second assignment is what
keeps the ILAP visible, so the sub-jenis-level filter is the only thing left to
get this right.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

ILAP_NAME = "ZZ Dummy ILAP - Uji PIC End Date"
SUB_EXPIRED = "ZZ9990101"   # PIC ended yesterday -> must NOT be offered
SUB_KEPT = "ZZ9990202"      # PIC still active    -> must be offered
USER_EXPIRED = ("dummy_p3de_expired", "dummy12345")
USER_TAKEOVER = ("dummy_p3de_takeover", "dummy12345")


def _open_rekam_and_pick_ilap(page, rep, sc):
    """Go to the rekam form, select the dummy ILAP, wait for the AJAX populate.

    Returns the list of visible option texts in #id_periode_data.
    """
    page.goto(f"{H.BASE_URL}/tiket/rekam/")
    page.wait_for_selector("#id_ilap")

    ilap_value = page.eval_on_selector(
        "#id_ilap",
        "(sel, name) => { const o=[...sel.options].find(o=>o.textContent.includes(name)); return o?o.value:''; }",
        ILAP_NAME,
    )
    if not ilap_value:
        rep.fail(sc, "dummy ILAP present in ILAP dropdown",
                 f"'{ILAP_NAME}' not offered -- run: python manage.py seed_pic_end_date_dummy")
        return None
    rep.ok(sc, "dummy ILAP present in ILAP dropdown", f"value={ilap_value}")

    page.select_option("#id_ilap", ilap_value)
    # The AJAX populate replaces the options; wait for it to land rather than
    # reading the placeholder-only select.
    try:
        page.wait_for_function(
            """() => {
                const s = document.getElementById('id_periode_data');
                return s && [...s.options].some(o => o.value);
            }""",
            timeout=15000,
        )
    except Exception:
        pass  # an empty dropdown is a legitimate outcome for the takeover check

    return page.eval_on_selector(
        "#id_periode_data",
        "(sel) => [...sel.options].filter(o => o.value).map(o => o.textContent.trim())",
    )


def expired_pic_loses_sub_jenis_data(page, rep):
    """The reported bug, driven through the real browser."""
    sc = "pic_end_date_expired"
    H.login(page, *USER_EXPIRED)

    options = _open_rekam_and_pick_ilap(page, rep, sc)
    if options is None:
        return
    detail = " | ".join(options) or "(empty)"

    if any(SUB_EXPIRED in o for o in options):
        rep.fail(sc, f"{SUB_EXPIRED} (PIC ended) must not be offered", detail)
        rep.bug(
            "Rekam tiket: sub jenis data of an ENDED P3DE PIC still offered",
            "HIGH",
            f"User {USER_EXPIRED[0]}'s P3DE assignment on {SUB_EXPIRED} ended "
            f"yesterday, but the Jenis Data ILAP dropdown still lists it. "
            f"Options seen: {detail}",
        )
    else:
        rep.ok(sc, f"{SUB_EXPIRED} (PIC ended) correctly hidden", detail)

    # Guard against "fixed" by simply emptying the dropdown.
    if any(SUB_KEPT in o for o in options):
        rep.ok(sc, f"{SUB_KEPT} (PIC active) still offered", detail)
    else:
        rep.fail(sc, f"{SUB_KEPT} (PIC active) must still be offered", detail)

    H.shot(page, f"{sc}_dropdown")


def active_pic_keeps_sub_jenis_data(page, rep):
    """Positive control: the user who took over still sees it."""
    sc = "pic_end_date_takeover"
    H.login(page, *USER_TAKEOVER)

    options = _open_rekam_and_pick_ilap(page, rep, sc)
    if options is None:
        return
    detail = " | ".join(options) or "(empty)"

    if any(SUB_EXPIRED in o for o in options):
        rep.ok(sc, f"{SUB_EXPIRED} offered to the active PIC", detail)
    else:
        rep.fail(sc, f"{SUB_EXPIRED} must be offered to the active PIC", detail)

    if any(SUB_KEPT in o for o in options):
        rep.fail(sc, f"{SUB_KEPT} must NOT be offered (not their assignment)", detail)
    else:
        rep.ok(sc, f"{SUB_KEPT} correctly hidden from the takeover user", detail)

    H.shot(page, f"{sc}_dropdown")


def run(page, rep):
    for fn in (expired_pic_loses_sub_jenis_data, active_pic_keeps_sub_jenis_data):
        try:
            fn(page, rep)
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
