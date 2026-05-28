import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.api.maas_legacy as legacy_mod


def _force_legacy_dependencies_ready(monkeypatch):
    monkeypatch.setattr(legacy_mod, "_legacy_registries_available", lambda: True)
    monkeypatch.setattr(legacy_mod, "_legacy_services_available", lambda: True)
    monkeypatch.setattr(legacy_mod, "_legacy_auth_dependencies_available", lambda: True)
    monkeypatch.setattr(legacy_mod, "_legacy_security_helpers_available", lambda: True)
    monkeypatch.setattr(legacy_mod, "_legacy_db_models_available", lambda: True)
    monkeypatch.setattr(legacy_mod, "PQC_AVAILABLE", True)


def test_legacy_router_has_readiness_route():
    route_paths = [route.path for route in legacy_mod.router.routes]

    assert "/api/v1/maas/readiness" in route_paths


def test_legacy_readiness_ready_when_local_surfaces_are_available(monkeypatch):
    _force_legacy_dependencies_ready(monkeypatch)
    db = MagicMock(spec=["query", "add", "commit", "rollback"])

    payload = legacy_mod._legacy_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["maas_legacy_runtime_ready"] is True
    assert payload["legacy_db_ready"] is True
    assert payload["legacy_registries_ready"] is True
    assert payload["legacy_services_ready"] is True
    assert payload["legacy_auth_ready"] is True
    assert payload["legacy_security_ready"] is True
    assert payload["legacy_models_ready"] is True
    assert payload["pqc_identity_available"] is True
    assert payload["degraded_dependencies"] == []


def test_legacy_readiness_degraded_when_local_surfaces_are_missing(monkeypatch):
    monkeypatch.setattr(legacy_mod, "_legacy_registries_available", lambda: False)
    monkeypatch.setattr(legacy_mod, "_legacy_services_available", lambda: False)
    monkeypatch.setattr(legacy_mod, "_legacy_auth_dependencies_available", lambda: False)
    monkeypatch.setattr(legacy_mod, "_legacy_security_helpers_available", lambda: False)
    monkeypatch.setattr(legacy_mod, "_legacy_db_models_available", lambda: False)

    payload = legacy_mod._legacy_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["maas_legacy_runtime_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "registries",
        "legacy_services",
        "auth_dependencies",
        "security_helpers",
        "db_models",
    ]
    assert "dynamic /{mesh_id}/... route" in payload["claim_boundary"]


def test_legacy_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    _force_legacy_dependencies_ready(monkeypatch)
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(
        legacy_mod.maas_legacy_readiness(request, db=SimpleNamespace())
    )

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database"}
