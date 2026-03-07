"""Unit tests for src/api/maas/endpoints/mesh.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import mesh as mod
from src.api.maas.models import MeshDeployRequest
from src.api.maas.registry import _mesh_registry, _registry_lock


def _build_instance(mesh_id: str, owner_id: str, nodes: int) -> SimpleNamespace:
    now = datetime.utcnow()
    return SimpleNamespace(
        mesh_id=mesh_id,
        name="unit-mesh",
        owner_id=owner_id,
        plan="pro",
        status="active",
        join_token=f"token-{uuid.uuid4().hex}",
        join_token_expires_at=now + timedelta(hours=1),
        created_at=now,
        target_nodes=nodes,
        pqc_profile="edge",
        pqc_enabled=True,
        obfuscation="none",
        traffic_profile="none",
        region="global",
    )


class _Provisioner:
    def __init__(self, instance: SimpleNamespace):
        self._instance = instance

    async def provision_mesh(self, **_kwargs):
        return self._instance


@pytest.mark.asyncio
async def test_deploy_mesh_persists_mesh_instance_to_db(monkeypatch):
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    instance = _build_instance(mesh_id=mesh_id, owner_id="owner-1", nodes=7)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    request = MeshDeployRequest(name="mesh-unit", nodes=7, billing_plan="pro")
    user = UserContext(user_id="owner-1", plan="pro")
    db = MagicMock()

    response = await mod.deploy_mesh(request, user, db)

    db.add.assert_called_once()
    db.commit.assert_called_once()

    persisted = db.add.call_args.args[0]
    assert persisted.id == mesh_id
    assert persisted.owner_id == "owner-1"
    assert persisted.plan == "pro"
    assert persisted.nodes == 7
    assert persisted.pqc_profile == "edge"
    assert persisted.region == "global"

    assert response.mesh_id == mesh_id
    assert response.status == "active"
    assert response.join_config["enrollment_token"] == instance.join_token


@pytest.mark.asyncio
async def test_deploy_mesh_db_failure_rolls_back_registry_and_returns_http_500(monkeypatch):
    mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
    instance = _build_instance(mesh_id=mesh_id, owner_id="owner-2", nodes=3)
    monkeypatch.setattr(mod, "get_provisioner", lambda: _Provisioner(instance))

    async with _registry_lock:
        _mesh_registry[mesh_id] = instance

    request = MeshDeployRequest(name="mesh-unit-fail", nodes=3, billing_plan="pro")
    user = UserContext(user_id="owner-2", plan="pro")
    db = MagicMock()
    db.commit.side_effect = RuntimeError("db write failed")

    with pytest.raises(HTTPException) as exc:
        await mod.deploy_mesh(request, user, db)

    assert exc.value.status_code == 500
    assert "database persistence error" in str(exc.value.detail).lower()
    db.rollback.assert_called_once()

    async with _registry_lock:
        assert mesh_id not in _mesh_registry

