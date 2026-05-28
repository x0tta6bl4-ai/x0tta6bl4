from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.api.maas_policies as policies_mod


def test_policy_readiness_ready_when_db_model_and_rbac_are_available():
    db = MagicMock(spec=["query", "add", "commit", "delete"])

    payload = policies_mod._policy_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["route_registered"] is True
    assert payload["registration_mode"] == "full_mode_only"
    assert payload["route_present_in_light_mode"] is False
    assert payload["lifecycle_binding"] == "route_import_only"
    assert payload["startup_hook_completed"] is None
    assert payload["policy_runtime_ready"] is True
    assert payload["policy_db_ready"] is True
    assert payload["acl_policy_model_ready"] is True
    assert payload["rbac_dependency_ready"] is True
    assert payload["legacy_route_shadowing"]["get_post_shadowed_by_legacy"] is True
    assert payload["degraded_dependencies"] == []


def test_policy_readiness_degraded_when_db_model_and_rbac_are_missing(monkeypatch):
    monkeypatch.setattr(policies_mod, "require_role", None)
    monkeypatch.setattr(policies_mod, "ACLPolicy", SimpleNamespace(id="id"))

    payload = policies_mod._policy_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["policy_runtime_ready"] is False
    assert payload["policy_db_ready"] is False
    assert payload["acl_policy_model_ready"] is False
    assert payload["rbac_dependency_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "acl_policy_model",
        "rbac",
    ]
    assert "legacy in-memory policy handlers" in payload["claim_boundary"]


def test_policy_readiness_endpoint_marks_degraded_dependencies():
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(
        policies_mod.policy_readiness(request=request, db=SimpleNamespace())
    )

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database"}
