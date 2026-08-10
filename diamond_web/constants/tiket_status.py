STATUS_LABELS = {
    1: 'Direkam',
    2: 'Diteliti',
    3: 'Dikembalikan',
    4: 'Dikirim ke PIDE',
    5: 'Identifikasi',
    6: 'Pengendalian Mutu',
    7: 'Dibatalkan',
    8: 'Selesai'
}

STATUS_BADGE_CLASSES = {
    1: 'bg-primary',
    2: 'bg-secondary',
    3: 'bg-info',
    4: 'bg-warning text-dark',
    5: 'bg-info',
    6: 'bg-secondary',
    7: 'bg-danger',
    8: 'bg-success'
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

# The statuses a tiket holds while it is still at P3DE: recorded, researched
# and returned. Its data has one count at this point, the P3DE baris lengkap.
STATUSES_DI_P3DE = (
    STATUS_DIREKAM,
    STATUS_DITELITI,
    STATUS_DIKEMBALIKAN,
)

# The statuses a tiket holds while it is at PIDE: sent on, then identified.
# Identification is what splits its data into baris I/U/CDE/Res.
STATUSES_DI_PIDE = (
    STATUS_DIKIRIM_KE_PIDE,
    STATUS_IDENTIFIKASI,
)

# Every status a tiket passes through before PMDE receives it, so a tiket in one
# of these is still upstream of quality control.
STATUSES_SEBELUM_PENGENDALIAN_MUTU = STATUSES_DI_P3DE + STATUSES_DI_PIDE
