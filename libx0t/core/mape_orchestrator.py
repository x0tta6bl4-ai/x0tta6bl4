"""
Compatibility redirect → src.core.mape_orchestrator (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_orchestrator")
sys.modules[__name__] = _mod
