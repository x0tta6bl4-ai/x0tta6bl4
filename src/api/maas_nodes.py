"""Compatibility module for the DB-backed MaaS node API.

The split MaaS node implementation is being prepared under
``src.api.maas.nodes`` and ``src.api.maas.endpoints.nodes``.  This public module
keeps the existing DB-backed API surface stable for callers, tests, and
monkeypatches that import ``src.api.maas_nodes`` directly.
"""

from __future__ import annotations

import sys

from src.api import maas_nodes_legacy as _legacy

sys.modules[__name__] = _legacy
