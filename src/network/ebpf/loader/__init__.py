"""
eBPF loader package.

This package intentionally exposes two API surfaces:
1) Legacy `src.network.ebpf.loader` symbols used by old runtime/tests.
2) New modular components under `src.network.ebpf.loader.*`.
"""

from __future__ import annotations

import sys
import types

from . import _legacy
from ._legacy import (
    EBPFAttachError,
    EBPFAttachMode,
    EBPFLoader,
    EBPFLoadError,
    EBPFProgramType,
    ELF_TOOLS_AVAILABLE,
    Path,
    record_ebpf_compilation,
    record_ebpf_event,
    safe_run,
    subprocess,
)
from .attach_manager import EBPFAttachManager
from .map_manager import EBPFMapManager
from .orchestrator import EBPFLoaderOrchestrator
from .program_loader import EBPFProgramLoader

# Optional when pyelftools is not installed.
ELFFile = getattr(_legacy, "ELFFile", None)

_PATCH_THROUGH_NAMES = {
    "ELF_TOOLS_AVAILABLE",
    "ELFFile",
    "safe_run",
    "Path",
    "subprocess",
    "record_ebpf_event",
    "record_ebpf_compilation",
}


class _CompatLoaderModule(types.ModuleType):
    """Keep legacy module globals in sync with package-level monkeypatching."""

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in _PATCH_THROUGH_NAMES:
            setattr(_legacy, name, value)


_module = sys.modules.get(__name__)
if _module is not None and not isinstance(_module, _CompatLoaderModule):
    _module.__class__ = _CompatLoaderModule

__all__ = [
    "EBPFLoader",
    "EBPFLoaderOrchestrator",
    "EBPFProgramLoader",
    "EBPFAttachManager",
    "EBPFMapManager",
    "EBPFProgramType",
    "EBPFAttachMode",
    "EBPFLoadError",
    "EBPFAttachError",
]
