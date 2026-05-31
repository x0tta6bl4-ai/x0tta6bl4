"""Compatibility module for MaaS telemetry.

Expose ``src.api.maas.endpoints.telemetry`` under the historical
``src.api.maas_telemetry`` import path, including underscored helper functions
used by MaaS node heartbeat/readback code.
"""

from __future__ import annotations

import sys

from src.api.maas.endpoints import telemetry as _telemetry

sys.modules[__name__] = _telemetry
