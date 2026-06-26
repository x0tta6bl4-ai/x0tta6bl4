"""Compatibility bridge to the top-level signed gossip implementation."""
from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("libx0t.network.byzantine.signed_gossip")
sys.modules[__name__] = _mod

