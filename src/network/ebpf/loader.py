"""
EBPFLoader — Base class for eBPF program loaders.

Provides common infrastructure for loading and managing eBPF programs.
Subclasses implement specific program loading logic (XDP, TC, etc.).

BCC_STUB_MODE env var allows unit tests to instantiate loaders without
root privileges or a real BCC installation.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from bcc import BPF
    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False


class EBPFLoader:
    """
    Base class for eBPF program loaders.

    Provides:
    - programs_dir path management
    - bpf object lifecycle (set by subclass)
    - graceful cleanup

    Raises RuntimeError on init when BCC is unavailable AND
    BCC_STUB_MODE env var is not set to "true".
    """

    def __init__(self, programs_dir: Path):
        stub_mode = os.getenv("BCC_STUB_MODE", "false").lower() == "true"
        if not BCC_AVAILABLE and not stub_mode:
            raise RuntimeError(
                "BCC (BPF Compiler Collection) not available. "
                "Install bcc-tools or set BCC_STUB_MODE=true for testing."
            )
        self.programs_dir = Path(programs_dir)
        self.bpf = None
        logger.debug("EBPFLoader initialized: programs_dir=%s", self.programs_dir)

    def cleanup(self):
        """Release eBPF resources held by the BPF object."""
        if self.bpf:
            try:
                self.bpf.cleanup()
            except Exception as exc:
                logger.warning("BPF cleanup error: %s", exc)
            self.bpf = None

    def __del__(self):
        self.cleanup()
