"""Compatibility bridge to the top-level signed gossip implementation."""

import sys
from importlib import import_module

_mod = import_module("libx0t.network.byzantine.signed_gossip")
sys.modules[__name__] = _mod
