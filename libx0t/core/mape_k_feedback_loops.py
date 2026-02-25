"""
Compatibility redirect → src.core.mape_k_feedback_loops (canonical implementation).
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_k_feedback_loops")
sys.modules[__name__] = _mod
