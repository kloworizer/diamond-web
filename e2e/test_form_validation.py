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
        page.fill("#id_tgl_terima_vertikal", H.hours_ago(52))
    # FUTURE dip
    page.fill("#id_tgl_terima_dip", H.future_dt(3))
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
    page.fill("#rekam-hasil-penelitian-form-container #id_tgl_teliti", H.hours_ago(40))
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


def run(page, rep):
    H.login(page)
    for fn in (rekam_future_date_guard, rekam_missing_required,
               penelitian_negative, transfer_and_selesaikan_gaps):
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
