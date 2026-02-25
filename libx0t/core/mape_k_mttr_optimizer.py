"""
Compatibility redirect → src.core.mape_k_mttr_optimizer (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_k_mttr_optimizer")
sys.modules[__name__] = _mod
