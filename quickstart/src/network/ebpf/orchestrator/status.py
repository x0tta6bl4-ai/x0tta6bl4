"""Component status tracking."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class ComponentStatus:
    """Status of an orchestrator component"""

    name: str
    available: bool
    running: bool
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


