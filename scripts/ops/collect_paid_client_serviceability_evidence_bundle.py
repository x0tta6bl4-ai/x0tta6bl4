import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integration.operator_bundle_gate import main_for_profile


if __name__ == "__main__":
    raise SystemExit(main_for_profile(
        "paid_client_path",
        ".tmp/validation-shards/paid-client-serviceability-evidence-collector-current.json",
    ))
