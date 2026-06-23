from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agent_bazaar_submit_skill.py"


def load_module():
    spec = importlib.util.spec_from_file_location("agent_bazaar_submit_skill", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_payload_points_to_public_x402_endpoint() -> None:
    module = load_module()

    payload = module.build_payload(
        public_base_url="https://example.ngrok-free.dev/",
        service_path="/paid/api-docs",
        price_usd=0.03,
    )

    assert payload["name"] == "x0tta6bl4 API Docs Generator"
    assert payload["type"] == "api"
    assert payload["category"] == "code-generation"
    assert payload["price_per_call"] == 0.03
    assert payload["x402_endpoint"] == "https://example.ngrok-free.dev/paid/api-docs"
    assert module.missing_payload_fields(payload) == []


def test_missing_payload_fields_rejects_zero_price() -> None:
    module = load_module()

    payload = module.build_payload(
        public_base_url="https://example.ngrok-free.dev",
        service_path="/paid/api-docs",
        price_usd=0.0,
    )

    assert "price_per_call" in module.missing_payload_fields(payload)
