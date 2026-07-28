"""
Form *interaction* coverage -- "does the form still WORK?" -- as opposed to the
input-validation coverage in test_form_validation.py ("does it reject bad data?").

Motivation: the Tanda Terima "Tambah" modal shipped a bug where a server-side
validation error re-rendered the form via `$('#modalBody').html(response.html)`
without re-running its initialiser. The markup came back, but every listener
bound to the old DOM died with it: the Lingkup dropdown stopped toggling, the
ILAP field stayed visible under "Regional", and previously-shown field errors
never cleared. Nothing in the suite caught it, because every existing test
submits a *valid* form and never looks at the form again afterwards.

That failure mode is generic to every AJAX CRUD modal in this app (they all
share the `#crudModal` + `.html(response.html)` pattern), so this module sweeps
all of them and asserts the invariants that bug violated:

  A. the POST does not 5xx
  B. the modal stays open and the form is re-rendered
  C. field errors are actually displayed
  D. flatpickr / select2 enhancements survive the re-render
  E. values the user already typed are preserved
  F. page-specific dynamic behaviour (dependent dropdowns, info panels) still
     responds AFTER the re-render, not just on first open
  G. the interaction raises no uncaught JS exception

Both Tambah and Edit are driven, because their form action comes from separate
view methods and can break independently.

Plus a deep, dedicated scenario for the Tanda Terima create modal covering the
scope switching, the submit-button gating and the stale-error clearing.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H


# --------------------------------------------------------------------------- #
# Generic modal driving
# --------------------------------------------------------------------------- #
def _close_modal(page):
    try:
        page.evaluate(
            """() => {
                const m = document.getElementById('crudModal');
                if (m) {
                    if (window.bootstrap) { const i = bootstrap.Modal.getInstance(m); if (i) i.hide(); }
                    m.classList.remove('show'); m.style.display = 'none';
                }
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = ''; document.body.style.paddingRight = '';
            }"""
        )
    except Exception:
        pass


def _open_create(page, slug):
    page.goto(f"{H.BASE_URL}/{slug}/", wait_until="domcontentloaded", timeout=25000)
    page.wait_for_selector('[data-action="create"]', timeout=12000)
    _close_modal(page)
    page.click('[data-action="create"]')
    page.wait_for_selector("#crudModal form", timeout=12000)
    page.wait_for_timeout(900)   # let select2/flatpickr enhancers run


def _open_edit(page, slug):
    """Open the first row's Edit modal. Returns False if the table has no rows."""
    page.goto(f"{H.BASE_URL}/{slug}/", wait_until="domcontentloaded", timeout=25000)
    _close_modal(page)
    try:
        page.wait_for_selector('[data-action="edit"]', timeout=12000)
    except Exception:
        return False
    page.locator('[data-action="edit"]').first.click()
    page.wait_for_selector("#crudModal form", timeout=12000)
    page.wait_for_timeout(900)
    return True


# Snapshot of everything the re-render is allowed to keep intact.
_SNAPSHOT = """() => {
    const root = document.querySelector('#crudModal');
    if (!root) return null;
    const inputs = [...root.querySelectorAll('input')];
    const selects = [...root.querySelectorAll('select')];
    return {
        hasForm:   !!root.querySelector('form'),
        selects:   selects.length,
        select2:   selects.filter(s => s.classList.contains('select2-hidden-accessible')).length,
        dates:     inputs.filter(i => i.type === 'date' || i._flatpickr).length,
        flatpickr: inputs.filter(i => !!i._flatpickr).length,
        errors:    root.querySelectorAll('.text-danger, .invalid-feedback, .alert-danger, ul.errorlist').length,
    };
}"""


def _marker_field(page):
    """Name of the first editable free-text field, used for the value-preservation
    check. Skips csrf, readonly/auto fields and flatpickr's unnamed alt inputs."""
    return page.evaluate(
        """() => {
            const f = document.querySelector('#crudModal form');
            const el = [...f.querySelectorAll('input[type=text], textarea')].find(e =>
                e.name && e.name !== 'csrfmiddlewaretoken' &&
                !e.readOnly && !e.disabled && e.offsetParent !== null);
            return el ? el.name : null;
        }"""
    )


def _force_invalid_submit(page):
    """Submit the modal form so the SERVER rejects it.

    HTML5 constraint validation would stop the submit event before the page's
    jQuery `$(document).on('submit', '#crudModal form')` handler ever runs, so
    an empty form never reaches the server through the UI. Strip `required` and
    set `novalidate` to push an empty payload through the real AJAX path -- the
    same round-trip a user hits when they violate a server-only rule."""
    page.evaluate(
        """() => {
            const f = document.querySelector('#crudModal form');
            f.setAttribute('novalidate', 'novalidate');
            f.querySelectorAll('[required]').forEach(e => e.removeAttribute('required'));
            if (window.jQuery) jQuery(f).trigger('submit');
            else f.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
        }"""
    )
    page.wait_for_timeout(2600)


def _force_rejected_edit_submit(page):
    """Submit an EDIT form with a payload the server is guaranteed to reject.

    Unlike the create sweep this must never risk a *successful* save, because
    that would overwrite a real row. Blanking fields could legitimately validate
    on an all-optional form; overflowing every free-text field past its
    max_length cannot, and neither can a select value that matches no choice.
    Returns False only if the form offers neither, in which case the caller
    skips rather than gamble on a destructive save."""
    ok = page.evaluate(
        """() => {
            const f = document.querySelector('#crudModal form');
            const text = [...f.querySelectorAll('input[type=text], textarea')]
                .filter(e => e.name && e.name !== 'csrfmiddlewaretoken' && !e.disabled);
            let poisoned = false;
            if (text.length) {
                // Assign directly: the maxlength attribute only caps typing, so
                // this is what reaches the server and trips the model's max_length.
                text.forEach(e => { e.value = 'E2E'.repeat(120); });
                poisoned = true;
            } else {
                // Select/date-only form: inject a choice that cannot exist, which
                // ModelChoiceField always rejects with "Select a valid choice".
                const sel = [...f.querySelectorAll('select')]
                    .find(e => e.name && !e.disabled);
                if (sel) {
                    const o = document.createElement('option');
                    o.value = '__e2e_invalid__';
                    o.textContent = '__e2e_invalid__';
                    sel.appendChild(o);
                    sel.value = '__e2e_invalid__';
                    poisoned = true;
                }
            }
            if (!poisoned) return false;
            f.setAttribute('novalidate', 'novalidate');
            if (window.jQuery) jQuery(f).trigger('submit');
            else f.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
            return true;
        }"""
    )
    if ok:
        page.wait_for_timeout(2600)
    return ok


def edit_form_reaches_server(page, rep, sc, slug):
    """The Edit modal must POST to a real URL and come back with field errors.

    Split out from the create sweep because a wrong `form_action` breaks create
    and edit independently -- they are built from separate view methods."""
    sc = f"{sc}_edit"
    if not _open_edit(page, slug):
        rep.info(sc, "no rows to edit", "skipped")
        return

    with H.collect_requests(page, lambda u: True) as responses:
        submitted = _force_rejected_edit_submit(page)
    if not submitted:
        rep.info(sc, "no field can be safely poisoned",
                 "skipped to avoid a destructive save")
        _close_modal(page)
        return

    posts = [r for r in responses if r[0] == "POST"]
    if not posts:
        rep.fail(sc, "edit form never POSTed")
    elif posts[0][2] >= 400:
        action = page.evaluate(
            """() => { const f = document.querySelector('#crudModal form');
                       return f ? f.getAttribute('action') : null; }""")
        rep.fail(sc, f"edit submit HTTP {posts[0][2]}", posts[0][1])
        rep.bug(f"{slug}: the Edit form posts to a broken URL (HTTP {posts[0][2]})",
                "HIGH",
                f"POST {posts[0][1]} responded {posts[0][2]}, so edits can never be "
                f"saved. The form's action attribute is {action!r}.")
        H.shot(page, f"{sc}_broken")
    else:
        rep.ok(sc, "edit submit reached server", f"{posts[0][2]}")
        errs = page.evaluate(
            """() => document.querySelectorAll(
                '#crudModal .text-danger, #crudModal .invalid-feedback, #crudModal ul.errorlist').length""")
        rep.ok(sc, "edit errors displayed", f"{errs} error nodes") if errs else \
            rep.fail(sc, "edit rejected without visible errors")
    _close_modal(page)


def form_survives_validation_error(page, rep, sc, slug, probe=None):
    """A -> G for one CRUD modal."""
    _open_create(page, slug)

    before = page.evaluate(_SNAPSHOT)
    if not before or not before["hasForm"]:
        rep.fail(sc, "open create modal", "no form rendered")
        return

    # Dynamic behaviour must work on FIRST open (baseline for F). A probe that
    # reports SKIP found no data to drive the control with and proves nothing.
    probe_usable = True
    if probe:
        status, detail = probe(page)
        if status == "skip":
            probe_usable = False
            rep.info(sc, "dynamic behaviour not probeable", detail)
        elif status == "ok":
            rep.ok(sc, "dynamic behaviour on open", detail)
        else:
            probe_usable = False
            rep.fail(sc, "dynamic behaviour broken on open", detail)
            rep.bug(f"{slug}: a dependent control does not respond even on a fresh form",
                    "MEDIUM",
                    f"On first open, before any submit, the form's dynamic behaviour is "
                    f"already broken: {detail}. Check the browser console/network tab for "
                    f"a failing AJAX call behind this control.")
            H.shot(page, f"{sc}_dynamic_broken_on_open")

    # maxlength silently truncates as we type, so the expected value is whatever
    # actually landed in the field -- not the literal we asked for.
    marker_name = _marker_field(page)
    marker = None
    if marker_name:
        page.fill(f'#crudModal [name="{marker_name}"]', "E2EMARK")
        marker = page.input_value(f'#crudModal [name="{marker_name}"]')

    with H.collect_pageerrors(page) as js_errors, \
            H.collect_requests(page, lambda u: True) as responses:
        _force_invalid_submit(page)

    posts = [r for r in responses if r[0] == "POST"]
    server_error = [r for r in posts if r[2] >= 500]

    # A. no 5xx
    if server_error:
        # The raw action attribute is the usual culprit (a relative or
        # slash-less URL), so report it rather than just the resolved URL.
        action = page.evaluate(
            """() => { const f = document.querySelector('#crudModal form');
                       return f ? f.getAttribute('action') : null; }""")
        rep.fail(sc, "invalid submit 5xx", f"{server_error[0][2]} {server_error[0][1]}")
        rep.bug(f"{slug}: submitting the form returns HTTP {server_error[0][2]}",
                "HIGH",
                f"POST {server_error[0][1]} responded {server_error[0][2]} instead of "
                f"re-rendering the form with field errors, so the user only sees a "
                f"generic 'Terjadi kesalahan' toast and cannot discover what is wrong. "
                f"The form's action attribute is {action!r}.")
        H.shot(page, f"{sc}_5xx")
        _close_modal(page)
        return
    if not posts:
        rep.fail(sc, "invalid submit", "form never POSTed")
        _close_modal(page)
        return
    rep.ok(sc, "invalid submit reached server", f"{posts[0][2]}")

    after = page.evaluate(_SNAPSHOT)

    # B. modal stays open, form re-rendered
    still_open = page.locator("#crudModal.show").count() > 0
    if still_open and after and after["hasForm"]:
        rep.ok(sc, "modal stays open with form")
    else:
        rep.fail(sc, "modal lost after invalid submit",
                 f"open={still_open} hasForm={after and after['hasForm']}")

    # C. errors displayed
    if after and after["errors"] > 0:
        rep.ok(sc, "field errors displayed", f"{after['errors']} error nodes")
    else:
        rep.fail(sc, "no field errors displayed",
                 "server rejected the submit but the form shows no error text")
        rep.bug(f"{slug}: rejected submit renders no visible error",
                "MEDIUM",
                "The POST was rejected but the re-rendered form displays no error "
                "message, leaving the user with no idea which field is wrong.")

    # D. enhancements survive
    if after:
        if before["flatpickr"] and after["flatpickr"] < before["flatpickr"]:
            rep.fail(sc, "flatpickr lost on re-render",
                     f"{before['flatpickr']} -> {after['flatpickr']}")
            rep.bug(f"{slug}: date pickers stop working after a validation error",
                    "MEDIUM",
                    "The re-rendered form's date inputs are no longer flatpickr-enhanced, "
                    "so the calendar no longer opens and the field cannot be corrected.")
        elif before["flatpickr"]:
            rep.ok(sc, "flatpickr survives re-render", f"{after['flatpickr']} pickers")

        if before["select2"] and after["select2"] < before["select2"]:
            rep.fail(sc, "select2 lost on re-render",
                     f"{before['select2']} -> {after['select2']}")
            rep.bug(f"{slug}: searchable dropdowns degrade after a validation error",
                    "MEDIUM",
                    "select2 is not re-applied to the re-rendered form, so the "
                    "search-as-you-type dropdown reverts to a plain <select>.")
        elif before["select2"]:
            rep.ok(sc, "select2 survives re-render", f"{after['select2']} widgets")

    # E. typed values preserved
    if marker_name and marker:
        kept = page.evaluate(
            """(n) => {
                const el = document.querySelector(`#crudModal [name="${n}"]`);
                return el ? el.value : null;
            }""", marker_name)
        if kept == marker:
            rep.ok(sc, "typed value preserved", f"{marker_name}={kept}")
        else:
            rep.fail(sc, "typed value lost on re-render",
                     f"{marker_name}: {marker!r} -> {kept!r}")
            rep.bug(f"{slug}: user input is discarded when the form is rejected",
                    "MEDIUM",
                    f"After a rejected submit the field '{marker_name}' came back as "
                    f"{kept!r} instead of the submitted {marker!r}, forcing the user to "
                    f"retype the whole form.")

    # F. dynamic behaviour still alive AFTER the re-render (the tanda terima bug).
    # Only meaningful if the same probe demonstrably worked before the submit.
    if probe and probe_usable:
        status, detail = probe(page)
        if status == "ok":
            rep.ok(sc, "dynamic behaviour survives re-render", detail)
        elif status == "skip":
            rep.info(sc, "dynamic behaviour not probeable after re-render", detail)
        else:
            rep.fail(sc, "dynamic behaviour DEAD after re-render", detail)
            rep.bug(f"{slug}: dependent fields stop responding after a validation error",
                    "HIGH",
                    "The modal re-renders its HTML without re-running the form's "
                    "initialiser, so every listener bound to the previous markup is "
                    f"lost. {detail}")
            H.shot(page, f"{sc}_dynamic_dead")

    # G. no uncaught JS
    if js_errors:
        rep.fail(sc, "uncaught JS during submit", "; ".join(js_errors[:2]))
    else:
        rep.ok(sc, "no uncaught JS during submit")

    _close_modal(page)


# --------------------------------------------------------------------------- #
# Page-specific dynamic probes -> ("ok" | "fail" | "skip", detail)
#
# "skip" means the control had no data to drive it (an empty reference table on
# this dev DB), which says nothing about whether the listener is alive -- it
# must never be reported as a broken form.
# --------------------------------------------------------------------------- #
def _pick_option(page, select_sel, index=1):
    """Select the Nth real option and fire the events both native and jQuery /
    select2 listeners need. Returns the chosen value ('' if none available)."""
    return page.evaluate(
        """([sel, idx]) => {
            const s = document.querySelector(sel);
            if (!s) return '';
            const opts = [...s.options].filter(o => o.value);
            if (!opts.length) return '';
            const o = opts[Math.min(idx, opts.length - 1)];
            s.value = o.value;
            s.dispatchEvent(new Event('change', {bubbles: true}));
            if (window.jQuery) jQuery(s).trigger('change');
            return o.value;
        }""", [select_sel, index])


def probe_ilap(page):
    """Changing Kategori ILAP must re-fetch and fill the auto id_ilap."""
    page.evaluate("""() => { const e=document.querySelector('#id_id_ilap'); if(e) e.value=''; }""")
    chosen = _pick_option(page, "#id_id_kategori", 1)
    if not chosen:
        return "skip", "no kategori option to select"
    try:
        page.wait_for_function(
            "() => { const e=document.querySelector('#id_id_ilap'); return e && e.value.trim() !== ''; }",
            timeout=6000)
    except Exception:
        return "fail", "kategori change did not populate id_ilap (next-id AJAX not wired)"
    return "ok", f"kategori={chosen} -> id_ilap auto-filled"


def probe_ilap_kpp_toggle(page):
    """Kategori Wilayah 'Regional' must reveal the KPP checkbox list."""
    idx = page.evaluate(
        """() => {
            const s = document.querySelector('#id_id_kategori_wilayah');
            if (!s) return -1;
            const opts = [...s.options].filter(o => o.value);
            return opts.findIndex(o => o.text.toLowerCase().includes('regional'));
        }""")
    if idx < 0:
        return "skip", "no 'Regional' option in kategori wilayah"
    _pick_option(page, "#id_id_kategori_wilayah", idx)
    page.wait_for_timeout(500)
    shown = page.evaluate(
        """() => { const d=document.querySelector('#div_id_kpp_list');
                   return d ? getComputedStyle(d).display !== 'none' : null; }""")
    if shown is None:
        return "fail", "#div_id_kpp_list missing"
    return ("ok" if shown else "fail"), f"regional -> kpp list visible={shown}"


def probe_pic(page):
    """Selecting a Sub Jenis Data must populate the ILAP info panel via AJAX."""
    chosen = _pick_option(page, "#id_id_sub_jenis_data_ilap", 1)
    if not chosen:
        return "skip", "no sub jenis data option"
    try:
        page.wait_for_function(
            """() => { const d=document.querySelector('#div_id_ilap_info');
                       return d && getComputedStyle(d).display !== 'none'; }""",
            timeout=6000)
    except Exception:
        return "fail", "sub jenis change did not reveal the ILAP info panel"
    return "ok", f"sub_jenis={chosen} -> info panel shown"


def probe_backup(page):
    """Selecting a Tiket must populate the tiket info panel."""
    chosen = _pick_option(page, "#id_id_tiket", 1)
    if not chosen:
        # BackupDataForm scopes id_tiket to tikets the logged-in user is an
        # active PIC P3DE for, with status < 4; pw_tester often matches none.
        return "skip", "no tiket option available for this user (PIC-scoped queryset)"
    try:
        page.wait_for_function(
            """() => { const d=document.querySelector('#div_id_tiket_info');
                       return d && getComputedStyle(d).display !== 'none'; }""",
            timeout=6000)
    except Exception:
        return "fail", "tiket change did not reveal the tiket info panel"
    return "ok", f"tiket={chosen} -> info panel shown"


def probe_jenis_data_ilap(page):
    """The wizard's ILAP select drives the downstream jenis-data controls."""
    chosen = _pick_option(page, "#id_id_ilap", 1)
    if not chosen:
        chosen = _pick_option(page, "#crudModal select", 1)
    if not chosen:
        return "skip", "no ILAP option to select"
    page.wait_for_timeout(900)
    live = page.evaluate(
        """() => {
            const f = document.querySelector('#crudModal form');
            return [...f.querySelectorAll('select, input[type=checkbox]')]
                .filter(e => e.offsetParent !== null).length;
        }""")
    return ("ok" if live > 0 else "fail"), f"ilap={chosen}, {live} live wizard controls"


# --------------------------------------------------------------------------- #
# Deep scenario: the Tanda Terima create modal (regression for the fixed bug)
# --------------------------------------------------------------------------- #
TT = "#crudModal"


def _tt_state(page):
    return page.evaluate(
        """() => {
            const q = s => document.querySelector(s);
            const vis = s => { const e = q(s); return !!e && getComputedStyle(e).display !== 'none'; };
            const simpan = q('#crudModal button[type="submit"]');
            const tidak  = q('#tidak-terbit-tt-btn');
            return {
                kanwilVisible: vis('#scope-kanwil-wrapper'),
                ilapVisible:   vis('#scope-ilap-wrapper'),
                simpanDisabled: simpan ? simpan.disabled : null,
                tidakDisabled:  tidak ? tidak.disabled : null,
                rows: document.querySelectorAll('#tiket-table-body tr[data-tiket-row], #tiket-table-body input[type=checkbox]').length,
                lingkup: (q('#id_lingkup') || {}).value,
            };
        }""")


def _tt_set_lingkup(page, value):
    page.evaluate(
        """(v) => {
            const s = document.querySelector('#id_lingkup');
            s.value = v;
            s.dispatchEvent(new Event('change', {bubbles: true}));
            if (window.jQuery) jQuery(s).trigger('change');
        }""", value)
    page.wait_for_timeout(900)


def tanda_terima_scope_and_gating(page, rep):
    """The exact regression: scope switching, button gating and stale errors
    must all still work after the server rejects a submit."""
    sc = "form_tanda_terima_gating"
    _open_create(page, "tanda-terima-data")

    st = _tt_state(page)
    # Default lingkup is regional -> Kanwil shown, ILAP hidden.
    if st["kanwilVisible"] and not st["ilapVisible"]:
        rep.ok(sc, "regional shows Kanwil, hides ILAP")
    else:
        rep.fail(sc, "wrong scope fields on open",
                 f"kanwil={st['kanwilVisible']} ilap={st['ilapVisible']}")

    # Gating: nothing filled -> both action buttons disabled.
    if st["simpanDisabled"] and st["tidakDisabled"]:
        rep.ok(sc, "Simpan + Tidak Diterbitkan disabled on empty form")
    else:
        rep.fail(sc, "action buttons enabled on empty form",
                 f"simpan_disabled={st['simpanDisabled']} tidak_disabled={st['tidakDisabled']}")

    # Lingkup switching swaps the scope field.
    _tt_set_lingkup(page, "nasional")
    st = _tt_state(page)
    if st["ilapVisible"] and not st["kanwilVisible"]:
        rep.ok(sc, "nasional shows ILAP, hides Kanwil")
    else:
        rep.fail(sc, "lingkup switch did not swap scope field",
                 f"kanwil={st['kanwilVisible']} ilap={st['ilapVisible']}")
    _tt_set_lingkup(page, "regional")

    # --- force the server to reject, then re-test EVERYTHING above ---------- #
    H.fill_date(page, "#crudModal #id_tanggal_tanda_terima", H.date_ago(24))
    with H.collect_pageerrors(page) as js_errors:
        _force_invalid_submit(page)

    if not page.locator("#crudModal.show").count():
        rep.fail(sc, "modal closed on rejected submit")
        return
    errors_now = page.locator("#crudModal .text-danger").count()
    rep.ok(sc, "server rejected submit", f"{errors_now} error nodes") if errors_now else \
        rep.fail(sc, "rejected submit showed no error")

    st = _tt_state(page)
    if st["kanwilVisible"] and not st["ilapVisible"]:
        rep.ok(sc, "scope fields correct AFTER error")
    else:
        rep.fail(sc, "ILAP field wrongly visible after error",
                 f"kanwil={st['kanwilVisible']} ilap={st['ilapVisible']}")

    _tt_set_lingkup(page, "nasional")
    st = _tt_state(page)
    if st["ilapVisible"] and not st["kanwilVisible"]:
        rep.ok(sc, "lingkup dropdown still live AFTER error")
    else:
        rep.fail(sc, "lingkup dropdown DEAD after error",
                 "changing Lingkup no longer swaps the scope field")
        rep.bug("Tanda Terima modal goes inert after a validation error",
                "HIGH",
                "The AJAX error branch replaces the modal HTML without re-running "
                "initTandaTerimaForm(), so the Lingkup dropdown, the tiket loader and "
                "the button gating all stop responding.")
        H.shot(page, f"{sc}_dead")
    _tt_set_lingkup(page, "regional")

    # Choosing a Kanwil must (a) clear the stale 'Kanwil harus dipilih' error
    # and (b) load the tiket list.
    chosen = _pick_option(page, "#id_id_kanwil", 1)
    if chosen:
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('#tiket-table-body input[type=checkbox]').length > 0",
                timeout=8000)
            rep.ok(sc, "kanwil choice loads tikets AFTER error")
        except Exception:
            rep.fail(sc, "kanwil choice did not load tikets after error",
                     "tiket table stayed empty")
        stale = page.evaluate(
            """() => {
                const w = document.querySelector('#scope-kanwil-wrapper');
                return w ? w.querySelectorAll('.text-danger').length : -1;
            }""")
        rep.ok(sc, "stale Kanwil error cleared") if stale == 0 else rep.fail(
            sc, "stale Kanwil error persists", f"{stale} error node(s) with a Kanwil selected")
    else:
        rep.info(sc, "no Kanwil option available", "skipped tiket-load assertions")

    # Ticking a tiket must enable both buttons.
    ticked = page.evaluate(
        """() => {
            const cb = document.querySelector('#tiket-table-body input[type=checkbox]');
            if (!cb) return false;
            cb.click();
            return true;
        }""")
    if ticked:
        page.wait_for_timeout(600)
        st = _tt_state(page)
        if st["simpanDisabled"] is False and st["tidakDisabled"] is False:
            rep.ok(sc, "buttons enable once a tiket is selected")
        else:
            rep.fail(sc, "buttons stay disabled with a complete form",
                     f"simpan_disabled={st['simpanDisabled']} tidak_disabled={st['tidakDisabled']}")
    else:
        rep.info(sc, "no tiket row to tick", "skipped enable assertion")

    if js_errors:
        rep.fail(sc, "uncaught JS in tanda terima modal", "; ".join(js_errors[:2]))
    else:
        rep.ok(sc, "no uncaught JS in tanda terima modal")

    H.shot(page, sc)
    _close_modal(page)


# --------------------------------------------------------------------------- #
PAGES = [
    # (scenario, url slug, dynamic probe)
    ("form_kategori_wilayah",      "kategori-wilayah",        None),
    ("form_jenis_tabel",           "jenis-tabel",             None),
    ("form_status_data",           "status-data",             None),
    ("form_status_penelitian",     "status-penelitian",       None),
    ("form_bentuk_data",           "bentuk-data",             None),
    ("form_cara_penyampaian",      "cara-penyampaian",        None),
    ("form_media_backup",          "media-backup",            None),
    ("form_kanwil",                "kanwil",                  None),
    ("form_kpp",                   "kpp",                     None),
    ("form_kategori_ilap",         "kategori-ilap",           None),
    ("form_dasar_hukum",           "dasar-hukum",             None),
    ("form_periode_pengiriman",    "periode-pengiriman",      None),
    ("form_ilap",                  "ilap",                    probe_ilap),
    ("form_jenis_data_ilap",       "jenis-data-ilap",         probe_jenis_data_ilap),
    ("form_klasifikasi_jenis_data", "klasifikasi-jenis-data",  None),
    ("form_periode_jenis_data",    "periode-jenis-data",      None),
    ("form_jenis_prioritas_data",  "jenis-prioritas-data",    None),
    ("form_nama_tabel",            "nama-tabel",              None),
    ("form_pic_p3de",              "pic-p3de",                probe_pic),
    ("form_pic_pide",              "pic-pide",                probe_pic),
    ("form_pic_pmde",              "pic-pmde",                probe_pic),
    ("form_durasi_pide",           "durasi-jatuh-tempo-pide", None),
    ("form_durasi_pmde",           "durasi-jatuh-tempo-pmde", None),
    ("form_docx_template",         "docx-template",           None),
    ("form_sequence_tanda_terima", "sequence-tanda-terima",   None),
    ("form_backup_data",           "backup-data",             probe_backup),
    ("form_tanda_terima_data",     "tanda-terima-data",       None),
]


def run(page, rep):
    H.login(page)
    for sc, slug, probe in PAGES:
        try:
            form_survives_validation_error(page, rep, sc, slug, probe)
        except Exception as e:
            H.shot(page, f"{sc}_EXCEPTION")
            rep.fail(sc, "exception", str(e))
            _close_modal(page)
        try:
            edit_form_reaches_server(page, rep, sc, slug)
        except Exception as e:
            H.shot(page, f"{sc}_edit_EXCEPTION")
            rep.fail(f"{sc}_edit", "exception", str(e))
            _close_modal(page)

    # ILAP has a second independent dynamic control worth its own check.
    try:
        _open_create(page, "ilap")
        status, detail = probe_ilap_kpp_toggle(page)
        if status == "ok":
            rep.ok("form_ilap", "kpp list toggles with kategori wilayah", detail)
        elif status == "skip":
            rep.info("form_ilap", "kpp toggle not probeable", detail)
        else:
            rep.fail("form_ilap", "kpp list toggle broken", detail)
        _close_modal(page)
    except Exception as e:
        rep.fail("form_ilap", "kpp toggle exception", str(e))
        _close_modal(page)

    try:
        tanda_terima_scope_and_gating(page, rep)
    except Exception as e:
        H.shot(page, "form_tanda_terima_gating_EXCEPTION")
        rep.fail("form_tanda_terima_gating", "exception", str(e))
        _close_modal(page)


if __name__ == "__main__":
    rep = H.Reporter()
    with H.browser_page(headless=os.environ.get("E2E_HEADFUL") != "1") as page:
        run(page, rep)
    rep.write()
