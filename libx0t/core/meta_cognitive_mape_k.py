"""
Compatibility redirect → src.core.meta_cognitive_mape_k (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.meta_cognitive_mape_k")
sys.modules[__name__] = _mod
