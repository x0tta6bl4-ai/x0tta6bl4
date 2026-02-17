"""
Shim for backward compatibility.
The core logic has been moved to libx0t.core.
"""
import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
logger.warning("DEPRECATED: src.core is moved to libx0t.core. Please update your imports.")

# Adding libx0t.core to path for compatibility
_ALT = Path(__file__).resolve().parents[1] / 'libx0t' / 'core'
if _ALT.exists() and str(_ALT) not in __path__:
    __path__.append(str(_ALT))
