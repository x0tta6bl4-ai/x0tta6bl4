"""
Deprecated compatibility proxy for legacy post-quantum imports.

Use ``src.security.pqc`` for new code.  This module keeps its legacy
``__file__`` while mirroring old monkeypatch targets such as
``src.libx0t.security.post_quantum.KeyEncapsulation`` into
``src.security.pqc.compat``.
"""
from __future__ import annotations

from types import ModuleType
import sys
import warnings

from src.security.pqc import compat as _compat

warnings.warn(
    "Importing from " + "src.libx0t.security.post_quantum is deprecated. "
    "Use 'from src.security.pqc import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = list(_compat.__all__) + ["KeyEncapsulation", "Signature"]
_MIRRORED_NAMES = set(__all__) | {"CRYPTOGRAPHY_AVAILABLE"}

for _name in __all__:
    globals()[_name] = getattr(_compat, _name)


class _CompatProxyModule(ModuleType):
    def __getattr__(self, name: str):
        try:
            return getattr(_compat, name)
        except AttributeError as exc:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from exc

    def __setattr__(self, name: str, value):
        super().__setattr__(name, value)
        if name in _MIRRORED_NAMES or hasattr(_compat, name):
            setattr(_compat, name, value)


sys.modules[__name__].__class__ = _CompatProxyModule
