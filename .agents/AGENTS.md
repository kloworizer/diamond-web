# Diamond Web — Workspace Agent Rules

## Aturan Desain Wajib

Setiap kali menerima permintaan yang berkaitan dengan desain antarmuka (modal, form, halaman, komponen UI, styling, warna, layout, atau tampilan apapun), saya **wajib**:

### 1. Membaca dan mematuhi Design Guideline proyek ini
- File: `D:\PROJECT\diamond-web\docs\DESIGN_GUIDELINE.md`
- Baca ulang guideline sebelum mengimplementasikan komponen baru bila terdapat keraguan
- Seluruh keputusan warna, spacing, tipografi, pola modal, tombol, dan card **harus sesuai** dengan guideline tersebut
- Referensi utama komponen yang benar: **Modal Assign PIC PIDE** di `home.html` L.2076

### 2. Mengaktifkan Skill UIUX Promax
- Setiap desain UI harus memenuhi standar premium UIUX Promax
- Baca `C:\Users\958635581\.gemini\config\skills\uiux_promax\SKILL.md` bila skill belum aktif di konteks saat ini
- Terapkan hierarki visual, spacing yang breathable, dan interaksi yang terasa premium

### 3. Prinsip penyelarasan keduanya

Bila ada konflik antara guideline proyek dan skill UIUX Promax, utamakan:
- **Guideline proyek** untuk: palet warna, ukuran font, struktur modal, kelas tombol
- **UIUX Promax** untuk: kualitas hierarki visual, keseimbangan komposisi, spacing, dan feel premium keseluruhan

### 4. Daftar hal yang selalu diperiksa sebelum deliver komponen UI

- [ ] Background card menggunakan `#f8fafc` (bukan warna lain untuk info biasa)
- [ ] Tombol modal menggunakan `btn-figma-primary` / `btn-figma-outline` / `btn-figma-danger`
- [ ] Icon header modal mengikuti palet warna semantik dari guideline
- [ ] Font size label field: `10.5–11px`, warna `#94a3b8`
- [ ] Font size nilai field: `12.5px`, `fw-semibold`
- [ ] Modal: `border-radius: 12px`, `border: none`, `box-shadow: 0 8px 30px rgba(0,0,0,0.12)`
- [ ] Section label: uppercase, muted, icon kecil 10px
- [ ] Tombol label: UPPERCASE
- [ ] Tidak ada warna decorative berlebih (gradient, background warna-warni pada card)
- [ ] Konsisten dengan komponen yang sudah ada di `home.html`
