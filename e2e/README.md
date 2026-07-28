# DIAMOND Tiket Workflow — Playwright E2E Tests

Local-only end-to-end tests that drive the tiket workflow through the real UI
with Playwright (uses the **system Google Chrome** via `channel="chrome"`, so no
Chromium download is required). This folder is committed (added in 44fe656),
report output and screenshots included.

## What it covers

Full workflow, exhausting the documented paths (see `docs/status_tiket_flow.md`):

| Scenario file | Path |
|---|---|
| `test_happy_path.py` | Direkam → Diteliti → Dikirim ke PIDE → Identifikasi → Pengendalian Mutu → Selesai |
| `test_alt_paths.py`  | Data Tidak Tersedia → Selesai; Penelitian baris_lengkap==0 → Selesai; Batalkan (P3DE); Dikembalikan (PIDE) |
| `test_form_validation.py` | Negative / boundary inputs on the rekam form and the penelitian / transfer / selesaikan modals |
| `test_form_interactions.py` | Every AJAX CRUD form (Tambah **and** Edit): does the form still *work* after the server rejects it? |
| `test_form_interactions_pages.py` | Same question for the non-CRUD surfaces: tiket detail workflow modals, the 12 `#filter-form` report pages, and the full-page profil form |

Every workflow modal is exercised through the actual AJAX UI: rekam form,
rekam backup (Bagian C at rekam-time), buat tanda terima, rekam hasil
penelitian, generate ND pengantar, kirim ke PIDE, identifikasi, transfer ke
PMDE, selesaikan, batalkan, dikembalikan.

`test_form_interactions.py` covers a failure mode the others structurally
cannot: they all submit *valid* data and never look at the form again. Every
CRUD page shares one AJAX pattern — on rejection it replaces the modal markup
with `.html(response.html)`, which silently destroys every listener bound to
the old DOM. So for all 27 form pages it forces a server-side rejection and
then asserts the form is still usable: modal still open, errors visible,
flatpickr/select2 still attached, typed values preserved, dependent dropdowns
still firing, and no uncaught JS. Both Tambah and Edit are driven.

The Edit pass never risks overwriting a real row: instead of blanking fields
(which an all-optional form could legitimately save) it overflows every text
field past its `max_length`, or, for select-only forms, injects a choice that
matches nothing. Both are guaranteed rejections.

`test_form_interactions_pages.py` applies the same question to the tiket detail
modals, which hand-roll their own `fetch` instead of using the CRUD pages'
delegated handler. Two rules it depends on:

- **Click the real submit button.** `form.dispatchEvent(new Event('submit'))`
  never triggers the browser's own form submission, so a form that lost its AJAX
  listener looks like it merely "did nothing" when a real user actually gets a
  full page navigation.
- **Read the response body inside the handler.** These endpoints answer 200 for
  both a save and a rejection; the outcome is the JSON `success` flag. A success
  triggers a reload, after which the body is no longer retrievable, so a
  deferred `.json()` raises and the success is misread as a rejection.

Confirmation-only modals (Generate ND Pengantar, Identifikasi) have no editable
field, so an empty submit is legitimately valid — they are detected and skipped
rather than submitted, since clicking would advance the tiket for real.

## Setup

```bash
# 1. Install Playwright (already in .venv) and confirm system Chrome is used.
.venv/Scripts/python.exe -m pip install playwright

# 2. Create an isolated test user (pw_tester) that is an active PIC for all
#    three roles on one sub-jenis-data, so a single login can drive the whole
#    flow through the UI. Idempotent.
.venv/Scripts/python.exe e2e/setup_test_data.py

# 3. Run the Django dev server (DEBUG=True) in another terminal.
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

## Run

```bash
# All scenarios, one consolidated report:
.venv/Scripts/python.exe e2e/run_all.py

# Watch it in a real browser window:
E2E_HEADFUL=1 .venv/Scripts/python.exe e2e/run_all.py

# Or run a single scenario:
.venv/Scripts/python.exe e2e/test_happy_path.py
```

Output:
- `report/RESULTS.md` — bugs/findings + a per-step PASS/FAIL log
- `report/results.json` — machine-readable
- `report/screenshots/*.png` — full-page screenshots at each milestone

## Notes / test-only side effects

- Creates a superuser `pw_tester` and three `PIC` rows on sub-jenis `AS0010101`
  (ILAP id 1). These live in the dev `db.sqlite3` (already git-ignored).
- Each run creates a handful of real tikets in the dev DB (statuses vary).
- The detail-page **Transfer ke PMDE** and **Selesaikan Tiket** buttons render
  with a hardcoded `disabled` attribute; the tests force-enable them to keep
  exercising the downstream flow and separately report the disabled state.
