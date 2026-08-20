## Overview
This PR introduces the **Unified PIC Management** interface, implements bidirectional global cross-filtering (`runMasterCascade`) across modal filters and summary cards, fixes access control mixins for Kasi roles, and adds automatic cross-tab session restoration with auto-redirect to the "Dashboard". Additionally, UI/UX styling across modal forms and buttons has been standardized according to project design guidelines.

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

### 2. 🔐 Access Control & Role Mixin Hardening (`mixins.py`)
- **Kasi Role Access Enforcement**: Explicitly allowed `kasi_p3de`, `kasi_pide`, and `kasi_pmde` roles across `UserP3DERequiredMixin`, `UserPIDERequiredMixin`, and `UserPMDERequiredMixin`.
- **403 Forbidden Handling**: Enforced `raise_exception = True` on role mixins to return proper 403 Forbidden status codes for unauthorized access.

### 3. 🔄 Multi-Tab Session Synchronization & Auto-Redirect (`base.html` & `login.html`)
- **Cross-Tab Auth Sync**: Added `localStorage` event broadcasting (`diamond_login_event`) to synchronize login/logout states instantly across multiple open browser tabs.
- **Auto-Redirect to "Dashboard"**: Configured `redirect_authenticated_user=True` on the `login` view so active sessions automatically redirect to "Dashboard" when navigating to the login page from another tab.
- **Session Restored Event**: Dispatched `diamond:session-restored` event to reset idle timer counters seamlessly upon cross-tab authentication.

### 4. 🎨 UI/UX & Modal Button Standardization
- **Cancel Button Styling**: Standardized all "Batal" (Cancel) buttons across modal forms to use neutral `btn-light text-secondary` styling (`border-radius: 6px`, avoiding heavy solid uppercase styles).
- **Modal Header Styling**: Aligned modal header backgrounds with the modern gradient style from `home.html`.
- **Table Index Badges**: Updated row number badges from circular shapes to rounded rectangles (`border-radius: 6px`).

---

## Verification & Testing
- [x] Verified filter cascading logic on PIC, ILAP, and Jenis Data dropdowns.
- [x] Checked responsive layout and text truncation on Matriks Penugasan table.
- [x] Tested multi-tab login/logout broadcast events and automatic redirect to "Dashboard".
- [x] Validated access control for Kasi roles (`kasi_p3de`, `kasi_pide`, `kasi_pmde`).
- [x] Verified unit tests `test_kasi_role_access.py` and `test_profil_pic.py` (77 passed).
- [x] Validated modal header and "Batal" button rendering across all master data forms.
