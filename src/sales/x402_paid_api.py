"""Shim for backward compatibility. Use src.sales.x402 instead."""
import warnings
warnings.warn("x402_paid_api.py is deprecated, use src.sales.x402 instead", DeprecationWarning, stacklevel=2)

from src.sales.x402 import create_app, PaidApiSettings
from src.sales.x402.settings import *

__all__ = ["create_app", "PaidApiSettings"]
