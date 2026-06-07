from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/jaypay_402directory_submit_all.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("jaypay_402directory_submit_all", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_all_submits_each_public_service(tmp_path: Path, monkeypatch) -> None:
    mod = _load_module()
    calls = []

    def fake_build_public_services(public_base_url, settings):
        return [
            {
                "id": "svc-one",
                "name": "Service One",
                "description": "First paid x402 service.",
                "url": f"{public_base_url}/paid/one",
                "price_usd": 0.01,
                "network": "base",
                "category": "developer-tool",
                "tags": ["x402", "one"],
            },
            {
                "id": "svc-two",
                "name": "Service Two",
                "description": "Second paid x402 service.",
                "url": f"{public_base_url}/paid/two",
                "price_usd": 0.02,
                "network": "base",
                "category": "data-tool",
                "tags": ["x402", "two"],
            },
        ]

    def fake_run(args):
        calls.append(args)
        return {
            "summary": {
                "submitted": True,
                "submission_known": True,
                "directory_visible": False,
            }
        }

    monkeypatch.setattr(mod, "build_public_services", fake_build_public_services)
    monkeypatch.setattr(mod.single, "run", fake_run)

    status = mod.run_all(
        SimpleNamespace(
            api_base="https://directory.example",
            public_base_url="https://public.example",
            submitter_email="",
            status_file=tmp_path / "all.json",
            timeout_seconds=5.0,
            skip_submit=False,
            force_submit=False,
        )
    )

    assert status["services_total"] == 2
    assert status["submitted_total"] == 2
    assert status["submission_known_total"] == 2
    assert status["failed_total"] == 0
    assert [call.name for call in calls] == ["Service One", "Service Two"]
    assert calls[0].endpoint == "https://public.example/paid/one"
    assert calls[1].tags == "x402,two"
    assert json.loads((tmp_path / "all.json").read_text(encoding="utf-8"))["services_total"] == 2
