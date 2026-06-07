from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/archtools_directory_submit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("archtools_directory_submit", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_submission_payload_uses_archtools_field_names() -> None:
    mod = _load_module()

    payload = mod.build_submission_payload(
        name="x0tta6bl4 Domain Health Lite",
        service_url="https://example.test/paid/domain-health",
        description="Small x402 API.",
        contact_email="ops@example.test",
    )

    assert payload == {
        "name": "x0tta6bl4 Domain Health Lite",
        "url": "https://example.test/paid/domain-health",
        "description": "Small x402 API.",
        "contact_email": "ops@example.test",
    }
    assert mod.missing_payload_fields(payload) == []


def test_missing_payload_fields_requires_contact_email() -> None:
    mod = _load_module()

    missing = mod.missing_payload_fields(
        {
            "name": "x0tta6bl4",
            "url": "https://example.test/paid/domain-health",
            "description": "Small x402 API.",
            "contact_email": "",
        }
    )

    assert missing == ["contact_email"]


def test_summarize_reports_missing_contact_email_without_submission() -> None:
    mod = _load_module()

    summary = mod.summarize(
        skipped_reason="missing_contact_email",
        submit=None,
        search=mod.HttpResult(ok=True, http_status=200, payload={"services": []}),
        payload=None,
    )

    assert summary["submitted"] is False
    assert summary["skipped_reason"] == "missing_contact_email"
    assert summary["next_action"] == "set_ARCHTOOLS_CONTACT_EMAIL_locally_then_rerun"


def test_summarize_detects_directory_visibility() -> None:
    mod = _load_module()

    summary = mod.summarize(
        skipped_reason=None,
        submit=mod.HttpResult(ok=True, http_status=200, payload={"ok": True}),
        search=mod.HttpResult(
            ok=True,
            http_status=200,
            payload={"services": [{"name": "x0tta6bl4 Domain Health Lite"}]},
        ),
        payload={
            "url": "https://example.test/paid/domain-health",
            "contact_email": "ops@example.test",
        },
    )

    assert summary["submitted"] is True
    assert summary["directory_visible"] is True
    assert summary["next_action"] == "keep_directory_watch_running"
