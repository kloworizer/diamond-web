## Overview
This PR introduces the **Unified PIC Management** interface, implements bidirectional global cross-filtering (`runMasterCascade`) across modal filters and summary cards, enhances Kasi role access controls and supervisor scoping, and adds context-aware multi-tab session restoration with auto-dismissal overlays (preserving unsaved form drafts). Additionally, UI/UX styling across modal forms and buttons has been standardized according to project design guidelines.

> [!NOTE]
> The experimental `bulk_teliti` view module has been excluded from this branch as requested and will be handled in a separate feature branch.

---

## Key Changes

### 1. 🗂️ Unified PIC Management & Bidirectional Cascading Filters (`unified_list.html` & `views/pic.py`)
- **Unified Tabbed Interface**: Consolidated "Matriks Penugasan", "PIC P3DE", "PIC PIDE", and "PIC PMDE" views into a single unified tabbed layout (`pic_unified_list`).
- **Bidirectional Cascading Filter (`runMasterCascade`)**: Implemented dynamic cross-filtering where selecting a PIC automatically filters applicable "Nama ILAP" and "Jenis Data", and vice versa.
- **Filter Modal Reordering**: Reordered filter hierarchy to **PIC -> Nama ILAP -> Jenis Data**.
- **PIC Display Format**: Standardized PIC name formatting to `Nama Lengkap - Username/NIP`.
- **Text Overflow & Tooltip**: Prevented cell overflow in the Matrix table using `text-truncate` with native title tooltips on hover.
- **Section Badge Color Palette**: Updated P3DE, PIDE, and PMDE icon colors in summary cards to align with section identity color standards.
- **Duplicate DataTables Numbering Fix**: Fixed duplicate row numbering in "PIC Data" tables where local badge rendering conflicted with global DataTables row numbering.

### 2. 🔐 Access Control, Kasi Role Scoping & RBAC (`mixins.py` & `seksi_queue.py`)
- **Kasi Supervisor Scope**: Configured `pic_scope` in `seksi_queue.py` so Kasi roles (`kasi_p3de`, `kasi_pide`, `kasi_pmde`) act as section supervisors with visibility over all section tickets, while regular staff are scoped to their assigned tickets.
- **Kasi Role Access Enforcement**: Explicitly allowed `kasi_p3de`, `kasi_pide`, and `kasi_pmde` roles across `UserP3DERequiredMixin`, `UserPIDERequiredMixin`, and `UserPMDERequiredMixin`.
- **403 Forbidden Handling**: Enforced `raise_exception = True` on role mixins to return proper 403 Forbidden status codes for unauthorized AJAX requests.

### 3. 🔄 Multi-Tab Session Synchronization & Silent Restoration (`base.html` & `login.html`)
- **Context-Aware Session Expired Modal**:
  - **Form Pages**: Displays `Sesi Berakhir!` with a green success text explicit reassurance (`✓ Draf formulir Anda tetap aman`) that unsaved form drafts remain safe.
  - **Non-Form Pages**: Displays standard session expiration notices.
- **Cross-Tab Auto-Dismiss Overlay**: When logging back in via Tab C, open tabs (Tab A & B) automatically detect the active session, update CSRF tokens silently, and dismiss the timeout overlay **without a full page reload**, preserving unsaved form inputs.
- **Focus & Storage Sync**: Added `focus` and client-side `storage` event listeners for instant cross-tab session restoration.
- **Auto-Redirect on Login**: Configured `redirect_authenticated_user=True` on `login` view to automatically redirect authenticated sessions to "Dashboard".

### 4. ⚡ Quick Action Modals from Dashboard (`views/home.py` & `home.html`)
- **Direct Modal Triggers**: Enabled quick action buttons ("Proses Identifikasi", "Belum Diteliti", "Backup Data", "Tanda Terima") directly from the "Dashboard" via AJAX modals without requiring page navigation.

### 5. 🎨 UI/UX & Modal Button Standardization
- **Cancel Button Styling**: Standardized all "Batal" (Cancel) buttons across modal forms to use neutral `btn-light text-secondary` styling (`border-radius: 6px`, avoiding heavy solid uppercase styles).
- **Modal Header Styling**: Aligned modal header backgrounds with the modern gradient style from `home.html`.
- **Table Index Badges**: Updated row number badges from circular shapes to rounded rectangles (`border-radius: 6px`).

---

## Verification & Testing
- [x] Verified filter cascading logic on PIC, ILAP, and Jenis Data dropdowns.
- [x] Tested multi-tab session expiration, cross-tab login auto-dismissal, and form draft preservation.
- [x] Validated Kasi role supervisor scoping (`kasi_p3de`, `kasi_pide`, `kasi_pmde`) and RBAC permissions.
- [x] Verified unit tests `test_login_form_markup.py`, `test_kasi_role_access.py`, and `test_profil_pic.py` (all passed).
- [x] Validated modal header and "Batal" button rendering across all master data forms.
