"""
Negative / form-validation tests aimed at surfacing bugs.

Covered:
  1. Rekam: future 'Tanggal Terima DIP' triggers the client-side guard modal.
  2. Rekam: missing required fields block the confirmation modal (HTML5).
  3. Rekam Hasil Penelitian: mismatched baris keeps the submit button disabled.
  4. Rekam Hasil Penelitian: NEGATIVE baris_lengkap that still sums to
     baris_diterima is accepted by the server (no non-negative validation).
  5. Transfer ke PMDE: NEGATIVE baris values that sum to baris_lengkap are
     accepted by the server (no non-negative validation).
  6. Selesaikan Tiket: server accepts QC where lolos+tidak_lolos != baris_i
     (SelesaikanTiketForm has no server-side clean(); only client JS guards it).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

BARIS = 1000


# --------------------------------------------------------------------------- #
def rekam_future_date_guard(page, rep):
    sc = "val_rekam_future_date"
    page.goto(f"{H.BASE_URL}/tiket/rekam/")
    H.select_ilap_periode(page, tahun="2010")
    page.check("#status_tersedia")
    H._select_first_real_option(page, "id_id_bentuk_data")
    H._select_first_real_option(page, "id_id_cara_penyampaian")
    page.fill("#id_baris_diterima", str(BARIS))
    page.select_option("#id_satuan_data", "1")
    if not page.is_disabled("#id_tgl_terima_vertikal"):
        H.fill_date(page, "#id_tgl_terima_vertikal", H.date_ago(52))
    # FUTURE dip
    H.fill_date(page, "#id_tgl_terima_dip", H.future_date(3))
    H.clear_overlays(page)
    page.click("#btn-confirm-save")
    page.wait_for_timeout(600)
    guard = page.locator("#endDateValidationModal.show")
    confirm = page.locator("#confirmModal.show")
    if guard.count() and guard.is_visible():
        rep.ok(sc, "future DIP blocked by client guard", "endDateValidationModal shown")
    elif confirm.count() and confirm.is_visible():
        rep.fail(sc, "future DIP NOT blocked", "confirmModal appeared for a future date")
        rep.bug("Rekam accepts future Tanggal Terima DIP (client guard bypassed)",
                "MEDIUM",
                "Selecting a future 'Tanggal Terima DIP' still opened the confirmation "
                "modal instead of the validation-error modal.")
    else:
        rep.info(sc, "future DIP", "neither modal shown (inconclusive)")
    H.shot(page, f"{sc}")


def rekam_missing_required(page, rep):
    sc = "val_rekam_missing_required"
    page.goto(f"{H.BASE_URL}/tiket/rekam/")
    page.wait_for_selector("#id_ilap")
    # Do not select ILAP/periode; click save.
    H.clear_overlays(page)
    page.click("#btn-confirm-save")
    page.wait_for_timeout(600)
    confirm = page.locator("#confirmModal.show")
    if confirm.count() and confirm.is_visible():
        rep.fail(sc, "missing required NOT blocked", "confirmModal appeared with empty form")
        rep.bug("Rekam confirmation modal opens with required fields empty",
                "MEDIUM", "Clicking Simpan with no ILAP/periode still opened the "
                "confirmation modal.")
    else:
        rep.ok(sc, "missing required blocked", "confirmModal not shown (HTML5 validation)")


# --------------------------------------------------------------------------- #
def penelitian_negative(page, rep):
    sc = "val_penelitian_negative"
    H.rekam_tiket(page, rep, sc, tahun="2009", baris_diterima=BARIS, backup=True)
    H.do_tanda_terima(page, rep, sc)

    # First: mismatched total keeps the button disabled (client validation OK)
    H.open_modal(page, '[data-bs-target="#rekamHasilPenelitianModal"]',
                 "#rekam-hasil-penelitian-form-container")
    H.fill_date(page, "#rekam-hasil-penelitian-form-container #id_tgl_teliti", H.date_ago(40))
    page.fill("#id_baris_lengkap", "600")
    page.fill("#id_baris_tidak_lengkap", "100")   # total 700 != 1000
    page.wait_for_timeout(300)
    if page.locator("#rekam-hasil-penelitian-simpan-btn").is_disabled():
        rep.ok(sc, "mismatched total disables submit", "client validation works")
    else:
        rep.fail(sc, "mismatched total NOT blocked", "submit enabled with wrong total")

    # Now: NEGATIVE baris_lengkap that still sums to baris_diterima
    page.fill("#id_baris_lengkap", "-100")
    page.fill("#id_baris_tidak_lengkap", str(BARIS + 100))  # total == 1000
    page.wait_for_timeout(300)
    enabled = not page.locator("#rekam-hasil-penelitian-simpan-btn").is_disabled()
    H._wait_reload_after(
        page, lambda: page.locator("#rekam-hasil-penelitian-simpan-btn").click(force=True))
    status = H.status_label(page)
    H.shot(page, f"{sc}")
    if "diteliti" in status.lower():
        rep.fail(sc, "negative baris_lengkap accepted", f"status -> {status}")
        rep.bug("Server accepts NEGATIVE baris_lengkap in Rekam Hasil Penelitian",
                "MEDIUM",
                "RekamHasilPenelitianForm only checks baris_lengkap + baris_tidak_lengkap "
                "== baris_diterima; it has no non-negative validator (the `min=0` is a "
                "client-only widget attribute). Submitting baris_lengkap=-100 / "
                "baris_tidak_lengkap=1100 (total 1000) was accepted and moved the tiket "
                f"to '{status}', storing negative row counts. (submit was "
                f"client-enabled={enabled}).")
    else:
        rep.ok(sc, "negative baris_lengkap rejected", f"status stayed {status}")


# --------------------------------------------------------------------------- #
def transfer_and_selesaikan_gaps(page, rep):
    sc = "val_pide_pmde_gaps"
    # Drive a clean tiket to Identifikasi
    H.rekam_tiket(page, rep, sc, tahun="2008", baris_diterima=BARIS, backup=True)
    H.do_tanda_terima(page, rep, sc)
    H.do_rekam_penelitian(page, rep, sc, baris_lengkap=BARIS, baris_tidak_lengkap=0)
    H.do_generate_nd(page, rep, sc)
    H.do_kirim_ke_pide(page, rep, sc)
    H.do_identifikasi(page, rep, sc)
    if "identifikasi" not in H.status_label(page).lower():
        rep.fail(sc, "setup", f"expected Identifikasi, got {H.status_label(page)}")
        return

    # 5a) Transfer with NEGATIVE values that still sum to baris_lengkap (1000).
    #     Expected: rejected (Tiket.baris_i is a positive-integer model field).
    H.do_transfer_pmde(page, rep, sc, i=-100, u=BARIS + 100, res=0, cde=0)
    status = H.status_label(page)
    if "pengendalian mutu" in status.lower():
        rep.fail(sc, "negative transfer accepted", f"status -> {status}")
        rep.bug("Server accepts NEGATIVE baris_i/u in Transfer ke PMDE",
                "MEDIUM",
                "TransferKePMDEForm has no non-negative validator; negative Baris I was "
                "accepted and moved the tiket to Pengendalian Mutu.")
    else:
        rep.ok(sc, "negative transfer rejected (model-level protection)", f"status stayed {status}")

    # 5b) Valid transfer to actually reach Pengendalian Mutu.
    if "identifikasi" in H.status_label(page).lower():
        H.do_transfer_pmde(page, rep, sc, i=BARIS, u=0, res=0, cde=0)

    # 6) Selesaikan with QC where lolos + tidak_lolos != baris_i (server has no clean())
    if "pengendalian mutu" in H.status_label(page).lower():
        H.do_selesaikan(page, rep, sc, lolos=1, tidak_lolos=1, qc_c=0)
        status = H.status_label(page)
        H.shot(page, f"{sc}_selesaikan")
        if "selesai" in status.lower():
            rep.fail(sc, "invalid QC accepted", f"status -> {status}")
            rep.bug("Selesaikan Tiket has NO server-side validation of QC totals",
                    "HIGH",
                    "The Selesaikan modal promises 'Lolos QC + Tidak Lolos QC harus sama "
                    "dengan Baris I', but SelesaikanTiketForm defines no clean() and the "
                    "view saves whatever is posted. Submitting lolos_qc=1, tidak_lolos_qc=1 "
                    "(sum 2, unrelated to Baris I) completed the tiket to 'Selesai'. The "
                    "check is client-side only and is trivially bypassed.")
        else:
            rep.ok(sc, "invalid QC rejected", f"status stayed {status}")


# --------------------------------------------------------------------------- #
# Chronological chain: Tanda Terima must not be before Tanggal Terima DIP.
# --------------------------------------------------------------------------- #
def tanda_terima_before_dip_rejected(page, rep):
    sc = "val_tanda_terima_before_dip"
    H.rekam_tiket(page, rep, sc, tahun="2017", baris_diterima=BARIS, backup=False)
    # tgl_terima_dip was set to date_ago(48) (= today-2, a clean 24h multiple
    # so it isn't ambiguous vs. the current clock time) by rekam_tiket().
    # Try a tanda terima date a full day further back (date_ago(72) = today-3)
    # -- must be rejected. (Offsets here are always exact multiples of 24h so
    # the resulting calendar date is deterministic regardless of what time of
    # day the test happens to run.)
    H.open_modal(page, '[data-bs-target="#createTandaTerimaModal"]',
                 "#tanda-terima-form-container")
    H.fill_date(page, "#tanda-terima-form-container #id_tanggal_tanda_terima", H.date_ago(72))
    page.click('#tanda-terima-form-container button[type="submit"]')
    page.wait_for_timeout(1200)
    rejected = (
        page.locator("#tanda-terima-form-container .alert-danger").count() > 0
        or page.locator(".toast-danger").count() > 0
    )
    if rejected:
        rep.ok(sc, "tanda terima before tgl_terima_dip rejected")
    else:
        rep.fail(sc, "tanda terima before tgl_terima_dip NOT rejected")
        rep.bug("Tanda Terima accepts a date before the tiket's Tanggal Terima DIP",
                "MEDIUM", "Submitting a Tanggal Tanda Terima earlier than the tiket's "
                "tgl_terima_dip was not rejected.")
        H.shot(page, f"{sc}_rejected")
        return
    H.shot(page, f"{sc}_rejected")
    H.clear_overlays(page)

    # Now a valid date (after tgl_terima_dip = today-2) must succeed.
    H.fill_date(page, "#tanda-terima-form-container #id_tanggal_tanda_terima", H.date_ago(24))
    ok = H._wait_reload_after(
        page, lambda: page.click('#tanda-terima-form-container button[type="submit"]'))
    status = H.status_label(page)
    rep.ok(sc, "valid tanda terima accepted", status) if ok else rep.fail(sc, "valid tanda terima rejected")
    H.shot(page, f"{sc}_accepted")


# --------------------------------------------------------------------------- #
# Chronological chain: Tanggal Teliti must not be before Tanggal Tanda Terima
# (the step immediately before Rekam Hasil Penelitian).
# --------------------------------------------------------------------------- #
def teliti_before_tanda_terima_rejected(page, rep):
    sc = "val_teliti_before_tanda_terima"
    # backup=True is required: the "Rekam Hasil Penelitian" button on the
    # detail page only renders when `tiket.backup and tiket.tanda_terima`.
    H.rekam_tiket(page, rep, sc, tahun="2016", baris_diterima=BARIS, backup=True)
    # tgl_terima_dip = date_ago(48) (= today-2). Set tanda terima at
    # date_ago(24) (= today-1). All offsets are exact 24h multiples so the
    # resulting calendar date is deterministic regardless of current clock time.
    H.open_modal(page, '[data-bs-target="#createTandaTerimaModal"]',
                 "#tanda-terima-form-container")
    H.fill_date(page, "#tanda-terima-form-container #id_tanggal_tanda_terima", H.date_ago(24))
    ok = H._wait_reload_after(
        page, lambda: page.click('#tanda-terima-form-container button[type="submit"]'))
    if not ok:
        rep.fail(sc, "setup: buat tanda terima failed")
        return
    rep.ok(sc, "setup: buat tanda terima", H.date_ago(24))

    # tgl_teliti at the SAME date as tgl_terima_dip (today-2) is before the
    # tanda terima date (today-1) -- must be rejected.
    H.open_modal(page, '[data-bs-target="#rekamHasilPenelitianModal"]',
                 "#rekam-hasil-penelitian-form-container")
    H.fill_date(page, "#rekam-hasil-penelitian-form-container #id_tgl_teliti", H.date_ago(48))
    page.fill("#id_baris_lengkap", str(BARIS))
    page.fill("#id_baris_tidak_lengkap", "0")
    page.wait_for_timeout(300)
    btn = page.locator("#rekam-hasil-penelitian-simpan-btn")
    # Client-side date guard (min attribute) may already disable the button;
    # force the submit through to prove the SERVER also rejects it.
    btn.click(force=True)
    page.wait_for_timeout(1200)
    rejected = (
        page.locator("#rekam-hasil-penelitian-form-container .text-danger").count() > 0
        or page.locator(".toast-danger").count() > 0
    )
    if rejected and "diteliti" not in H.status_label(page).lower():
        rep.ok(sc, "tgl_teliti before tanda terima rejected", H.status_label(page))
    else:
        rep.fail(sc, "tgl_teliti before tanda terima NOT rejected", H.status_label(page))
        rep.bug("Rekam Hasil Penelitian accepts a Tanggal Teliti before Tanggal Tanda Terima",
                "MEDIUM", "Submitting tgl_teliti earlier than the tiket's own tanda terima "
                "date was not rejected server-side.")
        H.shot(page, f"{sc}_rejected")
        return
    H.shot(page, f"{sc}_rejected")
    H.clear_overlays(page)
    page.reload(wait_until="networkidle")
    H.clear_overlays(page)

    # A valid tgl_teliti (today, clearly on/after the tanda terima date) must succeed.
    H.open_modal(page, '[data-bs-target="#rekamHasilPenelitianModal"]',
                 "#rekam-hasil-penelitian-form-container")
    H.fill_date(page, "#rekam-hasil-penelitian-form-container #id_tgl_teliti", H.date_ago(0))
    page.fill("#id_baris_lengkap", str(BARIS))
    page.fill("#id_baris_tidak_lengkap", "0")
    page.wait_for_timeout(300)
    btn = page.locator("#rekam-hasil-penelitian-simpan-btn")
    H._wait_reload_after(page, lambda: btn.click(force=True))
    status = H.status_label(page)
    rep.ok(sc, "valid tgl_teliti accepted", status) if "diteliti" in status.lower() else rep.fail(
        sc, "valid tgl_teliti rejected", status)
    H.shot(page, f"{sc}_accepted")


# --------------------------------------------------------------------------- #
# Every datepicker must render the calendar icon and be flatpickr-enhanced,
# whether it's on a full page (rekam tiket) or loaded via an AJAX modal
# (edit tiket) -- guards against the icon/flatpickr regressing per-page.
# --------------------------------------------------------------------------- #
def datepicker_icon_and_flatpickr_consistency(page, rep):
    sc = "val_datepicker_consistency"

    def check(selector, label):
        page.wait_for_selector(selector, state="attached", timeout=8000)
        wrapped = page.eval_on_selector(selector, "el => !!el.closest('.input-icon-wrapper')")
        icon = page.locator(selector).locator(
            "xpath=ancestor::div[contains(@class,'input-icon-wrapper')]"
            "//i[contains(@class,'feather-calendar')]"
        ).count()
        flatpickr_on = page.eval_on_selector(selector, "el => !!el._flatpickr")
        ok = wrapped and icon == 1 and flatpickr_on
        if ok:
            rep.ok(sc, f"{label} has icon + flatpickr")
        else:
            rep.fail(sc, f"{label} missing icon/flatpickr",
                     f"wrapped={wrapped} icon_count={icon} flatpickr={flatpickr_on}")

    page.goto(f"{H.BASE_URL}/tiket/rekam/")
    check("#id_tgl_terima_dip", "rekam tiket page")

    detail_url, _ = H.rekam_tiket(page, rep, sc, tahun="2019", baris_diterima=BARIS, backup=False)
    H.open_modal(page, '[data-bs-target="#editTiketModal"]', "#edit-tiket-form-container")
    check("#id_edit_tgl_terima_dip", "edit tiket AJAX modal")
    H.shot(page, sc)


def run(page, rep):
    H.login(page)
    for fn in (rekam_future_date_guard, rekam_missing_required,
               penelitian_negative, transfer_and_selesaikan_gaps,
               tanda_terima_before_dip_rejected, teliti_before_tanda_terima_rejected,
               datepicker_icon_and_flatpickr_consistency):
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
