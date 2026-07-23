"""Compatibility bridge to the top-level eBPF explainer implementation."""
from __future__ import annotations

import sys
from importlib import import_module

_mod = import_module("libx0t.network.ebpf.explainer")
sys.modules[__name__] = _mod

