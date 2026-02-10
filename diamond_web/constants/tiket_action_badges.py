"""Compatibility shim re-exporting tiket action constants.

This module re-exports `ACTION_BADGES` and `ROLE_BADGES` from
``tiket_action_types.py`` for backward compatibility with older imports.
"""

from .tiket_action_types import ACTION_BADGES, ROLE_BADGES

__all__ = ["ACTION_BADGES", "ROLE_BADGES"]
