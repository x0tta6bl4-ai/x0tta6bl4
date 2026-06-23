from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/jaypay_402directory_submit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("jaypay_402directory_submit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_submission_payload_matches_402directory_form_fields() -> None:
    mod = _load_module()

    payload = mod.build_submission_payload(
        name="x0tta6bl4 Domain Health Lite",
        description="Small x402 API.",
        endpoint="https://example.test/paid/domain-health",
        method="post",
        price_usdc=0.001,
        chain="Base",
        protocol="x402",
        category="security",
        tags="domain-health,x402",
        example="https://example.test/paid/domain-health",
    )

    assert payload == {
        "name": "x0tta6bl4 Domain Health Lite",
        "description": "Small x402 API.",
        "endpoint": "https://example.test/paid/domain-health",
        "method": "POST",
        "price_usdc": 0.001,
        "chain": "base",
        "protocol": "x402",
        "category": "security",
        "tags": "domain-health,x402",
        "example": "https://example.test/paid/domain-health",
        "submitter_email": "",
    }
    assert mod.missing_payload_fields(payload) == []


def test_missing_payload_fields_does_not_require_optional_email() -> None:
    mod = _load_module()

    payload = {
        "name": "x0tta6bl4",
        "description": "Small x402 API.",
        "endpoint": "https://example.test/paid/domain-health",
        "method": "POST",
        "price_usdc": 0.001,
        "chain": "base",
        "protocol": "x402",
        "category": "security",
        "submitter_email": "",
    }

    assert mod.missing_payload_fields(payload) == []


def test_summarize_waits_for_review_after_successful_submit() -> None:
    mod = _load_module()

    summary = mod.summarize(
        skipped_reason=None,
        submit=mod.HttpResult(ok=True, http_status=200, payload={"ok": True}),
        directory=mod.HttpResult(ok=True, http_status=200, payload={"entries": []}),
        payload={
            "name": "x0tta6bl4 Domain Health Lite",
            "endpoint": "https://example.test/paid/domain-health",
            "price_usdc": 0.001,
        },
    )

    assert summary["submitted"] is True
    assert summary["submission_known"] is True
    assert summary["directory_visible"] is False
    assert summary["next_action"] == "wait_for_402directory_review_and_indexing"


def test_summarize_detects_directory_visibility() -> None:
    mod = _load_module()

    summary = mod.summarize(
        skipped_reason=None,
        submit=None,
        directory=mod.HttpResult(
            ok=True,
            http_status=200,
            payload={"entries": [{"name": "x0tta6bl4 Domain Health Lite"}]},
        ),
        payload={
            "name": "x0tta6bl4 Domain Health Lite",
            "endpoint": "https://example.test/paid/domain-health",
            "price_usdc": 0.001,
        },
    )

    assert summary["directory_visible"] is True
    assert summary["submission_known"] is True
    assert summary["next_action"] == "keep_directory_watch_running"


def test_summarize_reports_already_submitted_as_watch_only() -> None:
    mod = _load_module()

    summary = mod.summarize(
        skipped_reason="already_submitted_or_visible",
        submit=None,
        directory=mod.HttpResult(ok=True, http_status=200, payload={"entries": []}),
        payload={
            "name": "x0tta6bl4 Domain Health Lite",
            "endpoint": "https://example.test/paid/domain-health",
            "price_usdc": 0.001,
        },
    )

    assert summary["submitted"] is False
    assert summary["submission_known"] is True
    assert summary["skipped_reason"] == "already_submitted_or_visible"
    assert summary["next_action"] == "wait_for_402directory_review_and_indexing"
