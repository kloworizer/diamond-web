"""
Coverage for the two tiket-detail actions that are reachable from the detail
page but were NOT part of the original workflow scenarios: "Ubah Isian
Tiket" (Edit Tiket, P3DE-only, only while status is Direkam and no tanda
terima yet) and "Ubah Special Request" (P3DE/PIDE/PMDE depending on status).

Exhausts: missing/invalid dates, tgl_terima_dip before tgl_terima_vertikal,
future dates, a valid edit, special-request toggle on/off (including the
mandatory due date that comes with switching it on), and the
post-tanda-terima regression check that Edit Tiket disappears once it is no
longer allowed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

BARIS = 500


def _open_edit_tiket(page):
    H.clear_overlays(page)
    page.wait_for_timeout(200)
    H.clear_overlays(page)
    page.click('[data-bs-target="#editTiketModal"]')
    page.wait_for_selector("#edit-tiket-form-container form", timeout=10000)
    page.wait_for_timeout(400)


def _submit_edit_tiket(page):
    page.click('#editTiketForm button[type="submit"]')
    page.wait_for_timeout(1200)


def edit_tiket_flow(page, rep):
    sc = "edit_tiket"
    detail_url, nomor = H.rekam_tiket(page, rep, sc, tahun="2007", baris_diterima=BARIS, backup=False)
    if "direkam" not in H.status_label(page).lower():
        rep.fail(sc, "setup: expected Direkam", H.status_label(page))
        return

    # Submission errors on this modal are AJAX/toast-only (see
    # tiket_detail.html editTiketModal submit handler: on failure it calls
    # showToast(data.message, 'danger') and re-enables the submit button, but
    # does NOT re-render the form with inline field errors) -> detect via the
    # '.toast-danger' element, not inline .invalid-feedback/.alert-danger.
    def _rejected_via_toast():
        page.wait_for_timeout(300)
        return page.locator(".toast-danger").count() > 0

    # 1) tgl_terima_dip in the FUTURE -> must be rejected
    _open_edit_tiket(page)
    H.fill_date(page, "#id_edit_tgl_terima_dip", H.future_date(5))
    _submit_edit_tiket(page)
    rejected = _rejected_via_toast()
    rep.ok(sc, "future tgl_terima_dip rejected") if rejected else rep.fail(
        sc, "future tgl_terima_dip NOT rejected")
    if not rejected:
        rep.bug("Edit Tiket accepts a future Tanggal Terima DIP", "MEDIUM",
                "Submitting the Ubah Isian Tiket form with tgl_terima_dip in the future "
                "was not rejected (no danger toast, no reload guard).")
    H.clear_overlays(page)
    page.reload(wait_until="networkidle")
    H.clear_overlays(page)

    # 2) tgl_terima_dip BEFORE tgl_terima_vertikal -> must be rejected (cross-field clean())
    _open_edit_tiket(page)
    vertikal_disabled = page.is_disabled("#id_edit_tgl_terima_vertikal")
    if not vertikal_disabled:
        H.fill_date(page, "#id_edit_tgl_terima_vertikal", H.date_ago(5))
        H.fill_date(page, "#id_edit_tgl_terima_dip", H.date_ago(10))  # earlier than vertikal
        _submit_edit_tiket(page)
        rejected = _rejected_via_toast()
        rep.ok(sc, "tgl_terima_dip < tgl_terima_vertikal rejected") if rejected else rep.fail(
            sc, "tgl_terima_dip < tgl_terima_vertikal NOT rejected")
        if not rejected:
            rep.bug("Edit Tiket accepts Tanggal Terima DIP earlier than Tanggal Terima Vertikal",
                    "MEDIUM", "The form's clean() is documented to reject tgl_terima_dip < "
                    "tgl_terima_vertikal, but submitting dip=date_ago(10) with "
                    "vertikal=date_ago(5) was not rejected.")
    else:
        rep.info(sc, "tgl_terima_vertikal disabled (non-regional ILAP)", "skipped cross-field check")
    H.clear_overlays(page)
    page.reload(wait_until="networkidle")
    H.clear_overlays(page)

    # 3) Valid edit: change nomor_surat_pengantar + baris_diterima
    _open_edit_tiket(page)
    new_nomor_surat = f"E2E-EDIT-{nomor[-6:] if nomor else '000000'}"
    page.fill("#id_nomor_surat_pengantar", new_nomor_surat)
    page.fill("#id_edit_baris_diterima", str(BARIS + 25))
    if not vertikal_disabled:
        H.fill_date(page, "#id_edit_tgl_terima_vertikal", H.date_ago(70))
    # Must stay before H.do_tanda_terima()'s hardcoded date_ago(44) below, or
    # the new Tanda-Terima-vs-Tanggal-Terima-DIP chronology check (added
    # alongside this test) will correctly reject the tanda terima step.
    H.fill_date(page, "#id_edit_tgl_terima_dip", H.date_ago(60))
    ok = H._wait_reload_after(page, lambda: _submit_edit_tiket(page))
    page_text = page.content()
    if new_nomor_surat in page_text:
        rep.ok(sc, "valid edit persisted", new_nomor_surat)
    else:
        rep.fail(sc, "valid edit NOT reflected on detail page", new_nomor_surat)
        rep.bug("Edit Tiket valid submit does not persist / reflect changes", "MEDIUM",
                f"After a valid Ubah Isian Tiket submit, '{new_nomor_surat}' was not found "
                "on the reloaded detail page.")
    H.shot(page, f"{sc}_after_valid_edit")

    # 4) Regression: after Buat Tanda Terima, Edit Tiket button must disappear.
    H.do_tanda_terima(page, rep, sc)
    edit_btn_visible = page.locator('[data-bs-target="#editTiketModal"]').count() > 0
    if edit_btn_visible:
        rep.fail(sc, "Edit Tiket button still visible after tanda terima created",
                 "user_can_edit_tiket should turn False once tanda_terima=True")
        rep.bug("Ubah Isian Tiket remains available after Tanda Terima has been created",
                "MEDIUM", "Per the view's own rule (only editable while Direkam AND no "
                "tanda terima yet), the button should disappear once Buat Tanda Terima "
                "succeeds, but it was still present in the DOM.")
    else:
        rep.ok(sc, "Edit Tiket correctly hidden after tanda terima")
    H.shot(page, f"{sc}_post_tanda_terima")


def special_request_flow(page, rep):
    """Toggle + the due-date rule that came with it.

    Since the due date was added (SpecialRequestForm.clean()), turning the
    switch ON without one is a server-side error -- the toggle no longer
    persists on its own."""
    sc = "special_request"
    detail_url, nomor = H.rekam_tiket(page, rep, sc, tahun="2006", baris_diterima=BARIS, backup=False)
    due_date = H.date_ago(0)

    def open_sr():
        H.clear_overlays(page)
        page.click('[data-bs-target="#specialRequestModal"]')
        page.wait_for_selector("#special-request-form-container form", timeout=10000)
        page.wait_for_timeout(400)

    def submit_sr():
        page.click('#special-request-form-container button[type="submit"]')
        page.wait_for_timeout(1200)

    def badge():
        loc = page.locator("#special-request-value")
        return loc.inner_text().strip().lower() if loc.count() else ""

    # 1) Switch ON with NO due date -> must be rejected. The due-date input is
    #    marked required by the modal's own JS, so HTML5 would swallow the
    #    submit before it ever reaches the server; strip that to test the rule.
    open_sr()
    cb = page.locator("#id_special_request")
    if not cb.is_checked():
        cb.check()
    page.wait_for_timeout(200)
    H.disable_client_validation(page, "#special-request-form-container form")
    page.eval_on_selector("#id_tgl_special_request",
                          "el => { if (el._flatpickr) el._flatpickr.clear(); el.value = ''; }")
    ev, _ = H.probe_modal_rejection(page, "#special-request-form-container",
                                    modal_id="specialRequestModal", reload_after=False)
    page.reload(wait_until="networkidle")
    H.clear_overlays(page)
    val = badge()
    if ev and "wajib diisi" in ev.lower() and "tidak" in val:
        rep.ok(sc, "special request without due date rejected", ev[:120])
    elif "ya" in val:
        rep.fail(sc, "special request without due date accepted", f"badge={val}")
        rep.bug("Special Request can be switched on without a due date", "MEDIUM",
                "SpecialRequestForm.clean() marks Tanggal Jatuh Tempo mandatory as soon "
                "as the switch is on, but submitting with an empty due date still "
                "flagged the tiket as a special request.")
    else:
        rep.fail(sc, "special request without due date: wrong rejection",
                 f"evidence={ev[:120] or 'none'} badge={val}")
    H.shot(page, f"{sc}_no_due_date")

    # 2) Turn ON with a due date + catatan -> persists, and the due date shows.
    open_sr()
    cb = page.locator("#id_special_request")
    if not cb.is_checked():
        cb.check()
    page.wait_for_timeout(200)
    H.fill_date(page, "#id_tgl_special_request", due_date)
    page.fill("#id_catatan", "E2E: marked as special request")
    H._wait_reload_after(page, submit_sr)
    val = badge()
    if "ya" in val:
        rep.ok(sc, "toggle ON persisted", val)
    else:
        rep.fail(sc, "toggle ON NOT persisted", val)
        rep.bug("Special Request toggle-ON does not persist", "LOW",
                f"After checking the switch, setting a due date and submitting, the "
                f"detail page badge read '{val}' instead of 'Ya'.")
    shown_due = page.locator("#tgl-special-request-value")
    expected_due = "-".join(reversed(due_date.split("-")))  # d-m-Y on the detail page
    if shown_due.count() and expected_due in shown_due.inner_text():
        rep.ok(sc, "due date persisted", expected_due)
    else:
        rep.fail(sc, "due date NOT shown on detail page",
                 shown_due.inner_text().strip() if shown_due.count() else "element missing")
    H.shot(page, f"{sc}_on")

    # 3) Turn back OFF, no catatan (optional field). The due date is dropped
    #    server-side, so its row disappears from the detail page.
    open_sr()
    cb = page.locator("#id_special_request")
    if cb.is_checked():
        cb.uncheck()
    H._wait_reload_after(page, submit_sr)
    val = badge()
    if "tidak" in val:
        rep.ok(sc, "toggle OFF persisted", val)
    else:
        rep.fail(sc, "toggle OFF NOT persisted", val)
        rep.bug("Special Request toggle-OFF does not persist", "LOW",
                f"After unchecking the switch and submitting, the detail page badge read "
                f"'{val}' instead of 'Tidak'.")
    if page.locator("#tgl-special-request-value").count():
        rep.fail(sc, "due date still shown after switching off",
                 "tgl_special_request should be cleared when special_request is off")
    else:
        rep.ok(sc, "due date cleared with the switch")
    H.shot(page, f"{sc}_off")


def run(page, rep):
    H.login(page)
    for fn in (edit_tiket_flow, special_request_flow):
        try:
            fn(page, rep)
        except Exception as e:
            H.shot(page, f"{fn.__name__}_EXCEPTION")
            rep.fail(fn.__name__, "exception", str(e))


if __name__ == "__main__":
    rep = H.Reporter()
    with H.browser_page(headless=True) as page:
        run(page, rep)
    rep.write()
