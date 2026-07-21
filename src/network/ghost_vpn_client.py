from __future__ import annotations

"""
Ghost VPN Client Bridge

The real implementation is located at:
services/nl-server/ghost-vpn/ghost_vpn_client.py

This bridge module exports the required classes without duplicating code.
Экспериментально.
"""

import importlib.util
import sys
from pathlib import Path


def _load_real_module():
    base_dir = Path(__file__).parent.parent.parent
    real_path = base_dir / "services" / "nl-server" / "ghost-vpn" / "ghost_vpn_client.py"

    if real_path.exists():
        spec = importlib.util.spec_from_file_location("ghost_vpn_client_real", str(real_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["ghost_vpn_client_real"] = module
            spec.loader.exec_module(module)
            return module
    return None

_real_module = _load_real_module()
if _real_module:
    globals().update({k: v for k, v in _real_module.__dict__.items() if not k.startswith('_')})
