STATUS_LABELS = {
    1: 'Proses Perekaman',
    2: 'Diteliti',
    3: 'Data Dikembalikan',
    4: 'Belum Diterima',
    5: 'Proses Identifikasi',
    6: 'Proses QC',
    7: 'Tiket Dibatalkan',
    8: 'Selesai',
    9: 'Tidak Direkam'
}

STATUS_BADGE_CLASSES = {
    1: 'status-perekaman',
    2: 'status-diteliti',
    3: 'status-dikembalikan',
    4: 'status-belum-diterima',
    5: 'status-identifikasi',
    6: 'status-qc',
    7: 'status-dibatalkan',
    8: 'status-selesai',
    9: 'status-tidak-direkam'
}

# Named constants for ticket statuses to avoid magic numbers across the codebase.
STATUS_DIREKAM = 1
STATUS_DITELITI = 2
STATUS_DIKEMBALIKAN = 3
STATUS_DIKIRIM_KE_PIDE = 4
STATUS_IDENTIFIKASI = 5
STATUS_PENGENDALIAN_MUTU = 6
STATUS_DIBATALKAN = 7
STATUS_SELESAI = 8

# Optional helpers for common comparisons
# Tickets with status < STATUS_DIBATALKAN are considered non-final (not cancelled or finished)
STATUS_KLARIFIKASI_MAX = STATUS_PENGENDALIAN_MUTU
