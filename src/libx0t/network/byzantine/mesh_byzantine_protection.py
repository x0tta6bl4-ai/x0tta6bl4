"""Compatibility bridge to the canonical Byzantine protection implementation."""

import sys
from importlib import import_module

_mod = import_module("src.network.byzantine.mesh_byzantine_protection")
sys.modules[__name__] = _mod
