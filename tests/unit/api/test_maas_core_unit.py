"""
Focused unit tests for src/api/maas_core.py performance-critical paths.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.api import maas_core
from src.database import Base, MeshInstance, MeshNode, User


def _fake_cross_plane_claim_gate(_claims, *, surface):
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "surface": surface,
        "allowed": False,
    }


def test_list_meshes_uses_single_select_and_aggregates_node_counts(tmp_path, monkeypatch):
    db_path = tmp_path / "maas_core_perf.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()

    try:
        owner_id = "user-perf-1"
        db.add(
            User(
                id=owner_id,
                email="perf-owner@example.com",
                password_hash="hash",
                api_key="perf-key-1",
            )
        )
        db.add(
            User(
                id="other-user",
                email="other-owner@example.com",
                password_hash="hash",
                api_key="perf-key-2",
            )
        )
        db.add_all(
            [
                MeshInstance(id="mesh-a", name="A", owner_id=owner_id, plan="starter", status="active"),
                MeshInstance(id="mesh-b", name="B", owner_id=owner_id, plan="starter", status="active"),
                MeshInstance(id="mesh-c", name="C", owner_id="other-user", plan="starter", status="active"),
            ]
        )
        db.add_all(
            [
                MeshNode(id="a-1", mesh_id="mesh-a", status="healthy", device_class="edge"),
                MeshNode(id="a-2", mesh_id="mesh-a", status="healthy", device_class="edge"),
                MeshNode(id="b-1", mesh_id="mesh-b", status="healthy", device_class="edge"),
                MeshNode(id="c-1", mesh_id="mesh-c", status="healthy", device_class="edge"),
            ]
        )
        db.commit()

        monkeypatch.setattr(maas_core, "_last_pricing_agent_attempt_at", None)
        monkeypatch.setattr(maas_core, "_PRICING_AGENT_INTERVAL_SECONDS", 3600)
        pricing_mock = MagicMock()
        monkeypatch.setattr(maas_core.pricing_agent, "analyze_and_propose", pricing_mock)
        monkeypatch.setattr(
            maas_core,
            "cross_plane_claim_gate_metadata",
            _fake_cross_plane_claim_gate,
        )

        select_statements = []

        def _capture_selects(_conn, _cursor, statement, _params, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine, "before_cursor_execute", _capture_selects)
        try:
            result = maas_core.list_meshes(
                current_user=SimpleNamespace(id=owner_id),
                db=db,
            )
        finally:
            event.remove(engine, "before_cursor_execute", _capture_selects)

        assert pricing_mock.call_count == 1
        assert len(select_statements) == 1

        by_id = {item["id"]: item for item in result}
        assert set(by_id.keys()) == {"mesh-a", "mesh-b"}
        assert by_id["mesh-a"]["nodes_count"] == 2
        assert by_id["mesh-b"]["nodes_count"] == 1
        assert (
            by_id["mesh-a"]["maas_core_lifecycle_claim_gate"][
                "local_mesh_lifecycle_claim_allowed"
            ]
            is True
        )
        assert (
            by_id["mesh-a"]["maas_core_lifecycle_claim_gate"][
                "infrastructure_provisioning_claim_allowed"
            ]
            is False
        )
        assert (
            by_id["mesh-a"]["maas_core_lifecycle_claim_gate"][
                "dataplane_delivery_claim_allowed"
            ]
            is False
        )
        assert (
            by_id["mesh-a"]["cross_plane_claim_gate"]["surface"]
            == "maas_core.lifecycle.list"
        )
        assert by_id["mesh-a"]["cross_plane_claim_gate"]["allowed"] is False
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_maybe_run_pricing_agent_is_rate_limited(monkeypatch):
    monkeypatch.setattr(maas_core, "_last_pricing_agent_attempt_at", None)
    monkeypatch.setattr(maas_core, "_PRICING_AGENT_INTERVAL_SECONDS", 3600)
    pricing_mock = MagicMock()
    monkeypatch.setattr(maas_core.pricing_agent, "analyze_and_propose", pricing_mock)

    fake_db = MagicMock()
    maas_core._maybe_run_pricing_agent(fake_db)
    maas_core._maybe_run_pricing_agent(fake_db)

    assert pricing_mock.call_count == 1


def test_lifecycle_claim_headers_explain_local_db_boundary():
    response = maas_core.Response()

    maas_core._set_maas_core_lifecycle_claim_headers(response)

    assert (
        response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_core_lifecycle_claim_gate.v1"
    )
    assert (
        response.headers["X-X0TTA6BL4-Local-DB-Lifecycle-Claim-Allowed"]
        == "true"
    )
    assert (
        response.headers["X-X0TTA6BL4-Infrastructure-Provisioning-Claim-Allowed"]
        == "false"
    )
    assert (
        response.headers["X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"]
        == "false"
    )
    assert (
        response.headers["X-X0TTA6BL4-Production-Readiness-Claim-Allowed"]
        == "false"
    )


@pytest.mark.asyncio
async def test_deploy_mesh_returns_lifecycle_claim_gate(monkeypatch):
    monkeypatch.setattr(
        maas_core,
        "cross_plane_claim_gate_metadata",
        _fake_cross_plane_claim_gate,
    )

    req = maas_core.MeshDeployRequest(
        name="test-mesh",
        nodes=2,
        billing_plan="starter",
    )
    db = MagicMock()

    def _refresh(instance):
        instance.created_at = datetime(2026, 1, 1)

    db.refresh.side_effect = _refresh

    result = await maas_core.deploy_mesh(
        req,
        current_user=SimpleNamespace(id="owner-1"),
        db=db,
    )

    assert result["status"] == "active"
    assert (
        result["maas_core_lifecycle_claim_gate"][
            "local_db_lifecycle_claim_allowed"
        ]
        is True
    )
    assert (
        result["maas_core_lifecycle_claim_gate"][
            "node_reachability_claim_allowed"
        ]
        is False
    )
    assert (
        result["maas_core_lifecycle_claim_gate"][
            "dataplane_delivery_claim_allowed"
        ]
        is False
    )
    assert result["cross_plane_claim_gate"]["surface"] == "maas_core.lifecycle.deploy"
    assert result["cross_plane_claim_gate"]["allowed"] is False


@pytest.mark.asyncio
async def test_terminate_mesh_returns_lifecycle_claim_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        maas_core,
        "cross_plane_claim_gate_metadata",
        _fake_cross_plane_claim_gate,
    )

    db_path = tmp_path / "maas_core_terminate.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_local()

    try:
        owner_id = "owner-term-1"
        db.add(
            User(
                id=owner_id,
                email="owner-term@example.com",
                password_hash="hash",
                api_key="term-key-1",
            )
        )
        db.add(
            MeshInstance(
                id="mesh-term",
                name="Terminate",
                owner_id=owner_id,
                plan="starter",
                status="active",
            )
        )
        db.commit()

        result = await maas_core.terminate_mesh(
            "mesh-term",
            current_user=SimpleNamespace(id=owner_id),
            db=db,
        )

        assert result["status"] == "terminated"
        assert (
            result["maas_core_lifecycle_claim_gate"][
                "infrastructure_provisioning_claim_allowed"
            ]
            is False
        )
        assert (
            result["cross_plane_claim_gate"]["surface"]
            == "maas_core.lifecycle.terminate"
        )
        assert result["cross_plane_claim_gate"]["allowed"] is False
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
