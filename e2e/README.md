# DIAMOND Tiket Workflow — Playwright E2E Tests

Local-only end-to-end tests that drive the tiket workflow through the real UI
with Playwright (uses the **system Google Chrome** via `channel="chrome"`, so no
Chromium download is required). This whole folder is git-ignored.

## What it covers

Full workflow, exhausting the documented paths (see `docs/status_tiket_flow.md`):

| Scenario file | Path |
|---|---|
| `test_happy_path.py` | Direkam → Diteliti → Dikirim ke PIDE → Identifikasi → Pengendalian Mutu → Selesai |
| `test_alt_paths.py`  | Data Tidak Tersedia → Selesai; Penelitian baris_lengkap==0 → Selesai; Batalkan (P3DE); Dikembalikan (PIDE) |
| `test_form_validation.py` | Negative / boundary inputs on the rekam form and the penelitian / transfer / selesaikan modals |

Every workflow modal is exercised through the actual AJAX UI: rekam form,
rekam backup (Bagian C at rekam-time), buat tanda terima, rekam hasil
penelitian, generate ND pengantar, kirim ke PIDE, identifikasi, transfer ke
PMDE, selesaikan, batalkan, dikembalikan.

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
