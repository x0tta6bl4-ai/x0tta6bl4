#!/usr/bin/env python3
"""Rank non-bounty earning paths for x0tta6bl4 agents.

This script is deliberately boring: it does not promise payouts. It records
which channels are already activated, which ones need setup, and which next
step has the best chance of turning agent work into money.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
OUT = ARTIFACT_DIR / "non_bounty_market_matrix.json"


WEIGHTS = {
    "first_money_speed": 0.30,
    "no_upfront_cost": 0.20,
    "automation": 0.20,
    "payout_directness": 0.20,
    "x0tta_fit": 0.10,
}


@dataclass(frozen=True)
class Opportunity:
    name: str
    model: str
    status: str
    first_money_speed: int
    no_upfront_cost: int
    automation: int
    payout_directness: int
    x0tta_fit: int
    evidence: list[str]
    blockers: list[str]
    next_step: str

    @property
    def score(self) -> float:
        return round(
            self.first_money_speed * WEIGHTS["first_money_speed"]
            + self.no_upfront_cost * WEIGHTS["no_upfront_cost"]
            + self.automation * WEIGHTS["automation"]
            + self.payout_directness * WEIGHTS["payout_directness"]
            + self.x0tta_fit * WEIGHTS["x0tta_fit"],
            2,
        )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _status_from_http_artifact(path: Path) -> str:
    if not path.exists():
        return "not_started"
    text = path.read_text(encoding="utf-8", errors="replace")
    if "HTTP/2 201" in text or '"status":"submitted"' in text:
        return "submitted"
    if "HTTP/2 200" in text:
        return "live"
    return "artifact_present_unverified"


def _http_artifact_contains(path: Path, *needles: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return all(needle in text for needle in needles)


def build_matrix() -> dict[str, Any]:
    wallet_watch = _read_json(ARTIFACT_DIR / "agentpact_wallet_watch.json")
    agentpact_matches = wallet_watch.get("matches_total", 0)
    agentpact_offers = wallet_watch.get("active_offers_total", 0)
    wallet_ready = wallet_watch.get("wallet_ready") is True
    bothire_register = _read_json(ARTIFACT_DIR / "bothire_register_status.json")
    bothire_work = _read_json(ARTIFACT_DIR / "bothire_work_status.json")
    agentworld_status_file = _read_json(ARTIFACT_DIR / "agentworld_register_status.json")
    agentworld_watcher_file = _read_json(ARTIFACT_DIR / "agentworld_message_watcher_status.json")
    payanagent_status_file = _read_json(ARTIFACT_DIR / "payanagent_register_status.json")
    payanagent_webhook_file = _read_json(ARTIFACT_DIR / "payanagent_webhook_status.json")
    payanagent_watcher_file = _read_json(ARTIFACT_DIR / "payanagent_job_watcher_status.json")
    agentstamp_status_file = _read_json(ARTIFACT_DIR / "agentstamp_register_status.json")
    agentmart_status_file = _read_json(ARTIFACT_DIR / "agentmart_seller_status.json")
    agentbazaar_status_file = _read_json(ARTIFACT_DIR / "agentbazaar_register_status.json")
    clustly_status_file = _read_json(ARTIFACT_DIR / "clustly_agent_status.json")
    opentask_status_file = _read_json(ARTIFACT_DIR / "opentask_agent_status.json")
    opentask_ranking_file = _read_json(ARTIFACT_DIR / "non_bounty_task_ranking.json")
    agentjob_secret_file = _read_json(ARTIFACT_DIR / "agentjob_auto.secret.json")
    agentjob_worker_file = _read_json(ARTIFACT_DIR / "agentjob_autoworker_status_latest.json")
    agentjob_profile_file = _read_json(ARTIFACT_DIR / "agentjob_auto_paid_profile_latest.json")
    agoragentic_register_file = _read_json(ARTIFACT_DIR / "agoragentic_register_status.json")
    agoragentic_publish_file = _read_json(ARTIFACT_DIR / "agoragentic_publish_domain_health_status.json")
    agoragentic_seller_file = _read_json(ARTIFACT_DIR / "agoragentic_seller_post_publish_status.json")
    agoragentic_self_test_file = (
        _read_json(ARTIFACT_DIR / "agoragentic_self_test_poll_live_status.json")
        or _read_json(ARTIFACT_DIR / "agoragentic_self_test_poll_status.json")
    )
    agoragentic_watch_file = (
        _read_json(ARTIFACT_DIR / "agoragentic_seller_watch_status_latest.json")
        or _read_json(ARTIFACT_DIR / "agoragentic_seller_watch_status.json")
    )
    machina_register_file = _read_json(ARTIFACT_DIR / "machina_register_status.json")
    machina_register_services_file = _read_json(ARTIFACT_DIR / "machina_register_services_status.json")
    machina_watch_file = _read_json(ARTIFACT_DIR / "machina_listing_watch_status.json")
    machina_agents_file = _read_json(ARTIFACT_DIR / "machina_agents_latest.json")
    machina_discover_file = _read_json(ARTIFACT_DIR / "machina_discover_domain_health_latest.json")
    bothire_register_status = str((bothire_register.get("register") or {}).get("status") or "not_registered")
    bothire_posts = [
        item
        for item in bothire_register.get("posts", [])
        if isinstance(item, dict) and item.get("status") in {"posted", "already_posted"}
    ]
    bothire_bot_visible = bool(
        ((bothire_register.get("search") or {}).get("checks") or {})
        .get("bots", {})
        .get("response", {})
        .get("bots")
    )
    bothire_active_hires = int(bothire_work.get("active_hires_total", 0) or 0)
    if bothire_register_status in {"registered", "already_registered"} and len(bothire_posts) >= 2 and bothire_bot_visible:
        bothire_status = f"registered_posts={len(bothire_posts)}, visible=True, active_hires={bothire_active_hires}"
    elif bothire_register_status in {"registered", "already_registered"}:
        bothire_status = f"registered_posts={len(bothire_posts)}, visible={bothire_bot_visible}"
    else:
        bothire_status = "not_registered"
    agentworld_register = agentworld_status_file.get("register") or {}
    agentworld_register_status = str(agentworld_register.get("status") or "not_registered")
    agentworld_checks = (agentworld_status_file.get("checks") or {}).get("checks") or {}
    agentworld_registry_http = int((agentworld_checks.get("registry") or {}).get("http_status") or 0)
    agentworld_visible = "x0tta6bl4" in json.dumps(agentworld_checks, ensure_ascii=False).lower()
    if agentworld_register_status in {"registered", "already_registered"}:
        agentworld_status = (
            f"{agentworld_register_status}, registry_http={agentworld_registry_http}, "
            f"visible={agentworld_visible}, "
            f"messages={agentworld_watcher_file.get('messages_total', 0)}, "
            f"earnings_usdc={agentworld_watcher_file.get('earnings_usdc', 0)}"
        )
    else:
        agentworld_status = agentworld_register_status
    payan_register = payanagent_status_file.get("register") or {}
    payan_service = payanagent_status_file.get("service") or {}
    payan_preview_service = payanagent_status_file.get("preview_service") or {}
    payan_payment_risk_service = payanagent_status_file.get("payment_risk_service") or {}
    payan_income_route_service = payanagent_status_file.get("income_route_service") or {}
    payan_x402_validate_service = payanagent_status_file.get("x402_validate_service") or {}
    payan_url_snapshot_service = payanagent_status_file.get("url_snapshot_service") or {}
    payan_domain_health_service = payanagent_status_file.get("domain_health_service") or {}
    payan_checks = (payanagent_status_file.get("checks") or {}).get("checks") or {}
    payan_services_http = int((payan_checks.get("services") or {}).get("http_status") or 0)
    payan_visible = "x0tta6bl4" in json.dumps(payan_checks, ensure_ascii=False).lower()
    payan_webhook = payanagent_webhook_file.get("registration") or {}
    payan_watcher_open_jobs = int(payanagent_watcher_file.get("open_jobs_total", 0) or 0)
    payan_watcher_bids = len(payanagent_watcher_file.get("bids", []) or [])
    payan_status = (
        f"register={payan_register.get('status') or 'not_registered'}, "
        f"service={payan_service.get('status') or 'not_listed'}, "
        f"preview_service={payan_preview_service.get('status') or 'not_listed'}, "
        f"payment_risk_service={payan_payment_risk_service.get('status') or 'not_listed'}, "
        f"income_route_service={payan_income_route_service.get('status') or 'not_listed'}, "
        f"x402_validate_service={payan_x402_validate_service.get('status') or 'not_listed'}, "
        f"url_snapshot_service={payan_url_snapshot_service.get('status') or 'not_listed'}, "
        f"domain_health_service={payan_domain_health_service.get('status') or 'not_listed'}, "
        f"webhook={payan_webhook.get('status') or 'not_registered'}, "
        f"services_http={payan_services_http}, visible={payan_visible}, "
        f"open_jobs={payan_watcher_open_jobs}, bids_seen={payan_watcher_bids}"
    )
    agentstamp_register_status = str(
        (agentstamp_status_file.get("register") or {}).get("status") or "not_started"
    )
    agentstamp_register_response = (agentstamp_status_file.get("register") or {}).get("response") or {}
    agentstamp_needs_signature = "signature" in json.dumps(agentstamp_register_response).lower()
    agentstamp_status = (
        f"register={agentstamp_register_status}, "
        f"needs_wallet_signature={agentstamp_needs_signature}"
    )
    agentmart_identity = agentmart_status_file.get("identity") or {}
    agentmart_products_total = int(agentmart_status_file.get("products_total", 0) or 0)
    agentmart_mode = str(agentmart_status_file.get("mode") or "not_started")
    agentmart_ready = (
        agentmart_products_total >= 3
        and agentmart_status_file.get("wallet") == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    )
    agentmart_status = (
        f"mode={agentmart_mode}, products_ready={agentmart_products_total}, "
        f"email_present={bool(agentmart_identity.get('email_present'))}, "
        f"api_key_present={bool(agentmart_identity.get('api_key_present'))}, "
        f"store_key_present={bool(agentmart_identity.get('store_key_present'))}"
    )
    agentbazaar_registration = agentbazaar_status_file.get("registration") or {}
    agentbazaar_status = (
        f"mode={agentbazaar_status_file.get('mode') or 'not_started'}, "
        f"registered={bool(agentbazaar_registration.get('ok'))}, "
        f"http_status={agentbazaar_registration.get('http_status') or 0}, "
        f"endpoint={agentbazaar_status_file.get('agent_endpoint') or 'not_prepared'}"
    )
    clustly_actions = clustly_status_file.get("actions") or {}
    clustly_register = clustly_actions.get("register") or {}
    clustly_agent_status_response = (clustly_actions.get("agent_status") or {}).get("response") or {}
    clustly_publish = clustly_actions.get("publish_service") or {}
    clustly_webhook = clustly_actions.get("register_webhook") or {}
    clustly_webhook_response = clustly_webhook.get("response") or {}
    clustly_webhook_data = clustly_webhook_response.get("webhook") or {}
    clustly_open_tasks = ((clustly_actions.get("open_tasks") or {}).get("response") or {}).get("tasks") or []
    clustly_pending_orders = (
        ((clustly_actions.get("orders_pending_acceptance") or {}).get("response") or {}).get("data") or []
    )
    clustly_funded_orders = (
        ((clustly_actions.get("orders_funded") or {}).get("response") or {}).get("data") or []
    )
    clustly_status = (
        f"registered={bool(clustly_status_file.get('has_agent_key'))}, "
        f"claim_status={clustly_agent_status_response.get('status') or 'unknown'}, "
        f"publish_http={clustly_publish.get('http_status') or 0}, "
        f"webhook_active={bool(clustly_webhook_data.get('active'))}, "
        f"open_tasks={len(clustly_open_tasks)}, "
        f"pending_orders={len(clustly_pending_orders)}, "
        f"funded_orders={len(clustly_funded_orders)}, "
        f"profile={(clustly_register.get('response') or {}).get('profile_url') or 'saved_in_secret'}"
    )
    opentask_secret = opentask_status_file.get("secret") or {}
    opentask_me_response = ((opentask_status_file.get("me") or {}).get("response") or {})
    opentask_me_profile = opentask_me_response.get("profile") or {}
    opentask_active_bids = (
        ((opentask_status_file.get("active_bids") or {}).get("response") or {}).get("bids") or []
    )
    opentask_trust = opentask_me_response.get("trust") or {}
    opentask_evidence = opentask_trust.get("evidence") or {}
    opentask_identity = opentask_trust.get("identity") or {}
    opentask_active_bid_count = (
        len(opentask_active_bids)
        if opentask_active_bids
        else int((opentask_me_response.get("stats") or {}).get("activeBids") or 0)
    )
    opentask_claim_updates = [
        item
        for item in ((opentask_status_file.get("refresh_bid_claims") or {}).get("updated_or_skipped") or [])
        if isinstance(item, dict) and item.get("ok") and not item.get("skipped")
    ]
    opentask_router_ready = int(opentask_me_response.get("routerPayablePayoutMethodCount") or 0) > 0
    opentask_selected = opentask_ranking_file.get("account_gate_first_total", 0)
    opentask_status = (
        f"registered={bool(opentask_secret.get('token'))}, "
        f"profile={opentask_me_profile.get('handle') or 'unknown'}, "
        f"active_bids={opentask_active_bid_count}, "
        f"portfolio_evidence={int(opentask_evidence.get('portfolioEvidenceCount') or 0)}, "
        f"claim_updates={len(opentask_claim_updates)}, "
        f"identity={opentask_identity.get('status') or 'unknown'}, "
        f"verified_keys={int(opentask_identity.get('verifiedKeyCount') or 0)}, "
        f"router_ready={opentask_router_ready}, "
        f"safe_targets_seen={opentask_selected}"
    )
    agentjob_profile_text = ""
    try:
        agentjob_profile_text = (
            (((agentjob_profile_file.get("profile") or {}).get("response") or {}).get("result") or {})
            .get("content", [{}])[0]
            .get("text", "")
        )
        agentjob_profile = json.loads(agentjob_profile_text) if agentjob_profile_text else {}
    except (AttributeError, IndexError, json.JSONDecodeError):
        agentjob_profile = {}
    agentjob_pricing = agentjob_profile.get("pricing") or {}
    agentjob_stats = agentjob_profile.get("stats") or {}
    agentjob_online = bool(agentjob_worker_file.get("heartbeat_ok") or (agentjob_profile.get("status") or {}).get("online"))
    agentjob_registered = bool(agentjob_secret_file.get("api_key"))
    agentjob_status = (
        f"registered={agentjob_registered}, "
        f"online={agentjob_online}, "
        f"price_usdc={agentjob_pricing.get('per_message_usdc') or 'unknown'}, "
        f"free_daily_slots={agentjob_pricing.get('free_daily_slots') if agentjob_pricing else 'unknown'}, "
        f"task_received={bool(agentjob_worker_file.get('task_received'))}, "
        f"revenue_usdc={agentjob_stats.get('total_revenue_usdc') or 0}, "
        f"platform_wallet={agentjob_secret_file.get('wallet_address') or 'unknown'}, "
        f"target_wallet={agentjob_secret_file.get('target_payout_wallet') or 'unknown'}"
    )

    spore_bid_files = [
        ARTIFACT_DIR / "sporeagent_bid_fastapi_tests_response.txt",
        ARTIFACT_DIR / "sporeagent_bid_fastapi_service_response.txt",
        ARTIFACT_DIR / "sporeagent_bid_api_docs_response.txt",
    ]
    spore_submitted = sum(
        1 for path in spore_bid_files if _status_from_http_artifact(path) == "submitted"
    )
    spore_live = _read_json(ARTIFACT_DIR / "sporeagent_live_bid_check.json")
    spore_visible = int(spore_live.get("submitted_bids_visible_live", 0) or 0)
    spore_live_decision = str(spore_live.get("decision") or "not_checked")
    spore_live_ok = spore_live_decision == "SPORE_BIDS_VISIBLE_LIVE"
    x402_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_repo_triage_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
        "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_unpaid_response_latest.txt",
        "HTTP/2 402",
        "payment-required:",
        "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_unpaid_response.txt",
        "HTTP/2 402",
        "payment-required:",
    )
    x402_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_response.txt",
        "HTTP/2 201",
        '"registered":true',
        "9e6ee7ef-601a-4c86-9a19-df9e007ad27f",
    )
    x402_api_docs_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_api_docs_response.txt",
        "HTTP/2 201",
        '"registered":true',
        "8757956c-a66c-4fa3-887b-399154e29dc8",
    )
    x402_listing_audit_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_listing_audit_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "20a406a5-7a7f-453e-a191-b1b6251a8294",
    )
    x402_payment_risk_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_payment_risk_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "9d4db86d-cbda-48a5-ae20-c291a8a2cbfc",
    )
    x402_income_route_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_income_route_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "x0tta6bl4 Income Route",
    )
    x402_validate_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_x402_validate_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "x0tta6bl4 x402 Endpoint Validator",
    )
    x402_url_snapshot_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_url_snapshot_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "x0tta6bl4 Public URL Snapshot",
    )
    x402_domain_health_registered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_register_domain_health_response.txt",
        "HTTP_STATUS 201",
        '"registered":true',
        "x0tta6bl4 Domain Health Lite",
    )
    x402_discovered = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_discovery_current_after_public_manifest.json",
        "9e6ee7ef-601a-4c86-9a19-df9e007ad27f",
        "8757956c-a66c-4fa3-887b-399154e29dc8",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_discovery_after_get_routes.json",
        "9e6ee7ef-601a-4c86-9a19-df9e007ad27f",
        "8757956c-a66c-4fa3-887b-399154e29dc8",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_discovery_after_api_docs_register.json",
        "9e6ee7ef-601a-4c86-9a19-df9e007ad27f",
        "8757956c-a66c-4fa3-887b-399154e29dc8",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_discovery_after_register.json",
        "9e6ee7ef-601a-4c86-9a19-df9e007ad27f",
        "x0tta6bl4 Repo Triage",
    )
    x402_income_route_discovered = _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_discovery_current.json",
        "x0tta6bl4-income-route",
        "/paid/income-route",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_discovery_current_after_income_route.json",
        "x0tta6bl4 Income Route",
        "/paid/income-route",
    )
    x402_validate_discovered = _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_discovery_current.json",
        "x0tta6bl4-x402-validator",
        "/paid/x402-validate",
    )
    x402_url_snapshot_discovered = _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_discovery_current.json",
        "x0tta6bl4-url-snapshot",
        "/paid/url-snapshot",
    )
    x402_domain_health_discovered = _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_public_discovery_current.json",
        "x0tta6bl4-domain-health",
        "/paid/domain-health",
    )
    x402_api_docs_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_api_docs_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_paid_api_docs_public_unpaid_response.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_api_docs_public_get_unpaid_response.txt",
        "HTTP/2 402",
        "payment-required:",
    )
    x402_listing_audit_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_listing_audit_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_listing_audit_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_payment_risk_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_payment_risk_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_payment_risk_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_income_route_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_income_route_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_income_route_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_validate_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_validate_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_validate_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_url_snapshot_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_url_snapshot_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_url_snapshot_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_domain_health_public_402 = _http_artifact_contains(
        ARTIFACT_DIR / "x402_domain_health_public_get_unpaid_response_current.txt",
        "HTTP/2 402",
        "payment-required:",
    ) or _http_artifact_contains(
        ARTIFACT_DIR / "x402_domain_health_public_get_unpaid_response_current.txt",
        "HTTP/1.1 402",
        "Payment-Required:",
    )
    x402_payment_addresses_verified = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_verify_payment_addresses_current.json",
        "live_payment_address",
        "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
        '"http_status": 200',
    )
    x402_url_snapshot_payment_address_verified = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_verify_url_snapshot_payment_address_current.json",
        '"live_payment_address":"0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"',
        '"payment_address_match":true',
        '"live_x402_network":"eip155:8453"',
    )
    x402_domain_health_payment_address_verified = _http_artifact_contains(
        ARTIFACT_DIR / "x402scout_verify_domain_health_payment_address_current.json",
        '"live_payment_address":"0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"',
        '"payment_address_match":true',
        '"live_x402_network":"eip155:8453"',
    )
    x402_endpoint_count = (
        int(x402_public_402)
        + int(x402_api_docs_public_402)
        + int(x402_listing_audit_public_402)
        + int(x402_payment_risk_public_402)
        + int(x402_income_route_public_402)
        + int(x402_validate_public_402)
        + int(x402_url_snapshot_public_402)
        + int(x402_domain_health_public_402)
    )
    if (
        x402_public_402
        and x402_api_docs_public_402
        and x402_listing_audit_public_402
        and x402_payment_risk_public_402
        and x402_income_route_public_402
        and x402_validate_public_402
        and x402_url_snapshot_public_402
        and x402_domain_health_public_402
        and x402_registered
        and x402_api_docs_registered
        and x402_listing_audit_registered
        and x402_payment_risk_registered
        and x402_income_route_registered
        and x402_validate_registered
        and x402_url_snapshot_registered
        and x402_domain_health_registered
        and x402_discovered
        and x402_income_route_discovered
        and x402_validate_discovered
        and x402_url_snapshot_discovered
        and x402_domain_health_discovered
        and x402_payment_addresses_verified
        and x402_url_snapshot_payment_address_verified
        and x402_domain_health_payment_address_verified
    ):
        x402_status = "public_402_registered_discovered_verified_eight_endpoints"
    elif x402_public_402 and x402_api_docs_public_402 and x402_registered and x402_api_docs_registered and x402_discovered:
        x402_status = "public_402_registered_discovered_two_endpoints"
    elif x402_public_402 and x402_registered and x402_discovered:
        x402_status = "public_402_registered_discovered_one_endpoint"
    elif x402_public_402 and x402_registered:
        x402_status = "public_402_registered"
    elif x402_public_402:
        x402_status = "public_402_unregistered"
    else:
        x402_status = "not_deployed"

    agoragentic_listing_response = agoragentic_publish_file.get("response") or {}
    agoragentic_listing_id = str(agoragentic_listing_response.get("id") or "")
    agoragentic_checks = (agoragentic_watch_file.get("checks") or agoragentic_seller_file.get("checks") or {})
    agoragentic_summary = agoragentic_watch_file.get("summary") or {}
    agoragentic_seller_health = (agoragentic_checks.get("/api/seller/health") or {}).get("response") or {}
    agoragentic_agent_me = (agoragentic_checks.get("/api/agents/me") or {}).get("response") or {}
    agoragentic_webhooks = (agoragentic_checks.get("/api/webhooks") or {}).get("response") or {}
    agoragentic_listings = agoragentic_seller_health.get("listings") or []
    agoragentic_listing = next(
        (
            item
            for item in agoragentic_listings
            if isinstance(item, dict) and item.get("id") == agoragentic_listing_id
        ),
        agoragentic_listings[0] if agoragentic_listings and isinstance(agoragentic_listings[0], dict) else {},
    )
    agoragentic_public_visible = bool(
        ((agoragentic_listing.get("public_browse_visibility") or {}).get("visible"))
    ) or "public_browse_visibility" in json.dumps(agoragentic_self_test_file, ensure_ascii=False).lower()
    agoragentic_webhook_count = len(agoragentic_webhooks.get("webhooks") or [])
    agoragentic_wallet = agoragentic_agent_me.get("wallet") or {}
    agoragentic_status = (
        f"registered={bool(agoragentic_register_file.get('id'))}, "
        f"listing_id={agoragentic_listing_id or 'not_published'}, "
        f"review={agoragentic_summary.get('review_status') or agoragentic_listing.get('review_status') or agoragentic_listing_response.get('review_status') or 'unknown'}, "
        f"verification={agoragentic_summary.get('verification_status') or agoragentic_listing.get('verification_status') or 'unknown'}, "
        f"public_visible={bool(agoragentic_summary.get('public_visible') or agoragentic_public_visible)}, "
        f"price_usdc={agoragentic_summary.get('price_per_unit_usdc') or agoragentic_listing.get('price_per_unit_usdc') or 0.1}, "
        f"invocations={agoragentic_summary.get('total_invocations') or agoragentic_listing.get('total_invocations') or 0}, "
        f"webhooks={agoragentic_webhook_count}, "
        f"earned_usdc={agoragentic_summary.get('wallet_total_earned_usdc') or (agoragentic_wallet.get('total_earned') or 0)}"
    )
    machina_registered_agent = machina_register_file.get("response") or {}
    machina_services = (
        machina_register_services_file.get("services")
        if isinstance(machina_register_services_file.get("services"), list)
        else []
    )
    machina_registered_total = int(
        machina_register_services_file.get("registered_or_existing_total")
        or (1 if machina_register_file.get("ok") else 0)
    )
    machina_services_expected = int(machina_register_services_file.get("services_expected") or 1)
    machina_failed_total = sum(1 for item in machina_services if isinstance(item, dict) and item.get("status") == "failed")
    machina_agent_id = str(machina_registered_agent.get("id") or "")
    machina_list_visible = bool(machina_watch_file.get("list_visible"))
    machina_discover_visible = bool(machina_watch_file.get("discover_visible"))
    machina_calls_30d = int(machina_watch_file.get("calls_30d") or machina_registered_agent.get("calls_30d") or 0)
    machina_receive_matches = bool(machina_watch_file.get("receive_address_matches")) or (
        str(machina_registered_agent.get("receive_address") or "").lower()
        == "0x6017613e80d7893eb2ad5c0585b3f1f88cd6e099"
    )
    machina_status = (
        f"registered_total={machina_registered_total}, "
        f"services_expected={machina_services_expected}, "
        f"failed_total={machina_failed_total}, "
        f"agent_id={machina_agent_id or 'multi_or_not_registered'}, "
        f"active={bool(machina_watch_file.get('active') or machina_registered_agent.get('active'))}, "
        f"list_visible={machina_list_visible}, "
        f"discover_visible={machina_discover_visible}, "
        f"list_visible_total={machina_watch_file.get('list_visible_total') or 0}, "
        f"discover_visible_total={machina_watch_file.get('discover_visible_total') or 0}, "
        f"calls_30d={machina_calls_30d}, "
        f"receive_address_matches={machina_receive_matches}"
    )

    opportunities = [
        Opportunity(
            name="Machina permissionless x402 listings",
            model="Permissionless x402 marketplace listings; buyers pay USDC on Base directly to the receive address",
            status=machina_status,
            first_money_speed=5 if machina_discover_visible else 4,
            no_upfront_cost=5,
            automation=5,
            payout_directness=5,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/machina_register_status.json",
                ".tmp/non-bounty/machina_register_services_status.json",
                ".tmp/non-bounty/machina_listing_watch_status.json",
                ".tmp/non-bounty/machina_agents_latest.json",
                ".tmp/non-bounty/machina_discover_domain_health_latest.json",
                "src/sales/x402_paid_api.py",
            ],
            blockers=[
                "Needs a buyer x402 call; current calls_30d is zero.",
                "Some extra listings may need retry after Machina registration rate limit cools down.",
                "Listing is off-chain API registered, not wallet-signed on-chain verified.",
            ],
            next_step="Keep paid x402 endpoints online; retry rate-limited Machina registrations, then poll Machina list/discover and Base USDC balance.",
        ),
        Opportunity(
            name="Agoragentic public paid listing",
            model="Free first seller listing; platform charges buyer and seller receives USDC after settlement",
            status=agoragentic_status,
            first_money_speed=5 if agoragentic_public_visible else 4,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/agoragentic_register_status.json",
                ".tmp/non-bounty/agoragentic_publish_domain_health_status.json",
                ".tmp/non-bounty/agoragentic_self_test_poll_status.json",
                ".tmp/non-bounty/agoragentic_seller_watch_status.json",
                ".tmp/non-bounty/agoragentic_seller_post_publish_status.json",
                ".tmp/non-bounty/agoragentic_public_visibility_status.json",
                ".tmp/non-bounty/agoragentic_webhook_register_status.json",
                "src/sales/x402_paid_api.py",
            ],
            blockers=[
                "Needs a buyer invocation; current total_invocations is zero.",
                "Earnings first land inside Agoragentic wallet state; external wallet withdrawal is a later settlement step.",
            ],
            next_step="Keep /agentbazaar/task and /agoragentic/webhook online; poll seller tasks, invocations, wallet earned balance, and public visibility.",
        ),
        Opportunity(
            name="AgentPact wallet-linked offers",
            model="Agent marketplace: sell Python/data/API work for USDC",
            status=(
                f"active_offers={agentpact_offers}, matches={agentpact_matches}, "
                f"wallet_ready={wallet_ready}"
            ),
            first_money_speed=4,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/agentpact_wallet_watch.json",
                ".tmp/non-bounty/agentpact_wallet_matches.json",
                ".tmp/non-bounty/agentpact_wallet_linked_offer_response.txt",
            ],
            blockers=["Buyer or matching engine must accept/propose a deal."],
            next_step="Keep watcher running; create narrower 1-5 USDC offers for API docs, pytest, and data cleanup.",
        ),
        Opportunity(
            name="SporeAgent USD paid tasks",
            model="Open task marketplace: bid on concrete coding/data tasks",
            status=(
                f"submit_artifacts={spore_submitted}, live_visible={spore_visible}, "
                f"live_decision={spore_live_decision}, target_budget_usd=230"
            ),
            first_money_speed=3 if spore_live_ok else 1,
            no_upfront_cost=5,
            automation=3 if spore_live_ok else 2,
            payout_directness=2 if spore_live_ok else 1,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/sporeagent_x0t_register_response.txt",
                ".tmp/non-bounty/sporeagent_bid_fastapi_tests_response.txt",
                ".tmp/non-bounty/sporeagent_bid_fastapi_service_response.txt",
                ".tmp/non-bounty/sporeagent_bid_api_docs_response.txt",
                ".tmp/non-bounty/sporeagent_live_bid_check.json",
            ],
            blockers=[
                "Task owner must accept the bid; payout mechanism is not wallet-verified yet.",
                "Latest live check did not show the submitted bids as durable marketplace state.",
            ],
            next_step="Poll assigned tasks; deliver only after assigned_agent_id equals our Spore agent ID.",
        ),
        Opportunity(
            name="OpenTask non-bounty tasks",
            model="Headless agent marketplace: bid on public coding/data/API tasks for USD/USDC",
            status=opentask_status,
            first_money_speed=5 if opentask_active_bid_count else 4,
            no_upfront_cost=5,
            automation=4,
            payout_directness=3 if not opentask_router_ready else 4,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/non_bounty_task_collection.json",
                ".tmp/non-bounty/non_bounty_task_ranking.json",
                ".tmp/non-bounty/opentask_agent_status.json",
                "scripts/ops/run_non_bounty_scout.py",
                "scripts/ops/opentask_agent_cli.py",
            ],
            blockers=[
                "Task owner must accept one of our active bids.",
                "OpenTask public payment methods currently report router status unavailable, so settlement readiness is platform-gated.",
            ],
            next_step="Poll OpenTask bids/contracts; if a bid is accepted, deliver only the accepted parser/OpenAPI artifact.",
        ),
        Opportunity(
            name="x402 paid MCP/API for x0tta6bl4",
            model="Sell tool calls directly: agents pay USDC per request",
            status=x402_status,
            first_money_speed=5 if x402_status.startswith("public_402_registered_discovered") else 4,
            no_upfront_cost=4,
            automation=5,
            payout_directness=5,
            x0tta_fit=5,
            evidence=[
                "docs/ai_agents/THINKING_TECHNIQUES_FOR_AGENTS.md",
                ".tmp/non-bounty/x402_paid_api_public_discovery_current.json",
                ".tmp/non-bounty/x402_paid_api_public_mcp_manifest_current.json",
                ".tmp/non-bounty/x402_repo_triage_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_api_docs_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_listing_audit_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_payment_risk_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_income_route_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_validate_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_url_snapshot_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_domain_health_public_get_unpaid_response_current.txt",
                ".tmp/non-bounty/x402_paid_api_public_unpaid_response_latest.txt",
                ".tmp/non-bounty/x402_paid_api_docs_public_unpaid_response.txt",
                ".tmp/non-bounty/x402scout_register_response.txt",
                ".tmp/non-bounty/x402scout_register_api_docs_response.txt",
                ".tmp/non-bounty/x402scout_register_listing_audit_response.txt",
                ".tmp/non-bounty/x402scout_register_payment_risk_response.txt",
                ".tmp/non-bounty/x402scout_register_income_route_response.txt",
                ".tmp/non-bounty/x402scout_register_x402_validate_response.txt",
                ".tmp/non-bounty/x402scout_register_url_snapshot_response.txt",
                ".tmp/non-bounty/x402scout_register_domain_health_response.txt",
                ".tmp/non-bounty/x402scout_catalog_after_listing_audit.json",
                ".tmp/non-bounty/x402scout_verify_payment_addresses_current.json",
                ".tmp/non-bounty/x402scout_verify_url_snapshot_payment_address_current.json",
                ".tmp/non-bounty/x402scout_verify_domain_health_payment_address_current.json",
                ".tmp/non-bounty/x402scout_discovery_after_get_routes.json",
            ],
            blockers=["Traffic is not automatic; buyers still need to call and pay the endpoint."],
            next_step=f"Keep public endpoint alive; current paid x402 endpoint count is {x402_endpoint_count}.",
        ),
        Opportunity(
            name="Agent402 marketplace",
            model="List an existing paid API; buyers discover it by semantic search and pay via x402",
            status="not_registered",
            first_money_speed=4,
            no_upfront_cost=3,
            automation=5,
            payout_directness=5,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/x402_paid_api_public_discovery_current.json",
                ".tmp/non-bounty/x402_paid_api_public_mcp_manifest_current.json",
            ],
            blockers=["Requires account/sign-in gate; real listing acceptance not verified from this session."],
            next_step="Register the existing ngrok x402 API as a seller service when account gate is available.",
        ),
        Opportunity(
            name="BotHire",
            model="Machine-first bot marketplace on Base with x402 service payments",
            status=bothire_status,
            first_money_speed=5 if bothire_bot_visible else 4,
            no_upfront_cost=3,
            automation=5,
            payout_directness=5,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/bothire_register_status.json",
                ".tmp/non-bounty/bothire_search_status.json",
                ".tmp/non-bounty/bothire_work_status.json",
                ".tmp/non-bounty/x402_paid_api_public_discovery_current.json",
                ".tmp/non-bounty/x402_paid_api_public_mcp_manifest_current.json",
            ],
            blockers=["Needs a buyer hire; current active_hires is zero."],
            next_step="Keep scripts/ops/bothire_work_loop.py polling for mailbox hires and deliver paid requests.",
        ),
        Opportunity(
            name="AgentJob paid chat worker",
            model="Auto-register server-wallet agent; stay online; receive paid chat tasks and withdraw earned USDC later",
            status=agentjob_status,
            first_money_speed=5 if agentjob_online else 3,
            no_upfront_cost=5,
            automation=4,
            payout_directness=3,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/agentjob_auto.secret.json",
                ".tmp/non-bounty/agentjob_auto_paid_profile_latest.json",
                ".tmp/non-bounty/agentjob_autoworker_status_latest.json",
                "scripts/ops/agentjob_autoworker.py",
            ],
            blockers=[
                "Needs a buyer to start a paid chat; latest poll returned no task.",
                "Earnings first land in the AgentJob server wallet; target wallet receives funds only after withdrawal threshold/cooldown.",
                "Autonomous rich replies need a local reply command or local model; current environment has no Ollama server.",
            ],
            next_step="Run scripts/ops/agentjob_autoworker.py --once --set-profile every 45 seconds, or attach a local reply command for full auto-delivery.",
        ),
        Opportunity(
            name="AgentWorld paid messages",
            model="Register a public agent; earn a share of x402-paid messages on Base",
            status=agentworld_status,
            first_money_speed=4 if agentworld_visible else 3,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[
                ".tmp/non-bounty/agentworld_register_status.json",
                ".tmp/non-bounty/agentworld_message_watcher_status.json",
                ".tmp/non-bounty/x402_paid_api_public_discovery_current.json",
            ],
            blockers=["Needs another agent or user to send a paid AgentWorld message."],
            next_step="Keep /agentworld/message online; poll AgentWorld message logs, registry earnings, and wallet balance.",
        ),
        Opportunity(
            name="PayanAgent service registry",
            model="Register an agent and list per-request paid API service for USDC/x402 buyers",
            status=payan_status,
            first_money_speed=4 if payan_visible else 3,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[
                ".tmp/non-bounty/payanagent_register_status.json",
                ".tmp/non-bounty/payanagent_webhook_status.json",
                ".tmp/non-bounty/payanagent_job_watcher_status.json",
                ".tmp/non-bounty/x0tta6bl4_public_preview_route_current.json",
                ".tmp/non-bounty/payanagent_identity.secret.json",
            ],
            blockers=["Needs a buyer to invoke the listed service or an open job to appear and accept our bid."],
            next_step="Keep PayanAgent service, webhook, and job watcher online; bid only on safe public-input jobs.",
        ),
        Opportunity(
            name="AgentStamp trust booster",
            model="Free trust registry/stamp to improve buyer confidence before paid calls",
            status=agentstamp_status,
            first_money_speed=1,
            no_upfront_cost=4,
            automation=2,
            payout_directness=1,
            x0tta_fit=3,
            evidence=[
                ".tmp/non-bounty/agentstamp_register_status.json",
            ],
            blockers=["Current free registration requires wallet signature headers; no private key is used in chat."],
            next_step="Only retry locally if a signing key is configured safely through environment variables.",
        ),
        Opportunity(
            name="AgentMart reusable agent products",
            model="Sell instant-delivery markdown packs to agents; seller keeps 97% after platform fee",
            status=agentmart_status,
            first_money_speed=4 if agentmart_ready else 2,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=5,
            evidence=[
                "docs/commercial/agentmart_product_pack.json",
                "docs/commercial/agentmart_products/x402_micro_api_seller_pack.md",
                "docs/commercial/agentmart_products/public_url_snapshot_buyer_kit.md",
                "docs/commercial/agentmart_products/domain_health_lite_workflow.md",
                ".tmp/non-bounty/agentmart_seller_status.json",
                ".tmp/non-bounty/agentmart_skill_current.md",
            ],
            blockers=[
                "AgentMart registration and store verification require a real email flow.",
                "Publishing requires local AGENTMART_EMAIL or existing AGENTMART_API_KEY/AGENTMART_STORE_KEY.",
            ],
            next_step="Run scripts/ops/agentmart_seller_cli.py --submit --publish after local AgentMart email/API key setup; payout wallet is already set in the pack.",
        ),
        Opportunity(
            name="AgentBazaar Solana paid tasks",
            model="Register a push webhook; buyers prepay USDC, task is delivered to /agentbazaar/task",
            status=agentbazaar_status,
            first_money_speed=4 if agentbazaar_registration.get("ok") else 3,
            no_upfront_cost=5,
            automation=5,
            payout_directness=3,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/agentbazaar_register_status.json",
                ".tmp/non-bounty/agentbazaar_register_secret.json",
                "scripts/ops/agentbazaar_register.py",
                "src/sales/x402_paid_api.py",
            ],
            blockers=[
                "AgentBazaar settles earnings to a Solana wallet, not directly to the Base wallet.",
                "Live API must accept registration and buyers must send paid tasks.",
            ],
            next_step="Run scripts/ops/agentbazaar_register.py --submit; keep /agentbazaar/task online for prepaid push tasks.",
        ),
        Opportunity(
            name="Clustly escrowed USDC tasks",
            model="Register agent, publish fixed service after claim, poll escrowed tasks/orders",
            status=clustly_status,
            first_money_speed=4 if clustly_agent_status_response.get("status") == "claimed" else 3,
            no_upfront_cost=5,
            automation=4,
            payout_directness=4,
            x0tta_fit=5,
            evidence=[
                ".tmp/non-bounty/clustly_agent_status.json",
                ".tmp/non-bounty/clustly_agent.secret.json",
                ".tmp/non-bounty/clustly_llms_current.txt",
                ".tmp/non-bounty/clustly_agent_prompt_current.md",
                "scripts/ops/clustly_agent_cli.py",
            ],
            blockers=[
                "Profile must be claimed before services can be published.",
                "Current open task list is empty; service orders require buyer demand.",
            ],
            next_step="After claim status becomes claimed, run scripts/ops/clustly_agent_cli.py --publish-service --open-tasks.",
        ),
        Opportunity(
            name="ClawMart skill marketplace",
            model="Pack a narrow agent role or skill behind x402/MCP payment",
            status="not_registered",
            first_money_speed=3,
            no_upfront_cost=3,
            automation=4,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[
                ".tmp/non-bounty/x402_paid_api_public_discovery_current.json",
            ],
            blockers=["Appears productized around packaged agents, not instant open self-serve API payout."],
            next_step="Reuse API docs and repo-triage as a 'developer assistant' role if seller onboarding opens.",
        ),
        Opportunity(
            name="ClawdGigs x402 escrow",
            model="Offer fixed-scope gigs to humans or agents; payment via x402 escrow",
            status="not_registered",
            first_money_speed=3,
            no_upfront_cost=3,
            automation=4,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[
                ".tmp/non-bounty/x402_paid_api_public_mcp_manifest_current.json",
            ],
            blockers=["Registration, escrow release, and demand are external gates."],
            next_step="Create one fixed gig: 'API docs from endpoint JSON, delivered in Markdown'.",
        ),
        Opportunity(
            name="Apify Actor Store",
            model="Publish scraper/automation actors; earn per result or per event",
            status="not_started",
            first_money_speed=2,
            no_upfront_cost=2,
            automation=5,
            payout_directness=3,
            x0tta_fit=4,
            evidence=[],
            blockers=["Account/payout setup required; testing may need paid creator plan or credits."],
            next_step="Package one low-cost actor: public-page structured extractor or Telegram public-channel digest.",
        ),
        Opportunity(
            name="ClawGig",
            model="Freelance marketplace for AI agents with USDC escrow",
            status="not_registered",
            first_money_speed=3,
            no_upfront_cost=3,
            automation=4,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[],
            blockers=["Requires HTTPS webhook, contact email verification, profile claim, and portfolio item."],
            next_step="Prepare webhook endpoint and portfolio; register only after email/payout path is usable.",
        ),
        Opportunity(
            name="Tetto",
            model="Per-call Solana agent marketplace",
            status="not_registered",
            first_money_speed=3,
            no_upfront_cost=3,
            automation=5,
            payout_directness=4,
            x0tta_fit=4,
            evidence=[],
            blockers=["Requires Tetto API key, public endpoint, and Solana owner wallet setup."],
            next_step="Reuse the same x0tta6bl4 paid API endpoint after x402 scaffold exists.",
        ),
        Opportunity(
            name="ArcAgent",
            model="USDC escrow and micropayment marketplace on Arc testnet/mainnet path",
            status="testnet_only_seen",
            first_money_speed=2,
            no_upfront_cost=2,
            automation=4,
            payout_directness=3,
            x0tta_fit=4,
            evidence=[],
            blockers=["Observed page says testnet; registration needs wallet gas and endpoint URL."],
            next_step="Do not prioritize until real mainnet payout path is visible.",
        ),
        Opportunity(
            name="RapidAPI",
            model="Publish API, get paid by marketplace subscription/usage",
            status="low_priority",
            first_money_speed=1,
            no_upfront_cost=2,
            automation=4,
            payout_directness=1,
            x0tta_fit=3,
            evidence=[],
            blockers=["Payout documented as PayPal-only; bad fit if PayPal access is blocked."],
            next_step="Skip unless a working payout account exists.",
        ),
        Opportunity(
            name="Human-in-loop broker",
            model="Agent routes physical/social tasks to humans",
            status="not_agent_earns_directly",
            first_money_speed=2,
            no_upfront_cost=1,
            automation=2,
            payout_directness=1,
            x0tta_fit=2,
            evidence=[],
            blockers=["This spends money to hire humans; it is not a direct agent earning channel."],
            next_step="Ignore for seed capital.",
        ),
    ]

    ranked = sorted(opportunities, key=lambda item: item.score, reverse=True)
    return {
        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": {
            "x0tta6bl4_techniques": [
                "First principles: money requires buyer, measurable value, settlement path.",
                "Reverse planning: start from wallet payment and work back to accepted task or paid call.",
                "SCAMPER: turn existing repo skills into small paid tools.",
                "Weighted matrix: score speed, no-upfront-cost, automation, payout directness, and fit.",
            ],
            "weights": WEIGHTS,
        },
        "top_next_action": ranked[0].next_step,
        "opportunities": [
            {
                **asdict(item),
                "score": item.score,
            }
            for item in ranked
        ],
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix()
    OUT.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote: {OUT}")
    print("top options:")
    for idx, item in enumerate(matrix["opportunities"][:5], start=1):
        print(f"{idx}. {item['name']} score={item['score']} status={item['status']}")
        print(f"   next: {item['next_step']}")


if __name__ == "__main__":
    main()
