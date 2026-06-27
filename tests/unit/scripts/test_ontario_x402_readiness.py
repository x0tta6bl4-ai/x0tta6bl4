from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/ontario_x402_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ontario_x402_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_listing_payload_uses_ontario_category_and_endpoint() -> None:
    module = load_module()

    payload = module.build_listing_payload(
        public_base_url="https://example.ngrok-free.dev/",
        service_path="/paid/api-docs",
    )

    assert payload["name"] == "x0tta6bl4 API Docs Generator"
    assert payload["endpoint"] == "https://example.ngrok-free.dev/paid/api-docs"
    assert payload["method"] == "POST"
    assert payload["category"] == "tools"
    assert payload["price_atomic"] == 30000
    assert payload["price_usdc"] == "0.03"


def test_summarize_readiness_extracts_grade_and_report_url() -> None:
    module = load_module()

    summary = module.summarize_readiness(
        {
            "grade": "ready",
            "readiness_score": 95,
            "report_id": "vrf_test",
            "report_url": "https://ontarioprotocol.com/verify/report/vrf_test",
            "warnings": [{"field": "manifest"}],
        }
    )

    assert summary["grade"] == "ready"
    assert summary["score"] == 95
    assert summary["report_id"] == "vrf_test"
    assert summary["warnings_total"] == 1
