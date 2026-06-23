import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.api.maas_compat as compat_mod


def _force_compat_dependencies_ready(monkeypatch):
    monkeypatch.setattr(compat_mod, "_compat_auth_alias_available", lambda: True)
    monkeypatch.setattr(compat_mod, "_compat_legacy_deploy_available", lambda: True)
    monkeypatch.setattr(compat_mod, "_compat_billing_alias_available", lambda: True)
    monkeypatch.setattr(compat_mod, "_compat_models_available", lambda: True)


def test_compat_router_has_readiness_route():
    route_paths = [route.path for route in compat_mod.router.routes]

    assert "/api/v1/maas/compat/readiness" in route_paths


def test_compat_readiness_ready_when_alias_surfaces_are_available(monkeypatch):
    _force_compat_dependencies_ready(monkeypatch)
    db = MagicMock(spec=["query", "add", "commit"])

    payload = compat_mod._compat_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["compat_runtime_ready"] is True
    assert payload["compat_db_ready"] is True
    assert payload["auth_alias_ready"] is True
    assert payload["legacy_deploy_ready"] is True
    assert payload["billing_alias_ready"] is True
    assert payload["compat_models_ready"] is True
    assert payload["degraded_dependencies"] == []


def test_compat_readiness_degraded_when_alias_surfaces_are_missing(monkeypatch):
    monkeypatch.setattr(compat_mod, "_compat_auth_alias_available", lambda: False)
    monkeypatch.setattr(compat_mod, "_compat_legacy_deploy_available", lambda: False)
    monkeypatch.setattr(compat_mod, "_compat_billing_alias_available", lambda: False)
    monkeypatch.setattr(compat_mod, "_compat_models_available", lambda: False)

    payload = compat_mod._compat_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["compat_runtime_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "auth_alias",
        "legacy_deploy_alias",
        "billing_alias",
        "compat_models",
    ]
    assert "does not register a user" in payload["claim_boundary"]


def test_compat_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    _force_compat_dependencies_ready(monkeypatch)
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(
        compat_mod.maas_compat_readiness(request, db=SimpleNamespace())
    )

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database"}
