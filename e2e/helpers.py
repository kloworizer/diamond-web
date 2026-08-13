"""
Shared Playwright helpers for driving the DIAMOND tiket workflow through the
real UI (system Chrome, no chromium download).

Config comes from setup_test_data.py output:
  user=pw_tester / pass=PwTest12345! / ILAP id=1 / sub jenis AS0010101

All scenario scripts import from here. A single Reporter aggregates PASS/FAIL
and BUG findings into e2e/report/RESULTS.md (+ .json) and saves screenshots.
"""
from __future__ import annotations

import json
import os
import re
import datetime as dt
from contextlib import contextmanager

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:8000")
USER = "pw_tester"
PASS = "PwTest12345!"
ILAP_VALUE = "1"          # ILAP primary key (select value)
SUB_JENIS = "AS0010101"   # sub jenis data id used to pick the periode_data option

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_DIR = os.path.join(HERE, "report")
SHOTS_DIR = os.path.join(REPORT_DIR, "screenshots")
os.makedirs(SHOTS_DIR, exist_ok=True)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
class Reporter:
    def __init__(self):
        self.results = []   # (scenario, step, status, detail)
        self.bugs = []      # (title, severity, detail)

    def ok(self, scenario, step, detail=""):
        self.results.append((scenario, step, "PASS", detail))
        print(f"  [PASS] {scenario} :: {step} {('- ' + detail) if detail else ''}")

    def fail(self, scenario, step, detail=""):
        self.results.append((scenario, step, "FAIL", detail))
        print(f"  [FAIL] {scenario} :: {step} - {detail}")

    def info(self, scenario, step, detail=""):
        self.results.append((scenario, step, "INFO", detail))
        print(f"  [INFO] {scenario} :: {step} {('- ' + detail) if detail else ''}")

    def bug(self, title, severity, detail):
        self.bugs.append((title, severity, detail))
        print(f"  [BUG/{severity}] {title} - {detail}")

    def write(self):
        md = ["# DIAMOND Tiket Workflow — Playwright E2E Results", ""]
        md.append(f"_Generated: {dt.datetime.now():%Y-%m-%d %H:%M:%S}_")
        md.append("")
        n_pass = sum(1 for r in self.results if r[2] == "PASS")
        n_fail = sum(1 for r in self.results if r[2] == "FAIL")
        md.append(f"**Steps:** {n_pass} passed, {n_fail} failed. "
                  f"**Bugs found:** {len(self.bugs)}.")
        md.append("")
        md.append("## Bugs / Findings")
        md.append("")
        if self.bugs:
            for i, (title, sev, detail) in enumerate(self.bugs, 1):
                md.append(f"### {i}. [{sev}] {title}")
                md.append("")
                md.append(detail)
                md.append("")
        else:
            md.append("_None recorded._")
            md.append("")
        md.append("## Step log")
        md.append("")
        md.append("| Scenario | Step | Status | Detail |")
        md.append("|---|---|---|---|")
        for scn, step, status, detail in self.results:
            d = (detail or "").replace("|", "\\|").replace("\n", " ")
            md.append(f"| {scn} | {step} | {status} | {d} |")
        md.append("")
        with open(os.path.join(REPORT_DIR, "RESULTS.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        with open(os.path.join(REPORT_DIR, "results.json"), "w", encoding="utf-8") as f:
            json.dump({"results": self.results, "bugs": self.bugs}, f, indent=2)
        print(f"\nReport written to {os.path.join(REPORT_DIR, 'RESULTS.md')}")


# --------------------------------------------------------------------------- #
# Browser / session
# --------------------------------------------------------------------------- #
@contextmanager
def browser_page(headless=True):
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            # System Chrome isn't installed on this machine; fall back to the
            # Playwright-managed Chromium build.
            b = p.chromium.launch(headless=headless)
        ctx = b.new_context(viewport={"width": 1500, "height": 1000},
                            accept_downloads=True)
        ctx.set_default_timeout(15000)
        # Hide the Django Debug Toolbar overlay which otherwise intercepts clicks.
        ctx.add_init_script(
            """document.addEventListener('DOMContentLoaded', () => {
                const s = document.createElement('style');
                s.textContent = '#djDebug,#djDebugToolbar,#djDebugToolbarHandle{display:none!important;pointer-events:none!important;}';
                document.head.appendChild(s);
            });"""
        )
        page = ctx.new_page()
        # Surface console errors for debugging (not treated as failures).
        page.on("pageerror", lambda e: print(f"    (pageerror) {e}"))
        try:
            yield page
        finally:
            ctx.close()
            b.close()


@contextmanager
def collect_pageerrors(page):
    """Collect uncaught JS exceptions raised inside the block.

    browser_page() only *prints* pageerrors; a scenario that wants to assert
    "this interaction threw nothing" needs them as data. Yields a list that is
    appended to for the duration of the block.
    """
    errors = []
    handler = lambda e: errors.append(str(e))  # noqa: E731
    page.on("pageerror", handler)
    try:
        yield errors
    finally:
        page.remove_listener("pageerror", handler)


@contextmanager
def collect_requests(page, predicate=None):
    """Collect (method, url, status) for responses matching `predicate(url)`.

    Used to prove a single user interaction fires exactly one AJAX call --
    re-executing an AJAX-loaded <script> can silently double-bind listeners.
    """
    seen = []

    def handler(resp):
        if predicate is None or predicate(resp.url):
            seen.append((resp.request.method, resp.url, resp.status))

    page.on("response", handler)
    try:
        yield seen
    finally:
        page.remove_listener("response", handler)


def login(page, user=USER, password=PASS):
    """Log in as `user`, defaulting to the pw_tester account from setup_test_data.

    Scenarios that need a *different* account (e.g. to exercise per-user PIC
    scoping) pass one explicitly. Always log out first: the session cookie of a
    previous scenario would otherwise keep the old user signed in and the login
    form would never be shown.
    """
    # Drop any existing session cookie rather than GETting /accounts/logout/,
    # which Django 5 no longer allows.
    page.context.clear_cookies()
    page.goto(f"{BASE_URL}/accounts/login/")
    page.fill('input[name="username"]', user)
    page.fill('input[name="password"]', password)
    with page.expect_navigation():
        page.click('button[type="submit"], input[type="submit"]')
    assert "/accounts/login" not in page.url, f"login failed for {user}"


def shot(page, name):
    path = os.path.join(SHOTS_DIR, f"{name}.png")
    try:
        page.screenshot(path=path, full_page=True)
    except Exception:
        page.screenshot(path=path)
    return path


def fill_date(page, selector, value):
    """Set a date-only field's value (YYYY-MM-DD), flatpickr-aware.

    base.html globally enhances every <input type="date"> with flatpickr
    (altInput: true), which hides the real form field (type="hidden") and
    shows a separate friendly-format text input (with its own cloned
    `required` attribute) in its place. Playwright's actionability-gated
    .fill() can't reach the hidden element, and just poking the hidden
    input's raw .value leaves the visible altInput empty (still "required",
    still invalid). Go through flatpickr's own setDate() so both stay in
    sync, exactly like a real user interaction would.
    """
    page.eval_on_selector(
        selector,
        """(el, v) => {
            if (el._flatpickr) {
                el._flatpickr.setDate(v, true);
            } else {
                el.value = v;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }
        }""",
        value,
    )


# --------------------------------------------------------------------------- #
# Small utils
# --------------------------------------------------------------------------- #
def past_dt(days_ago=1, hour=9, minute=0):
    d = dt.datetime.now() - dt.timedelta(days=days_ago)
    d = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return d.strftime("%Y-%m-%dT%H:%M")


def hours_ago(h):
    """Timestamp `h` hours before now (always in the past), for datetime-local.

    Workflow dates must be ordered dip <= teliti <= nadine <= kirim <= rekam_pide
    <= transfer and all <= now, so scenarios pass DECREASING hour offsets."""
    d = (dt.datetime.now() - dt.timedelta(hours=h)).replace(second=0, microsecond=0)
    return d.strftime("%Y-%m-%dT%H:%M")


def date_ago(h):
    """Date-only (YYYY-MM-DD) string `h` hours before now, for <input type="date">."""
    return hours_ago(h)[:10]


def future_dt(days_ahead=3, hour=9, minute=0):
    d = dt.datetime.now() + dt.timedelta(days=days_ahead)
    d = d.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return d.strftime("%Y-%m-%dT%H:%M")


def future_date(days_ahead=3):
    """Date-only (YYYY-MM-DD) string `days_ahead` days in the future, for <input type="date">."""
    return future_dt(days_ahead)[:10]


def status_label(page):
    """Read the top status badge text on the tiket detail page."""
    try:
        el = page.locator(".breadcrumb-status-badge").first
        return el.inner_text().strip()
    except Exception:
        return ""


def dismiss_duplicate_modal(page):
    """Force-remove the non-blocking 'duplicate tiket' modal + backdrop.

    The modal is shown asynchronously by an AJAX check on periode/tahun change,
    so we forcibly hide it via JS (clicking is racy and the backdrop intercepts
    pointer events)."""
    try:
        page.evaluate(
            """() => {
                const m = document.getElementById('duplicateTiketModal');
                if (m) {
                    if (window.bootstrap) {
                        const inst = bootstrap.Modal.getInstance(m);
                        if (inst) inst.hide();
                    }
                    m.classList.remove('show');
                    m.style.display = 'none';
                    m.setAttribute('aria-hidden', 'true');
                }
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }"""
        )
    except Exception:
        pass


def clear_overlays(page):
    """Force-remove transient success/toast modals + stray backdrops that
    would otherwise intercept pointer events on the detail page."""
    try:
        page.evaluate(
            """() => {
                document.querySelectorAll('.modal.show').forEach(m => {
                    if (/^success-modal|^message/.test(m.id) || m.dataset.bsBackdrop === 'static') {
                        if (window.bootstrap) { const i = bootstrap.Modal.getInstance(m); if (i) i.hide(); }
                        m.classList.remove('show'); m.style.display='none'; m.remove();
                    }
                });
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow=''; document.body.style.paddingRight='';
            }"""
        )
    except Exception:
        pass


def force_close_modal(page, modal_id):
    """Hide a modal + its backdrop via JS regardless of how it got there.

    A server-rejected submit deliberately leaves its modal open; the next
    interaction then clicks into an intercepting backdrop. clear_overlays()
    only removes success/toast modals, so a rejection probe has to close its
    own modal explicitly."""
    try:
        page.evaluate(
            """(id) => {
                const m = document.getElementById(id);
                if (m) {
                    // dispose(), not hide(): stripping the classes mid-transition
                    // leaves bootstrap's _isShown set, and a later show() on the
                    // same element silently does nothing.
                    if (window.bootstrap) {
                        const i = bootstrap.Modal.getInstance(m);
                        if (i) i.dispose();
                    }
                    m.classList.remove('show'); m.style.display = 'none';
                    m.setAttribute('aria-hidden', 'true');
                }
                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = ''; document.body.style.paddingRight = '';
            }""",
            modal_id,
        )
    except Exception:
        pass


def toast_texts(page, kind="danger"):
    """Text of every currently rendered toast of `kind` (see base.html showToast).

    Several workflow modals (Identifikasi, Kirim ke PIDE, Special Request)
    report a server rejection *only* through a danger toast -- there is no
    inline error to look for -- and bootstrap removes the node ~5s after it is
    shown, so read this straight after the submit."""
    try:
        return page.eval_on_selector_all(
            f".toast.toast-{kind}",
            "els => els.map(e => (e.querySelector('.toast-message') || e).textContent.trim())",
        )
    except Exception:
        return []


def dismiss_toasts(page):
    """Remove every toast so the next probe can't read a stale message."""
    try:
        page.evaluate("() => document.querySelectorAll('.toast').forEach(t => t.remove())")
    except Exception:
        pass


def inline_error_texts(page, container_selector):
    """Text of the inline validation errors rendered inside a form container."""
    try:
        return page.eval_on_selector_all(
            f"{container_selector} .text-danger, {container_selector} .invalid-feedback, "
            f"{container_selector} .alert-danger, {container_selector} .errorlist",
            """els => els.map(e => e.textContent.trim())
                        .filter(t => t && !/^\\*$/.test(t))""",
        )
    except Exception:
        return []


def disable_client_validation(page, form_selector):
    """Set novalidate + strip `required` so a submit reaches the server.

    HTML5 constraint validation kills the submit event before any JS handler
    runs, so an intentionally-empty field never exercises the server-side rule
    it is meant to prove."""
    page.eval_on_selector(
        form_selector,
        """(f) => {
            f.setAttribute('novalidate', 'novalidate');
            f.querySelectorAll('[required]').forEach(el => el.removeAttribute('required'));
        }""",
    )


def probe_modal_rejection(page, container_selector, *, submit_selector=None,
                          modal_id=None, force=False, reload_after=True):
    """Submit a modal expected to be REJECTED and report what the server said.

    Returns (evidence, status) where `evidence` is the combined danger-toast +
    inline-error text and `status` is the tiket status badge re-read from the
    server afterwards. A rule that fired leaves evidence non-empty *and* the
    status unchanged -- assert both, because a modal that silently swallows
    the error also produces empty evidence.
    """
    dismiss_toasts(page)
    sel = submit_selector or f'{container_selector} button[type="submit"]'
    page.locator(sel).first.click(force=force)
    page.wait_for_timeout(1800)
    evidence = " ".join(toast_texts(page, "danger") + inline_error_texts(page, container_selector)).strip()
    if modal_id:
        force_close_modal(page, modal_id)
    dismiss_toasts(page)
    status = ""
    if reload_after:
        try:
            page.reload(wait_until="networkidle")
        except Exception:
            pass
        clear_overlays(page)
        status = status_label(page)
    return evidence, status


def check_rejected(rep, scenario, step, evidence, status, *, expect_status,
                   expect_text=None, bug=None):
    """Assert a rejection probe: an error was shown AND the state didn't move.

    `expect_text` is a substring of the rule's own message -- matching it is
    what makes this a test of *that rule* rather than of "something failed".
    `bug` is an optional (title, severity, detail) tuple recorded when the
    server accepted the invalid data.
    """
    advanced = expect_status.lower() not in (status or "").lower()
    matched = (expect_text is None) or (expect_text.lower() in evidence.lower())
    if evidence and not advanced and matched:
        rep.ok(scenario, step, evidence[:160] or status)
        return True
    if advanced:
        detail = f"accepted: status -> {status or '(unknown)'}"
    elif not evidence:
        detail = f"no error surfaced (status stayed {status})"
    else:
        detail = f"wrong error: {evidence[:160]}"
    rep.fail(scenario, step, detail)
    if bug and advanced:
        rep.bug(*bug)
    return False


def _select_first_real_option(page, select_id):
    """Select the first <option> that has a non-empty value and isn't a
    'tidak tersedia' placeholder. Returns the chosen visible text."""
    value = page.eval_on_selector(
        f"#{select_id}",
        """(sel) => {
            const o = [...sel.options].find(o => o.value &&
                !o.textContent.toLowerCase().includes('tidak tersedia'));
            return o ? o.value : '';
        }""",
    )
    if value:
        page.select_option(f"#{select_id}", value)
    return value


# --------------------------------------------------------------------------- #
# Rekam tiket (step 1) via the real form
# --------------------------------------------------------------------------- #
def select_ilap_periode(page, tahun):
    """Select ILAP -> periode_data (our sub jenis) -> periode -> tahun on the
    rekam form. Assumes page is already on /tiket/rekam/."""
    page.wait_for_selector("#id_ilap")
    # 1) ILAP -> triggers AJAX populate of periode_data
    page.select_option("#id_ilap", ILAP_VALUE)
    page.wait_for_function(
        """sj => {
            const s = document.getElementById('id_periode_data');
            return s && [...s.options].some(o => o.textContent.includes(sj));
        }""",
        arg=SUB_JENIS,
        timeout=15000,
    )
    # 2) periode_data option matching our sub jenis
    pd_value = page.eval_on_selector(
        "#id_periode_data",
        "(sel, sj) => { const o=[...sel.options].find(o=>o.textContent.includes(sj)); return o?o.value:''; }",
        SUB_JENIS,
    )
    assert pd_value, f"no periode_data option for {SUB_JENIS}"
    page.select_option("#id_periode_data", pd_value)
    # 3) periode dropdown now populated (Semester 1/2 for Semesteran); pick 1
    page.wait_for_function(
        "() => { const s=document.getElementById('id_periode'); return s && s.options.length>1; }"
    )
    page.select_option("#id_periode", "1")
    # 4) tahun (may trigger async duplicate-check modal)
    page.select_option("#id_tahun", tahun)
    page.wait_for_timeout(1300)
    dismiss_duplicate_modal(page)


def rekam_tiket(page, rep, scenario, *, tersedia=True, baris_diterima=1000,
                tahun="2026", backup=True):
    """Drive /tiket/rekam/ and return the new tiket detail URL.

    Returns (detail_url, nomor_tiket) or raises with a screenshot on failure.
    """
    page.goto(f"{BASE_URL}/tiket/rekam/")
    select_ilap_periode(page, tahun)

    # 5) status ketersediaan
    if tersedia:
        page.check("#status_tersedia")
        # bentuk & cara penyampaian (skip 'tidak tersedia' options)
        _select_first_real_option(page, "id_id_bentuk_data")
        _select_first_real_option(page, "id_id_cara_penyampaian")
        page.fill("#id_baris_diterima", str(baris_diterima))
        page.select_option("#id_satuan_data", "1")
        # tgl terima vertikal only if enabled (regional ILAP)
        if not page.is_disabled("#id_tgl_terima_vertikal"):
            fill_date(page, "#id_tgl_terima_vertikal", date_ago(52))
        fill_date(page, "#id_tgl_terima_dip", date_ago(48))
        if backup:
            page.check("#rekam-backup-checkbox")
            page.fill("#backup_lokasi_backup", r"D:\\Backup\\E2E")
            page.fill("#backup_nama_file", "e2e_backup.zip")
            _select_first_real_option(page, "backup_id_media_backup")
    else:
        page.check("#status_tidak_tersedia")
        page.wait_for_timeout(300)  # JS disables/sets fields
        page.fill("#id_alasan_ketidaktersediaan", "Data tidak tersedia (E2E test)")
        # tgl_terima_dip still required
        fill_date(page, "#id_tgl_terima_dip", date_ago(48))

    dismiss_duplicate_modal(page)

    # 6) confirm -> submit
    page.wait_for_timeout(300)
    dismiss_duplicate_modal(page)
    page.click("#btn-confirm-save")
    # endDateValidationModal would block; ensure confirm modal shows
    page.wait_for_selector("#confirmModal.show", timeout=8000)
    with page.expect_navigation(timeout=15000):
        page.click("#btn-submit-form")

    if "/tiket/" not in page.url or page.url.rstrip("/").endswith("/rekam"):
        shot(page, f"{scenario}_rekam_failed")
        raise AssertionError(f"rekam did not navigate to detail; url={page.url}")

    detail_url = page.url
    nomor = ""
    try:
        nomor = page.locator("p.fw-bold.fs-5").first.inner_text().strip()
    except Exception:
        pass
    rep.ok(scenario, "rekam tiket", f"{nomor} -> {status_label(page)}")
    return detail_url, nomor


# --------------------------------------------------------------------------- #
# Detail-page modal step helpers
# --------------------------------------------------------------------------- #
def _wait_reload_after(page, click_fn, timeout=12000):
    """Run click_fn (submits a modal), then read server state deterministically.

    Success handlers call location.reload() after ~800ms; detecting that
    navigation is racy, so we let the AJAX POST land, then force a reload
    ourselves. Backend state is committed on success regardless of the JS
    reload firing. Returns True (state re-read); callers assert on status.
    """
    click_fn()
    page.wait_for_timeout(1800)  # let the fetch POST + JS handler run
    try:
        page.reload(wait_until="networkidle", timeout=timeout)
    except Exception:
        try:
            page.wait_for_load_state("networkidle")
        except Exception:
            pass
    page.wait_for_timeout(700)   # let messages JS create the success modal
    clear_overlays(page)
    return True


def open_modal(page, trigger_selector, container_selector, *, force_enable=False):
    """Click a sidebar action button and wait for its AJAX form to load."""
    clear_overlays(page)
    page.wait_for_timeout(300)
    clear_overlays(page)  # catch success modal created on DOMContentLoaded
    if force_enable:
        # Work around hardcoded-disabled trigger buttons so the modal opens.
        page.eval_on_selector(trigger_selector, "el => el.removeAttribute('disabled')")
    page.click(trigger_selector)
    page.wait_for_selector(f"{container_selector} form, {container_selector} input, {container_selector} .modal-body",
                           timeout=12000)
    page.wait_for_timeout(400)


def do_tanda_terima(page, rep, scenario, tanggal=None):
    open_modal(page, '[data-bs-target="#createTandaTerimaModal"]',
               "#tanda-terima-form-container")
    fill_date(page, "#tanda-terima-form-container #id_tanggal_tanda_terima",
              tanggal or date_ago(44))
    ok = _wait_reload_after(
        page, lambda: page.click('#tanda-terima-form-container button[type="submit"]'))
    rep.ok(scenario, "buat tanda terima", "reloaded" if ok else "no-reload")


def do_rekam_penelitian(page, rep, scenario, baris_lengkap, baris_tidak_lengkap,
                        tgl_teliti=None):
    open_modal(page, '[data-bs-target="#rekamHasilPenelitianModal"]',
               "#rekam-hasil-penelitian-form-container")
    fill_date(page, "#rekam-hasil-penelitian-form-container #id_tgl_teliti",
              tgl_teliti or date_ago(40))
    page.fill("#id_baris_lengkap", str(baris_lengkap))
    page.fill("#id_baris_tidak_lengkap", str(baris_tidak_lengkap))
    page.wait_for_timeout(300)
    btn = page.locator("#rekam-hasil-penelitian-simpan-btn")
    disabled = btn.is_disabled()
    _wait_reload_after(page, lambda: btn.click(force=True))
    rep.ok(scenario, "rekam hasil penelitian",
           f"lengkap={baris_lengkap} -> {status_label(page)} (btn_was_disabled={disabled})")


def do_generate_nd(page, rep, scenario):
    open_modal(page, '[data-bs-target="#kirimTiketModal"]', "#kirim-tiket-form-container")
    ok = _wait_reload_after(
        page, lambda: page.click('#kirim-tiket-form-container button[type="submit"]'),
        timeout=15000)
    rep.ok(scenario, "generate ND pengantar", "reloaded" if ok else "no-reload (check toast)")


def open_kirim_ke_pide(page, *, tgl_nadine=None, tgl_kirim_pide=None,
                       nomor_nd="ND-E2E-001"):
    """Open the 'Kirim Tiket ke PIDE' modal and fill it (no submit).

    Only available after Generate ND Pengantar: the sidebar button carries the
    data-id-temp the modal needs to fetch its form."""
    clear_overlays(page)
    trigger = '[data-bs-target="#kirimTiketKePideModal"]'
    page.wait_for_selector(trigger, timeout=8000)
    page.click(trigger)
    page.wait_for_selector("#kirim-tiket-ke-pide-form-container form", timeout=12000)
    fill_date(page, '#kirim-tiket-ke-pide-form-container [name="tgl_nadine"]',
              tgl_nadine or date_ago(36))
    page.fill('#kirim-tiket-ke-pide-form-container [name="nomor_nd_nadine"]', nomor_nd)
    fill_date(page, '#kirim-tiket-ke-pide-form-container [name="tgl_kirim_pide"]',
              tgl_kirim_pide or date_ago(32))


def do_kirim_ke_pide(page, rep, scenario, tgl_nadine=None, tgl_kirim_pide=None):
    open_kirim_ke_pide(page, tgl_nadine=tgl_nadine, tgl_kirim_pide=tgl_kirim_pide)
    ok = _wait_reload_after(
        page, lambda: page.click('#kirim-tiket-ke-pide-form-container button[type="submit"]'))
    rep.ok(scenario, "kirim ke PIDE", f"-> {status_label(page)}" if ok else "no-reload")


def do_identifikasi(page, rep, scenario, tgl_rekam_pide=None):
    open_modal(page, '[data-bs-target="#identifikasiTiketModal"]',
               "#identifikasi-tiket-form-container")
    fill_date(page, '#identifikasi-tiket-form-container [name="tgl_rekam_pide"]',
              tgl_rekam_pide or date_ago(24))
    ok = _wait_reload_after(
        page, lambda: page.click('#identifikasi-tiket-form-container button[type="submit"]'))
    rep.ok(scenario, "identifikasi", f"-> {status_label(page)}" if ok else "no-reload")


def open_transfer_pmde(page, i, u, res, cde, tgl_transfer=None):
    """Open + fill the Transfer ke PMDE modal (no submit) and enable Simpan.

    The open button is hardcoded `disabled` in the template (open bug) and the
    submit button is JS-disabled until the row totals match, so both are
    force-enabled here."""
    trigger = '[data-bs-target="#transferKePMDEModal"]'
    disabled = page.locator(trigger).is_disabled()
    open_modal(page, trigger, "#transfer-ke-pmde-form-container", force_enable=True)
    page.fill('#transfer-ke-pmde-form-container [name="baris_i"]', str(i))
    page.fill('#transfer-ke-pmde-form-container [name="baris_u"]', str(u))
    page.fill('#transfer-ke-pmde-form-container [name="baris_res"]', str(res))
    page.fill('#transfer-ke-pmde-form-container [name="baris_cde"]', str(cde))
    fill_date(page, '#transfer-ke-pmde-form-container [name="tgl_transfer"]',
              tgl_transfer or date_ago(12))
    page.wait_for_timeout(300)
    page.eval_on_selector("#transfer-submit-btn", "el => el.removeAttribute('disabled')")
    return disabled


def do_transfer_pmde(page, rep, scenario, i, u, res, cde, tgl_transfer=None):
    disabled = open_transfer_pmde(page, i, u, res, cde, tgl_transfer)
    ok = _wait_reload_after(
        page, lambda: page.locator("#transfer-submit-btn").click(force=True))
    rep.ok(scenario, "transfer ke PMDE",
           f"-> {status_label(page)} (open_btn_was_disabled={disabled})" if ok
           else f"no-reload (open_btn_was_disabled={disabled})")
    return disabled


def do_selesaikan(page, rep, scenario, lolos, tidak_lolos, qc_c):
    trigger = '[data-bs-target="#selesaikanTiketModal"]'
    disabled = page.locator(trigger).is_disabled()
    open_modal(page, trigger, "#selesaikan-tiket-form-container", force_enable=True)
    page.fill('#selesaikan-tiket-form-container [name="lolos_qc"]', str(lolos))
    page.fill('#selesaikan-tiket-form-container [name="tidak_lolos_qc"]', str(tidak_lolos))
    page.fill('#selesaikan-tiket-form-container [name="qc_c"]', str(qc_c))
    page.wait_for_timeout(300)
    page.eval_on_selector('#selesaikan-tiket-form-container button[type="submit"]',
                          "el => el.removeAttribute('disabled')")
    ok = _wait_reload_after(
        page, lambda: page.locator('#selesaikan-tiket-form-container button[type="submit"]').click(force=True))
    rep.ok(scenario, "selesaikan tiket",
           f"-> {status_label(page)} (open_btn_was_disabled={disabled})" if ok
           else f"no-reload (open_btn_was_disabled={disabled})")
    return disabled


def do_batalkan(page, rep, scenario, catatan="Dibatalkan oleh E2E test"):
    open_modal(page, '[data-bs-target="#batalkanTiketModal"]',
               "#batalkan-tiket-form-container")
    page.fill('#batalkan-tiket-form-container [name="catatan"]', catatan)
    ok = _wait_reload_after(
        page, lambda: page.click('#batalkan-tiket-form-container button[type="submit"]'))
    rep.ok(scenario, "batalkan tiket", f"-> {status_label(page)}" if ok else "no-reload")


def do_dikembalikan(page, rep, scenario, catatan="Dikembalikan oleh E2E test"):
    open_modal(page, '[data-bs-target="#dikembalikanTiketModal"]',
               "#dikembalikan-tiket-form-container")
    page.fill('#dikembalikan-tiket-form-container [name="catatan"]', catatan)
    ok = _wait_reload_after(
        page, lambda: page.click('#dikembalikan-tiket-form-container button[type="submit"]'))
    rep.ok(scenario, "dikembalikan ke P3DE", f"-> {status_label(page)}" if ok else "no-reload")
