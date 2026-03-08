"""Unit tests for src/api/maas_supply_chain.py — pure helpers and in-memory paths."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.maas_supply_chain import (
    AttestationMeta,
    BinaryVerifyRequest,
    ComponentEntry,
    SBOMRegisterRequest,
    SBOMResponse,
    _coerce_components,
    _db_session_available,
    _legacy_verify,
    _lookup_in_memory_sbom,
    _safe_record_audit,
    _sbom_registry,
    router,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_db() -> MagicMock:
    """Return a mock that looks like a valid SQLAlchemy Session."""
    db = MagicMock()
    db.query = MagicMock()
    db.commit = MagicMock()
    return db


def _no_db() -> SimpleNamespace:
    """Return an object that does NOT look like a DB session."""
    return SimpleNamespace()


# ---------------------------------------------------------------------------
# _db_session_available
# ---------------------------------------------------------------------------

class TestDbSessionAvailable:
    def test_mock_session_is_available(self):
        assert _db_session_available(_fake_db()) is True

    def test_plain_object_not_available(self):
        assert _db_session_available(_no_db()) is False

    def test_none_not_available(self):
        assert _db_session_available(None) is False

    def test_object_with_only_query_not_available(self):
        obj = SimpleNamespace(query=lambda: None)
        assert _db_session_available(obj) is False

    def test_object_with_only_commit_not_available(self):
        obj = SimpleNamespace(commit=lambda: None)
        assert _db_session_available(obj) is False

    def test_object_with_both_attrs_available(self):
        obj = SimpleNamespace(query=lambda: None, commit=lambda: None)
        assert _db_session_available(obj) is True


# ---------------------------------------------------------------------------
# _coerce_components
# ---------------------------------------------------------------------------

class TestCoerceComponents:
    def test_component_entry_object(self):
        comp = ComponentEntry(name="foo", version="1.0", type="library")
        result = _coerce_components([comp])
        assert result == [{"name": "foo", "version": "1.0", "type": "library"}]

    def test_dict_passthrough(self):
        d = {"name": "bar", "version": "2.0", "type": "application"}
        result = _coerce_components([d])
        assert result[0] == d

    def test_dict_is_copied(self):
        d = {"name": "bar", "version": "2.0"}
        result = _coerce_components([d])
        result[0]["extra"] = "x"
        assert "extra" not in d  # mutation does not affect original

    def test_arbitrary_object_via_dict(self):
        obj = SimpleNamespace(name="baz", version="3.0", type="tool")
        result = _coerce_components([obj])
        assert result[0]["name"] == "baz"
        assert result[0]["version"] == "3.0"

    def test_empty_list(self):
        assert _coerce_components([]) == []

    def test_multiple_entries(self):
        comps = [
            ComponentEntry(name="a", version="1"),
            {"name": "b", "version": "2"},
        ]
        result = _coerce_components(comps)
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[1]["name"] == "b"


# ---------------------------------------------------------------------------
# _lookup_in_memory_sbom
# ---------------------------------------------------------------------------

class TestLookupInMemorySBOM:
    def test_exact_key_with_prefix(self):
        result = _lookup_in_memory_sbom("v3.4.0")
        assert result is not None
        assert result["version"] == "3.4.0"

    def test_key_without_prefix_adds_v(self):
        # "3.4.0" → candidates = ["3.4.0", "v3.4.0"] → matches "v3.4.0" in registry
        result = _lookup_in_memory_sbom("3.4.0")
        assert result is not None
        assert result["version"] == "3.4.0"

    def test_unknown_version_returns_none(self):
        result = _lookup_in_memory_sbom("v99.0.0")
        assert result is None

    def test_result_is_a_copy(self):
        r1 = _lookup_in_memory_sbom("v3.4.0")
        r2 = _lookup_in_memory_sbom("v3.4.0")
        r1["injected"] = True
        assert "injected" not in r2

    def test_returns_dict_type(self):
        result = _lookup_in_memory_sbom("v3.4.0")
        assert isinstance(result, dict)

    def test_has_expected_fields(self):
        result = _lookup_in_memory_sbom("v3.4.0")
        for field in ("id", "version", "format", "checksum_sha256", "components", "attestation"):
            assert field in result


# ---------------------------------------------------------------------------
# _legacy_verify
# ---------------------------------------------------------------------------

class TestLegacyVerify:
    def _known_checksum(self) -> str:
        return _sbom_registry["v3.4.0"]["checksum_sha256"]

    def test_checksums_match_returns_verified(self):
        result = _legacy_verify("v3.4.0", self._known_checksum())
        assert result["status"] == "verified"
        assert result["integrity"] == "valid"
        assert result["pqc_compliant"] is True

    def test_checksum_mismatch_returns_mismatch(self):
        result = _legacy_verify("v3.4.0", "sha256:wrong")
        assert result["status"] == "mismatch"
        assert result["integrity"] == "compromised"
        assert result["pqc_compliant"] is False

    def test_unknown_version_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _legacy_verify("v0.0.0", "sha256:abc")
        assert exc_info.value.status_code == 400
        assert "not found" in exc_info.value.detail.lower()

    def test_node_id_default(self):
        result = _legacy_verify("v3.4.0", self._known_checksum())
        assert result["node_id"] == "legacy-node"

    def test_custom_node_id(self):
        result = _legacy_verify("v3.4.0", self._known_checksum(), node_id="node-xyz")
        assert result["node_id"] == "node-xyz"

    def test_sbom_id_present(self):
        result = _legacy_verify("v3.4.0", self._known_checksum())
        assert result["sbom_id"] == _sbom_registry["v3.4.0"]["id"]

    def test_agent_version_in_result(self):
        result = _legacy_verify("v3.4.0", self._known_checksum())
        assert result["agent_version"] == "v3.4.0"


# ---------------------------------------------------------------------------
# _safe_record_audit
# ---------------------------------------------------------------------------

class TestSafeRecordAudit:
    def test_no_op_when_db_unavailable(self):
        # Should not raise
        _safe_record_audit(
            _no_db(),
            action="TEST",
            user_id="u1",
            payload={},
            status_code=200,
        )

    def test_calls_record_audit_log_when_db_available(self):
        db = _fake_db()
        with patch("src.api.maas_supply_chain.record_audit_log") as mock_ral:
            _safe_record_audit(
                db,
                action="SBOM_REGISTERED",
                user_id="u1",
                payload={"version": "1.0"},
                status_code=201,
            )
            mock_ral.assert_called_once()
            db.commit.assert_called_once()

    def test_rollback_on_audit_exception(self):
        db = _fake_db()
        with patch("src.api.maas_supply_chain.record_audit_log", side_effect=RuntimeError("db down")):
            # Should not propagate exception
            _safe_record_audit(
                db,
                action="SBOM_REGISTERED",
                user_id="u1",
                payload={},
                status_code=201,
            )
            db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------

class TestComponentEntry:
    def test_defaults_type_to_library(self):
        c = ComponentEntry(name="x", version="1.0")
        assert c.type == "library"

    def test_custom_type(self):
        c = ComponentEntry(name="x", version="1.0", type="application")
        assert c.type == "application"

    def test_model_dump(self):
        c = ComponentEntry(name="x", version="1.0", type="tool")
        d = c.model_dump()
        assert d == {"name": "x", "version": "1.0", "type": "tool"}


class TestAttestationMeta:
    def test_defaults(self):
        a = AttestationMeta(signer="ci@x.net", signed_at="2026-01-01T00:00:00Z")
        assert a.type == "Sigstore-Bundle"
        assert a.bundle_url is None

    def test_optional_bundle_url(self):
        a = AttestationMeta(
            signer="ci@x.net",
            signed_at="2026-01-01T00:00:00Z",
            bundle_url="https://example.com/bundle",
        )
        assert a.bundle_url == "https://example.com/bundle"


class TestSBOMRegisterRequest:
    def test_valid_request(self):
        req = SBOMRegisterRequest(
            version="v4.0.0",
            checksum_sha256="sha256:abcdefabcdef",
            components=[ComponentEntry(name="lib", version="1.0")],
        )
        assert req.format == "CycloneDX-JSON"
        assert req.attestation is None

    def test_version_too_short_raises(self):
        with pytest.raises(Exception):
            SBOMRegisterRequest(
                version="v1",
                checksum_sha256="sha256:abcdefabcdef",
                components=[],
            )

    def test_checksum_too_short_raises(self):
        with pytest.raises(Exception):
            SBOMRegisterRequest(
                version="v4.0.0",
                checksum_sha256="short",
                components=[],
            )


class TestBinaryVerifyRequest:
    def test_required_fields(self):
        req = BinaryVerifyRequest(
            node_id="n1",
            agent_version="v3.4.0",
            checksum_sha256="sha256:abcdef",
        )
        assert req.mesh_id is None
        assert req.node_id == "n1"


# ---------------------------------------------------------------------------
# FastAPI endpoint tests (in-memory / no-DB mode)
# ---------------------------------------------------------------------------

def _make_app_client():
    """Build a TestClient with DB dependency overridden to return a no-DB stub."""
    from fastapi import FastAPI
    from src.database import get_db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: _no_db()
    return TestClient(app, raise_server_exceptions=False)


class TestGetSBOMEndpoint:
    def setup_method(self):
        self.client = _make_app_client()

    def test_known_version_returns_200(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom/v3.4.0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "3.4.0"

    def test_version_without_v_prefix_returns_200(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom/3.4.0")
        assert resp.status_code == 200

    def test_unknown_version_returns_404(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom/v99.0.0")
        assert resp.status_code == 404

    def test_response_has_components(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom/v3.4.0")
        data = resp.json()
        assert isinstance(data["components"], list)
        assert len(data["components"]) > 0


class TestListSBOMsEndpoint:
    def setup_method(self):
        self.client = _make_app_client()

    def test_returns_200(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom")
        assert resp.status_code == 200

    def test_returns_list(self):
        resp = self.client.get("/api/v1/maas/supply-chain/sbom")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestRegisterArtifactEndpoint:
    def setup_method(self):
        from fastapi import FastAPI
        from src.database import get_db
        from src.api.maas_auth import get_current_user_from_maas

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: _no_db()

        def _admin_user():
            return SimpleNamespace(id="admin-1", role="admin")

        app.dependency_overrides[get_current_user_from_maas] = _admin_user
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_register_new_version_returns_200(self):
        resp = self.client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            json={
                "version": "v5.0.0-test",
                "checksum_sha256": "sha256:newchecksum123",
                "components": [{"name": "agent", "version": "5.0.0"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v5.0.0-test"
        # cleanup
        _sbom_registry.pop("v5.0.0-test", None)

    def test_register_duplicate_version_returns_409(self):
        version = "v5.1.0-dup-test"
        _sbom_registry[version] = {"id": "x", "version": version, "format": "CycloneDX-JSON",
                                    "checksum_sha256": "sha256:x", "components": [], "attestation": None,
                                    "created_at": "2026-01-01"}
        try:
            resp = self.client.post(
                "/api/v1/maas/supply-chain/register-artifact",
                json={
                    "version": version,
                    "checksum_sha256": "sha256:newchecksum123",
                    "components": [],
                },
            )
            assert resp.status_code == 409
        finally:
            _sbom_registry.pop(version, None)


class TestVerifyBinaryEndpoint:
    def setup_method(self):
        self.client = _make_app_client()

    def test_known_version_correct_checksum_verified(self):
        checksum = _sbom_registry["v3.4.0"]["checksum_sha256"]
        resp = self.client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "node-test-1",
                "agent_version": "v3.4.0",
                "checksum_sha256": checksum,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["integrity"] == "valid"
        assert data["pqc_compliant"] is True

    def test_known_version_wrong_checksum_mismatch(self):
        resp = self.client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "node-test-2",
                "agent_version": "v3.4.0",
                "checksum_sha256": "sha256:wrong_checksum",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "mismatch"
        assert data["integrity"] == "compromised"

    def test_unknown_version_returns_400(self):
        resp = self.client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "node-test-3",
                "agent_version": "v99.0.0",
                "checksum_sha256": "sha256:abc",
            },
        )
        assert resp.status_code == 400

    def test_node_id_returned_in_result(self):
        checksum = _sbom_registry["v3.4.0"]["checksum_sha256"]
        resp = self.client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "my-node-123",
                "agent_version": "v3.4.0",
                "checksum_sha256": checksum,
            },
        )
        assert resp.json()["node_id"] == "my-node-123"
