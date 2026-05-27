from __future__ import annotations

import ast
from pathlib import Path

from src.services.service_identity_registry import (
    KNOWN_EVENT_IDENTITY_SERVICES,
    service_identity_registry_status,
)


ROOT = Path(__file__).resolve().parents[3]


def _service_identity_calls() -> dict[str, set[str]]:
    calls: dict[str, set[str]] = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "service_event_identity" not in source:
            continue
        tree = ast.parse(source)
        constants: dict[str, str] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                constants[node.targets[0].id] = node.value.value

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "service_event_identity":
                continue
            for keyword in node.keywords:
                if keyword.arg != "service_name":
                    continue
                if isinstance(keyword.value, ast.Constant):
                    service_name = str(keyword.value.value)
                elif (
                    isinstance(keyword.value, ast.Name)
                    and keyword.value.id in constants
                ):
                    service_name = constants[keyword.value.id]
                else:
                    raise AssertionError(
                        f"Unsupported service_name expression in {path}:{node.lineno}"
                    )
                calls.setdefault(service_name, set()).add(str(path.relative_to(ROOT)))
    return calls


def test_service_identity_registry_matches_current_service_event_identity_calls():
    observed = _service_identity_calls()
    registered = {
        item["service_name"]: item["entrypoint"]
        for item in KNOWN_EVENT_IDENTITY_SERVICES
    }

    assert registered == {
        service_name: sorted(paths)[0]
        for service_name, paths in observed.items()
    }


def test_service_identity_registry_status_is_redacted(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_SERVICE_SPIFFE_ID", "spiffe://secret/service")
    monkeypatch.setenv("X0TTA6BL4_SERVICE_DID", "did:mesh:secret")
    monkeypatch.setenv(
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    )

    payload = service_identity_registry_status()

    assert payload["status"] == "ok"
    assert payload["redacted"] is True
    assert payload["services_total"] == len(KNOWN_EVENT_IDENTITY_SERVICES)
    assert payload["services_with_any_identity"] == payload["services_total"]
    assert payload["services_complete"] == payload["services_total"]
    assert "spiffe://secret" not in repr(payload)
    assert "did:mesh:secret" not in repr(payload)
    assert "0xeeee" not in repr(payload)
