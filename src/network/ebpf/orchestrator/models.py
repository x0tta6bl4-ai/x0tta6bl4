"""Orchestrator models and utilities."""
from __future__ import annotations
import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from src.services.service_event_identity import service_event_identity
logger = logging.getLogger(__name__)

ORCHESTRATOR_SERVICE_NAME = "ebpf-orchestrator"


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        raw = str(value).encode("utf-8", errors="replace")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return str(hash(value))


import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

# Local imports with graceful fallback
try:
    from .loader import EBPFAttachMode, EBPFLoader, EBPFProgramType

    loader_available = True
except ImportError:
    loader_available = False
    EBPFLoader = None

try:
    from .bcc_probes import MeshNetworkProbes

    bcc_probes_available = True
except ImportError:
    bcc_probes_available = False
    MeshNetworkProbes = None

try:
    from .metrics_exporter import EBPFMetricsExporter

    metrics_available = True
except ImportError:
    metrics_available = False
    EBPFMetricsExporter = None

try:
    from .performance_monitor import EBPFPerformanceMonitor

    performance_monitor_available = True
except ImportError:
    performance_monitor_available = False
    EBPFPerformanceMonitor = None

try:
    from .cilium_integration import (CiliumLikeIntegration, FlowDirection,
                                     FlowVerdict)

    cilium_available = True
except ImportError:
    cilium_available = False
    CiliumLikeIntegration = None

try:
    from .dynamic_fallback import DynamicFallbackController

    fallback_available = True
except ImportError:
    fallback_available = False
    DynamicFallbackController = None

try:
    from .mape_k_integration import EBPFMAPEKIntegration

    mapek_available = True
except ImportError:
    mapek_available = False
    EBPFMAPEKIntegration = None

if TYPE_CHECKING:
    from .cilium_integration import CiliumLikeIntegration
    from .dynamic_fallback import DynamicFallbackController
    from .loader import EBPFLoader
    from .mape_k_integration import EBPFMAPEKIntegration
    from .mesh_probes import MeshNetworkProbes
    from .metrics_exporter import EBPFMetricsExporter
    from .performance_monitor import EBPFPerformanceMonitor

logger = logging.getLogger(__name__)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


