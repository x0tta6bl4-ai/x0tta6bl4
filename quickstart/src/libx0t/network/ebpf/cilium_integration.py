"""Compatibility bridge to the top-level Cilium-like eBPF integration."""
from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("libx0t.network.ebpf.cilium_integration")
sys.modules[__name__] = _mod

