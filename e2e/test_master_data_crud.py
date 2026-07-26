"""
CRUD + validation coverage for the P3DE "master data" admin pages that were
NOT part of the tiket workflow (see e2e/README.md). These all share one
generic pattern: a DataTables list page + a shared #crudModal loaded via
AJAX for Tambah / Edit / Hapus (see diamond_web/templates/*/list.html).

For each page we exercise:
  1. Empty required-field submit -> must be blocked (HTML5 or server error).
  2. Valid create -> row appears.
  3. Duplicate create (same unique value) -> must be rejected server-side.
  4. Edit -> value changes.
  5. Delete -> row disappears.

pw_tester is a superuser so it passes every Admin*RequiredMixin check.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H


def _force_close_modal(page):
    """Hide #crudModal + remove its backdrop via JS, regardless of whether it
    closed itself (a validation-rejected submit leaves it open by design)."""
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


def _open_create(page, table_id):
    _force_close_modal(page)
    H.clear_overlays(page)
    page.wait_for_selector(f"#{table_id}")
    page.click('[data-action="create"]')
    page.wait_for_selector("#crudModal form", timeout=8000)
    page.wait_for_timeout(300)


def _submit_and_wait(page, rep, sc, step):
    """Submit #crudModal form, wait for the AJAX round-trip, return whether
    the modal closed (success) or stayed open (validation error)."""
    page.click('#crudModal button[type="submit"]')
    page.wait_for_timeout(900)
    open_now = page.locator("#crudModal.show").count() > 0 and page.locator("#crudModal form").count() > 0
    return not open_now


def _search_column(page, table_id, col_index, value):
    """Fill a DataTables column-search box and force the 'change' event the
    page's jQuery `.on('keyup change', ...)` listener needs -- Playwright's
    .fill() only dispatches 'input', so without this the table never
    re-filters and callers can end up acting on the wrong row."""
    _force_close_modal(page)
    selector = f'#column-search-row input[data-column="{col_index}"]'
    page.fill(selector, value)
    page.dispatch_event(selector, "change")
    page.wait_for_timeout(800)


def _row_count(page, table_id):
    return page.locator(f"#{table_id} tbody tr").count()


# --------------------------------------------------------------------------- #
def crud_single_text_field(page, rep, sc, url_slug, table_id, unique_max_len,
                            search_col=1, page_title=None):
    """Models whose only field is a single unique `deskripsi` text input."""
    page.goto(f"{H.BASE_URL}/{url_slug}/")
    field = "#id_deskripsi"

    # 1) Empty submit blocked
    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty submit")
    if ok:
        rep.ok(sc, "empty submit blocked")
    else:
        rep.fail(sc, "empty submit NOT blocked", "modal closed with no value entered")
        rep.bug(f"{url_slug}: empty required 'deskripsi' accepted", "MEDIUM",
                 f"Submitting the Tambah form on /{url_slug}/ with the deskripsi field "
                 "left blank did not keep the modal open / show a validation error.")
    H.clear_overlays(page)

    # 2) Valid create
    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    value = f"E2E {url_slug[:12]} {int(time.time() * 1000) % 100000}"[:unique_max_len]
    page.fill(field, value)
    closed = _submit_and_wait(page, rep, sc, "valid create")
    if closed:
        rep.ok(sc, "valid create", value)
    else:
        err = page.locator("#crudModal .alert-danger, #crudModal .invalid-feedback").first
        detail = err.inner_text().strip() if err.count() else "(no error text found)"
        rep.fail(sc, "valid create rejected", detail)
        rep.bug(f"{url_slug}: valid unique create rejected", "MEDIUM",
                 f"Submitting a fresh unique value ('{value}') on /{url_slug}/ Tambah was "
                 f"rejected. Server said: {detail}")
        H.clear_overlays(page)
        return
    H.clear_overlays(page)

    # 3) Duplicate create -> must be rejected (uniqueness)
    _open_create(page, table_id)
    page.fill(field, value)
    closed = _submit_and_wait(page, rep, sc, "duplicate create")
    if not closed:
        rep.ok(sc, "duplicate rejected", "modal stayed open with validation error")
    else:
        rep.fail(sc, "duplicate NOT rejected", f"'{value}' accepted twice")
        rep.bug(f"{url_slug}: duplicate 'deskripsi' accepted", "MEDIUM",
                 f"The model declares deskripsi unique=True, but submitting the same "
                 f"value ('{value}') twice on /{url_slug}/ was accepted both times "
                 "(no server-side uniqueness validation error shown).")
    H.clear_overlays(page)

    # 4) Edit -> change value
    _search_column(page, table_id, search_col, value)
    edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
    if not edit_btn.count():
        rep.fail(sc, "edit: row not found after search", value)
        return
    edit_btn.click()
    page.wait_for_selector("#crudModal form", timeout=8000)
    page.wait_for_timeout(300)
    new_value = (value + " (edited)")[:unique_max_len]
    page.fill(field, new_value)
    closed = _submit_and_wait(page, rep, sc, "edit")
    rep.ok(sc, "edit", new_value) if closed else rep.fail(sc, "edit failed", new_value)
    H.clear_overlays(page)

    # 5) Delete
    _search_column(page, table_id, search_col, new_value)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if not del_btn.count():
        rep.fail(sc, "delete: row not found after edit", new_value)
        return
    del_btn.click()
    page.wait_for_selector("#crudModal form", timeout=8000)
    page.wait_for_timeout(300)
    closed = _submit_and_wait(page, rep, sc, "delete")
    if closed:
        rep.ok(sc, "delete")
    else:
        err = page.locator("#crudModal .alert-danger, #crudModal .invalid-feedback, .toast-danger").first
        detail = err.inner_text().strip() if err.count() else "(no error text found)"
        rep.fail(sc, "delete failed", detail)
    H.clear_overlays(page)
    H.shot(page, sc)


# --------------------------------------------------------------------------- #
def crud_kanwil(page, rep):
    sc = "crud_kanwil"
    page.goto(f"{H.BASE_URL}/kanwil/")
    table_id = "kanwil-table"

    # Empty submit
    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty")
    rep.ok(sc, "empty submit blocked") if ok else rep.fail(sc, "empty submit NOT blocked")
    H.clear_overlays(page)

    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    suffix = str(int(time.time() * 1000) % 1000).zfill(3)
    kode = f"E{suffix}"[:3]
    nama = f"E2E Kanwil {suffix}"
    page.fill("#id_kode_kanwil", kode)
    page.fill("#id_nama_kanwil", nama)
    closed = _submit_and_wait(page, rep, sc, "create")
    rep.ok(sc, "valid create", f"{kode}/{nama}") if closed else rep.fail(sc, "valid create rejected")
    H.clear_overlays(page)
    if not closed:
        return

    # Duplicate kode_kanwil
    _open_create(page, table_id)
    page.fill("#id_kode_kanwil", kode)
    page.fill("#id_nama_kanwil", "E2E Kanwil Duplicate Kode")
    closed = _submit_and_wait(page, rep, sc, "dup kode")
    if not closed:
        rep.ok(sc, "duplicate kode_kanwil rejected")
    else:
        rep.fail(sc, "duplicate kode_kanwil NOT rejected", kode)
        rep.bug("kanwil: duplicate kode_kanwil accepted", "MEDIUM",
                f"kode_kanwil is unique=True but '{kode}' was accepted twice.")
    H.clear_overlays(page)

    _search_column(page, table_id, 0, kode)  # col0=kode_kanwil, col1=nama_kanwil
    edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
    if edit_btn.count():
        edit_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        page.fill("#id_nama_kanwil", nama + " (edited)")
        closed = _submit_and_wait(page, rep, sc, "edit")
        rep.ok(sc, "edit") if closed else rep.fail(sc, "edit failed")
        H.clear_overlays(page)
    else:
        rep.fail(sc, "edit: row not found after search", kode)

    _search_column(page, table_id, 0, kode)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        closed = _submit_and_wait(page, rep, sc, "delete")
        rep.ok(sc, "delete") if closed else rep.fail(sc, "delete failed")
    else:
        rep.fail(sc, "delete: row not found after edit", kode)
    H.clear_overlays(page)
    H.shot(page, sc)


def crud_kategori_ilap(page, rep):
    sc = "crud_kategori_ilap"
    page.goto(f"{H.BASE_URL}/kategori-ilap/")
    table_id = "kategori-table"

    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty")
    rep.ok(sc, "empty submit blocked") if ok else rep.fail(sc, "empty submit NOT blocked")
    H.clear_overlays(page)

    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    suffix = str(int(time.time() * 1000) % 100).zfill(2)
    kode = f"E{suffix}"[:2]
    nama = f"E2E Kategori ILAP {suffix}"
    page.fill("#id_id_kategori", kode)
    page.fill("#id_nama_kategori", nama)
    closed = _submit_and_wait(page, rep, sc, "create")
    rep.ok(sc, "valid create", f"{kode}/{nama}") if closed else rep.fail(sc, "valid create rejected")
    H.clear_overlays(page)
    if not closed:
        return

    # id_kategori should be locked (readonly/disabled) on edit
    _search_column(page, table_id, 0, kode)
    edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
    if edit_btn.count():
        edit_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        locked = page.is_disabled("#id_id_kategori") or page.get_attribute("#id_id_kategori", "readonly") is not None
        rep.ok(sc, "id_kategori locked on edit") if locked else rep.fail(
            sc, "id_kategori NOT locked on edit", "field editable after creation")
        page.fill("#id_nama_kategori", nama + " (edited)")
        closed = _submit_and_wait(page, rep, sc, "edit")
        rep.ok(sc, "edit") if closed else rep.fail(sc, "edit failed")
        H.clear_overlays(page)

    _search_column(page, table_id, 0, kode)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        closed = _submit_and_wait(page, rep, sc, "delete")
        rep.ok(sc, "delete") if closed else rep.fail(sc, "delete failed")
    H.clear_overlays(page)
    H.shot(page, sc)


def crud_periode_pengiriman(page, rep):
    sc = "crud_periode_pengiriman"
    page.goto(f"{H.BASE_URL}/periode-pengiriman/")
    table_id = "periode-table"

    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty")
    rep.ok(sc, "empty submit blocked") if ok else rep.fail(sc, "empty submit NOT blocked")
    H.clear_overlays(page)

    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    suffix = str(int(time.time() * 1000) % 100000)
    penyampaian = f"E2E Penyampaian {suffix}"[:50]
    penerimaan = f"E2E Penerimaan {suffix}"[:50]
    page.fill("#id_periode_penyampaian", penyampaian)
    page.fill("#id_periode_penerimaan", penerimaan)
    closed = _submit_and_wait(page, rep, sc, "create")
    rep.ok(sc, "valid create", penyampaian) if closed else rep.fail(sc, "valid create rejected")
    H.clear_overlays(page)
    if not closed:
        return

    _search_column(page, table_id, 0, penyampaian)
    edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
    if edit_btn.count():
        edit_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        page.fill("#id_periode_penerimaan", penerimaan + " (edited)")
        closed = _submit_and_wait(page, rep, sc, "edit")
        rep.ok(sc, "edit") if closed else rep.fail(sc, "edit failed")
        H.clear_overlays(page)
    else:
        rep.fail(sc, "edit: row not found after search", penyampaian)

    _search_column(page, table_id, 0, penyampaian)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        closed = _submit_and_wait(page, rep, sc, "delete")
        rep.ok(sc, "delete") if closed else rep.fail(sc, "delete failed")
    H.clear_overlays(page)
    H.shot(page, sc)


def crud_dasar_hukum(page, rep):
    sc = "crud_dasar_hukum"
    page.goto(f"{H.BASE_URL}/dasar-hukum/")
    table_id = "dasar-hukum-table"

    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty")
    rep.ok(sc, "empty submit blocked") if ok else rep.fail(sc, "empty submit NOT blocked")
    H.clear_overlays(page)

    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    suffix = str(int(time.time() * 1000) % 100000)
    deskripsi = f"E2E Dasar Hukum {suffix}"[:50]
    page.select_option("#id_kategori", index=1)
    page.fill("#id_deskripsi", deskripsi)
    H.fill_date(page, "#id_start_date", H.date_ago(30))
    H.fill_date(page, "#id_end_date", H.future_date(300))
    closed = _submit_and_wait(page, rep, sc, "create")
    rep.ok(sc, "valid create", deskripsi) if closed else rep.fail(sc, "valid create rejected")
    H.clear_overlays(page)
    if not closed:
        return

    # end_date before start_date -> should be rejected
    _open_create(page, table_id)
    page.select_option("#id_kategori", index=1)
    page.fill("#id_deskripsi", f"E2E Dasar Hukum BAD {suffix}"[:50])
    H.fill_date(page, "#id_start_date", H.date_ago(10))
    H.fill_date(page, "#id_end_date", H.date_ago(50))  # end before start
    closed = _submit_and_wait(page, rep, sc, "end<start")
    if not closed:
        rep.ok(sc, "end_date < start_date rejected")
    else:
        rep.fail(sc, "end_date < start_date NOT rejected", "accepted an end_date before start_date")
        rep.bug("dasar_hukum: end_date before start_date accepted", "LOW",
                "Creating a Dasar Hukum row with end_date earlier than start_date "
                "was accepted with no validation error.")
    H.clear_overlays(page)

    _search_column(page, table_id, 0, deskripsi)
    edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
    if edit_btn.count():
        edit_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        page.fill("#id_deskripsi", deskripsi + " (edited)")
        closed = _submit_and_wait(page, rep, sc, "edit")
        rep.ok(sc, "edit") if closed else rep.fail(sc, "edit failed")
        H.clear_overlays(page)
    else:
        rep.fail(sc, "edit: row not found after search", deskripsi)

    _search_column(page, table_id, 0, deskripsi)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        closed = _submit_and_wait(page, rep, sc, "delete")
        rep.ok(sc, "delete") if closed else rep.fail(sc, "delete failed")
    H.clear_overlays(page)
    H.shot(page, sc)


def crud_kpp(page, rep):
    """KPP requires an existing Kanwil FK; creates + cleans up its own Kanwil."""
    sc = "crud_kpp"
    page.goto(f"{H.BASE_URL}/kanwil/")
    table_id_kanwil = "kanwil-table"
    _open_create(page, table_id_kanwil)
    suffix = str(int(time.time() * 1000) % 1000).zfill(3)
    kanwil_kode = f"K{suffix}"[:3]
    kanwil_nama = f"E2E KPP-dep Kanwil {suffix}"
    page.fill("#id_kode_kanwil", kanwil_kode)
    page.fill("#id_nama_kanwil", kanwil_nama)
    if not _submit_and_wait(page, rep, sc, "setup kanwil"):
        rep.fail(sc, "setup: could not create dependent kanwil")
        return
    H.clear_overlays(page)

    page.goto(f"{H.BASE_URL}/kpp/")
    table_id = "kpp-table"

    _open_create(page, table_id)
    ok = not _submit_and_wait(page, rep, sc, "empty")
    rep.ok(sc, "empty submit blocked") if ok else rep.fail(sc, "empty submit NOT blocked")
    H.clear_overlays(page)

    if not page.locator("#crudModal.show").count():
        _open_create(page, table_id)
    kode_kpp = f"Q{suffix}"[:3]  # kode_kpp is CharField(max_length=3)
    nama_kpp = f"E2E KPP {suffix}"
    page.fill("#id_kode_kpp", kode_kpp)
    page.fill("#id_nama_kpp", nama_kpp)
    picked = H._select_first_real_option(page, "id_id_kanwil")
    closed = _submit_and_wait(page, rep, sc, "create")
    if closed:
        rep.ok(sc, "valid create", f"{kode_kpp}/{nama_kpp} kanwil={picked}")
    else:
        err = page.locator("#crudModal .alert-danger, #crudModal .invalid-feedback").first
        detail = err.inner_text().strip() if err.count() else "(no error text found)"
        rep.fail(sc, "valid create rejected", f"picked_kanwil={picked!r} server_said={detail}")
    H.clear_overlays(page)

    if closed:
        _search_column(page, table_id, 0, kode_kpp)
        edit_btn = page.locator(f"#{table_id} tbody tr [data-action='edit']").first
        if edit_btn.count():
            edit_btn.click()
            page.wait_for_selector("#crudModal form", timeout=8000)
            page.wait_for_timeout(300)
            page.fill("#id_nama_kpp", nama_kpp + " (edited)")
            closed2 = _submit_and_wait(page, rep, sc, "edit")
            rep.ok(sc, "edit") if closed2 else rep.fail(sc, "edit failed")
            H.clear_overlays(page)

        _search_column(page, table_id, 0, kode_kpp)
        del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
        if del_btn.count():
            del_btn.click()
            page.wait_for_selector("#crudModal form", timeout=8000)
            page.wait_for_timeout(300)
            closed2 = _submit_and_wait(page, rep, sc, "delete")
            rep.ok(sc, "delete") if closed2 else rep.fail(sc, "delete failed")
        H.clear_overlays(page)
    H.shot(page, sc)

    # cleanup dependent kanwil (protected FK: should fail while KPP existed,
    # here KPP is already deleted so this should succeed)
    page.goto(f"{H.BASE_URL}/kanwil/")
    _search_column(page, "kanwil-table", 0, kanwil_kode)
    del_btn = page.locator("#kanwil-table tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        _submit_and_wait(page, rep, sc, "cleanup kanwil")
    H.clear_overlays(page)


def protected_delete_guard(page, rep):
    """Try to delete a Kanwil that still has a KPP referencing it (protected
    FK) and confirm the app shows a friendly error instead of a 500."""
    sc = "crud_protected_delete"
    page.goto(f"{H.BASE_URL}/kanwil/")
    table_id = "kanwil-table"
    _open_create(page, table_id)
    suffix = str(int(time.time() * 1000) % 1000).zfill(3)
    kode = f"P{suffix}"[:3]
    nama = f"E2E Protected Kanwil {suffix}"
    page.fill("#id_kode_kanwil", kode)
    page.fill("#id_nama_kanwil", nama)
    if not _submit_and_wait(page, rep, sc, "setup kanwil"):
        rep.fail(sc, "setup: could not create kanwil")
        return
    H.clear_overlays(page)

    page.goto(f"{H.BASE_URL}/kpp/")
    _open_create(page, "kpp-table")
    kode_kpp = f"R{suffix}"[:3]  # kode_kpp is CharField(max_length=3)
    page.fill("#id_kode_kpp", kode_kpp)
    page.fill("#id_nama_kpp", f"E2E Protected KPP {suffix}")
    # select the kanwil we just made (match by visible text containing nama, a
    # much less ambiguous substring than the 3-char kode)
    picked = page.eval_on_selector(
        "#id_id_kanwil",
        """(sel, nama) => {
            const o = [...sel.options].find(o => o.textContent.includes(nama));
            if (o) { sel.value = o.value; return o.value; }
            return '';
        }""",
        nama,
    )
    if not picked:
        H._select_first_real_option(page, "id_id_kanwil")
    if not _submit_and_wait(page, rep, sc, "setup kpp"):
        rep.fail(sc, "setup: could not create dependent kpp")
        return
    H.clear_overlays(page)

    # Now try to delete the kanwil while the KPP still references it.
    page.goto(f"{H.BASE_URL}/kanwil/")
    _search_column(page, table_id, 0, kode)
    del_btn = page.locator(f"#{table_id} tbody tr [data-action='delete']").first
    if not del_btn.count():
        rep.fail(sc, "row not found for protected-delete test")
        return
    del_btn.click()
    page.wait_for_selector("#crudModal form", timeout=8000)
    page.wait_for_timeout(300)
    page.click('#crudModal button[type="submit"]')
    page.wait_for_timeout(900)
    # Expect a graceful error (toast / modal message), NOT a hard 500.
    page_text = page.content()
    server_500 = "Server Error" in page_text or "Internal Server Error" in page_text or page.url.endswith("500")
    if server_500:
        rep.fail(sc, "protected delete caused a hard error page", "")
        rep.bug("Deleting a Kanwil referenced by a KPP crashes instead of showing a friendly error",
                "HIGH", "Expected SafeDeleteMixin to catch ProtectedError and show a friendly "
                "message; instead the app rendered a hard error page.")
    else:
        rep.ok(sc, "protected delete handled gracefully (no hard 500)")
    H.shot(page, sc)

    # cleanup: delete kpp then kanwil
    page.goto(f"{H.BASE_URL}/kpp/")
    _search_column(page, "kpp-table", 0, kode_kpp)
    del_btn = page.locator("#kpp-table tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        _submit_and_wait(page, rep, sc, "cleanup kpp")
    H.clear_overlays(page)
    page.goto(f"{H.BASE_URL}/kanwil/")
    _search_column(page, "kanwil-table", 0, kode)
    del_btn = page.locator("#kanwil-table tbody tr [data-action='delete']").first
    if del_btn.count():
        del_btn.click()
        page.wait_for_selector("#crudModal form", timeout=8000)
        page.wait_for_timeout(300)
        _submit_and_wait(page, rep, sc, "cleanup kanwil")
    H.clear_overlays(page)


SIMPLE_MODELS = [
    ("crud_kategori_wilayah", "kategori-wilayah", "kategori-table", 50),
    ("crud_jenis_tabel", "jenis-tabel", "jenis-tabel-table", 50),
    ("crud_status_data", "status-data", "status-data-table", 25),
    ("crud_status_penelitian", "status-penelitian", "status-penelitian-table", 25),
    ("crud_bentuk_data", "bentuk-data", "bentuk-data-table", 25),
    ("crud_cara_penyampaian", "cara-penyampaian", "cara-penyampaian-table", 25),
    ("crud_media_backup", "media-backup", "media-backup-table", 25),
]


def run(page, rep):
    H.login(page)
    for sc, slug, table_id, max_len in SIMPLE_MODELS:
        try:
            crud_single_text_field(page, rep, sc, slug, table_id, max_len)
        except Exception as e:
            H.shot(page, f"{sc}_EXCEPTION")
            rep.fail(sc, "exception", str(e))

    for fn in (crud_kanwil, crud_kategori_ilap, crud_periode_pengiriman,
               crud_dasar_hukum, crud_kpp, protected_delete_guard):
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
