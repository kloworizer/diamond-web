# PR Title
`feat(tiket): enhance filter UI cascading, status badges, and datatables formatting`

---

# PR Description

## Summary
This PR improves the UI/UX consistency, cascading filter responsiveness, and status badge visuals in the **"Daftar Tiket"** module and global base templates.

## Changes Introduced

### 1. Filter UI & Cascading Options (`Daftar Tiket`)
- **Card Header Styling:** Redesigned filter segment containers to use full-width gradient card headers (`linear-gradient`) matching the **"Filter Data"** accordion design.
- **Label Consistency:** Renamed the filter label from `"Status Tiket"` to `"Status"` to maintain 1:1 alignment with the table column header.
- **Race Condition Prevention:** Implemented `activeFilterAjax.abort()` to prevent out-of-order AJAX responses when switching between multiple **Select2** dropdowns (e.g., **"Tahun"**, **"Periode"**, **"Kategori ILAP"**).
- **Select2 Status Styling:** Rendered **Select2** dropdown options and selected tags for **"Status"** using full-color badges with **Feather Icons** (`status-perekaman`, `status-diteliti`, `status-selesai`, etc.).

### 2. DataTables Output & Formatting
- **Full-Color Status Badges:** Updated DataTables column rendering for **"Status"** to output full-color badge styles identical to the **"Detail Tiket"** view.
- **Typography & Spacing:** Refined the table footer info text (*"Menampilkan 1 - 10 dari 408 tiket"*) to use medium font weight (`fw-medium`), proper non-breaking spaces (`&nbsp;`), and subtle vertical dividers for filter status (`Difilter dari MAX data`).

### 3. Global UI Standards & Fixes
- **Button Casing & Neutral Cancel Standard:** Removed forced uppercase transformation on `.btn` elements and updated cancel button variants to neutral light styles (`btn-light text-secondary`) in accordance with project design guidelines.
- **Toast Z-Index & Multi-Tab Session Overlay:** Elevated **Toast Container** `z-index` above floating action buttons (FAB) and fixed `<style>` syntax warnings in `base.html`.

## Verification
- Verified dynamic cascading dropdown behavior in **"Daftar Tiket"** without clearing active selections unexpectedly.
- Confirmed full-color **"Status"** badge rendering in both **Select2** filter dropdowns and DataTables columns.
- Tested DataTables pagination, sorting, and responsive layout across desktop and mobile browsers.
