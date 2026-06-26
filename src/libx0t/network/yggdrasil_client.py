"""Compatibility bridge to the top-level Yggdrasil client implementation."""
from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("libx0t.network.yggdrasil_client")
sys.modules[__name__] = _mod

