"""Orchestrator configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class OrchestratorConfig:
    """Configuration for the EBPF orchestrator."""

    interface: str = "eth0"
    polling_interval: float = 5.0
    auto_recover: bool = True
    max_retries: int = 3
    event_bus: Optional[object] = None
    extra: Dict = field(default_factory=dict)
