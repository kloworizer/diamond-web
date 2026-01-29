"""Tiket workflow views"""
from .list import TiketListView, tiket_data
from .rekam import TiketRekamCreateView
from .detail import TiketDetailView
from .rekam_hasil_penelitian import RekamHasilPenelitianView
from .kirim_tiket import KirimTiketView

# Backward compatibility
TiketCreateView = TiketRekamCreateView

__all__ = [
    'TiketListView',
    'tiket_data',
    'TiketCreateView',
    'TiketDetailView',
    'TiketRekamCreateView',
    'RekamHasilPenelitianView',
    'KirimTiketView',
]
