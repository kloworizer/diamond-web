# Diamond Web Design and UI/UX Development Guidelines

This document defines the visual design system, UI layout conventions, and coding patterns to ensure consistency across the Diamond Web application. All developers and AI agents must follow these guidelines strictly when writing frontend code.

---

## 1. Typography & Theme Colors
*   **Fonts**: Primary font is **Inter/Outfit** or standard clean sans-serif. Do not use generic system serif fonts.
*   **Brand Color**: Diamond Blue (`#00BDFB` or `#0c92ff` for links/accents).
*   **Danger Color**: Red (`#ef4444` or `btn-danger`).
*   **Backgrounds**: Dark/Slate details paired with clean off-white backgrounds (`#f8fafc`).
*   **Consistency**: Avoid hardcoding raw color hex codes in style tags. Prefer Bootstrap classes (e.g. `text-muted`, `text-dark`, `bg-light`) or CSS variables.

---

## 2. Rounded Corners & Button Styling
*   **Buttons**: Do NOT override button border radius with custom styling (e.g. `border-radius: 8px`). Allow buttons to inherit the global Bootstrap border-radius for visual uniformity across the project.
*   **Modal & Cards**: Cards and custom premium containers can use rounded corners (e.g. `border-radius: 12px` or `border-radius: 16px`).
*   **Inputs**: Form inputs and select dropdowns must have consistent heights (`40px` to `42px`) and rounded corners (`8px`). When setting custom heights (e.g. `36px`, `38px`, `40px`), always override padding and line-height (`padding-top: 0 !important; padding-bottom: 0 !important; line-height: normal !important;`) to prevent text from being cut off or clipped at the bottom. For native Webkit `input[type="datetime-local"]`, use `display: inline-flex !important; align-items: center !important; height: 100% !important;` on the `::-webkit-datetime-edit` inner element to center content vertically, and set `color: inherit !important` on `::-webkit-datetime-edit-text` to ensure native separator characters (like slashes and colons) match the text input's placeholder or active color.
*   **Floating Cards (Stretch Card Layout)**:
    *   For premium cards like `class="card stretch stretch-full"`, apply a spacious custom padding:
        *   **Padding top**: Use the default Bootstrap theme top padding (no overrides).
        *   **Padding bottom**: `36px` on the card-body (distance from card bottom to the table/content).
        *   **Padding left and right**: `28px` on both the card-header and card-body to provide a beautiful floating gutter.
        *   **Header Border**: Set `border-bottom: none !important;` on the `.card-header` to avoid a double-line appearance when paired with a bordered table container.

---

## 3. Data Tables Layout (Premium Grid)
*   **Scrolling & Overflow**: Data tables must support vertical scrolling restricted only to the table body (`tbody`) using a scrollable container.
*   **Sticky Elements**:
    *   Table headers (`thead`) must be `position: sticky; top: 0; z-index: 10;`.
    *   Actions columns (`col-actions`) must be `position: sticky; right: 0; z-index: 5;` with a solid background color to keep them visible when scrolling horizontally.
*   **Spacing & Actions**: Table rows must be compact. Padding should be dense (`8px 10px`) similar to standard monitoring boards. Actions buttons inside tables (e.g. in an 'Aksi' column) MUST be perfectly centered horizontally (`d-flex justify-content-center gap-1`) rather than stacking vertically or being left-aligned.
*   **Column Search Inputs**: Inner table header search inputs (e.g. inside `#column-search-row input`) must be compact: `height: 28px !important`, `font-size: 11px !important`, `padding: 2px 8px !important`, and `border-radius: 6px !important` to prevent bloating the table header row height.
*   **Footer Centering**: Center DataTable info ("Showing 1 to 10...") and pagination controls vertically by applying `align-items: center !important` to the wrapper row (`.dt-layout-row` or `.row`). To ensure pixel-perfect vertical alignment, wrap the text elements in `display: inline-flex; align-items: center;` and match their height to the height of the pagination controls (e.g., `height: 38px`).

---

## 4. Modal Dialog Layouts (Figma Standards)
*   **Sizing & Structure**: 
    *   Avoid nested `.modal-content` wrappers in AJAX-loaded templates (use `w-100` for the outer container instead).
    *   Use `.modal-lg` for data-heavy entry forms (Tambah/Ubah).
    *   Use `.modal-adjustable` (with `min-width: 480px; max-width: 750px;`) for Delete confirmation modals so they resize dynamically based on content length.
*   **Header Styling**:
    *   **Tambah/Ubah**: Left-aligned titles with a circular icon on the left (blue `feather-plus` for Tambah, yellow `feather-edit-2` for Ubah).
    *   **Hapus**: Centered layout with a prominent red circular trash icon (`feather-trash-2`) at the top.
*   **Footer Buttons & Warnings**: Use Figma-styled buttons for actions (`btn-figma-primary` for Simpan, `btn-figma-danger` for Hapus, and `btn-figma-outline` for Batal). Always align footer buttons to the right. For Delete confirmation modals, use `justify-content-between align-items-center` on the footer. Place the warning text on the left side, wrapped in a soft amber/yellow warning box (`background-color: #fffbeb; color: #b45309;`) with an alert icon, and strictly keep the original wording intact. Place the action buttons on the right side.
*   **Dynamic Data Tables**:
    *   When listing complex data (e.g. PIC details, Ticket selections) inside a modal body, use clean, structured HTML tables instead of plain text lists.
    *   **Text Wrapping**: For Delete confirmation tables containing long strings (e.g. Nama ILAP), apply `white-space: normal !important; word-break: break-word;` to the table cells so the text wraps beautifully to a new line when the modal reaches its maximum width, preventing harsh truncation.
*   **Spacing**: 
    *   Keep the top margin of `.modal-body` tight (`pt-2 px-4 pb-1`) to avoid massive empty spaces under the header.
    *   For `.modal-footer`, use transparent backgrounds (`background: transparent !important; border-top: 0;`) and tight top padding (`pt-0 px-4 pb-4`).
*   **AJAX Session Expiry Protection**: In JavaScript functions that load modal HTML or submit modal forms via AJAX, always check if the server returned the login page (due to an expired session). For example, check if the response HTML string contains "Login" and "password", and if so, gracefully redirect the main window to the login page (`window.location.href = '/accounts/login/?next=' + window.location.pathname;`) instead of rendering the login form inside the modal.

---

## 5. Global Download Toast Notifications
*   **Placement**: Bottom right corner (non-blocking notification toast).
*   **Entry Animation**: Smooth hardware-accelerated slide-in from the right (`transform: translate3d(120%, 0, 0)`) fading in over `0.5s` using a `cubic-bezier(0.16, 1, 0.3, 1)` curve.
*   **Exit Animation**: Smooth slide-out to the right (`transform: translate3d(80px, 0, 0)`) fading to `opacity: 0` over `0.8s`.
*   **Progress Indicator**: A thin `4px` progress/loading bar at the bottom of the toast that shrinks from `100%` to `0%` over 4 seconds, automatically triggering the fade-out dismissal.
*   **Manual Close**: Click listener on close cross button (`x`) overrides Bootstrap defaults to play the same smooth custom exit transition.
*   **Triggering**: Whenever editing a page containing PDF or Excel export buttons, bind a click event listener that invokes `showDownloadToast()` before initiating the download.

## 6. Backend Modification Policy
*   **Frontend-First Approach**: As a strict rule, prioritize frontend-only solutions (HTML/CSS/JS/Templates) for any UI/UX tasks.
*   **Avoid Backend Changes**: Do not modify backend files (views, models, forms, urls, APIs) unless absolutely necessary.
*   **Mandatory Consultation**: If a feature cannot be implemented without a backend change, STOP and ask the user for permission. Explain clearly *why* the backend needs to change, what alternative frontend workarounds were considered (and why they failed), and exactly *what* files will be modified. Do not proceed with backend changes without explicit approval.
