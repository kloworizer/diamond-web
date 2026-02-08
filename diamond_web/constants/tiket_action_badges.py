"""Action and Role badges for Tiket workflow"""

from .tiket_action_types import ACTION_TYPE_LABELS, ACTION_TYPE_BADGE_CLASSES

# Action badges for TiketAction - Maps action IDs to display info
# Use the action type system from tiket_action_types.py for badge display
ACTION_BADGES = {action_id: {'label': label, 'class': ACTION_TYPE_BADGE_CLASSES.get(action_id, 'bg-secondary')} for action_id, label in ACTION_TYPE_LABELS.items()}

# Role badges for TiketPIC
ROLE_BADGES = {
    1: {'label': 'P3DE', 'class': 'bg-primary'},
    2: {'label': 'PIDE', 'class': 'bg-info'},
    3: {'label': 'PMDE', 'class': 'bg-warning text-dark'}
}

# Workflow step mapping based on status
WORKFLOW_STEPS = {
    1: 'rekam',
    2: 'backup',
    3: 'tanda_terima',
    4: 'teliti',
    5: 'kembali',
    6: 'kirim_pide',
    7: 'identifikasi',
    8: 'pengendalian_mutu',
    9: 'batal',
    10: 'selesai'
}
