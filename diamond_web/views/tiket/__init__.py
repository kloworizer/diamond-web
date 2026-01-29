"""Tiket workflow views"""
from .list import TiketListView, tiket_data
from .rekam import TiketRekamCreateView
from .detail import TiketDetailView

# Backward compatibility
TiketCreateView = TiketRekamCreateView

__all__ = [
    'TiketListView',
    'tiket_data',
    'TiketCreateView',
    'TiketDetailView',
    'TiketRekamCreateView',
]
