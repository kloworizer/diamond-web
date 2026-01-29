"""Tiket workflow views"""
from .list import TiketListView, tiket_data
from .rekam import TiketRekamCreateView, TiketRekamDetailView

# Backward compatibility
TiketCreateView = TiketRekamCreateView
TiketDetailView = TiketRekamDetailView

__all__ = [
    'TiketListView',
    'tiket_data',
    'TiketCreateView',
    'TiketDetailView',
    'TiketRekamCreateView',
    'TiketRekamDetailView',
]
