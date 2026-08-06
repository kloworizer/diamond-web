# Diamond Web — Design Guideline

> Versi 1.0 · 30 Juli 2026
> Acuan desain untuk seluruh tim yang mengembangkan antarmuka Diamond Web.

---

## 1. Prinsip Desain

| Prinsip | Penjelasan |
|---|---|
| **Clean & Professional** | Prioritaskan keterbacaan dan kejelasan di atas estetika berlebihan |
| **Monokromatik dengan aksen status** | Dominan biru/slate. Warna lain hanya untuk konteks semantik (success, danger, warning) |
| **Compact** | Maksimalkan informasi per layar. Font 11–12.5px, padding minimal tapi nyaman |
| **Konsisten** | Semua komponen sejenis menggunakan pola yang sama persis |

---

## 2. Color Palette

### Primary (Brand)

```
--color-primary:       #00BDFB   ← warna utama brand (biru terang)
--color-primary-dark:  #009ECC   ← hover state primary
--color-primary-soft:  #e0f7ff   ← background ringan / badge soft
```

### Neutral (Teks & Struktur)

```
--color-text-dark:     #0f172a   ← teks judul / heading utama
--color-text-body:     #1e293b   ← teks konten
--color-text-muted:    #64748b   ← label field, caption
--color-text-faint:    #94a3b8   ← sub-label, placeholder, disabled

--color-border:        #e2e8f0   ← border card, divider
--color-border-light:  #f1f5f9   ← divider halus dalam card
--color-bg-card:       #f8fafc   ← background card/section (light grey)
--color-bg-white:      #ffffff   ← background modal, page
```

### Semantic Colors (HANYA untuk status/konteks)

```
--color-success:       #16a34a   ← data diterima, konfirmasi berhasil
--color-success-soft:  #f0fdf4   ← background badge success
--color-success-border:#bbf7d0

--color-danger:        #ef4444   ← error, hapus, data kritis
--color-danger-soft:   #fef2f2
--color-danger-border: #fecaca

--color-warning:       #f59e0b   ← peringatan, perhatian
--color-warning-soft:  #fffbeb
--color-warning-border:#fde68a

--color-info:          #3b82f6   ← informasi netral
--color-info-soft:     #eff6ff
--color-info-border:   #bfdbfe
```

> ⚠️ **Larangan:** Jangan gunakan warna semantik untuk dekorasi atau estetika semata.
> Warna merah hanya untuk `danger`, hijau hanya untuk `success`, dll.

---

## 3. Tipografi

### Font Family
- **UI Font:** Sistem default (diatur oleh tema Duralux) — Inter / Roboto / -apple-system
- **Monospace:** `'Courier New', monospace` — khusus kode, nomor tiket

### Skala Font Size

| Penggunaan | Size | Weight | Color |
|---|---|---|---|
| Modal title / heading | `15px` | `fw-bold` | `#0f172a` |
| Section / cluster label | `11px` | `700` | `#94a3b8` |
| Konten / nilai field | `12.5px` | `fw-semibold` | `#1e293b` |
| Label field | `10.5–11px` | normal | `#94a3b8` |
| Sub-caption / badge label | `10px` | normal | `#94a3b8` |
| Subtitle di bawah modal title | `10px` | `fw-semibold` | `text-muted` |

> ✅ Jangan campurkan `14px` dan `13px` dalam satu konteks yang sama.

### Aturan Casing Teks

| Elemen | Casing |
|---|---|
| Modal title | `UPPERCASE` |
| Section / cluster label | `UPPERCASE` |
| Subtitle/tagline modal | `UPPERCASE` |
| Label field | Sentence case |
| Tombol aksi | `UPPERCASE` |
| Tooltip | Sentence case |
| Konten / data | Ikuti data aslinya |

---

## 4. Komponen: Modal

### Struktur HTML Standar

```html
<div class="modal fade" id="namaModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered" style="max-width: 480px;">
    <div class="modal-content"
         style="border-radius: 12px; border: none; box-shadow: 0 8px 30px rgba(0,0,0,0.12);">

      <!-- HEADER -->
      <div class="modal-header border-bottom-0 pb-0 pt-4 px-4">
        <div class="d-flex align-items-center gap-2">
          <div class="d-flex align-items-center justify-content-center"
               style="width: 36px; height: 36px; border-radius: 50%;
                      background-color: [SOFT_COLOR]; color: [ICON_COLOR]; flex-shrink: 0;">
            <i class="feather-[icon]" style="font-size: 16px;"></i>
          </div>
          <div>
            <h5 class="modal-title fw-bold mb-0"
                style="font-size: 15px; color: #0f172a;
                       text-transform: uppercase; letter-spacing: 0.5px;">
              Judul Modal
            </h5>
            <span class="text-muted fw-semibold text-uppercase"
                  style="font-size: 10px; letter-spacing: 0.5px;">
              Subtitle / Konteks Singkat
            </span>
          </div>
        </div>
        <button type="button" class="btn-close ms-auto" data-bs-dismiss="modal"></button>
      </div>

      <!-- BODY -->
      <div class="modal-body px-4 pt-3 pb-2">
        <!-- konten -->
      </div>

      <!-- FOOTER -->
      <div class="modal-footer border-top-0 pt-0 px-4 pb-4"
           style="background: transparent !important;">
        <button type="button" class="btn btn-figma-outline" data-bs-dismiss="modal">BATAL</button>
        <button type="button" class="btn btn-figma-primary">
          <i class="feather-check me-1"></i> SIMPAN
        </button>
      </div>

    </div>
  </div>
</div>
```

### Ukuran Modal

| Ukuran | max-width | Contoh penggunaan |
|---|---|---|
| Kecil | `480px` | Assign PIC, konfirmasi singkat |
| Sedang | `600px` | Form dengan beberapa field |
| Besar | `740px` | Konfirmasi perekaman tiket (multi-cluster) |

### Properti Wajib Modal

| Properti | Nilai |
|---|---|
| `border-radius` | `12px` — **selalu** |
| `box-shadow` | `0 8px 30px rgba(0,0,0,0.12)` |
| `border` | `none` |
| Header border | `border-bottom-0` — tanpa garis bawah |
| Footer background | `transparent !important` |
| Footer border | `border-top-0` |
| Scrollable body | `max-height: 72vh; overflow-y: auto;` |

### Icon Header — Palet Warna

| Konteks | Background | Icon Color | Icon Feather |
|---|---|---|---|
| Info / Default | `#dbeafe` | `#2563eb` | `feather-info` |
| Konfirmasi / File | `#dbeafe` | `#2563eb` | `feather-file-text` |
| Sukses | `#d1fae5` | `#059669` | `feather-check-circle` |
| Bahaya / Hapus | `#fee2e2` | `#dc2626` | `feather-alert-circle` |
| Peringatan | `#fef3c7` | `#d97706` | `feather-alert-triangle` |
| Assign / User | `#e0f2fe` | `#0284c7` | `feather-user-plus` |

---

## 5. Komponen: Card / Section dalam Modal

### Pola Standar — Info Card

```html
<div class="p-3 rounded mb-3" style="background: #f8fafc; border: 1px solid #e2e8f0;">

  <!-- Sub-label opsional -->
  <div style="font-size: 10px; font-weight: 700; color: #94a3b8;
              text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px;">
    <i class="feather-users me-1" style="font-size: 10px;"></i>Nama Seksi
  </div>

  <!-- Field grid -->
  <div class="row g-2" style="font-size: 12.5px;">
    <div class="col-6">
      <span style="font-size: 10.5px; color: #94a3b8; display: block;">Label</span>
      <span class="fw-semibold text-dark">Nilai</span>
    </div>
  </div>

  <!-- Separator antar sub-section -->
  <div class="pt-2 mt-2" style="border-top: 1px dashed #e2e8f0;">
    <!-- sub-section berikutnya -->
  </div>

</div>
```

### Aturan Card

| Aturan | Nilai |
|---|---|
| Background | `#f8fafc` |
| Border | `1px solid #e2e8f0` |
| Border radius | `rounded` (≈8px Bootstrap) |
| Padding dalam | `p-3` (12px) |
| Jarak antar card | `mb-3` |
| Separator antar sub-section | `border-top: 1px dashed #e2e8f0` |
| Separator solid (alternatif) | `<hr class="my-2" style="border-color: #e2e8f0;">` |

> ❌ **Jangan** gunakan background card berwarna (biru, hijau, kuning) untuk info biasa.
> Warna hanya untuk chip/badge status semantik.

---

## 6. Komponen: Tombol (Buttons)

Selalu gunakan kelas berikut yang sudah terdefinisi di `base.html`:

```
btn-figma-primary    ← aksi utama (submit, simpan, assign)
btn-figma-outline    ← aksi sekunder (batal, kembali)
btn-figma-danger     ← aksi destruktif (hapus, tolak)
```

### Aturan Tombol

| Aturan | Penjelasan |
|---|---|
| Label | **UPPERCASE** — `SIMPAN`, `BATAL`, `ASSIGN` |
| Icon | Selalu prefix: `<i class="feather-[icon] me-1"></i>` |
| Urutan footer | Kiri = Sekunder (BATAL), Kanan = Primer (SIMPAN) |
| Jangan pakai | `btn-primary`, `btn-secondary` Bootstrap standar di dalam modal |

---

## 7. Komponen: Status Badge / Chip

```html
<!-- Chip teks status -->
<span style="display: inline-block; background: #16a34a; color: #fff;
             font-size: 12px; font-weight: 700;
             padding: 2px 12px; border-radius: 999px;">Aktif</span>

<!-- Chip angka besar (Baris Diterima) -->
<span style="display: inline-block; background: #16a34a; color: #fff;
             font-size: 15px; font-weight: 800;
             padding: 3px 16px; border-radius: 999px;">1.234</span>
```

### Palet Chip Semantik

| Status | Background | Contoh teks |
|---|---|---|
| Aktif / Diterima / Berhasil | `#16a34a` | Aktif, Diterima |
| Nonaktif / Ditolak / Error | `#ef4444` | Nonaktif, Gagal |
| Menunggu / Pending | `#f59e0b` | Menunggu, Proses |
| Info / Netral | `#3b82f6` | Informasi |
| Disabled / Tidak Relevan | `#94a3b8` | Tidak Aktif |

---

## 8. Komponen: Form Fields

### Label Wajib

```html
<label class="form-label fw-semibold" style="font-size: 12px;">
  Nama Field <span class="text-danger">*</span>
</label>
```

### Input & Select

```html
<input type="text" class="form-control"
       style="height: 40px; border-radius: 8px; font-size: 13px;">
<select class="form-select"
        style="height: 40px; border-radius: 8px; font-size: 13px;">
```

### Aturan Form

| Elemen | Nilai |
|---|---|
| Input / select height | `40px` |
| Border radius | `8px` |
| Font size | `13px` |
| Label font size | `12px`, `fw-semibold` |
| Tanda wajib | `<span class="text-danger">*</span>` |
| Tooltip | Sentence case, `text-start`, width max `200px` |

---

## 9. Spacing System

| Kegunaan | Bootstrap class | Nilai px |
|---|---|---|
| Padding dalam card | `p-3` | 12px |
| Padding modal body horizontal | `px-4` | 16px |
| Padding modal body atas | `pt-3` | 12px |
| Jarak antar card | `mb-3` | 16px |
| Gap field dalam row (normal) | `g-2` | 8px |
| Gap field dalam row (lebar) | `g-3` | 12px |
| Jarak besar antar section | `mb-4` | 24px |

---

## 10. Panduan Per Konteks

### Modal Konfirmasi (Review sebelum Submit)

- **Icon header:** `feather-file-text`, biru soft `#dbeafe`
- **Nomor/ID utama:** tampilkan sebagai mini-card atau highlighted terpisah di atas
- **Data section:** card `#f8fafc` dengan sub-label `#94a3b8`, separator `dashed`
- **Angka/volume penting:** chip hijau `border-radius: 999px`
- **Footer:** `btn-figma-outline` BATAL + `btn-figma-primary` SIMPAN

### Modal Validasi Gagal

- **Icon header:** `feather-alert-circle`, merah soft `#fee2e2`
- **Deskripsi:** `<p class="text-muted">` di bawah title — **bukan alert box merah**
- **Field error:** card `#f8fafc` + nilai `text-danger`
- **Footer:** satu tombol `btn-figma-primary` (TUTUP / OK)

### Modal Assign / Form Pendek

- Tidak perlu cluster — satu card `#f8fafc` berisi info read-only + form di bawahnya
- **Footer:** `btn-figma-outline` BATAL + `btn-figma-primary` ASSIGN/SIMPAN

### Halaman Form Panjang

- Kelompokkan field dalam card/section dengan label uppercase muted
- Separator antar kelompok: gap `mb-4` atau `<hr>`
- Tombol submit di kanan bawah

---

## 11. Do's & Don'ts

### ✅ DO

- Gunakan `#f8fafc` untuk background card informasi
- Gunakan `btn-figma-primary` dan `btn-figma-outline` untuk tombol di modal
- Label field selalu di atas nilai (`display: block; margin-bottom: 2px`)
- Section label: uppercase, `#94a3b8`, icon kecil 10px, `font-size: 10–11px`
- Tombol: **UPPERCASE**
- Warna semantik: hanya untuk konteks yang sesuai

### ❌ DON'T

- Jangan pakai background card berwarna (biru/hijau/kuning) untuk info biasa
- Jangan pakai gradient dalam modal atau card
- Jangan campurkan `btn-primary` Bootstrap standar dengan `btn-figma-*`
- Jangan buat section header > `12px`
- Jangan `text-uppercase` untuk kalimat atau teks panjang
- Jangan buat modal dengan `border` frame yang terlihat
- Jangan shadow terlalu kuat (`rgba(0,0,0,0.25)` ke atas)
- Jangan gunakan lebih dari 2 jenis warna decorative dalam satu modal

---

## 12. Referensi Komponen yang Sudah Benar

| Komponen | File | Lokasi |
|---|---|---|
| **Modal Assign PIC PIDE** ← _referensi utama_ | `home.html` | L.2076–2141 |
| Modal Assign PIC PMDE | `home.html` | L.2144–2210 |
| Modal Summary Detail | `home.html` | L.2049–2073 |
| Definisi CSS `btn-figma-*` | `base.html` | L.914–972 |
| Modal Validasi Gagal | `rekam_tiket_form.html` | `endDateValidationModal` |

---

## 13. Responsiveness & Adaptive Layouts

### Dukungan Resolusi Lawas (4:3)
Diamond Web dirancang untuk tahan banting (*robust*) di berbagai resolusi layar, termasuk monitor 4:3 lama (seperti `1024x768`).
- **Selalu Gunakan Flex-Wrap:** Pada kontainer *Toolbar*, *Header*, atau baris yang berisi deretan tombol filter/metrik, wajib menyertakan kelas `flex-wrap` (seperti `d-flex flex-wrap`). Ini mencegah elemen saling menghimpit dan tumpah (overflow) keluar dari batas kartu.
- **Lindungi Label Teks Singkat:** Untuk tombol seperti *toggle switches* atau *badges* yang berisi icon dan satu kata (misal: "Prioritas", "Pantauan"), tambahkan style `white-space: nowrap; flex-shrink: 0;` pada kontainer terluarnya. Ini memastikan kata tersebut tidak akan pernah terpotong atau turun setengah kata ke baris baru ketika layar menyempit.
- **Tumpuk Secara Harmonis:** Biarkan elemen turun ke bawah (*stack*) secara alami di resolusi sempit alih-alih mengecilkan ukuran teks (*font-size*) secara paksa yang dapat merusak keterbacaan (prinsip *Accessibility*).

---

*Guideline ini adalah living document. Perbarui setiap kali ada keputusan desain baru yang disepakati bersama.*
