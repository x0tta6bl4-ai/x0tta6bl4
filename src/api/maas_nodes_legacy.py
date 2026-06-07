"""
MaaS Nodes Legacy API Shim — x0tta6bl4
=====================================

Compatibility shim for v4.0 architecture.
Redirects to modular nodes_legacy router in src/api/maas/endpoints/nodes_legacy.py.

DEPRECATED: Use src.api.maas.endpoints.nodes instead.
"""

import logging
import warnings
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

# Import from modular router
from .maas.endpoints.nodes_legacy import router, _set_external_telemetry

logger = logging.getLogger(__name__)

warnings.warn(
    "src.api.maas_nodes_legacy is deprecated. Use src.api.maas.endpoints.nodes instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-exports for existing imports
__all__ = [
    "router",
    "_set_external_telemetry",
]
