"""
src.core — canonical package location.

NOTE: Migration to libx0t.core is in progress but not yet complete;
src/core/*.py files are still the authoritative source.
The warning below is suppressed until migration finishes.
"""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
# Migration in progress — src/core is still the canonical location.
# Warning suppressed until libx0t.core contains up-to-date implementations.
logger.debug("src.core: migration to libx0t.core pending.")

# Forward libx0t.core → src.core so both import paths resolve correctly.
_ALT = Path(__file__).resolve().parents[1] / 'libx0t' / 'core'
if _ALT.exists() and str(_ALT) not in __path__:
    __path__.append(str(_ALT))
