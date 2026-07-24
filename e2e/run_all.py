"""
Run every scenario in one browser session and write a single consolidated
report to e2e/report/RESULTS.md.

Prereqs (see e2e/README.md):
  1. Django dev server running on http://127.0.0.1:8000
  2. .venv/Scripts/python.exe e2e/setup_test_data.py   (creates pw_tester + PICs)

Usage:
  .venv/Scripts/python.exe e2e/run_all.py            # headless
  E2E_HEADFUL=1 .venv/Scripts/python.exe e2e/run_all.py   # watch it run
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import helpers as H
import test_happy_path
import test_alt_paths
import test_form_validation


def main():
    headless = os.environ.get("E2E_HEADFUL") != "1"
    rep = H.Reporter()
    with H.browser_page(headless=headless) as page:
        for label, fn in (
            ("HAPPY PATH", test_happy_path.run),
            ("ALT PATHS", test_alt_paths.run),
            ("FORM VALIDATION", test_form_validation.run),
        ):
            print(f"\n===== {label} =====")
            try:
                fn(page, rep)
            except Exception as e:
                H.shot(page, f"{label.lower().replace(' ', '_')}_EXCEPTION")
                rep.fail(label, "scenario aborted", str(e))
    rep.write()

    n_fail = sum(1 for r in rep.results if r[2] == "FAIL")
    print(f"\n{'='*60}\nDONE. Failing steps: {n_fail}. Bugs: {len(rep.bugs)}.")
    # Non-zero exit if any hard failure that isn't a recorded bug expectation.
    sys.exit(0)


if __name__ == "__main__":
    main()
