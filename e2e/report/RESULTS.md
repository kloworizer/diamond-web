# DIAMOND Tiket Workflow — Playwright E2E Results

_Generated: 2026-07-26 19:38:28_

**Steps:** 126 passed, 0 failed. **Bugs found:** 2.

## Bugs / Findings

### 1. [HIGH] Sidebar 'Transfer ke PMDE' button is permanently disabled

On the tiket detail page (status Identifikasi), the button that opens the Transfer ke PMDE modal is rendered with a hardcoded `disabled` attribute (tiket_detail.html ~L750) and no JS ever enables it. A PIDE PIC therefore cannot open the modal or transfer the tiket to PMDE through the intended UI. (E2E forced-enabled it to verify the underlying flow still works.)

### 2. [HIGH] Sidebar 'Selesaikan Tiket' button is permanently disabled

On the tiket detail page (status Pengendalian Mutu), the button that opens the Selesaikan Tiket modal is rendered with a hardcoded `disabled` attribute (tiket_detail.html ~L766) and no JS enables it. A PMDE PIC cannot complete the tiket through the intended UI. (E2E forced-enabled it to verify the underlying flow still works.)

## Step log

| Scenario | Step | Status | Detail |
|---|---|---|---|
| happy_path | rekam tiket | PASS |  -> Direkam |
| happy_path | status after rekam | PASS | Direkam |
| happy_path | buat tanda terima | PASS | reloaded |
| happy_path | rekam hasil penelitian | PASS | lengkap=1000 -> Diteliti (btn_was_disabled=False) |
| happy_path | status after penelitian (Lengkap) | PASS | Diteliti |
| happy_path | generate ND pengantar | PASS | reloaded |
| happy_path | kirim ke PIDE | PASS | -> Dikirim ke PIDE |
| happy_path | status after kirim ke PIDE | PASS | Dikirim ke PIDE |
| happy_path | identifikasi | PASS | -> Identifikasi |
| happy_path | status after identifikasi | PASS | Identifikasi |
| happy_path | transfer ke PMDE | PASS | -> Pengendalian Mutu (open_btn_was_disabled=True) |
| happy_path | status after transfer ke PMDE | PASS | Pengendalian Mutu |
| happy_path | selesaikan tiket | PASS | -> Selesai (open_btn_was_disabled=True) |
| happy_path | status after selesaikan | PASS | Selesai |
| langsung_selesai | rekam tiket | PASS |  -> Selesai |
| langsung_selesai | status after rekam (data tidak tersedia) | PASS | Selesai |
| penelitian_tidak_lengkap | rekam tiket | PASS |  -> Direkam |
| penelitian_tidak_lengkap | buat tanda terima | PASS | reloaded |
| penelitian_tidak_lengkap | rekam hasil penelitian | PASS | lengkap=0 -> Selesai (btn_was_disabled=False) |
| penelitian_tidak_lengkap | status after penelitian (baris_lengkap==0) | PASS | Selesai |
| batalkan | rekam tiket | PASS |  -> Direkam |
| batalkan | status after rekam | PASS | Direkam |
| batalkan | batalkan tiket | PASS | -> Dibatalkan |
| batalkan | status after batalkan | PASS | Dibatalkan |
| dikembalikan | rekam tiket | PASS |  -> Direkam |
| dikembalikan | buat tanda terima | PASS | reloaded |
| dikembalikan | rekam hasil penelitian | PASS | lengkap=800 -> Diteliti (btn_was_disabled=False) |
| dikembalikan | generate ND pengantar | PASS | reloaded |
| dikembalikan | kirim ke PIDE | PASS | -> Dikirim ke PIDE |
| dikembalikan | status after kirim ke PIDE | PASS | Dikirim ke PIDE |
| dikembalikan | dikembalikan ke P3DE | PASS | -> Dibatalkan |
| dikembalikan | status after dikembalikan (expected Dibatalkan per design) | PASS | Dibatalkan |
| val_rekam_future_date | future DIP blocked by client guard | PASS | endDateValidationModal shown |
| val_rekam_missing_required | missing required blocked | PASS | confirmModal not shown (HTML5 validation) |
| val_penelitian_negative | rekam tiket | PASS |  -> Direkam |
| val_penelitian_negative | buat tanda terima | PASS | reloaded |
| val_penelitian_negative | mismatched total disables submit | PASS | client validation works |
| val_penelitian_negative | negative baris_lengkap rejected | PASS | status stayed Direkam |
| val_pide_pmde_gaps | rekam tiket | PASS |  -> Direkam |
| val_pide_pmde_gaps | buat tanda terima | PASS | reloaded |
| val_pide_pmde_gaps | rekam hasil penelitian | PASS | lengkap=1000 -> Diteliti (btn_was_disabled=False) |
| val_pide_pmde_gaps | generate ND pengantar | PASS | reloaded |
| val_pide_pmde_gaps | kirim ke PIDE | PASS | -> Dikirim ke PIDE |
| val_pide_pmde_gaps | identifikasi | PASS | -> Identifikasi |
| val_pide_pmde_gaps | transfer ke PMDE | PASS | -> Identifikasi (open_btn_was_disabled=True) |
| val_pide_pmde_gaps | negative transfer rejected (model-level protection) | PASS | status stayed Identifikasi |
| val_pide_pmde_gaps | transfer ke PMDE | PASS | -> Pengendalian Mutu (open_btn_was_disabled=True) |
| val_pide_pmde_gaps | selesaikan tiket | PASS | -> Pengendalian Mutu (open_btn_was_disabled=True) |
| val_pide_pmde_gaps | invalid QC rejected | PASS | status stayed Pengendalian Mutu |
| val_tanda_terima_before_dip | rekam tiket | PASS |  -> Direkam |
| val_tanda_terima_before_dip | tanda terima before tgl_terima_dip rejected | PASS |  |
| val_tanda_terima_before_dip | valid tanda terima accepted | PASS | Direkam |
| val_teliti_before_tanda_terima | rekam tiket | PASS |  -> Direkam |
| val_teliti_before_tanda_terima | setup: buat tanda terima | PASS | 2026-07-25 |
| val_teliti_before_tanda_terima | tgl_teliti before tanda terima rejected | PASS | Direkam |
| val_teliti_before_tanda_terima | valid tgl_teliti accepted | PASS | Diteliti |
| val_datepicker_consistency | rekam tiket page has icon + flatpickr | PASS |  |
| val_datepicker_consistency | rekam tiket | PASS |  -> Direkam |
| val_datepicker_consistency | edit tiket AJAX modal has icon + flatpickr | PASS |  |
| edit_tiket | rekam tiket | PASS |  -> Direkam |
| edit_tiket | future tgl_terima_dip rejected | PASS |  |
| edit_tiket | tgl_terima_vertikal disabled (non-regional ILAP) | INFO | skipped cross-field check |
| edit_tiket | valid edit persisted | PASS | E2E-EDIT-000000 |
| edit_tiket | buat tanda terima | PASS | reloaded |
| edit_tiket | Edit Tiket correctly hidden after tanda terima | PASS |  |
| special_request | rekam tiket | PASS |  -> Direkam |
| special_request | toggle ON persisted | PASS | ya |
| special_request | toggle OFF persisted | PASS | tidak |
| crud_kategori_wilayah | empty submit blocked | PASS |  |
| crud_kategori_wilayah | valid create | PASS | E2E kategori-wil 87305 |
| crud_kategori_wilayah | duplicate rejected | PASS | modal stayed open with validation error |
| crud_kategori_wilayah | edit | PASS | E2E kategori-wil 87305 (edited) |
| crud_kategori_wilayah | delete | PASS |  |
| crud_jenis_tabel | empty submit blocked | PASS |  |
| crud_jenis_tabel | valid create | PASS | E2E jenis-tabel 96825 |
| crud_jenis_tabel | duplicate rejected | PASS | modal stayed open with validation error |
| crud_jenis_tabel | edit | PASS | E2E jenis-tabel 96825 (edited) |
| crud_jenis_tabel | delete | PASS |  |
| crud_status_data | empty submit blocked | PASS |  |
| crud_status_data | valid create | PASS | E2E status-data 5966 |
| crud_status_data | duplicate rejected | PASS | modal stayed open with validation error |
| crud_status_data | edit | PASS | E2E status-data 5966 (edi |
| crud_status_data | delete | PASS |  |
| crud_status_penelitian | empty submit blocked | PASS |  |
| crud_status_penelitian | valid create | PASS | E2E status-penel 15494 |
| crud_status_penelitian | duplicate rejected | PASS | modal stayed open with validation error |
| crud_status_penelitian | edit | PASS | E2E status-penel 15494 (e |
| crud_status_penelitian | delete | PASS |  |
| crud_bentuk_data | empty submit blocked | PASS |  |
| crud_bentuk_data | valid create | PASS | E2E bentuk-data 24839 |
| crud_bentuk_data | duplicate rejected | PASS | modal stayed open with validation error |
| crud_bentuk_data | edit | PASS | E2E bentuk-data 24839 (ed |
| crud_bentuk_data | delete | PASS |  |
| crud_cara_penyampaian | empty submit blocked | PASS |  |
| crud_cara_penyampaian | valid create | PASS | E2E cara-penyamp 33980 |
| crud_cara_penyampaian | duplicate rejected | PASS | modal stayed open with validation error |
| crud_cara_penyampaian | edit | PASS | E2E cara-penyamp 33980 (e |
| crud_cara_penyampaian | delete | PASS |  |
| crud_media_backup | empty submit blocked | PASS |  |
| crud_media_backup | valid create | PASS | E2E media-backup 43214 |
| crud_media_backup | duplicate rejected | PASS | modal stayed open with validation error |
| crud_media_backup | edit | PASS | E2E media-backup 43214 (e |
| crud_media_backup | delete | PASS |  |
| crud_kanwil | empty submit blocked | PASS |  |
| crud_kanwil | valid create | PASS | E47/E2E Kanwil 477 |
| crud_kanwil | duplicate kode_kanwil rejected | PASS |  |
| crud_kanwil | edit | PASS |  |
| crud_kanwil | delete | PASS |  |
| crud_kategori_ilap | empty submit blocked | PASS |  |
| crud_kategori_ilap | valid create | PASS | E8/E2E Kategori ILAP 83 |
| crud_kategori_ilap | id_kategori locked on edit | PASS |  |
| crud_kategori_ilap | edit | PASS |  |
| crud_kategori_ilap | delete | PASS |  |
| crud_periode_pengiriman | empty submit blocked | PASS |  |
| crud_periode_pengiriman | valid create | PASS | E2E Penyampaian 69399 |
| crud_periode_pengiriman | edit | PASS |  |
| crud_periode_pengiriman | delete | PASS |  |
| crud_dasar_hukum | empty submit blocked | PASS |  |
| crud_dasar_hukum | valid create | PASS | E2E Dasar Hukum 76991 |
| crud_dasar_hukum | end_date < start_date rejected | PASS |  |
| crud_dasar_hukum | edit | PASS |  |
| crud_dasar_hukum | delete | PASS |  |
| crud_kpp | empty submit blocked | PASS |  |
| crud_kpp | valid create | PASS | Q28/E2E KPP 283 kanwil=1 |
| crud_kpp | edit | PASS |  |
| crud_kpp | delete | PASS |  |
| crud_protected_delete | protected delete handled gracefully (no hard 500) | PASS |  |
