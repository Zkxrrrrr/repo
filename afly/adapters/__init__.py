"""Adapter registry. Adapters self-register via @register."""
from __future__ import annotations

from typing import Dict, Type

from .base import SignupAdapter

REGISTRY: Dict[str, Type[SignupAdapter]] = {}


def register(cls: Type[SignupAdapter]) -> Type[SignupAdapter]:
    REGISTRY[cls.target_id] = cls
    return cls


def get_adapter(target_id: str) -> Type[SignupAdapter]:
    if target_id not in REGISTRY:
        raise KeyError(f"No adapter registered for target {target_id!r}. "
                       f"Known: {sorted(REGISTRY)}")
    return REGISTRY[target_id]


# Importing modules below triggers their @register decorators.
from . import swagbucks  # noqa: E402,F401
from . import inboxdollars  # noqa: E402,F401
from . import freecash  # noqa: E402,F401
from . import idle_empire  # noqa: E402,F401
from . import timebucks  # noqa: E402,F401
from . import paidviewpoint  # noqa: E402,F401
from . import ysense  # noqa: E402,F401
from . import prizerebel  # noqa: E402,F401
