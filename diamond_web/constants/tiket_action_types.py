"""TiketAction types and rules - Keep organized and DRY"""

# Action types for Tiket workflow
class TiketActionType:
    """Action types for tiket operations"""
    DIREKAM = 1
    DITELITI = 2
    DIKEMBALIKAN = 3
    DIKIRIM_KE_PIDE = 4
    IDENTIFIKASI = 5
    PENGENDALIAN_MUTU = 6
    DIBATALKAN = 7
    SELESAI = 8

# Action types for Backup workflow
class BackupActionType:
    """Action types for backup operations"""
    DIREKAM = 101
    DIHAPUS = 102

# Action types for TandaTerima workflow
class TandaTerimaActionType:
    """Action types for tanda terima operations"""
    DIREKAM = 201
    DIBATALKAN = 202

# Action types for PIC workflow
class PICActionType:
    """Action types for PIC operations"""
    DITAMBAHKAN = 301
    TIDAK_AKTIF = 302
    DIAKTIFKAN_KEMBALI = 303

# Map action types to display labels
ACTION_TYPE_LABELS = {
    # Tiket actions
    1: 'Direkam',
    2: 'Diteliti',
    3: 'Dikembalikan',
    4: 'Dikirim ke PIDE',
    5: 'Identifikasi',
    6: 'Pengendalian Mutu',
    7: 'Dibatalkan',
    8: 'Selesai',
    # Backup actions
    101: 'Backup Direkam',
    102: 'Backup Dihapus',
    # TandaTerima actions
    201: 'Tanda Terima Direkam',
    202: 'Tanda Terima Dibatalkan',
    # PIC actions
    301: 'PIC Ditambahkan',
    302: 'PIC Tidak Aktif',
    303: 'PIC Diaktifkan Kembali',
}

# Map action types to badge classes
ACTION_TYPE_BADGE_CLASSES = {
    # Tiket actions
    1: 'bg-primary',
    2: 'bg-secondary',
    3: 'bg-info',
    4: 'bg-warning',
    5: 'bg-info',
    6: 'bg-secondary',
    7: 'bg-danger',
    8: 'bg-success',
    # Backup actions
    101: 'bg-primary',
    102: 'bg-danger',
    # TandaTerima actions
    201: 'bg-primary',
    202: 'bg-danger',
    # PIC actions
    301: 'bg-success',
    302: 'bg-warning',
    303: 'bg-info',
}


def get_tiket_action_type(action_name):
    """Get tiket action type ID by name (case-insensitive)
    
    Args:
        action_name: One of 'direkam', 'diteliti', 'dikembalikan', 'dikirim_ke_pide', 
                    'identifikasi', 'pengendalian_mutu', 'dibatalkan', 'selesai'
    
    Returns:
        Action type ID or None if not found
    """
    action_map = {
        'direkam': TiketActionType.DIREKAM,
        'diteliti': TiketActionType.DITELITI,
        'dikembalikan': TiketActionType.DIKEMBALIKAN,
        'dikirim_ke_pide': TiketActionType.DIKIRIM_KE_PIDE,
        'identifikasi': TiketActionType.IDENTIFIKASI,
        'pengendalian_mutu': TiketActionType.PENGENDALIAN_MUTU,
        'dibatalkan': TiketActionType.DIBATALKAN,
        'selesai': TiketActionType.SELESAI,
    }
    return action_map.get(action_name.lower())


def get_backup_action_type(action_name):
    """Get backup action type ID by name (case-insensitive)
    
    Args:
        action_name: One of 'direkam', 'dihapus'
    
    Returns:
        Action type ID or None if not found
    """
    action_map = {
        'direkam': BackupActionType.DIREKAM,
        'dihapus': BackupActionType.DIHAPUS,
    }
    return action_map.get(action_name.lower())


def get_tanda_terima_action_type(action_name):
    """Get tanda terima action type ID by name (case-insensitive)
    
    Args:
        action_name: One of 'direkam', 'dibatalkan'
    
    Returns:
        Action type ID or None if not found
    """
    action_map = {
        'direkam': TandaTerimaActionType.DIREKAM,
        'dibatalkan': TandaTerimaActionType.DIBATALKAN,
    }
    return action_map.get(action_name.lower())


def get_action_label(action_id):
    """Get display label for an action ID
    
    Args:
        action_id: The action ID
    
    Returns:
        Display label or 'Unknown' if not found
    """
    return ACTION_TYPE_LABELS.get(action_id, 'Unknown')


def get_action_badge_class(action_id):
    """Get badge CSS class for an action ID
    
    Args:
        action_id: The action ID
    
    Returns:
        CSS class or 'bg-secondary' if not found
    """
    return ACTION_TYPE_BADGE_CLASSES.get(action_id, 'bg-secondary')


# Aggregate action metadata for convenience (label + badge class)
ACTION_BADGES = {
    action_id: {
        'label': label,
        'class': ACTION_TYPE_BADGE_CLASSES.get(action_id, 'bg-secondary')
    }
    for action_id, label in ACTION_TYPE_LABELS.items()
}


# Role badges for TiketPIC (kept here to centralize workflow constants)
ROLE_BADGES = {
    1: {'label': 'P3DE', 'class': 'bg-primary'},
    2: {'label': 'PIDE', 'class': 'bg-info'},
    3: {'label': 'PMDE', 'class': 'bg-warning text-dark'}
}


# Workflow step mapping based on status (kept here for convenience)

