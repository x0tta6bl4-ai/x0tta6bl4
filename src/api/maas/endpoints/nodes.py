"""Compatibility module for modular MaaS node endpoints.

The split implementation is still in progress under ``src.api.maas.nodes``.
Keep this router on the proven endpoint implementation until the split reaches
behavioral parity with the existing registry/provisioner route tests.
"""

from __future__ import annotations

import sys

from src.api.maas.endpoints import nodes_legacy as _legacy

sys.modules[__name__] = _legacy
