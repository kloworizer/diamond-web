"""Tiket workflow views"""
from .list import TiketListView, tiket_data
from .rekam_tiket import (
    TiketRekamCreateView,
    ILAPPeriodeDataAPIView,
    CheckJenisPrioritasAPIView
)
from .detail import TiketDetailView
from .rekam_hasil_penelitian import RekamHasilPenelitianView
from .batalkan_tiket import BatalkanTiketView
from .kirim_tiket import KirimTiketView

# Backward compatibility
TiketCreateView = TiketRekamCreateView

__all__ = [
    'TiketListView',
    'tiket_data',
    'TiketCreateView',
    'TiketDetailView',
    'TiketRekamCreateView',
    'ILAPPeriodeDataAPIView',
    'CheckJenisPrioritasAPIView',
    'RekamHasilPenelitianView',
    'BatalkanTiketView',
    'KirimTiketView',
]
