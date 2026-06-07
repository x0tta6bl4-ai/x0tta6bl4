"""Compatibility exports for the MaaS signed playbooks endpoint module."""

import sys

from .maas.endpoints import playbooks as _playbooks

sys.modules[__name__] = _playbooks
