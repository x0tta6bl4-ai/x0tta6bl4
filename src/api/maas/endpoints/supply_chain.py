"""
MaaS Supply Chain Security — x0tta6bl4
=======================================

DB-backed SBOM registry and per-node binary attestation.
Includes an in-memory compatibility layer for direct unit calls.
"""

import json
import logging
import uuid
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import get_current_user_from_maas, require_role
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.resilience.reliability_policy import mark_degraded_dependency
from src.database import MeshNode, NodeBinaryAttestation, SBOMEntry, User, get_db
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/supply-chain", tags=["MaaS Supply Chain"])

_SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT = "maas-supply-chain-sbom-read"
_SUPPLY_CHAIN_SBOM_READ_LAYER = "api_supply_chain_sbom_observed_state"
_SUPPLY_CHAIN_SBOM_LIST_SOURCE_AGENT = "maas-supply-chain-sbom-list-read"
_SUPPLY_CHAIN_SBOM_LIST_LAYER = "api_supply_chain_sbom_observed_state"
_SUPPLY_CHAIN_REGISTER_SOURCE_AGENT = "maas-supply-chain-artifact-register"
_SUPPLY_CHAIN_REGISTER_LAYER = "api_supply_chain_artifact_control_action"
_SUPPLY_CHAIN_VERIFY_SOURCE_AGENT = "maas-supply-chain-binary-verify"
_SUPPLY_CHAIN_VERIFY_LAYER = "api_supply_chain_binary_attestation_control"
_SUPPLY_CHAIN_NODE_ATTESTATION_SOURCE_AGENT = "maas-supply-chain-node-attestation-read"
_SUPPLY_CHAIN_NODE_ATTESTATION_LAYER = "api_supply_chain_attestation_observed_state"
_SUPPLY_CHAIN_MESH_ATTESTATION_SOURCE_AGENT = "maas-supply-chain-mesh-attestation-read"
_SUPPLY_CHAIN_MESH_ATTESTATION_LAYER = "api_supply_chain_attestation_observed_state"
_SUPPLY_CHAIN_CLAIM_BOUNDARY = (
    "MaaS supply-chain evidence records bounded local SBOM and binary-attestation "
    "metadata from DB, compatibility registry, audit-log, and optional eBPF adapter "
    "surfaces. It does not expose raw emails, user IDs, node IDs, mesh IDs, SBOM IDs, "
    "versions, checksums, component names, attestation signer or bundle URLs, API keys, "
    "session tokens, or prove external Sigstore transparency, kernel map state, or "
    "production artifact provenance."
)

_sbom_registry: Dict[str, Dict[str, Any]] = {
    "v3.4.0": {
        "id": "sbom-v340a",
        "version": "3.4.0",
        "format": "CycloneDX-JSON",
        "checksum_sha256": "sha256:abc123",
        "components": [
            {"name": "x0tta6bl4-agent", "version": "3.4.0", "type": "application"},
            {"name": "liboqs", "version": "0.10.1", "type": "library"},
        ],
        "attestation": {
            "type": "Sigstore-Bundle",
            "signer": "ci@x0tta6bl4.net",
            "signed_at": "2026-02-20T00:00:00Z",
            "bundle_url": "https://example.local/sigstore/bundle/v3.4.0",
        },
        "created_at": "2026-02-20T00:00:00Z",
    }
}


class ComponentEntry(BaseModel):
    name: str
    version: str
    type: str = "library"


class AttestationMeta(BaseModel):
    type: str = "Sigstore-Bundle"
    signer: str
    signed_at: str
    bundle_url: Optional[str] = None


class SBOMRegisterRequest(BaseModel):
    version: str = Field(..., min_length=3)
    format: str = Field(default="CycloneDX-JSON")
    checksum_sha256: str = Field(..., min_length=10)
    components: List[ComponentEntry]
    attestation: Optional[AttestationMeta] = None


class SBOMResponse(BaseModel):
    id: Optional[str] = None
    version: str
    format: str
    checksum_sha256: Optional[str] = None
    components: List[Dict[str, Any]]
    attestation: Optional[Dict[str, Any]] = None
    pqc_signature: Optional[str] = None
    created_at: Optional[str] = None


class BinaryVerifyRequest(BaseModel):
    node_id: str
    mesh_id: Optional[str] = None
    agent_version: str
    checksum_sha256: str


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _supply_chain_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS supply-chain EventBus: %s", exc)
        return None


def _supply_chain_actor_summary(user: Any) -> Dict[str, Any]:
    if user is None:
        return {
            "actor_user_id_hash": None,
            "actor_email_hash": None,
            "actor_email_present": False,
            "actor_role": "",
        }
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", "") or "")[:40],
    }


def _status_counts(records: list[Any]) -> Dict[str, int]:
    counts = {"verified": 0, "mismatch": 0, "unknown": 0, "other": 0}
    for record in records:
        status = str(getattr(record, "status", "") or "").strip().lower()
        if status in counts and status != "other":
            counts[status] += 1
        else:
            counts["other"] += 1
    return counts


def _component_count_from_entry(entry: Any) -> int:
    components = None
    if isinstance(entry, dict):
        components = entry.get("components")
    else:
        raw = getattr(entry, "components_json", None)
        if raw:
            try:
                components = json.loads(raw)
            except Exception:
                components = None
    return len(components) if isinstance(components, list) else 0


def _sbom_event_metadata(entry: Any) -> Dict[str, Any]:
    if not entry:
        return {
            "sbom_id_hash": None,
            "version_hash": None,
            "checksum_hash": None,
            "component_count": 0,
            "attestation_present": False,
        }
    if isinstance(entry, dict):
        sbom_id = entry.get("id")
        version = entry.get("version")
        checksum = entry.get("checksum_sha256")
        attestation = entry.get("attestation")
    else:
        sbom_id = getattr(entry, "id", None)
        version = getattr(entry, "version", None)
        checksum = getattr(entry, "checksum_sha256", None)
        attestation = getattr(entry, "attestation_json", None)
    return {
        "sbom_id_hash": _redacted_sha256_prefix(sbom_id),
        "version_hash": _redacted_sha256_prefix(version),
        "checksum_hash": _redacted_sha256_prefix(checksum),
        "component_count": _component_count_from_entry(entry),
        "attestation_present": bool(attestation),
    }


def _publish_supply_chain_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status: str,
    current_user: Any = None,
    version: Any = None,
    checksum_sha256: Any = None,
    sbom_entry: Any = None,
    sbom_entries: list[Any] | None = None,
    node_id: Any = None,
    mesh_id: Any = None,
    sbom_id: Any = None,
    agent_version: Any = None,
    attestation_records: list[Any] | None = None,
    integrity: str | None = None,
    db_backed: bool | None = None,
    legacy_registry_used: bool = False,
    audit_log_attempted: bool = False,
    ebpf_update_attempted: bool = False,
    ebpf_update_succeeded: bool | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _supply_chain_event_bus_from_request(request)
    if event_bus is None:
        return None

    records = list(attestation_records or [])
    entries = list(sbom_entries or [])
    payload: Dict[str, Any] = {
        "component": "api.maas_supply_chain",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_supply_chain_actor_summary(current_user),
        "version_hash": _redacted_sha256_prefix(version or agent_version),
        "checksum_hash": _redacted_sha256_prefix(checksum_sha256),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "sbom_id_hash": _redacted_sha256_prefix(sbom_id),
        "db_backed": db_backed,
        "legacy_registry_used": legacy_registry_used,
        "audit_log_attempted": audit_log_attempted,
        "ebpf_update_attempted": ebpf_update_attempted,
        "ebpf_update_succeeded": ebpf_update_succeeded,
        "http_status_code": http_status_code,
        "read_only": source_agent in {
            _SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
            _SUPPLY_CHAIN_SBOM_LIST_SOURCE_AGENT,
            _SUPPLY_CHAIN_NODE_ATTESTATION_SOURCE_AGENT,
            _SUPPLY_CHAIN_MESH_ATTESTATION_SOURCE_AGENT,
        },
        "observed_state": source_agent in {
            _SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
            _SUPPLY_CHAIN_SBOM_LIST_SOURCE_AGENT,
            _SUPPLY_CHAIN_NODE_ATTESTATION_SOURCE_AGENT,
            _SUPPLY_CHAIN_MESH_ATTESTATION_SOURCE_AGENT,
        },
        "safe_actuator": False,
        "control_action": source_agent in {
            _SUPPLY_CHAIN_REGISTER_SOURCE_AGENT,
            _SUPPLY_CHAIN_VERIFY_SOURCE_AGENT,
        },
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _SUPPLY_CHAIN_CLAIM_BOUNDARY,
    }

    if sbom_entry is not None:
        payload.update(_sbom_event_metadata(sbom_entry))
    if entries:
        payload.update(
            {
                "sbom_count": len(entries),
                "component_count_total": sum(
                    _component_count_from_entry(entry) for entry in entries
                ),
                "attested_sbom_count": sum(
                    1
                    for entry in entries
                    if (
                        bool(entry.get("attestation"))
                        if isinstance(entry, dict)
                        else bool(getattr(entry, "attestation_json", None))
                    )
                ),
            }
        )
    if records:
        status_counts = _status_counts(records)
        payload.update(
            {
                "attestation_count": len(records),
                "status_counts": status_counts,
                "compromised_count": status_counts.get("mismatch", 0),
            }
        )
    if integrity is not None:
        payload["integrity"] = str(integrity or "")[:40]

    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            source_agent,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS supply-chain event: %s", exc)
        return None


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit")


def _ebpf_attestation_filter_available() -> bool:
    try:
        from src.network.ebpf.map_manager import EBPFMapManager

        return callable(getattr(EBPFMapManager, "update_attestation", None))
    except Exception:
        return False


def _supply_chain_readiness_status(db: Any) -> Dict[str, Any]:
    attestation_store_ready = _db_session_available(db)
    sbom_registry_ready = bool(_sbom_registry)
    audit_log_ready = attestation_store_ready and callable(record_audit_log)
    ebpf_filter_adapter_ready = _ebpf_attestation_filter_available()
    persistent_supply_chain_ready = (
        attestation_store_ready
        and audit_log_ready
        and sbom_registry_ready
    )

    degraded_dependencies = []
    if not attestation_store_ready:
        degraded_dependencies.append("database")
    if not sbom_registry_ready:
        degraded_dependencies.append("legacy_sbom_registry")
    if not audit_log_ready:
        degraded_dependencies.append("audit_log")
    if not ebpf_filter_adapter_ready:
        degraded_dependencies.append("ebpf_attestation_filter")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "persistent_supply_chain_ready": persistent_supply_chain_ready,
        "attestation_store_ready": attestation_store_ready,
        "sbom_registry_ready": sbom_registry_ready,
        "audit_log_ready": audit_log_ready,
        "ebpf_filter_adapter_ready": ebpf_filter_adapter_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "SBOMEntry and NodeBinaryAttestation persistence require a "
                "real SQLAlchemy session."
            ),
            "legacy_sbom_registry": (
                "In-memory SBOM registry keeps compatibility verification alive "
                "when the database path is absent."
            ),
            "audit_log": (
                "SBOM registration audit evidence is persisted only when the "
                "database-backed audit path is available."
            ),
            "ebpf_attestation_filter": (
                "Binary verification can update the eBPF attestation adapter, "
                "but readiness does not execute bpftool or prove a kernel map is loaded."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_supply_chain_readiness"
        ),
        "claim_boundary": (
            "Supply-chain readiness distinguishes route availability from durable "
            "SBOM and binary-attestation evidence. It does not prove external "
            "Sigstore transparency, kernel eBPF map state, or production artifact "
            "provenance beyond the local backing services listed above."
        ),
    }


@router.get("/readiness")
async def supply_chain_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _supply_chain_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


def _coerce_components(components: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for component in components:
        if isinstance(component, ComponentEntry):
            normalized.append(component.model_dump())
        elif isinstance(component, dict):
            normalized.append(dict(component))
        else:
            normalized.append(dict(component.__dict__))
    return normalized


def _lookup_in_memory_sbom(version: str) -> Optional[Dict[str, Any]]:
    candidates = [version]
    if version.startswith("v"):
        candidates.append(version[1:])
    else:
        candidates.append(f"v{version}")

    for key in candidates:
        entry = _sbom_registry.get(key)
        if entry:
            return dict(entry)
    return None


def _sbom_to_response_dict(row: SBOMEntry) -> Dict[str, Any]:
    components = json.loads(row.components_json) if row.components_json else []
    attestation = json.loads(row.attestation_json) if row.attestation_json else None
    payload = {
        "id": row.id,
        "version": row.version,
        "format": row.format,
        "checksum_sha256": row.checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }

    # PQC attestation is best-effort in environments where legacy app shims
    # don't expose pqc_sign(). Never fail SBOM read/write because of this.
    try:
        from src.core.app import pqc_sign

        signed = pqc_sign(f"{row.version}:{row.checksum_sha256}".encode())
        if signed:
            payload["pqc_signature"] = signed.hex()
    except Exception as exc:
        logger.warning("PQC signature unavailable for SBOM %s: %s", row.id, exc)
    return payload


def _legacy_verify(agent_version: str, checksum_sha256: str, node_id: str = "legacy-node") -> Dict[str, Any]:
    sbom = _lookup_in_memory_sbom(agent_version)
    if not sbom:
        raise HTTPException(status_code=400, detail=f"SBOM for version '{agent_version}' not found")

    checksums_match = sbom.get("checksum_sha256") == checksum_sha256
    return {
        "status": "verified" if checksums_match else "mismatch",
        "node_id": node_id,
        "agent_version": agent_version,
        "integrity": "valid" if checksums_match else "compromised",
        "pqc_compliant": checksums_match,
        "sbom_id": sbom.get("id"),
    }


def _safe_record_audit(
    db: Any,
    *,
    action: str,
    user_id: Optional[str],
    payload: Dict[str, Any],
    status_code: int,
) -> None:
    if not _db_session_available(db):
        return
    try:
        record_audit_log(
            db, None, action,
            user_id=user_id,
            payload=payload,
            status_code=status_code,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist audit log (%s): %s", action, exc)


@router.get("/sbom/{version}", response_model=SBOMResponse)
async def get_sbom(
    version: str,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Fetch SBOM for a specific agent version. Publicly accessible."""
    started = time.monotonic()
    db_backed = _db_session_available(db)
    if _db_session_available(db):
        row = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
        if not row and version.startswith("v"):
            row = db.query(SBOMEntry).filter(SBOMEntry.version == version[1:]).first()
        if not row:
            _publish_supply_chain_event(
                request,
                source_agent=_SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
                layer=_SUPPLY_CHAIN_SBOM_READ_LAYER,
                stage="supply_chain_sbom_read",
                operation="maas_supply_chain_sbom_read",
                status="denied",
                version=version,
                db_backed=True,
                http_status_code=404,
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="sbom_not_found",
            )
            raise HTTPException(status_code=404, detail=f"SBOM for version '{version}' not found")
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_SBOM_READ_LAYER,
            stage="supply_chain_sbom_read",
            operation="maas_supply_chain_sbom_read",
            status="success",
            version=version,
            sbom_entry=row,
            db_backed=True,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="db_backed_sbom_read",
        )
        return _sbom_to_response_dict(row)

    entry = _lookup_in_memory_sbom(version)
    if not entry:
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_SBOM_READ_LAYER,
            stage="supply_chain_sbom_read",
            operation="maas_supply_chain_sbom_read",
            status="denied",
            version=version,
            db_backed=db_backed,
            legacy_registry_used=True,
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="sbom_not_found",
        )
        raise HTTPException(status_code=404, detail=f"SBOM for version '{version}' not found")
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_SBOM_READ_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_SBOM_READ_LAYER,
        stage="supply_chain_sbom_read",
        operation="maas_supply_chain_sbom_read",
        status="success",
        version=version,
        sbom_entry=entry,
        db_backed=db_backed,
        legacy_registry_used=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="legacy_registry_sbom_read",
    )
    return entry


@router.get("/sbom", response_model=List[SBOMResponse])
async def list_sboms(
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    db_backed = _db_session_available(db)
    if _db_session_available(db):
        rows = db.query(SBOMEntry).order_by(SBOMEntry.created_at.desc()).all()
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_SBOM_LIST_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_SBOM_LIST_LAYER,
            stage="supply_chain_sbom_list_read",
            operation="maas_supply_chain_sbom_list_read",
            status="success",
            sbom_entries=rows,
            db_backed=True,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="db_backed_sbom_list_read",
        )
        return [_sbom_to_response_dict(row) for row in rows]
    entries = [dict(entry) for entry in _sbom_registry.values()]
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_SBOM_LIST_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_SBOM_LIST_LAYER,
        stage="supply_chain_sbom_list_read",
        operation="maas_supply_chain_sbom_list_read",
        status="success",
        sbom_entries=entries,
        db_backed=db_backed,
        legacy_registry_used=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="legacy_registry_sbom_list_read",
    )
    return entries


@router.post("/register-artifact", response_model=SBOMResponse)
async def register_artifact(
    req: Union[SBOMRegisterRequest, SBOMResponse],
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Register a new build artifact SBOM (CI/CD pipeline only)."""
    started = time.monotonic()
    version = req.version
    checksum_sha256 = getattr(req, "checksum_sha256", None) or "sha256:abc123"
    components = _coerce_components(req.components)

    raw_attestation = getattr(req, "attestation", None)
    if isinstance(raw_attestation, AttestationMeta):
        attestation = raw_attestation.model_dump()
    elif isinstance(raw_attestation, dict):
        attestation = dict(raw_attestation)
    else:
        attestation = None

    if _db_session_available(db):
        existing = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
        if existing:
            _publish_supply_chain_event(
                request,
                source_agent=_SUPPLY_CHAIN_REGISTER_SOURCE_AGENT,
                layer=_SUPPLY_CHAIN_REGISTER_LAYER,
                stage="supply_chain_artifact_register",
                operation="maas_supply_chain_artifact_register",
                status="denied",
                current_user=current_user,
                version=version,
                checksum_sha256=checksum_sha256,
                sbom_entry=existing,
                db_backed=True,
                audit_log_attempted=False,
                http_status_code=409,
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="duplicate_sbom",
            )
            raise HTTPException(status_code=409, detail=f"SBOM for version '{version}' already registered")

        sbom_id = f"sbom-{uuid.uuid4().hex[:8]}"
        row = SBOMEntry(
            id=sbom_id,
            version=version,
            format=req.format,
            checksum_sha256=checksum_sha256,
            components_json=json.dumps(components),
            attestation_json=json.dumps(attestation) if attestation else None,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        response_payload = _sbom_to_response_dict(row)

        audit_attempted = True
        _safe_record_audit(
            db,
            action="SBOM_REGISTERED",
            user_id=current_user.id,
            payload={"version": version, "sbom_id": sbom_id, "checksum": checksum_sha256},
            status_code=201,
        )
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_REGISTER_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_REGISTER_LAYER,
            stage="supply_chain_artifact_register",
            operation="maas_supply_chain_artifact_register",
            status="success",
            current_user=current_user,
            version=version,
            checksum_sha256=checksum_sha256,
            sbom_entry=row,
            sbom_id=sbom_id,
            db_backed=True,
            audit_log_attempted=audit_attempted,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="db_backed_sbom_register",
        )
        return response_payload

    if version in _sbom_registry:
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_REGISTER_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_REGISTER_LAYER,
            stage="supply_chain_artifact_register",
            operation="maas_supply_chain_artifact_register",
            status="denied",
            current_user=current_user,
            version=version,
            checksum_sha256=checksum_sha256,
            sbom_entry=_sbom_registry.get(version),
            db_backed=False,
            legacy_registry_used=True,
            http_status_code=409,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="duplicate_sbom",
        )
        raise HTTPException(status_code=409, detail=f"SBOM for version '{version}' already registered")

    sbom_id = getattr(req, "id", None) or f"sbom-{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    entry = {
        "id": sbom_id,
        "version": version,
        "format": req.format,
        "checksum_sha256": checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": created_at,
    }
    _sbom_registry[version] = entry
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_REGISTER_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_REGISTER_LAYER,
        stage="supply_chain_artifact_register",
        operation="maas_supply_chain_artifact_register",
        status="success",
        current_user=current_user,
        version=version,
        checksum_sha256=checksum_sha256,
        sbom_entry=entry,
        sbom_id=sbom_id,
        db_backed=False,
        legacy_registry_used=True,
        audit_log_attempted=False,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="legacy_registry_sbom_register",
    )
    return {
        "status": "registered",
        "id": sbom_id,
        "version": version,
        "format": req.format,
        "checksum_sha256": checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": created_at,
    }


@router.post("/verify-binary")
async def verify_binary(
    req: Union[BinaryVerifyRequest, str],
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    Verify agent binary against the SBOM registry.
    In DB mode, unknown versions return unknown_version (200).
    In direct-call compatibility mode, unknown versions raise 400.
    """
    if isinstance(req, str):
        checksum = db if isinstance(db, str) else ""
        return _legacy_verify(req, checksum_sha256=checksum, node_id="legacy-node")

    if not _db_session_available(db):
        started = time.monotonic()
        try:
            result = _legacy_verify(
                req.agent_version,
                checksum_sha256=req.checksum_sha256,
                node_id=req.node_id,
            )
        except HTTPException as exc:
            _publish_supply_chain_event(
                request,
                source_agent=_SUPPLY_CHAIN_VERIFY_SOURCE_AGENT,
                layer=_SUPPLY_CHAIN_VERIFY_LAYER,
                stage="supply_chain_binary_verify",
                operation="maas_supply_chain_binary_verify",
                status="denied",
                agent_version=req.agent_version,
                checksum_sha256=req.checksum_sha256,
                node_id=req.node_id,
                mesh_id=req.mesh_id,
                db_backed=False,
                legacy_registry_used=True,
                http_status_code=exc.status_code,
                duration_ms=(time.monotonic() - started) * 1000.0,
                reason="sbom_not_found",
            )
            raise
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_VERIFY_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_VERIFY_LAYER,
            stage="supply_chain_binary_verify",
            operation="maas_supply_chain_binary_verify",
            status=result.get("status", "unknown"),
            agent_version=req.agent_version,
            checksum_sha256=req.checksum_sha256,
            node_id=req.node_id,
            mesh_id=req.mesh_id,
            sbom_id=result.get("sbom_id"),
            integrity=result.get("integrity"),
            db_backed=False,
            legacy_registry_used=True,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="legacy_registry_binary_verify",
        )
        return result

    started = time.monotonic()
    sbom = db.query(SBOMEntry).filter(SBOMEntry.version == req.agent_version).first()
    if not sbom:
        _publish_supply_chain_event(
            request,
            source_agent=_SUPPLY_CHAIN_VERIFY_SOURCE_AGENT,
            layer=_SUPPLY_CHAIN_VERIFY_LAYER,
            stage="supply_chain_binary_verify",
            operation="maas_supply_chain_binary_verify",
            status="unknown_version",
            agent_version=req.agent_version,
            checksum_sha256=req.checksum_sha256,
            node_id=req.node_id,
            mesh_id=req.mesh_id,
            db_backed=True,
            http_status_code=200,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="unknown_version",
        )
        return {
            "status": "unknown_version",
            "integrity": "unverifiable",
            "node_id": req.node_id,
            "agent_version": req.agent_version,
        }

    checksums_match = sbom.checksum_sha256 == req.checksum_sha256
    att_status = "verified" if checksums_match else "mismatch"
    ebpf_update_attempted = False
    ebpf_update_succeeded: bool | None = None

    existing_att = (
        db.query(NodeBinaryAttestation)
        .filter(
            NodeBinaryAttestation.node_id == req.node_id,
            NodeBinaryAttestation.sbom_id == sbom.id,
        )
        .first()
    )

    if existing_att:
        existing_att.status = att_status
        existing_att.checksum_sha256 = req.checksum_sha256
        existing_att.verified_at = datetime.utcnow()
    else:
        db.add(
            NodeBinaryAttestation(
                id=f"att-{uuid.uuid4().hex[:8]}",
                node_id=req.node_id,
                mesh_id=req.mesh_id,
                sbom_id=sbom.id,
                agent_version=req.agent_version,
                checksum_sha256=req.checksum_sha256,
                status=att_status,
                verified_at=datetime.utcnow(),
            )
        )

    # 5. Update Kernel-level eBPF filter
    try:
        ebpf_update_attempted = True
        from src.network.ebpf.map_manager import EBPFMapManager
        node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
        if node and node.ip_address:
            if checksums_match:
                EBPFMapManager.update_attestation(node.ip_address, is_attested=True)
            else:
                EBPFMapManager.update_attestation(node.ip_address, is_attested=False)
            ebpf_update_succeeded = True
        else:
            ebpf_update_succeeded = False
    except Exception as e:
        ebpf_update_succeeded = False
        logger.warning(f"⚠️ Failed to update eBPF supply chain filter: {e}")

    audit_attempted = False
    if not checksums_match:
        node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
        if node:
            node.status = "revoked"
            audit_attempted = True
            _safe_record_audit(
                db,
                action="NODE_AUTO_REVOKED_INTEGRITY_FAILURE",
                user_id=None,
                payload={"node_id": req.node_id, "version": req.agent_version},
                status_code=200,
            )
            logger.warning("Node %s auto-revoked due to binary mismatch", req.node_id)

    if _db_session_available(db):
        db.commit()
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_VERIFY_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_VERIFY_LAYER,
        stage="supply_chain_binary_verify",
        operation="maas_supply_chain_binary_verify",
        status=att_status,
        agent_version=req.agent_version,
        checksum_sha256=req.checksum_sha256,
        node_id=req.node_id,
        mesh_id=req.mesh_id,
        sbom_id=sbom.id,
        integrity="valid" if checksums_match else "compromised",
        db_backed=True,
        audit_log_attempted=audit_attempted,
        ebpf_update_attempted=ebpf_update_attempted,
        ebpf_update_succeeded=ebpf_update_succeeded,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="db_backed_binary_verify",
    )
    return {
        "status": att_status,
        "node_id": req.node_id,
        "agent_version": req.agent_version,
        "integrity": "valid" if checksums_match else "compromised",
        "pqc_compliant": checksums_match,
        "sbom_id": sbom.id,
    }


@router.get("/attestations/{node_id}")
async def get_node_attestations(
    node_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Get binary attestation history for a specific node."""
    started = time.monotonic()
    records = (
        db.query(NodeBinaryAttestation)
        .filter(NodeBinaryAttestation.node_id == node_id)
        .order_by(NodeBinaryAttestation.verified_at.desc())
        .all()
    )
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_NODE_ATTESTATION_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_NODE_ATTESTATION_LAYER,
        stage="supply_chain_node_attestation_read",
        operation="maas_supply_chain_node_attestation_read",
        status="success",
        current_user=current_user,
        node_id=node_id,
        attestation_records=records,
        db_backed=_db_session_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="node_attestation_history_read",
    )
    return {
        "node_id": node_id,
        "attestations": [
            {
                "id": record.id,
                "agent_version": record.agent_version,
                "status": record.status,
                "verified_at": record.verified_at.isoformat() if record.verified_at else None,
            }
            for record in records
        ],
    }


@router.get("/mesh-attestation-report/{mesh_id}")
async def get_mesh_attestation_report(
    mesh_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    Aggregate attestation status across all nodes in a mesh.
    Returns counts of verified, mismatch, and unknown nodes.
    """
    started = time.monotonic()
    records = (
        db.query(NodeBinaryAttestation)
        .filter(NodeBinaryAttestation.mesh_id == mesh_id)
        .all()
    )

    counts: Dict[str, int] = {"verified": 0, "mismatch": 0, "unknown": 0}
    for record in records:
        counts[record.status] = counts.get(record.status, 0) + 1

    compromised_nodes = [record.node_id for record in records if record.status == "mismatch"]
    integrity = "clean" if not compromised_nodes else "compromised"
    _publish_supply_chain_event(
        request,
        source_agent=_SUPPLY_CHAIN_MESH_ATTESTATION_SOURCE_AGENT,
        layer=_SUPPLY_CHAIN_MESH_ATTESTATION_LAYER,
        stage="supply_chain_mesh_attestation_read",
        operation="maas_supply_chain_mesh_attestation_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        attestation_records=records,
        integrity=integrity,
        db_backed=_db_session_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="mesh_attestation_report_read",
    )
    return {
        "mesh_id": mesh_id,
        "total_attested": len(records),
        "summary": counts,
        "compromised_nodes": compromised_nodes,
        "integrity": integrity,
    }
