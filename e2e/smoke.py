"""Quick smoke test: login + rekam tiket + tanda terima. Validates the harness."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H


def main():
    rep = H.Reporter()
    with H.browser_page(headless=True) as page:
        H.login(page)
        rep.ok("smoke", "login", page.url)
        url, nomor = H.rekam_tiket(page, rep, "smoke", tahun="2018", baris_diterima=500)
        H.shot(page, "smoke_detail")
        print("DETAIL URL:", url, "NOMOR:", nomor, "STATUS:", H.status_label(page))
        H.do_tanda_terima(page, rep, "smoke")
        print("AFTER TT STATUS:", H.status_label(page))
    rep.write()


if __name__ == "__main__":
    main()
