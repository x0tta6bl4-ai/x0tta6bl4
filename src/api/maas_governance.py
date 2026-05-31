"""Compatibility wrapper for the modular MaaS governance endpoint."""

import sys

from .maas.endpoints import governance as modular

sys.modules[__name__] = modular
