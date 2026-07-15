# Sesi Batch Push — 6 Juli 2026

Percakapan antara user (Alvian, frontend team) dan Claude.

## Konteks
Branch kerja: `alvian-frontend-redesign-whole1`
HEAD baseline: `03fbf19` — snapshot 113 file frontend redesign + read-only backend.
Status: **BELUM ada push ke mana pun.** Semua lokal.

## Prinsipal dari lead (backend team)
- ❌ **Tidak boleh ubah struktur backend / model / DB / migration**
- ❌ Tidak boleh ganggu CRUD atau alur data
- ✅ Read-only di GET payload **aman** (field tambahan di response JSON)
- Sebelum push/PR, audit dulu mana yang menyentuh backend non-read-only

## Hasil audit backend (16 file .py berubah)

### 🔴 KRITIS — jangan di-push tanpa klarifikasi tim backend
| File | Risiko |
|------|--------|
| `constants/tiket_status.py` | Menghapus status 9 "Ketidaktersediaan" → ganjalan. **DI-HOLD.** |
| `views/tiket/documents.py` | Merge dokumentasi + 2 tombol → key `label` dihapus. **Batch terpisah.** |
| `views/tanda_terima_data.py` | View logistik + UI signifikan. **Batch terpisah.** |

### 🟡 AMAN — read-only / tidak sentuh CRUD
| File | Perubahan |
|------|-----------|
| `views/tiket/detail.py` | +1 baris `nama_jenias_data` ke context |
| `views/tiket/rekam_tiket.py` | +field `nama_jenis_data` di payload API GET |
| `views/backup_data.py` | View baru endpoint JSON read-only |
| `views/pic.py` | View baru `jenis_data_ilap_info_ajax` read-only |

### 🟢 FRONTEND MURNI — template HTML (95 file)

## Rencana batch push (PR ke kloworizer/main)

Format branch: `alvian-frontend/{type}-{detail}`

| Batch | Branch | Isi | Tipe |
|-------|--------|-----|------|
| **1** | `alvian-frontend/feat-global-shell-home-login` | base.html, home.html, registration/profil.html, config/settings.py (locale id) | Frontend murni |
| 2 | `alvian-frontend/feat-crud-widget-filter-komponen` | CRUD templates (backup_data, bentuk_data, cara_penyampaian, etc.) + partials reusable | Frontend murni |
| 3 | `alvian-frontend/feat-report-module-ui` | Laporan templates (*laporan_*) | Frontend murni |
| 4 | `alvian-frontend/feat-tiket-ui-readonly-backend` | Tiket UI + read-only backend | Frontend + GET-only backend |
| 5 | `alvian-frontend/refactor-tiket-documents` | documents.py + tanda_terima_data.py | Khusus backend review |

### Batch 6 — DI-HOLD
- `constants/tiket_status.py` — sampai klarifikasi ke lead soal status 9.

## Detail Batch 1 (sudah disepakati)

**Branch:** `alvian-frontend/feat-global-shell-home-login`
**Strategi:** Branch dari `upstream/main`, lalu checkout 4 file dari baseline `03fbf19`:
1. `diamond_web/templates/base.html` — kerangka global (sidebar/navbar/footer/script)
2. `diamond_web/templates/home.html` — beranda
3. `diamond_web/templates/registration/profil.html` — profil (+359/−17)
4. `config/settings.py` — locale `id` (1 baris: LANGUAGE_CODE)

**Tidak masuk Batch 1:**
- `registration/login.html` — tidak ada perubahan
- `.gitignore` — entry lokal (.agents/, catatan_penting/) tidak di-push, tetap di baseline lokal
- `diamond_web/constants/tiket_status.py` — di-hold (stash)

## Langkah eksekusi (belum dijalankan)
```bash
cd /Volumes/Work-Yuk🔥/PROJECT/diamond-web

# 1. Branch dari upstream/main
git checkout upstream/main -b alvian-frontend/feat-global-shell-home-login

# 2. Checkout hanya 4 file Batch 1 dari baseline
git checkout 03fbf19 -- diamond_web/templates/base.html
git checkout 03fbf19 -- diamond_web/templates/home.html
git checkout 03fbf19 -- diamond_web/templates/registration/profil.html
git checkout 03fbf19 -- config/settings.py

# 3. Commit
git add -A
git commit -m "feat(ui): global shell, home, login, locale id

- base.html: kerangka global (sidebar/navbar/footer/script)
- home.html: beranda redesign
- profil.html: profil pengguna redesign
- config/settings.py: LANGUAGE_CODE = 'id'

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

# 4. Push
git push -u origin alvian-frontend/feat-global-shell-home-login

# 5. PR draft
gh pr create --draft \
  --base kloworizer:main \
  --head zcracktz:alvian-frontend/feat-global-shell-home-login \
  --title "feat(ui): global shell, home, profil, locale id" \
  --body "## Deskripsi

Perbaikan UI/UX untuk komponen global: base shell (sidebar, navbar, footer), halaman beranda, halaman profil, dan pengaturan locale ke bahasa Indonesia.

## Type of Change

- [x] New Feature

## Testing

- [x] Django check clean
- [ ] Smoke test di browser

## Screenshots
(opsional, tambahkan jika perlu)

## Related Issues
(TBD)"
```

## Ringkasan sesi
- Audit 16 file backend → 3 kritis (hold/batch terpisah), sisanya aman
- Strategi batch: 5 batch, 1 hold
- Batch 1 siap push (tinggal jalankan perintah di atas)
- `tiket_status.py` ada di stash (`stash@{0}`)
