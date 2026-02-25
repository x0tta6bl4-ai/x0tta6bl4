"""
Compatibility redirect → src.core.mape_k_thread_safe (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_k_thread_safe")
sys.modules[__name__] = _mod
