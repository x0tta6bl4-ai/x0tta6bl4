"""Compatibility bridge to the canonical Cilium-like eBPF integration."""

import sys
from importlib import import_module

_mod = import_module("src.network.ebpf.cilium_integration")
sys.modules[__name__] = _mod
