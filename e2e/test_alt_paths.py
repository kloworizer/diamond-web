"""
Alternate workflow paths:
  - langsung_selesai:  rekam with 'Data Tidak Tersedia' -> Selesai immediately
  - tidak_lengkap:     penelitian with baris_lengkap == 0 -> Selesai
  - batalkan:          P3DE cancels a Direkam tiket -> Dibatalkan
  - dikembalikan:      PIDE returns a Dikirim-ke-PIDE tiket -> Dibatalkan
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H

BARIS = 800


def _assert(rep, page, scenario, expected, where):
    actual = H.status_label(page)
    if expected.lower() in actual.lower():
        rep.ok(scenario, f"status {where}", actual)
    else:
        rep.fail(scenario, f"status {where}", f"expected '{expected}', got '{actual}'")


def langsung_selesai(page, rep):
    sc = "langsung_selesai"
    H.rekam_tiket(page, rep, sc, tahun="2014", tersedia=False)
    H.shot(page, f"{sc}_selesai")
    _assert(rep, page, sc, "Selesai", "after rekam (data tidak tersedia)")


def tidak_lengkap(page, rep):
    sc = "penelitian_tidak_lengkap"
    H.rekam_tiket(page, rep, sc, tahun="2013", baris_diterima=BARIS, backup=True)
    H.do_tanda_terima(page, rep, sc)
    H.do_rekam_penelitian(page, rep, sc, baris_lengkap=0, baris_tidak_lengkap=BARIS)
    H.shot(page, f"{sc}_selesai")
    _assert(rep, page, sc, "Selesai", "after penelitian (baris_lengkap==0)")


def batalkan(page, rep):
    sc = "batalkan"
    H.rekam_tiket(page, rep, sc, tahun="2012", baris_diterima=BARIS, backup=True)
    _assert(rep, page, sc, "Direkam", "after rekam")
    H.do_batalkan(page, rep, sc)
    H.shot(page, f"{sc}_dibatalkan")
    _assert(rep, page, sc, "Dibatalkan", "after batalkan")


def dikembalikan(page, rep):
    sc = "dikembalikan"
    H.rekam_tiket(page, rep, sc, tahun="2011", baris_diterima=BARIS, backup=True)
    H.do_tanda_terima(page, rep, sc)
    H.do_rekam_penelitian(page, rep, sc, baris_lengkap=BARIS, baris_tidak_lengkap=0)
    H.do_generate_nd(page, rep, sc)
    H.do_kirim_ke_pide(page, rep, sc)
    _assert(rep, page, sc, "Dikirim ke PIDE", "after kirim ke PIDE")
    H.do_dikembalikan(page, rep, sc)
    H.shot(page, f"{sc}_dibatalkan")
    # Per docs: returning a tiket sets status to Dibatalkan (7), not Dikembalikan (3)
    _assert(rep, page, sc, "Dibatalkan", "after dikembalikan (expected Dibatalkan per design)")


def run(page, rep):
    H.login(page)
    for fn in (langsung_selesai, tidak_lengkap, batalkan, dikembalikan):
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
