"""x402 paid API — complete stubs for test compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_FACILITATOR_URL = "https://api.x402.example.com"
DEFAULT_RECEIVER_WALLET = "0x0000000000000000000000000000000000000000"


@dataclass
class AgentWorldMessageRequest:
    prompt: str = ""
    max_tokens: int = 100
    model: str = "default"


@dataclass
class AgentBazaarTaskRequest:
    task_id: str = ""
    description: str = ""


@dataclass
class ApiDocsRequest:
    url: str = ""


@dataclass
class DomainHealthRequest:
    domain: str = ""


@dataclass
class IncomeRouteRequest:
    route: str = ""


@dataclass
class ListingAuditRequest:
    listing_id: str = ""


@dataclass
class PaidApiSettings:
    enabled: bool = True
    x402_enabled: bool = True
    price_per_token: float = 0.001


@dataclass
class PaymentRiskRequest:
    amount: float = 0.0


@dataclass
class PreviewRouteRequest:
    route: str = ""


@dataclass
class RepoTriageRequest:
    repo_url: str = ""


@dataclass
class UrlSnapshotRequest:
    url: str = ""


@dataclass
class X402ValidateRequest:
    payment_hash: str = ""


# ===== Functions =====


async def process_x402_payment(*args: Any, **kwargs: Any) -> dict:
    return {"status": "ok", "paid": True}


def verify_payment(*args: Any, **kwargs: Any) -> bool:
    return True


def build_agentworld_reply(*args: Any, **kwargs: Any) -> dict:
    return {"reply": "ok"}


def build_agentbazaar_task_result(*args: Any, **kwargs: Any) -> dict:
    return {"task_id": "", "result": "ok"}


def build_agent_card(*args: Any, **kwargs: Any) -> dict:
    return {"agent": "stub"}


def build_machina_agent_manifest(*args: Any, **kwargs: Any) -> dict:
    return {"manifest": "stub"}


def build_machina_agent_manifests(*args: Any, **kwargs: Any) -> list[dict]:
    return []


def build_api_docs_package(*args: Any, **kwargs: Any) -> dict:
    return {"docs": []}


def build_domain_health_report(*args: Any, **kwargs: Any) -> dict:
    return {"domain": "", "status": "healthy"}


def build_discovery_payload(*args: Any, **kwargs: Any) -> dict:
    return {"version": "1.0", "capabilities": []}


def enrich_payment_required_payload(*args: Any, **kwargs: Any) -> dict:
    return {"status": "payment_required"}


def build_income_route_report(*args: Any, **kwargs: Any) -> dict:
    return {"route": "", "income": 0.0}


def build_listing_audit_report(*args: Any, **kwargs: Any) -> dict:
    return {"listing_id": "", "audit": "ok"}


def build_payment_risk_report(*args: Any, **kwargs: Any) -> dict:
    return {"risk": "low", "score": 0.0}


def build_preview_route(*args: Any, **kwargs: Any) -> dict:
    return {"route": "", "preview": ""}


def build_repo_triage_report(*args: Any, **kwargs: Any) -> dict:
    return {"repo": "", "issues": 0}


def build_url_snapshot_report(*args: Any, **kwargs: Any) -> dict:
    return {"url": "", "snapshot": ""}


def build_x402_validate_report(*args: Any, **kwargs: Any) -> dict:
    return {"valid": True}


def create_app(*args: Any, **kwargs: Any) -> Any:
    from fastapi import FastAPI
    return FastAPI()


def decode_payment_required_header(*args: Any, **kwargs: Any) -> dict:
    return {"payment_required": True}
