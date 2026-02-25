"""
Compatibility redirect → src.core.parl_mapek_integration (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.parl_mapek_integration")
sys.modules[__name__] = _mod
