"""Compatibility bridge to the canonical signed gossip implementation."""

import sys
from importlib import import_module

_mod = import_module("src.network.byzantine.signed_gossip")
sys.modules[__name__] = _mod
