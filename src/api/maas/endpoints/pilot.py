"""
MaaS Pilot Endpoints - Pilot program signup and management.

Provides REST API endpoints for pilot customer onboarding,
mesh instance creation, and billing setup.
"""

import hashlib
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import MeshInstance, User, get_db
from ..auth import get_current_user, UserContext

logger = logging.getLogger(__name__)

router = APIRouter( tags=["pilot"])
_MODULAR_PILOT_SIGNUP_SOURCE_AGENT = "maas-modular-pilot-signup"
_MODULAR_PILOT_STATUS_SOURCE_AGENT = "maas-modular-pilot-status-read"
_MODULAR_PILOT_ACTIVATE_SOURCE_AGENT = "maas-modular-pilot-activate"
_MODULAR_PILOT_LAYERS = {
    _MODULAR_PILOT_SIGNUP_SOURCE_AGENT: "api_modular_pilot_signup_control_action",
    _MODULAR_PILOT_STATUS_SOURCE_AGENT: "api_modular_pilot_status_observed_state",
    _MODULAR_PILOT_ACTIVATE_SOURCE_AGENT: "api_modular_pilot_activation_control_action",
}
_MODULAR_PILOT_CLAIM_BOUNDARY = (
    "Modular MaaS pilot endpoint evidence only. It records local API and database "
    "observations for pilot signup, status, and activation; it does not expose raw "
    "customer identifiers or prove onboarding delivery, billing setup, support ticket "
    "creation, mesh dataplane reachability, durable infrastructure convergence, or "
    "production customer usage."
)
_KNOWN_REGION_BUCKETS = {
    "global",
    "us",
    "eu",
    "asia",
    "apac",
    "na",
    "emea",
}


def _pilot_claim_gate(*, local_api_db_claim_allowed: bool) -> Dict[str, Any]:
    return {
        "local_api_db_lifecycle_claim_allowed": bool(local_api_db_claim_allowed),
        "onboarding_delivery_claim_allowed": False,
        "billing_setup_claim_allowed": False,
        "support_ticket_creation_claim_allowed": False,
        "mesh_dataplane_reachability_claim_allowed": False,
        "durable_infrastructure_convergence_claim_allowed": False,
        "production_customer_usage_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_current_evidence_for_production_claim": True,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _pilot_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is not None:
        event_bus = getattr(getattr(request, "state", None), "event_bus", None)
        if isinstance(event_bus, EventBus):
            return event_bus
        project_root = getattr(getattr(request, "state", None), "project_root", ".")
    else:
        project_root = "."
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize modular MaaS pilot EventBus: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any, *, length: int = 16) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _safe_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, min(int(value), 1_000_000))
    except (TypeError, ValueError):
        return 0


def _length_bucket(value: Any) -> str:
    if value is None:
        return "missing"
    size = len(str(value))
    if size == 0:
        return "empty"
    if size <= 16:
        return "short"
    if size <= 64:
        return "medium"
    if size <= 256:
        return "long"
    return "very_long"


def _region_bucket(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "missing"
    return text if text in _KNOWN_REGION_BUCKETS else "custom"


def _billing_status_bucket(user: Any) -> str:
    if user is None:
        return "missing_user"
    if getattr(user, "stripe_subscription_id", None):
        return "active"
    if getattr(user, "stripe_customer_id", None):
        return "customer_created"
    return "not_setup"


def _pilot_request_summary(
    request: Any = None,
    *,
    pilot_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "pilot_id_hash": _redacted_sha256_prefix(pilot_id),
        "email_hash": _redacted_sha256_prefix(
            str(request.email).lower() if request else None
        ),
        "email_present": bool(request and request.email),
        "company_present": bool(request and request.company),
        "company_length_bucket": _length_bucket(request.company if request else None),
        "contact_name_present": bool(request and request.contact_name),
        "contact_name_length_bucket": _length_bucket(
            request.contact_name if request else None
        ),
        "use_case_present": bool(request and request.use_case),
        "use_case_length_bucket": _length_bucket(request.use_case if request else None),
        "expected_users": _safe_count(request.expected_users if request else None),
        "region": _region_bucket(request.region if request else None),
        "raw_request_values_redacted": True,
    }


def _actor_summary(user: UserContext | None) -> Dict[str, Any]:
    return {
        "authenticated": user is not None,
        "user_id_hash": _redacted_sha256_prefix(getattr(user, "user_id", None)),
        "role": str(getattr(user, "role", "unknown") or "unknown")[:32],
        "plan": str(getattr(user, "plan", "unknown") or "unknown")[:32],
        "raw_actor_values_redacted": True,
    }


def _pilot_identity_summary(
    *,
    pilot_id: Optional[str] = None,
    user_id: Optional[str] = None,
    mesh_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "pilot_id_hash": _redacted_sha256_prefix(pilot_id),
        "user_id_hash": _redacted_sha256_prefix(user_id),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "raw_identifiers_redacted": True,
    }


def _db_evidence(
    *,
    action: str,
    user_lookup_attempted: bool = False,
    user_found: bool = False,
    mesh_lookup_attempted: bool = False,
    mesh_found: bool = False,
    user_write_attempted: bool = False,
    mesh_write_attempted: bool = False,
    commit_attempted: bool = False,
    commit_succeeded: bool = False,
    rollback_attempted: bool = False,
) -> Dict[str, Any]:
    return {
        "storage_backend": "sqlalchemy_session",
        "action": action,
        "user_lookup_attempted": bool(user_lookup_attempted),
        "user_found": bool(user_found),
        "mesh_lookup_attempted": bool(mesh_lookup_attempted),
        "mesh_found": bool(mesh_found),
        "user_write_attempted": bool(user_write_attempted),
        "mesh_write_attempted": bool(mesh_write_attempted),
        "commit_attempted": bool(commit_attempted),
        "commit_succeeded": bool(commit_succeeded),
        "rollback_attempted": bool(rollback_attempted),
        "raw_db_values_redacted": True,
    }


def _mesh_summary(mesh: Any) -> Dict[str, Any]:
    return {
        "present": mesh is not None,
        "mesh_id_hash": _redacted_sha256_prefix(getattr(mesh, "id", None)),
        "owner_id_hash": _redacted_sha256_prefix(getattr(mesh, "owner_id", None)),
        "status": str(getattr(mesh, "status", "missing") or "missing")[:32],
        "nodes": _safe_count(getattr(mesh, "nodes", None)),
        "join_token_present": bool(getattr(mesh, "join_token", None)),
        "raw_mesh_values_redacted": True,
    }


def _pilot_http_event_type(status_code: int) -> EventType:
    if status_code >= 500:
        return EventType.TASK_FAILED
    if status_code >= 400:
        return EventType.TASK_BLOCKED
    return EventType.PIPELINE_STAGE_END


def _publish_pilot_event(
    *,
    http_request: Request | None,
    source_agent: str,
    operation: str,
    stage: str,
    status_text: str,
    started: float,
    http_status_code: int,
    request_summary: Optional[Dict[str, Any]] = None,
    actor_summary: Optional[Dict[str, Any]] = None,
    pilot_identity: Optional[Dict[str, Any]] = None,
    db_evidence: Optional[Dict[str, Any]] = None,
    mesh_summary: Optional[Dict[str, Any]] = None,
    billing_status: Optional[str] = None,
    onboarding_url_present: Optional[bool] = None,
    billing_setup_url_present: Optional[bool] = None,
    reason: Optional[str] = None,
    event_type: Optional[EventType] = None,
) -> Optional[str]:
    event_bus = _pilot_event_bus_from_request(http_request)
    if event_bus is None:
        return None

    layer = _MODULAR_PILOT_LAYERS[source_agent]
    payload: Dict[str, Any] = {
        "component": "api.maas.endpoints.pilot",
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "stage": stage,
        "status": status_text,
        "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        "http_status_code": http_status_code,
        "control_action": layer.endswith("_control_action"),
        "observed_state": "observed_state" in layer,
        "source_quality": "local_db_observed",
        "request_summary": request_summary
        or {"raw_request_values_redacted": True},
        "actor_summary": actor_summary or _actor_summary(None),
        "pilot_identity": pilot_identity or _pilot_identity_summary(),
        "db_evidence": db_evidence
        or _db_evidence(action="none"),
        "mesh_summary": mesh_summary or _mesh_summary(None),
        "billing_status": billing_status,
        "onboarding_url_present": (
            onboarding_url_present if isinstance(onboarding_url_present, bool) else None
        ),
        "billing_setup_url_present": (
            billing_setup_url_present
            if isinstance(billing_setup_url_present, bool)
            else None
        ),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_gate": _pilot_claim_gate(
            local_api_db_claim_allowed=http_status_code < 400,
        ),
        "claim_boundary": _MODULAR_PILOT_CLAIM_BOUNDARY,
    }
    if reason:
        payload["reason"] = reason

    try:
        event = event_bus.publish(
            event_type or _pilot_http_event_type(http_status_code),
            source_agent,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish modular MaaS pilot evidence: %s", exc)
        return None


class PilotSignupRequest(BaseModel):
    """Request model for pilot signup."""
    email: EmailStr = Field(..., description="Pilot customer email")
    company: Optional[str] = Field(None, description="Company name")
    contact_name: str = Field(..., description="Contact person name")
    expected_users: int = Field(5, description="Expected number of users", ge=1, le=50)
    use_case: str = Field(..., description="Pilot use case description")
    region: str = Field("global", description="Preferred region")


class PilotSignupResponse(BaseModel):
    """Response model for pilot signup."""
    pilot_id: str
    user_id: str
    mesh_id: str
    onboarding_url: str
    billing_setup_url: Optional[str] = None
    status: str = "pending_setup"


class PilotStatusResponse(BaseModel):
    """Response model for pilot status."""
    pilot_id: str
    status: str
    mesh_id: str
    user_count: int
    billing_status: str
    created_at: str


@router.post(
    "/signup",
    response_model=PilotSignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pilot program signup",
    description="Register a new pilot customer with mesh instance creation.",
)
async def pilot_signup(
    request: PilotSignupRequest,
    http_request: Request = None,
    db: Session = Depends(get_db),
) -> PilotSignupResponse:
    """
    Sign up a new pilot customer.

    Creates user account, mesh instance, and initiates billing setup.
    """
    started = time.monotonic()
    request_evidence = _pilot_request_summary(request)

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_SIGNUP_SOURCE_AGENT,
            operation="modular_pilot_signup",
            stage="signup_blocked",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_409_CONFLICT,
            request_summary=request_evidence,
            db_evidence=_db_evidence(
                action="duplicate_email_lookup",
                user_lookup_attempted=True,
                user_found=True,
            ),
            reason="email_already_registered",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Generate IDs
    pilot_id = str(uuid.uuid4())[:8]
    user_id = f"pilot-{pilot_id}"
    mesh_id = f"pilot-mesh-{pilot_id}"

    try:
        # Create user account
        new_user = User(
            id=user_id,
            email=request.email,
            full_name=request.contact_name,
            company=request.company,
            plan="pilot",
            role="user",
        )
        db.add(new_user)

        # Create mesh instance
        join_token = str(uuid.uuid4())
        mesh = MeshInstance(
            id=mesh_id,
            name=f"Pilot Mesh - {request.company or request.contact_name}",
            owner_id=user_id,
            plan="pilot",
            region=request.region,
            nodes=request.expected_users,
            join_token=join_token,
        )
        db.add(mesh)

        db.commit()

        logger.info(
            "Pilot signup completed: %s email_hash=%s",
            pilot_id,
            _redacted_sha256_prefix(str(request.email).lower()),
        )

        # In production, this would trigger:
        # - Email with onboarding instructions
        # - Stripe checkout session creation
        # - Pilot support ticket creation
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_SIGNUP_SOURCE_AGENT,
            operation="modular_pilot_signup",
            stage="signup_created",
            status_text="success",
            started=started,
            http_status_code=status.HTTP_201_CREATED,
            request_summary=request_evidence,
            pilot_identity=_pilot_identity_summary(
                pilot_id=pilot_id,
                user_id=user_id,
                mesh_id=mesh_id,
            ),
            db_evidence=_db_evidence(
                action="create_pilot_user_and_mesh",
                user_lookup_attempted=True,
                user_found=False,
                user_write_attempted=True,
                mesh_write_attempted=True,
                commit_attempted=True,
                commit_succeeded=True,
            ),
            mesh_summary=_mesh_summary(mesh),
            billing_status="not_setup",
            onboarding_url_present=True,
            billing_setup_url_present=True,
        )

        return PilotSignupResponse(
            pilot_id=pilot_id,
            user_id=user_id,
            mesh_id=mesh_id,
            onboarding_url=f"/pilot/{pilot_id}/onboarding",
            billing_setup_url=f"/pilot/{pilot_id}/billing",
            status="pending_setup",
        )

    except Exception as e:
        db.rollback()
        logger.error("Pilot signup failed: %s", type(e).__name__)
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_SIGNUP_SOURCE_AGENT,
            operation="modular_pilot_signup",
            stage="signup_failed",
            status_text="failed",
            started=started,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_summary=request_evidence,
            pilot_identity=_pilot_identity_summary(
                pilot_id=pilot_id,
                user_id=user_id,
                mesh_id=mesh_id,
            ),
            db_evidence=_db_evidence(
                action="create_pilot_user_and_mesh",
                user_lookup_attempted=True,
                user_found=False,
                user_write_attempted=True,
                mesh_write_attempted=True,
                commit_attempted=True,
                commit_succeeded=False,
                rollback_attempted=True,
            ),
            reason="db_write_failed",
            event_type=EventType.TASK_FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pilot account",
        )


@router.get(
    "/{pilot_id}/status",
    response_model=PilotStatusResponse,
    summary="Get pilot status",
    description="Get the current status of a pilot program.",
)
async def get_pilot_status(
    pilot_id: str,
    http_request: Request = None,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PilotStatusResponse:
    """
    Get pilot status.

    Only accessible by the pilot customer or admin.
    """
    started = time.monotonic()
    user_id = f"pilot-{pilot_id}"
    request_evidence = _pilot_request_summary(pilot_id=pilot_id)
    pilot_identity = _pilot_identity_summary(pilot_id=pilot_id, user_id=user_id)

    # Check permissions
    if user.user_id != user_id and getattr(user, "role", "user") != "admin":
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_STATUS_SOURCE_AGENT,
            operation="modular_pilot_status",
            stage="status_access_denied",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_403_FORBIDDEN,
            request_summary=request_evidence,
            actor_summary=_actor_summary(user),
            pilot_identity=pilot_identity,
            db_evidence=_db_evidence(action="permission_check"),
            reason="access_denied",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get user and mesh
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_STATUS_SOURCE_AGENT,
            operation="modular_pilot_status",
            stage="status_not_found",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_404_NOT_FOUND,
            request_summary=request_evidence,
            actor_summary=_actor_summary(user),
            pilot_identity=pilot_identity,
            db_evidence=_db_evidence(
                action="read_pilot_user",
                user_lookup_attempted=True,
                user_found=False,
            ),
            reason="pilot_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pilot not found",
        )

    mesh = db.query(MeshInstance).filter(MeshInstance.owner_id == user_id).first()

    # Determine billing status
    billing_status = "not_setup"
    if db_user.stripe_subscription_id:
        billing_status = "active"
    elif db_user.stripe_customer_id:
        billing_status = "customer_created"
    _publish_pilot_event(
        http_request=http_request,
        source_agent=_MODULAR_PILOT_STATUS_SOURCE_AGENT,
        operation="modular_pilot_status",
        stage="status_read",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        request_summary=request_evidence,
        actor_summary=_actor_summary(user),
        pilot_identity=_pilot_identity_summary(
            pilot_id=pilot_id,
            user_id=user_id,
            mesh_id=getattr(mesh, "id", None),
        ),
        db_evidence=_db_evidence(
            action="read_pilot_status",
            user_lookup_attempted=True,
            user_found=True,
            mesh_lookup_attempted=True,
            mesh_found=mesh is not None,
        ),
        mesh_summary=_mesh_summary(mesh),
        billing_status=_billing_status_bucket(db_user),
    )

    return PilotStatusResponse(
        pilot_id=pilot_id,
        status="active" if mesh and mesh.status == "active" else "setup",
        mesh_id=mesh.id if mesh else None,
        user_count=mesh.nodes if mesh else 0,
        billing_status=billing_status,
        created_at=db_user.created_at.isoformat() if db_user.created_at else None,
    )


@router.post(
    "/{pilot_id}/activate",
    summary="Activate pilot",
    description=(
        "Mark pilot lifecycle as active in local control state. This is not "
        "production readiness, customer usage, billing setup, or dataplane proof."
    ),
)
async def activate_pilot(
    pilot_id: str,
    http_request: Request = None,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Activate pilot instance.

    Only accessible by admin.
    """
    started = time.monotonic()
    request_evidence = _pilot_request_summary(pilot_id=pilot_id)
    user_id = f"pilot-{pilot_id}"
    pilot_identity = _pilot_identity_summary(pilot_id=pilot_id, user_id=user_id)

    if getattr(user, "role", "user") != "admin":
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_ACTIVATE_SOURCE_AGENT,
            operation="modular_pilot_activate",
            stage="activate_access_denied",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_403_FORBIDDEN,
            request_summary=request_evidence,
            actor_summary=_actor_summary(user),
            pilot_identity=pilot_identity,
            db_evidence=_db_evidence(action="permission_check"),
            reason="admin_required",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    mesh = db.query(MeshInstance).filter(MeshInstance.owner_id == user_id).first()
    if not mesh:
        _publish_pilot_event(
            http_request=http_request,
            source_agent=_MODULAR_PILOT_ACTIVATE_SOURCE_AGENT,
            operation="modular_pilot_activate",
            stage="activate_not_found",
            status_text="blocked",
            started=started,
            http_status_code=status.HTTP_404_NOT_FOUND,
            request_summary=request_evidence,
            actor_summary=_actor_summary(user),
            pilot_identity=pilot_identity,
            db_evidence=_db_evidence(
                action="find_pilot_mesh",
                mesh_lookup_attempted=True,
                mesh_found=False,
            ),
            reason="pilot_mesh_not_found",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pilot mesh not found",
        )

    mesh.status = "active"
    db.commit()

    logger.info("Pilot activated: pilot_hash=%s", _redacted_sha256_prefix(pilot_id))
    _publish_pilot_event(
        http_request=http_request,
        source_agent=_MODULAR_PILOT_ACTIVATE_SOURCE_AGENT,
        operation="modular_pilot_activate",
        stage="pilot_activated",
        status_text="success",
        started=started,
        http_status_code=status.HTTP_200_OK,
        request_summary=request_evidence,
        actor_summary=_actor_summary(user),
        pilot_identity=_pilot_identity_summary(
            pilot_id=pilot_id,
            user_id=user_id,
            mesh_id=getattr(mesh, "id", None),
        ),
        db_evidence=_db_evidence(
            action="activate_pilot_mesh",
            mesh_lookup_attempted=True,
            mesh_found=True,
            mesh_write_attempted=True,
            commit_attempted=True,
            commit_succeeded=True,
        ),
        mesh_summary=_mesh_summary(mesh),
    )

    return {
        "message": "Pilot activated successfully",
        "pilot_id": pilot_id,
        "mesh_id": mesh.id,
        "claim_gate": _pilot_claim_gate(local_api_db_claim_allowed=True),
        "claim_boundary": _MODULAR_PILOT_CLAIM_BOUNDARY,
    }


__all__ = ["router"]
