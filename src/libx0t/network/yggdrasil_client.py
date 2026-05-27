"""Compatibility bridge to the top-level Yggdrasil client implementation."""

import sys
from importlib import import_module

_mod = import_module("libx0t.network.yggdrasil_client")
sys.modules[__name__] = _mod
