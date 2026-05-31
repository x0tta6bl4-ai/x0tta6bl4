"""Compatibility wrapper for the modular MaaS analytics endpoint."""

import sys

from .maas.endpoints import analytics as modular

sys.modules[__name__] = modular
