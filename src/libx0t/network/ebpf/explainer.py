"""Compatibility bridge to the canonical eBPF explainer implementation."""

import sys
from importlib import import_module

_mod = import_module("src.network.ebpf.explainer")
sys.modules[__name__] = _mod
