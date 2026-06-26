"""Re-export names from the original _legacy.py module.

This package shadowed the ``_legacy.py`` file when its ``__init__.py`` was
added.  To preserve backwards compatibility we load the real module via
``importlib`` and re-export every name.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys as _sys

_here = pathlib.Path(__file__).resolve().parent
_src = _here.parent / "_legacy.py"
_spec = importlib.util.spec_from_file_location(
    f"{__name__}._original", str(_src)
)
_mod = importlib.util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

# Re-export every public name so existing import statements still work.
from src.network.ebpf.loader._legacy._original import *  # noqa: F401,F403
