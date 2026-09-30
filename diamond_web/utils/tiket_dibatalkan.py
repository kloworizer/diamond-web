"""What cancelling a tiket does to the counts its tarikan left on it."""

# The identification and QC counts the Oracle tiket update sync copies from
# the tarikan (PVPTD.ZA_REKAP_TARIKAN). A cancelled tiket's tarikan is void —
# PIDE deletes it from Oracle — so they are cleared, whichever way the tiket
# is cancelled, and the sync does not copy them back.
#
# baris_cde stays: it is what PIDE handed back, and the P3DE home cards
# (Pengembalian Sebagian dari PIDE, Diklarifikasi) read it on cancelled
# tikets. The dates stay too; they record what happened at PIDE.
KOLOM_TARIKAN_DIBATALKAN = (
    'baris_i', 'baris_u', 'baris_res',
    'sudah_qc', 'belum_qc', 'lolos_qc', 'tidak_lolos_qc',
    'qc_p', 'qc_x', 'qc_w', 'qc_f', 'qc_a', 'qc_c', 'qc_n',
    'qc_y', 'qc_z', 'qc_u', 'qc_e', 'qc_v', 'qc_r', 'qc_d',
)


def kolom_tarikan_terisi(tiket):
    """Return the `KOLOM_TARIKAN_DIBATALKAN` fields of *tiket* that hold a value."""
    return [f for f in KOLOM_TARIKAN_DIBATALKAN if getattr(tiket, f) is not None]


def kosongkan_kolom_tarikan(tiket):
    """Null the tarikan counts on *tiket*, unsaved; return the fields cleared."""
    fields = kolom_tarikan_terisi(tiket)
    for field in fields:
        setattr(tiket, field, None)
    return fields
