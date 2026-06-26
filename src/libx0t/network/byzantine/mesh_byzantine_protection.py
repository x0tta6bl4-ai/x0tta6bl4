"""Compatibility bridge to the top-level Byzantine protection implementation."""
from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("libx0t.network.byzantine.mesh_byzantine_protection")
sys.modules[__name__] = _mod

