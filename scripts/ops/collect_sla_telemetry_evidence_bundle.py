import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.production_raw_evidence_entrypoint import main_for_collector


if __name__ == "__main__":
    raise SystemExit(main_for_collector(
        "sla-telemetry",
        "collector",
        ".tmp/validation-shards/sla-telemetry-evidence-collector-current.json",
    ))
