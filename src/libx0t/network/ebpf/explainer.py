"""Compatibility bridge to the top-level eBPF explainer implementation."""

import sys
from importlib import import_module

_mod = import_module("libx0t.network.ebpf.explainer")
sys.modules[__name__] = _mod
