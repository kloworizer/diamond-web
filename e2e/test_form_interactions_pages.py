"""
The same "does the form still WORK after the server rejects it?" question as
test_form_interactions.py, applied to the form surfaces that are NOT AJAX CRUD
modals:

  1. the tiket detail-page workflow modals (rekam penelitian, kirim, transfer,
     selesaikan, batalkan, ...), which each hand-roll their own fetch + re-render
  2. the report / monitoring filter forms (`#filter-form`)
  3. the full-page profil form

The CRUD pages get away with a re-render because their submit handler is
*delegated* (`$(document).on('submit', '#crudModal form')`), so it survives the
markup being swapped. The detail-page modals instead bind directly to the form
element:

    form.addEventListener('submit', ...)      // bound once, on first load
    ...
    formContainer.innerHTML = data.html;      // error branch: NEW form element

Nothing re-attaches that listener, so the check below is specifically whether a
*second* submit is still an AJAX submit or falls through to a native browser
POST that navigates away from the page.
"""
import sys, os
from contextlib import contextmanager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

BARIS = 1000


@contextmanager
def _collect_posts(page):
    """Collect (status, url, body) for POST responses.

    These endpoints answer 200 for *both* a successful save and a rejected one
    (the outcome is in the JSON `success` flag), so the status code alone cannot
    tell us whether we actually managed to force a rejection.

    The body must be read inside the handler: a successful save triggers a
    reload/redirect, and once the page navigates Playwright can no longer serve
    the old response body, so a deferred .json() just raises and the success
    would be misread as a rejection."""
    got = []

    def handler(resp):
        if resp.request.method != "POST":
            return
        try:
            body = resp.text()
        except Exception:
            body = ""
        got.append((resp.status, resp.url, body))

    page.on("response", handler)
    try:
        yield got
    finally:
        page.remove_listener("response", handler)


def _succeeded(posts):
    """True if any POST reported success -- i.e. we failed to force a rejection."""
    return any('"success": true' in b.lower().replace('"success":true', '"success": true')
               for _, _, b in posts)


# --------------------------------------------------------------------------- #
# Tiket detail-page workflow modals
# --------------------------------------------------------------------------- #
def _editable_fields(page, container):
    """Count fields a user could actually get wrong.

    Some 'modals' are pure confirmations -- the Generate ND Pengantar one is a
    summary table plus a button. There is nothing to invalidate, so an empty
    submit is legitimately valid: clicking it would perform the real action and
    advance the tiket rather than exercise a rejection path."""
    return page.evaluate(
        """(sel) => {
            const f = document.querySelector(sel + ' form');
            if (!f) return -1;
            return [...f.querySelectorAll('input, select, textarea')].filter(e =>
                e.name && e.name !== 'csrfmiddlewaretoken' && e.type !== 'hidden'
                && !e.disabled).length;
        }""", container)


def _prepare_invalid(page, container):
    """Empty the form and disable HTML5 validation so a real click reaches the
    server and is rejected there."""
    return page.evaluate(
        """(sel) => {
            const f = document.querySelector(sel + ' form');
            if (!f) return false;
            f.setAttribute('novalidate', 'novalidate');
            f.querySelectorAll('[required]').forEach(e => e.removeAttribute('required'));
            f.querySelectorAll('input[type=number], input[type=text], textarea')
             .forEach(e => { if (e.name !== 'csrfmiddlewaretoken') e.value = ''; });
            return true;
        }""", container)


def _click_submit(page, container):
    """Click the modal's real submit button.

    It has to be a genuine click, not `form.dispatchEvent(new Event('submit'))`:
    a synthetic submit event never triggers the browser's own form submission,
    so a form whose AJAX listener has gone missing would look like it "did
    nothing" when what a real user actually gets is a full page navigation."""
    return page.evaluate(
        """(sel) => {
            const f = document.querySelector(sel + ' form');
            if (!f) return false;
            const btn = f.querySelector('button[type=submit], input[type=submit]')
                     || document.querySelector(sel + ' button[type=submit]');
            if (!btn) return false;
            btn.removeAttribute('disabled');
            btn.click();
            return true;
        }""", container)


def modal_survives_rejection(page, rep, sc, detail_url, trigger, container, label,
                             force_enable=False):
    """Force a rejected submit in one detail-page modal, then assert the modal
    is still usable -- and crucially that submitting again is still AJAX."""
    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    page.wait_for_timeout(400)
    H.clear_overlays(page)

    if not page.locator(trigger).count():
        rep.info(sc, f"{label}: trigger not present", "tiket status does not offer it")
        return
    try:
        H.open_modal(page, trigger, container, force_enable=force_enable)
    except Exception as e:
        rep.info(sc, f"{label}: modal did not open", str(e)[:120])
        return

    n_fields = _editable_fields(page, container)
    if n_fields == 0:
        # Submitting would just perform the action for real and advance the
        # tiket, which is a state change, not a test.
        rep.info(sc, f"{label}: confirmation-only modal",
                 "no editable field to invalidate; not submitted")
        H.clear_overlays(page)
        return

    url_before = page.url
    with H.collect_pageerrors(page) as js_errors, _collect_posts(page) as posts:
        if not _prepare_invalid(page, container) or not _click_submit(page, container):
            rep.info(sc, f"{label}: no form/submit button in container", "skipped")
            return
        page.wait_for_timeout(2400)

    bad = [r for r in posts if r[0] >= 500]
    if bad:
        rep.fail(sc, f"{label}: rejected submit 5xx", f"{bad[0][0]} {bad[0][1]}")
        rep.bug(f"tiket modal '{label}' returns HTTP {bad[0][0]} on an invalid submit",
                "HIGH",
                f"POST {bad[0][1]} responded {bad[0][0]} instead of re-rendering the "
                f"form with errors.")
        return
    if not posts:
        rep.info(sc, f"{label}: no POST observed", "client guard blocked it before the server")
        return
    if _succeeded(posts):
        # Nothing on this form is required, so an empty payload is legitimately
        # valid. There is no rejection path to test here.
        rep.info(sc, f"{label}: empty submit is valid", "no rejection path to exercise")
        return
    rep.ok(sc, f"{label}: rejected submit reached server", str(posts[0][0]))

    # The modal must still be there, showing the form.
    still_form = page.locator(f"{container} form").count() > 0
    if still_form:
        rep.ok(sc, f"{label}: form re-rendered")
    else:
        shown = page.evaluate(
            """(sel) => (document.querySelector(sel) || {}).innerText || ''""", container).strip()
        rep.fail(sc, f"{label}: form gone after rejection", shown[:120])
        # The detail-page JS does `innerHTML = data.html || ... || '<div>Terjadi
        # kesalahan</div>'`, so a form_invalid() that returns only JSON errors
        # and no re-rendered `html` wipes the form out entirely.
        rep.bug(f"tiket modal '{label}' replaces the form with a generic error",
                "HIGH",
                "The view's form_invalid() returns JSON errors without an `html` key, so "
                "the modal's `innerHTML = data.html || ... || 'Terjadi kesalahan'` fallback "
                "discards the whole form. The user loses everything they typed and has to "
                f"close and reopen the modal. Container now reads: {shown[:160]!r}")
        H.shot(page, f"{sc}_{label}_form_gone")

    # THE check: submit again. A delegated/re-attached handler keeps this an
    # AJAX call; a stale one lets the browser perform a real navigation.
    if still_form:
        with _collect_posts(page) as second_posts:
            _prepare_invalid(page, container)
            _click_submit(page, container)
            page.wait_for_timeout(2600)
        navigated = page.url != url_before
        if navigated:
            rep.fail(sc, f"{label}: second submit navigated away", f"{url_before} -> {page.url}")
            rep.bug(f"tiket modal '{label}' loses its submit handler after a validation error",
                    "HIGH",
                    "The error branch replaces the container's innerHTML, creating a new "
                    "<form> element, but only the original element had the AJAX submit "
                    "listener attached. The user's next Simpan therefore performs a native "
                    "browser POST and navigates away from the tiket, losing the modal and "
                    "any unsaved input.")
            H.shot(page, f"{sc}_{label}_navigated")
            page.goto(detail_url, wait_until="domcontentloaded")
        elif second_posts:
            rep.ok(sc, f"{label}: second submit still AJAX", str(second_posts[0][0]))
        else:
            rep.fail(sc, f"{label}: second submit did nothing",
                     "no POST and no navigation -- the button is dead")
            rep.bug(f"tiket modal '{label}' becomes unsubmittable after a validation error",
                    "HIGH",
                    "After the form is re-rendered, submitting it produces neither an AJAX "
                    "request nor a navigation: the submit handler was bound to the replaced "
                    "form element and never re-attached, so the modal is a dead end.")
            H.shot(page, f"{sc}_{label}_dead")

    if js_errors:
        rep.fail(sc, f"{label}: uncaught JS", "; ".join(js_errors[:2]))
    else:
        rep.ok(sc, f"{label}: no uncaught JS")
    H.clear_overlays(page)


def tiket_workflow_modals(page, rep):
    """Drive one tiket forward, exercising each modal's rejection path."""
    sc = "pages_tiket_modals"
    detail_url, nomor = H.rekam_tiket(page, rep, sc, tahun="2007",
                                      baris_diterima=BARIS, backup=True)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#editTiketModal"]',
                             "#edit-tiket-form-container", "edit tiket")
    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#createTandaTerimaModal"]',
                             "#tanda-terima-form-container", "buat tanda terima")

    # A real tanda terima is the precondition for the penelitian modal.
    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_tanda_terima(page, rep, sc)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#rekamHasilPenelitianModal"]',
                             "#rekam-hasil-penelitian-form-container", "rekam hasil penelitian")

    # Push the tiket downstream so the later modals become reachable.
    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_rekam_penelitian(page, rep, sc, baris_lengkap=BARIS, baris_tidak_lengkap=0)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#kirimTiketModal"]',
                             "#kirim-tiket-form-container", "generate ND pengantar")
    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_generate_nd(page, rep, sc)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#kirimTiketKePideModal"]',
                             "#kirim-tiket-ke-pide-form-container", "kirim ke PIDE")
    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_kirim_ke_pide(page, rep, sc)

    # Safe to probe inline: DikembalikanTiketForm.catatan is required=True, so
    # the empty payload cannot actually return the tiket and derail the chain.
    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#dikembalikanTiketModal"]',
                             "#dikembalikan-tiket-form-container", "dikembalikan ke P3DE")

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#identifikasiTiketModal"]',
                             "#identifikasi-tiket-form-container", "identifikasi")

    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_identifikasi(page, rep, sc)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#transferKePMDEModal"]',
                             "#transfer-ke-pmde-form-container", "transfer ke PMDE",
                             force_enable=True)

    page.goto(detail_url, wait_until="domcontentloaded")
    H.clear_overlays(page)
    H.do_transfer_pmde(page, rep, sc, i=BARIS, u=0, res=0, cde=0)

    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#selesaikanTiketModal"]',
                             "#selesaikan-tiket-form-container", "selesaikan tiket",
                             force_enable=True)


def tiket_cancel_modals(page, rep):
    """Batalkan / Dikembalikan take a free-text catatan and are reachable early."""
    sc = "pages_tiket_cancel_modals"
    # backup=False so the "Rekam Backup Data" modal is still offered.
    detail_url, _ = H.rekam_tiket(page, rep, sc, tahun="2006",
                                  baris_diterima=BARIS, backup=False)
    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#rekamBackupDataModal"]',
                             "#backup-data-form-container", "rekam backup data")
    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#specialRequestModal"]',
                             "#special-request-form-container", "special request")
    # Last: BatalkanTiketForm.catatan is required=True so the empty payload is
    # rejected, but keep it at the end anyway since it is a terminal action.
    modal_survives_rejection(page, rep, sc, detail_url,
                             '[data-bs-target="#batalkanTiketModal"]',
                             "#batalkan-tiket-form-container", "batalkan tiket")


# --------------------------------------------------------------------------- #
# Report / monitoring filter forms
# --------------------------------------------------------------------------- #
FILTER_PAGES = [
    ("filter_laporan_transfer",            "laporan-transfer"),
    ("filter_laporan_sla_perekaman",       "laporan-sla-perekaman"),
    ("filter_laporan_sla_identifikasi",    "laporan-sla-identifikasi"),
    ("filter_laporan_metrik",              "laporan-metrik-data-eksternal"),
    ("filter_laporan_pengendalian_mutu",   "laporan-pengendalian-mutu"),
    ("filter_laporan_prioritas",           "laporan-hasil-pengolahan-data-prioritas"),
    ("filter_laporan_kelengkapan",         "laporan-kelengkapan-data"),
    ("filter_laporan_rekap_himpun",        "laporan-rekap-himpun-olah-data"),
    ("filter_laporan_detail_himpun",       "laporan-detail-himpun-olah-data"),
    ("filter_register_penerimaan",         "register-penerimaan-data"),
    ("filter_monitoring",                  "monitoring-penyampaian-data"),
    ("filter_tiket_list",                  "tiket"),
]


def filter_form_applies(page, rep, sc, slug):
    """A filter form must apply without a 5xx or a JS error, and must still be
    usable afterwards (the results table is replaced, not the form)."""
    page.goto(f"{H.BASE_URL}/{slug}/", wait_until="domcontentloaded", timeout=30000)
    if not page.locator("#filter-form").count():
        rep.info(sc, "no #filter-form on page", "skipped")
        return
    page.wait_for_timeout(1200)

    with H.collect_pageerrors(page) as js_errors, \
            H.collect_requests(page, lambda u: True) as responses:
        # Drive every filter control to its first real value, then apply.
        changed = page.evaluate(
            """() => {
                const f = document.querySelector('#filter-form');
                let n = 0;
                f.querySelectorAll('select').forEach(s => {
                    const o = [...s.options].find(o => o.value);
                    if (o && s.value !== o.value) {
                        s.value = o.value;
                        s.dispatchEvent(new Event('change', {bubbles: true}));
                        if (window.jQuery) jQuery(s).trigger('change');
                        n++;
                    }
                });
                return n;
            }""")
        page.wait_for_timeout(1500)
        page.evaluate(
            """() => {
                const f = document.querySelector('#filter-form');
                const btn = f.querySelector('button[type=submit], #btn-terapkan, [id*=terapkan], [id*=apply]');
                if (btn) btn.click();
                else f.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
            }""")
        page.wait_for_timeout(2600)

    bad = [r for r in responses if r[2] >= 500]
    if bad:
        rep.fail(sc, "filter apply 5xx", f"{bad[0][2]} {bad[0][1]}")
        rep.bug(f"{slug}: applying filters returns HTTP {bad[0][2]}",
                "HIGH",
                f"GET/POST {bad[0][1]} responded {bad[0][2]} when the filter form was "
                f"applied with its first available option for every control.")
        H.shot(page, f"{sc}_5xx")
    else:
        rep.ok(sc, "filters applied without server error", f"{changed} control(s) changed")

    if page.locator("#filter-form").count():
        rep.ok(sc, "filter form still present after apply")
    else:
        rep.fail(sc, "filter form disappeared after apply")

    if js_errors:
        rep.fail(sc, "uncaught JS applying filters", "; ".join(js_errors[:2]))
    else:
        rep.ok(sc, "no uncaught JS applying filters")


def filter_reset_restores(page, rep):
    """Monitoring cascades kategori -> ilap -> jenis -> sub jenis; Reset must
    put every one of them back, not just the first."""
    sc = "filter_monitoring_reset"
    page.goto(f"{H.BASE_URL}/monitoring-penyampaian-data/", wait_until="domcontentloaded")
    if not page.locator("#btn-reset-filter").count():
        rep.info(sc, "no reset button", "skipped")
        return
    page.wait_for_timeout(1200)
    page.evaluate(
        """() => {
            const f = document.querySelector('#filter-form');
            f.querySelectorAll('select').forEach(s => {
                const o = [...s.options].find(o => o.value);
                if (o) { s.value = o.value; s.dispatchEvent(new Event('change', {bubbles: true})); }
            });
        }""")
    page.wait_for_timeout(1500)
    with H.collect_pageerrors(page) as js_errors:
        page.click("#btn-reset-filter")
        page.wait_for_timeout(2000)
    leftover = page.evaluate(
        """() => [...document.querySelectorAll('#filter-form select')]
                 .filter(s => s.value).map(s => s.name || s.id)""")
    if leftover:
        rep.fail(sc, "reset left filters applied", ", ".join(leftover))
    else:
        rep.ok(sc, "reset cleared every filter")
    rep.fail(sc, "uncaught JS on reset", "; ".join(js_errors[:2])) if js_errors else \
        rep.ok(sc, "no uncaught JS on reset")


# --------------------------------------------------------------------------- #
# Full-page form
# --------------------------------------------------------------------------- #
def profil_form_rejection(page, rep):
    """ProfilView re-renders on error. The name fields the user already typed
    must survive, and the password error must be shown."""
    sc = "pages_profil"
    # Scope everything to #profile-form: the navbar renders a tiket-search form
    # and a logout form BEFORE the page content, so a bare `form` selector picks
    # the wrong one and silently tests nothing.
    FORM = "#profile-form"
    page.goto(f"{H.BASE_URL}/profil/", wait_until="domcontentloaded")
    if not page.locator(FORM).count():
        rep.info(sc, "no #profile-form on profil page", "skipped")
        return

    marker = "E2E Profil"
    page.fill(f'{FORM} [name="first_name"]', marker)
    # Mismatched password confirmation -> guaranteed server-side rejection,
    # and (critically) it must NOT change the password.
    for name, value in (("old_password", "PwTest12345!"),
                        ("new_password1", "AnotherPass123!"),
                        ("new_password2", "MismatchPass123!")):
        if page.locator(f'{FORM} [name="{name}"]').count():
            page.fill(f'{FORM} [name="{name}"]', value)

    with H.collect_pageerrors(page) as js_errors:
        page.evaluate(
            """(sel) => {
                const f = document.querySelector(sel);
                f.setAttribute('novalidate', 'novalidate');
                const btn = f.querySelector('button[type=submit], input[type=submit]');
                if (btn) { btn.removeAttribute('disabled'); btn.click(); }
                else f.submit();
            }""", FORM)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1800)

    errs = page.locator(
        f"{FORM} .text-danger, {FORM} .invalid-feedback, {FORM} ul.errorlist, .alert-danger").count()
    rep.ok(sc, "password mismatch rejected", f"{errs} error nodes") if errs else \
        rep.fail(sc, "password mismatch not reported",
                 "form re-rendered without any visible error")

    kept = (page.input_value(f'{FORM} [name="first_name"]')
            if page.locator(f'{FORM} [name="first_name"]').count() else None)
    if kept == marker:
        rep.ok(sc, "typed name preserved across rejection")
    else:
        rep.fail(sc, "typed name lost on rejection", f"{marker!r} -> {kept!r}")
        rep.bug("profil: a rejected password change discards the name fields",
                "MEDIUM",
                f"After the password confirmation mismatch was rejected, first_name came "
                f"back as {kept!r} instead of the submitted {marker!r}.")

    # The login must still work -- i.e. the rejected submit did not change it.
    page.goto(f"{H.BASE_URL}/accounts/login/")
    try:
        H.login(page)
        rep.ok(sc, "password unchanged by rejected submit")
    except Exception:
        rep.fail(sc, "password CHANGED by a rejected submit", "cannot log back in")
        rep.bug("profil: a rejected profile submit still changed the password",
                "HIGH",
                "The password change was applied even though the form was rejected for a "
                "confirmation mismatch; the original password no longer works.")

    rep.fail(sc, "uncaught JS on profil", "; ".join(js_errors[:2])) if js_errors else \
        rep.ok(sc, "no uncaught JS on profil")


# --------------------------------------------------------------------------- #
def run(page, rep):
    H.login(page)

    for sc, slug in FILTER_PAGES:
        try:
            filter_form_applies(page, rep, sc, slug)
        except Exception as e:
            H.shot(page, f"{sc}_EXCEPTION")
            rep.fail(sc, "exception", str(e))

    for fn in (filter_reset_restores, profil_form_rejection,
               tiket_cancel_modals, tiket_workflow_modals):
        try:
            fn(page, rep)
        except Exception as e:
            H.shot(page, f"{fn.__name__}_EXCEPTION")
            rep.fail(fn.__name__, "exception", str(e))


if __name__ == "__main__":
    rep = H.Reporter()
    with H.browser_page(headless=os.environ.get("E2E_HEADFUL") != "1") as page:
        run(page, rep)
    rep.write()
