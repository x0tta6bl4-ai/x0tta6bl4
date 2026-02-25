"""
Compatibility redirect → src.core.mape_k_self_learning (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_k_self_learning")
sys.modules[__name__] = _mod
