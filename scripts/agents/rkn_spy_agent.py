"""RKN/TSPU intel stub.

Previous version (gemini Apr 23) emitted the same hardcoded "New TSPU module
update suspected" entry every cycle with a refreshed timestamp and
"Aggregated behavioral data (Simulated)" as source. Under rules/20 that is a
SIMULATED output, and under rules/40 the MAPE-K executor could act on it if
confidence ever drifted above 0.9. Both are unacceptable.

This module is disabled until a real feed (RSS / parser / telemetry source) is
wired in and the output is gated by explicit SIMULATED/VERIFIED tagging.
"""

from __future__ import annotations

import os
import sys


def spy_on_rkn() -> dict:
    raise NotImplementedError(
        "rkn_spy_agent: disabled. Implement a real intel source before "
        "enabling. The previous hardcoded-intel loop was fabrication and "
        "has been removed per rules/20 (evidence boundary)."
    )


def main() -> int:
    if os.environ.get("X0T_RKN_SPY_ALLOW_STUB") != "1":
        print(
            "rkn_spy_agent is disabled (stub fabrication). "
            "Set X0T_RKN_SPY_ALLOW_STUB=1 only for local dev testing.",
            file=sys.stderr,
        )
        return 2
    spy_on_rkn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
