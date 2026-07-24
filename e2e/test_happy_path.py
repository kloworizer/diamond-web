"""
Happy path: Direkam -> Diteliti -> Dikirim ke PIDE -> Identifikasi
            -> Pengendalian Mutu -> Selesai

Backup is recorded at rekam-time (Bagian C). Research result is 'Lengkap'
(baris_lengkap == baris_diterima).

Also asserts the two sidebar action buttons that gate the last two steps
("Transfer ke PMDE", "Selesaikan Tiket") are reachable; records a BUG if they
render disabled.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

SC = "happy_path"
BARIS = 1000


def run(page, rep, tahun="2015"):
    H.login(page)
    url, nomor = H.rekam_tiket(page, rep, SC, tahun=tahun, baris_diterima=BARIS, backup=True)
    H.shot(page, f"{SC}_01_direkam")
    _assert_status(rep, page, "Direkam", "after rekam")

    H.do_tanda_terima(page, rep, SC)

    H.do_rekam_penelitian(page, rep, SC, baris_lengkap=BARIS, baris_tidak_lengkap=0)
    H.shot(page, f"{SC}_02_diteliti")
    _assert_status(rep, page, "Diteliti", "after penelitian (Lengkap)")

    H.do_generate_nd(page, rep, SC)
    H.do_kirim_ke_pide(page, rep, SC)
    H.shot(page, f"{SC}_03_dikirim")
    _assert_status(rep, page, "Dikirim ke PIDE", "after kirim ke PIDE")

    H.do_identifikasi(page, rep, SC)
    H.shot(page, f"{SC}_04_identifikasi")
    _assert_status(rep, page, "Identifikasi", "after identifikasi")

    # Transfer button gating check
    transfer_disabled = H.do_transfer_pmde(page, rep, SC, i=BARIS, u=0, res=0, cde=0)
    if transfer_disabled:
        rep.bug(
            "Sidebar 'Transfer ke PMDE' button is permanently disabled",
            "HIGH",
            "On the tiket detail page (status Identifikasi), the button that opens "
            "the Transfer ke PMDE modal is rendered with a hardcoded `disabled` "
            "attribute (tiket_detail.html ~L750) and no JS ever enables it. A PIDE "
            "PIC therefore cannot open the modal or transfer the tiket to PMDE "
            "through the intended UI. (E2E forced-enabled it to verify the "
            "underlying flow still works.)",
        )
    H.shot(page, f"{SC}_05_pengendalian_mutu")
    _assert_status(rep, page, "Pengendalian Mutu", "after transfer ke PMDE")

    selesai_disabled = H.do_selesaikan(page, rep, SC, lolos=BARIS, tidak_lolos=0, qc_c=0)
    if selesai_disabled:
        rep.bug(
            "Sidebar 'Selesaikan Tiket' button is permanently disabled",
            "HIGH",
            "On the tiket detail page (status Pengendalian Mutu), the button that "
            "opens the Selesaikan Tiket modal is rendered with a hardcoded "
            "`disabled` attribute (tiket_detail.html ~L766) and no JS enables it. A "
            "PMDE PIC cannot complete the tiket through the intended UI. (E2E "
            "forced-enabled it to verify the underlying flow still works.)",
        )
    H.shot(page, f"{SC}_06_selesai")
    _assert_status(rep, page, "Selesai", "after selesaikan")


def _assert_status(rep, page, expected, where):
    actual = H.status_label(page)
    if expected.lower() in actual.lower():
        rep.ok(SC, f"status {where}", actual)
    else:
        rep.fail(SC, f"status {where}", f"expected '{expected}', got '{actual}'")


if __name__ == "__main__":
    rep = H.Reporter()
    with H.browser_page(headless=True) as page:
        try:
            run(page, rep)
        except Exception as e:
            H.shot(page, f"{SC}_EXCEPTION")
            rep.fail(SC, "exception", str(e))
            raise
    rep.write()
