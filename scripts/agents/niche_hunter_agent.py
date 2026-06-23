"""Niche hunter stub.

Previous version (gemini Apr 23) emitted the same hardcoded "AI-Driven
Geofencing for Corporate Laptops" entry every cycle with a refreshed timestamp.
That pattern matches the fabricated-benchmark incident on record for this agent
(see auto-memory evidence_integrity.md) and violates rules/20: a SIMULATED
source must never be allowed to look like fresh intel.

This module is disabled until a real search backend is wired in. To re-enable,
implement `hunt()` against a real source and remove the gate.
"""

from __future__ import annotations

import os
import sys


def hunt() -> dict:
    raise NotImplementedError(
        "niche_hunter_agent: disabled. Implement a real search backend before "
        "enabling. The previous hardcoded-opportunity loop was fabrication and "
        "has been removed per rules/20 (evidence boundary)."
    )


def main() -> int:
    if os.environ.get("X0T_NICHE_HUNTER_ALLOW_STUB") != "1":
        print(
            "niche_hunter_agent is disabled (stub fabrication). "
            "Set X0T_NICHE_HUNTER_ALLOW_STUB=1 only for local dev testing.",
            file=sys.stderr,
        )
        return 2
    hunt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
