"""Compatibility alias for the DB-backed MaaS auth API."""

import sys as _sys

from src.api import maas_auth_legacy_full as _legacy

globals().update(_legacy.__dict__)
_sys.modules[__name__] = _legacy
