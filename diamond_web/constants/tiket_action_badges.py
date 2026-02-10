"""Compatibility shim for tiket action badges.

This module previously defined `ACTION_BADGES`, `ROLE_BADGES`, and
`WORKFLOW_STEPS`. Those constants have been consolidated into
``tiket_action_types.py`` to reduce redundancy. Keep this file as a
thin shim to avoid breaking imports elsewhere.
"""

from .tiket_action_types import ACTION_BADGES, ROLE_BADGES, WORKFLOW_STEPS

__all__ = ["ACTION_BADGES", "ROLE_BADGES", "WORKFLOW_STEPS"]
