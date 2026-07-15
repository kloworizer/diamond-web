# CLAUDE.md — Panduan Kerja Diamond Web

## Stack Teknis

| Layer | Teknologi |
|-------|-----------|
| Backend | Django (Python 3) |
| Template | Django Template Language (DTL) + HTML5 |
| CSS | Bootstrap 5 + SCSS theme (NXL template) |
| JS | Vanilla JS + jQuery + Feather icons |
| Database | Akses via Django models — **jangan ubah tanpa persetujuan** |
| Vendor (via CDN/static) | DataTables, Select2, SweetAlert2, DateRangePicker, Tagify |

## Prinsip Utama

1. **UI = Enterprise, konsisten, aksesibel.** Profesional, bersih, komponen seragam.
2. **Backend = Best practice Django.** Jangan ubah struktur database/models/migrations tanpa persetujuan.
3. **Clarify before act.** Jika ada ambiguitas, tanya dulu.

## Tema & Design Tokens (SCSS)

Gunakan variabel SCSS yang sudah ada di `_bs-custom-variables.scss` sebagai satu-satunya sumber design tokens. Jangan tambah layer CSS variable custom baru tanpa persetujuan.

- **Warna primary**: `$blue: #00BDFB` / `$primary`
- **Warna success**: `$green: #17c666` / `$success`
- **Warna danger**: `$red: #ea4d4d` / `$danger`
- **Warna warning**: `$yellow: #ffa21d` / `$warning`
- **Warna info**: `$cyan: #3dc7be` / `$info`
- **Warna body-bg**: `$body-bg: #f0f2f8`
- **Warna text**: `$body-color: #4b5563` / `$text-muted: #64748b`
- **Border radius**: `$border-radius: 4px` / `$border-radius-lg: 6px` / `$border-radius-sm: 2px`
- **Spacing cards**: `$card-spacer-y/x: 25px`
- **Spacing modals**: `$modal-inner-padding: 25px; $modal-header-padding-y/x: 25px`
- **Font size**: `h6: 15px, h5: 16px, h4: 20px, h3: 24px, h2: 28px, h1: 36px`
- **Font weight utility**: `fw-light(200)` s.d. `fw-black(900)`

### Aturan Penggunaan CSS

1. **Gunakan utility kelas Bootstrap/NXL sebanyak mungkin.** Hindari CSS inline (`<style>` di dalam template) — taruh di `style` block template atau file terpisah.
2. **Jangan menimpa variabel SCSS**—semua modifikasi tema lewat `_bs-custom-variables.scss` saja.
3. **Tambahan CSS kecil** — gunakan `<style>{% block style %}{% endblock %}</style>` di template spesifik (bukan inline di elemen).

## Komponen Reusable — Panduan

Setiap komponen yang muncul di lebih dari 2 halaman harus mengikuti pola konsisten ini. Implementasi partial berbasis file akan menyusul — untuk sekarang ikuti **panduan template**:

### Filter Bar (`{% block filter_bar %}`)
```
<button class="btn btn-sm btn-outline-primary" ...>
  <i class="feather-{icon}"></i> {Label}
</button>
<select class="form-select form-select-sm" style="width:fit-content;min-width:180px">
  {option loop}
</select>
```
- Semua filter dalam 1 baris horizontal, `d-flex gap-2 align-items-center flex-wrap`.
- Select gunakan `form-select form-select-sm`.
- Tombol aksi: `btn btn-sm btn-primary` untuk utama, `btn btn-sm btn-outline-primary` untuk sekunder.

### Data Table
```
<div class="table-responsive">
  <table id="{id}" class="table table-hover align-middle w-100">
    <thead>
      <tr>
        <th>{header}</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</div>
```
- Wrapper `<div class="table-responsive">`.
- Wajib `table table-hover align-middle` (dan `w-100` jika butuh flex).
- Inisialisasi DataTables di JS:
  ```js
  $('#{id}').DataTable({
    ordering: true, searching: false, lengthChange: false, pageLength: 25,
    language: { emptyTable: "...", zeroRecords: "..." },
    columnDefs: [{ orderable: false, targets: [cols] }]
  });
  ```

### Page Header
```
<div class="page-header">
  <div class="row align-items-center">
    <div class="col">
      <h4 class="page-title">{title}</h4>
      <ul class="breadcrumb">
        <li class="breadcrumb-item"><a href="{url}">{parent}</a></li>
        <li class="breadcrumb-item active">{current}</li>
      </ul>
    </div>
    <div class="col-auto">{action_buttons}</div>
  </div>
</div>
```

### Modal (via Bootstrap)
```
<div class="modal fade" id="{id}" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header"><h5 class="modal-title">{title}</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">{body}</div>
      <div class="modal-footer">{footer_buttons}</div>
    </div>
  </div>
</div>
```
- `modal-dialog` bisa: default, `modal-lg`, `modal-xl`, `modal-sm`.

### Status Badge
```
<span class="badge bg-{color}">{label}</span>
```
- `bg-primary` (proses), `bg-success` (selesai/valid), `bg-danger` (batal/invalid), `bg-warning` (pending/hati-hati), `bg-info` (info), `bg-secondary` (nonaktif).

### Tombol Aksi di Tabel
```
<div class="btn-group" style="gap:2px">
  <a href="{detail_url}" class="btn btn-sm btn-outline-info" title="Detail"><i class="feather-eye"></i></a>
  <a href="{edit_url}" class="btn btn-sm btn-outline-primary" title="Edit"><i class="feather-edit"></i></a>
  <a href="{delete_url}" class="btn btn-sm btn-outline-danger" title="Hapus"><i class="feather-trash-2"></i></a>
</div>
```
- `btn btn-sm btn-outline-{color}` — ikon saja, tanpa teks.
- Tooltip via `title` (fallback) atau Bootstrap tooltip jika sudah terpasang.

### Form Field
```
<div class="form-group">
  <label class="form-label">{label} {required}<span class="text-danger">*</span>{/required}</label>
  <input type="{type}" name="{name}" class="form-control" {...attrs} />
  {errors}
</div>
```
- Label pakai `form-label` (atau `col-form-label` di layout grid).
- Input: `form-control`, Select: `form-select`, Textarea: `form-control`.
- Jika select2: `class="form-select select2"` + `$('.select2').select2({theme:'bootstrap-5',width:'100%'})`.

## Aksesibilitas

- Gunakan label eksplisit (`<label for="...">` atau `aria-label`).
- Pastikan kontras teks cukup (min 4.5:1 untuk teks normal).
- Fokus keyboard: tombol aksi dan link harus dapat di-tab dan di-Enter.
- Modal: `tabindex="-1"` + `aria-hidden="true"` + `aria-labelledby`.
- Ikon tanpa teks: tambah `title` dan/atau `aria-hidden="true"` + `sr-only` fallback.

## Scripting JS

- Vanilla JS + jQuery (tersedia global).
- DataTables: inisialisasi dengan opsi minimal (searching, ordering, pageLength).
- Select2: gunakan theme `bootstrap-5`.
- SweetAlert2: untuk konfirmasi hapus `Swal.fire({...})`.
- Semua event binding gunakan `document.addEventListener` (delegasi), bukan `onclick` di HTML.

## Alur Kerja

1. **Clarify** — pahami scope, tanya jika ambigu.
2. **Plan** — untuk perubahan >1 file, rencanakan dulu.
3. **UI task** — selalu konsisten dengan panduan di atas; jika halaman yang disentuh sudah punya pola sendiri, ikuti pola yang ada dan konsistenkan.
4. **Backend changes** — jangan sentuh models/migrations/db tanpa persetujuan.
5. **Verify** — cek hasilnya (tampilan, aksesibilitas, tidak broken).
6. **Report** — apa yang berubah, bagaimana validasinya.
