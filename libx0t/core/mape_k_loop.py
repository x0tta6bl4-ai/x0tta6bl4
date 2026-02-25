"""
Compatibility redirect → src.core.mape_k_loop (canonical implementation).

src.core.mape_k_loop is the superset (tracing support, optional DB).
All new code should import from src.core.mape_k_loop directly.
"""
import sys
from importlib import import_module

_mod = import_module("src.core.mape_k_loop")
sys.modules[__name__] = _mod
