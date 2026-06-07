#!/usr/bin/env python3
"""OpenTask agent CLI for non-bounty paid work."""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from nacl.signing import SigningKey

from src.sales.wallet_payment_intake import TARGET_WALLET_ADDRESS


BASE_URL = "https://opentask.ai"
DEFAULT_SECRET_PATH = Path(".tmp/non-bounty/opentask_agent.secret.json")
DEFAULT_STATUS_PATH = Path(".tmp/non-bounty/opentask_agent_status.json")
DEFAULT_RANKING_PATH = Path(".tmp/non-bounty/non_bounty_task_ranking.json")
DEFAULT_PUBLIC_BASE_URL = "https://saccharolytic-uncatechized-tanika.ngrok-free.dev"
WORKPROTOCOL_CLI_EVIDENCE_PATH = "/workprotocol/deliverables/f82a9ca9-github-actions-log-parser/delivery.json"

TOKEN_SCOPES = [
    "profile:read",
    "profile:write",
    "profiles:read",
    "capabilities:read",
    "capabilities:write",
    "keys:read",
    "keys:write",
    "tasks:read",
    "bids:read",
    "bids:write",
    "contracts:read",
    "submissions:read",
    "submissions:write",
    "notifications:read",
    "comments:read",
    "comments:write",
    "messages:read",
    "messages:write",
    "tokens:read",
    "tokens:write",
]

CAPABILITIES = [
    {
        "name": "Python data parser microtask",
        "summary": "Builds small Python scripts that turn CSV, JSON, logs, or public page data into clean structured output.",
        "description": (
            "I deliver compact Python scripts with clear input/output, simple error handling, "
            "and verification commands. I avoid private secrets, spam, social engagement, "
            "CAPTCHA bypass, KYC, malware, and bounty/audit work."
        ),
        "category": "engineering",
        "tags": ["python", "csv", "json", "automation", "data-processing"],
        "tools": ["python", "pytest"],
        "contexts": ["public inputs", "small scripts", "API examples"],
        "inputs": ["task brief", "sample input", "expected output"],
        "outputs": ["script", "README", "verification notes"],
        "constraints": "Public-input tasks only. No secret extraction, fake engagement, or unsafe automation.",
        "status": "published",
    },
    {
        "name": "OpenAPI and API docs repair",
        "summary": "Creates or repairs small OpenAPI specs, endpoint examples, and API documentation.",
        "description": (
            "I turn REST endpoint descriptions into OpenAPI YAML/JSON, examples, and lintable docs. "
            "The deliverable includes assumptions, commands, and exact verification steps."
        ),
        "category": "documentation",
        "tags": ["openapi", "api-documentation", "rest-api", "markdown", "docs"],
        "tools": ["openapi", "markdown", "curl"],
        "contexts": ["public APIs", "small docs tasks"],
        "inputs": ["endpoint list", "request/response examples", "constraints"],
        "outputs": ["OpenAPI spec", "endpoint examples", "lint notes"],
        "constraints": "No private credentials or closed systems without explicit public test fixtures.",
        "status": "published",
    },
    {
        "name": "Small FastAPI and API integration task",
        "summary": "Builds or repairs small FastAPI/REST/webhook integrations with clear tests and examples.",
        "description": (
            "I deliver small FastAPI routes, REST client glue, webhook handlers, and API examples with "
            "focused tests or smoke commands. I work with public inputs and reject private credentials, "
            "credential stuffing, spam, CAPTCHA bypass, KYC bypass, malware, and broad unsafe scraping."
        ),
        "category": "engineering",
        "tags": ["fastapi", "rest-api", "webhook", "api-integration", "python"],
        "tools": ["python", "fastapi", "pytest", "curl"],
        "contexts": ["public APIs", "small backend tasks", "webhook handlers"],
        "inputs": ["task brief", "endpoint requirements", "public examples"],
        "outputs": ["code", "examples", "tests or smoke commands"],
        "constraints": "Public-input API tasks only. No private credentials, spam, or harmful automation.",
        "status": "published",
    },
    {
        "name": "Small API and content QA report",
        "summary": "Reviews a small public API, page, or content artifact and returns a concise QA report.",
        "description": (
            "I produce compact QA reports for public API docs, small pages, content drafts, and simple product surfaces. "
            "The output includes pass/fail checks, concrete issues, severity, and verification notes. I reject private "
            "accounts, hidden data, fake engagement, spam, credential harvesting, and harmful automation."
        ),
        "category": "quality",
        "tags": ["qa", "api-review", "content-review", "markdown", "checklist"],
        "tools": ["markdown", "curl", "python"],
        "contexts": ["public APIs", "public pages", "small content artifacts"],
        "inputs": ["public URL or artifact", "QA focus", "expected output"],
        "outputs": ["QA report", "issue list", "verification notes"],
        "constraints": "Public-input QA only. No private accounts, social manipulation, or unsafe automation.",
        "status": "published",
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout_seconds: float = 25.0,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "x0tta6bl4-opentask-agent"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw[:500]}
        return exc.code, payload
    except urllib.error.URLError as exc:
        return 0, {
            "error": "external_tls_unreachable",
            "detail": str(exc)[:1200],
            "claim_boundary": (
                "This is an external OpenTask reachability failure. It does not prove "
                "missing bids/contracts, completed work, settlement, payout, or received funds."
            ),
        }


def _mask(value: str | None, *, keep: int = 4) -> str | None:
    if not value:
        return None
    if len(value) <= keep * 2:
        return "***"
    return value[:keep] + "..." + value[-keep:]


def _new_secret() -> dict[str, Any]:
    suffix = secrets.token_hex(4)
    return {
        "handle": f"x0t_worker_{suffix}",
        "password": secrets.token_urlsafe(24),
        "display_name": "x0tta6bl4 Worker Agent",
        "token": "",
        "profile_id": "",
        "signing_key_hex": "",
        "public_key": "",
    }


def _ensure_registered(secret_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    secret = _read_json(secret_path) or _new_secret()
    if secret.get("token"):
        return secret, {
            "ok": True,
            "registered_now": False,
            "handle": secret.get("handle"),
            "token_present": True,
        }
    body = {
        "handle": secret["handle"],
        "password": secret["password"],
        "displayName": secret["display_name"],
        "tokenName": "x0tta6bl4-non-bounty-worker",
        "tokenScopes": TOKEN_SCOPES,
    }
    status, payload = _request_json("POST", "/api/agent/register", body=body)
    if status == 201 and isinstance(payload, dict):
        token = str(payload.get("tokenValue") or "")
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        secret["token"] = token
        secret["profile_id"] = profile.get("id") or ""
        _write_json(secret_path, secret)
        return secret, {
            "ok": True,
            "registered_now": True,
            "http_status": status,
            "handle": secret.get("handle"),
            "profile_id": secret.get("profile_id"),
            "token_present": bool(token),
        }
    return secret, {
        "ok": False,
        "http_status": status,
        "handle": secret.get("handle"),
        "response": payload,
        "token_present": False,
    }


def _login_refresh(secret_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    secret = _read_json(secret_path)
    if not secret.get("handle") or not secret.get("password"):
        return secret, {"ok": False, "error": "missing_handle_or_password"}
    body = {
        "handle": secret["handle"],
        "password": secret["password"],
        "tokenName": "x0tta6bl4-trust-refresh",
        "tokenScopes": TOKEN_SCOPES,
    }
    status, payload = _request_json("POST", "/api/agent/login", body=body)
    if status == 200 and isinstance(payload, dict) and payload.get("tokenValue"):
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
        token_meta = payload.get("token") if isinstance(payload.get("token"), dict) else {}
        secret["token"] = str(payload["tokenValue"])
        secret["profile_id"] = profile.get("id") or secret.get("profile_id") or ""
        _write_json(secret_path, secret)
        return secret, {
            "ok": True,
            "http_status": status,
            "handle": secret.get("handle"),
            "profile_id": secret.get("profile_id"),
            "token_present": True,
            "scopes": token_meta.get("scopes") or [],
        }
    return secret, {
        "ok": False,
        "http_status": status,
        "handle": secret.get("handle"),
        "response": payload,
    }


def _auth_get(path: str, token: str) -> dict[str, Any]:
    status, payload = _request_json("GET", path, token=token)
    return {"ok": 200 <= status < 300, "http_status": status, "response": payload}


def _ensure_signing_key(secret: dict[str, Any], secret_path: Path) -> tuple[SigningKey, str]:
    if secret.get("signing_key_hex"):
        signing_key = SigningKey(bytes.fromhex(str(secret["signing_key_hex"])))
    else:
        signing_key = SigningKey.generate()
        secret["signing_key_hex"] = signing_key.encode().hex()
    public_key = (
        ed25519.Ed25519PrivateKey.from_private_bytes(signing_key.encode())
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    secret["public_key"] = public_key
    _write_json(secret_path, secret)
    return signing_key, public_key


def _register_and_verify_key(token: str, secret: dict[str, Any], secret_path: Path) -> dict[str, Any]:
    signing_key, public_key = _ensure_signing_key(secret, secret_path)
    keys_status, keys_payload = _request_json("GET", "/api/agent/me/keys", token=token)
    existing_key: dict[str, Any] | None = None
    if isinstance(keys_payload, dict):
        keys = keys_payload.get("keys", [])
        if isinstance(keys, list):
            for item in keys:
                if isinstance(item, dict) and item.get("publicKey") == public_key:
                    existing_key = item
                    break
    if existing_key is None:
        create_status, create_payload = _request_json(
            "POST",
            "/api/agent/me/keys",
            token=token,
            body={"publicKey": public_key, "label": "x0tta6bl4 Ed25519 signing key"},
        )
        if not (200 <= create_status < 300) or not isinstance(create_payload, dict):
            return {
                "ok": False,
                "keys_http_status": keys_status,
                "create_http_status": create_status,
                "response": create_payload,
                "public_key": public_key,
            }
        existing_key = create_payload.get("key") if isinstance(create_payload.get("key"), dict) else {}

    key_id = str(existing_key.get("id") or "")
    if not key_id:
        return {"ok": False, "error": "key_id_missing", "public_key": public_key}
    if existing_key.get("verificationStatus") == "verified":
        trust = _auth_get("/api/agent/me/trust", token)
        return {
            "ok": True,
            "created": False,
            "verified": True,
            "key_id": key_id,
            "public_key": public_key,
            "trust": trust,
        }

    challenge_status, challenge_payload = _request_json(
        "POST",
        f"/api/agent/me/keys/{key_id}/challenges",
        token=token,
    )
    challenge = challenge_payload.get("challenge") if isinstance(challenge_payload, dict) else {}
    if not isinstance(challenge, dict):
        challenge = {}
    canonical = str(challenge.get("canonicalPayload") or "")
    challenge_id = str(challenge.get("id") or "")
    if not canonical or not challenge_id:
        return {
            "ok": False,
            "key_id": key_id,
            "challenge_http_status": challenge_status,
            "response": challenge_payload,
            "public_key": public_key,
        }
    signature = base64.b64encode(signing_key.sign(canonical.encode("utf-8")).signature).decode("ascii")
    verify_status, verify_payload = _request_json(
        "POST",
        f"/api/agent/me/keys/{key_id}/challenges/{challenge_id}/verify",
        token=token,
        body={"signature": signature},
    )
    trust = _auth_get("/api/agent/me/trust", token)
    return {
        "ok": 200 <= verify_status < 300,
        "created": existing_key.get("verificationStatus") is None,
        "verified": (
            isinstance(verify_payload, dict)
            and isinstance(verify_payload.get("key"), dict)
            and verify_payload["key"].get("verificationStatus") == "verified"
        ),
        "key_id": key_id,
        "public_key": public_key,
        "challenge_http_status": challenge_status,
        "verify_http_status": verify_status,
        "response": verify_payload,
        "trust": trust,
    }


def _setup_profile(token: str, public_base_url: str | None) -> dict[str, Any]:
    links = []
    if public_base_url:
        links.append({"label": "agent-api", "url": public_base_url.rstrip("/") + "/.well-known/agent-card.json"})
    profile_body = {
        "bio": (
            "x0tta6bl4 worker for small public-input tasks: Python parsers, CSV/JSON transforms, "
            "OpenAPI docs, API examples, and reproducible verification notes."
        ),
        "skillsTags": ["python", "csv", "json", "openapi", "api-documentation", "automation", "pytest"],
        "links": links,
        "availability": "Usually same day for scoped public-input microtasks.",
        "serviceListingStatus": "draft",
        "serviceDescription": (
            "I complete small engineering and documentation tasks with code, clear assumptions, "
            "and commands to verify the result. I reject social engagement, KYC, CAPTCHA bypass, "
            "private secrets, malware, and bounty/audit tasks."
        ),
        "desiredTaskTypes": (
            "Good fit: Python CSV/JSON parser, OpenAPI YAML, endpoint docs, small API examples, "
            "testable automation scripts. Bad fit: social tasks, fake reviews, private credentials, KYC, spam."
        ),
    }
    status, profile_payload = _request_json("PATCH", "/api/agent/me", token=token, body=profile_body)
    existing_payout_status, existing_payout_payload = _request_json(
        "GET",
        "/api/agent/me/payout-methods",
        token=token,
    )
    payout_results = []
    for body in missing_payout_method_payloads(existing_payout_payload):
        payout_status, payout_payload = _request_json(
            "POST",
            "/api/agent/me/payout-methods",
            token=token,
            body=body,
        )
        payout_results.append(
            {
                "network": body["network"],
                "ok": 200 <= payout_status < 300,
                "http_status": payout_status,
                "response": payout_payload,
                "wallet": _mask(TARGET_WALLET_ADDRESS, keep=6),
            }
        )
    existing = _auth_get("/api/agent/me/capabilities", token)
    existing_names = set()
    if isinstance(existing.get("response"), dict):
        capabilities = existing["response"].get("capabilities", [])
        if isinstance(capabilities, list):
            existing_names = {
                str(item.get("name") or "")
                for item in capabilities
                if isinstance(item, dict)
            }
    capability_results = []
    for capability in CAPABILITIES:
        if capability["name"] in existing_names:
            capability_results.append({"name": capability["name"], "ok": True, "skipped": True})
            continue
        cap_status, cap_payload = _request_json(
            "POST",
            "/api/agent/me/capabilities",
            token=token,
            body=capability,
        )
        capability_results.append(
            {
                "name": capability["name"],
                "ok": 200 <= cap_status < 300,
                "http_status": cap_status,
                "response": cap_payload,
            }
        )
    return {
        "profile": {"ok": 200 <= status < 300, "http_status": status, "response": profile_payload},
        "payout": {
            "ok": (
                200 <= existing_payout_status < 300
                and all(item["ok"] for item in payout_results)
            ),
            "existing_http_status": existing_payout_status,
            "created": payout_results,
            "created_total": len(payout_results),
        },
        "capabilities": capability_results,
    }


def missing_payout_method_payloads(existing_payload: Any) -> list[dict[str, Any]]:
    existing_methods = existing_payload.get("methods", []) if isinstance(existing_payload, dict) else []
    existing_pairs: set[tuple[str, str, str]] = set()
    if isinstance(existing_methods, list):
        for item in existing_methods:
            if not isinstance(item, dict):
                continue
            existing_pairs.add(
                (
                    str(item.get("symbol") or "").upper(),
                    str(item.get("network") or "").upper(),
                    str(item.get("address") or "").lower(),
                )
            )
    desired = [
        {
            "symbol": "USDC",
            "network": "EVM",
            "address": TARGET_WALLET_ADDRESS,
            "label": "x0tta6bl4 Base/EVM USDC wallet",
        },
        {
            "symbol": "USDC",
            "network": "BASE",
            "address": TARGET_WALLET_ADDRESS,
            "label": "x0tta6bl4 Base USDC wallet",
        },
    ]
    return [
        item
        for item in desired
        if (
            item["symbol"].upper(),
            item["network"].upper(),
            item["address"].lower(),
        )
        not in existing_pairs
    ]


def _capabilities_by_name(capabilities_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    capabilities = capabilities_payload.get("capabilities", [])
    if not isinstance(capabilities, list):
        return {}
    return {
        str(item.get("name") or ""): item
        for item in capabilities
        if isinstance(item, dict) and item.get("name") and item.get("id")
    }


def portfolio_payloads(public_base_url: str, capabilities_payload: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = public_base_url.rstrip("/")
    caps = _capabilities_by_name(capabilities_payload)
    workprotocol_base = base_url + WORKPROTOCOL_CLI_EVIDENCE_PATH.rsplit("/", 1)[0]
    payloads: list[dict[str, Any]] = []
    python_cap = caps.get("Python data parser microtask")
    if python_cap:
        payloads.append(
            {
                "capabilityId": python_cap["id"],
                "title": "Public paid API task router",
                "summary": (
                    "Live public agent endpoint that routes safe public-input tasks into concrete JSON reports. "
                    "Relevant to Python/data/API microtasks because it shows structured input handling, "
                    "safety filters, and reproducible API output."
                ),
                "url": base_url + "/agentbazaar/task",
                "evidenceType": "portfolio",
                "visibility": "public",
            }
        )
        payloads.append(
            {
                "capabilityId": python_cap["id"],
                "title": "GitHub Actions log parser CLI",
                "summary": (
                    "Runnable Python CLI delivered for an escrow-backed WorkProtocol code job. "
                    "It parses GitHub Actions run URLs or local log files, returns JSON with failing step, "
                    "error message, stack trace, and fix category, and includes six pytest tests."
                ),
                "url": workprotocol_base + "/delivery.json",
                "evidenceType": "portfolio",
                "visibility": "public",
            }
        )
    docs_cap = caps.get("OpenAPI and API docs repair")
    if docs_cap:
        payloads.append(
            {
                "capabilityId": docs_cap["id"],
                "title": "Public x402 API discovery catalog",
                "summary": (
                    "Live machine-readable catalog for eight paid endpoints, including API docs generation, "
                    "repo triage, x402 validation, URL snapshots, and domain health reports."
                ),
                "url": base_url + "/.well-known/x402-discovery",
                "evidenceType": "portfolio",
                "visibility": "public",
            }
        )
    return payloads


def _setup_portfolio(token: str, public_base_url: str) -> dict[str, Any]:
    if not public_base_url:
        return {"ok": False, "error": "public_base_url_required"}
    caps_status, caps_payload = _request_json("GET", "/api/agent/me/capabilities", token=token)
    if not (200 <= caps_status < 300) or not isinstance(caps_payload, dict):
        return {"ok": False, "capabilities_http_status": caps_status, "capabilities_response": caps_payload}
    existing_status, existing_payload = _request_json("GET", "/api/agent/me/portfolio", token=token)
    existing_titles: set[str] = set()
    if isinstance(existing_payload, dict):
        existing = existing_payload.get("portfolioEvidence", [])
        if isinstance(existing, list):
            existing_titles = {
                str(item.get("title") or "")
                for item in existing
                if isinstance(item, dict) and item.get("title")
            }

    results = []
    for payload in portfolio_payloads(public_base_url, caps_payload):
        if payload["title"] in existing_titles:
            results.append({"title": payload["title"], "ok": True, "skipped": True})
            continue
        status, response = _request_json("POST", "/api/agent/me/portfolio", token=token, body=payload)
        results.append(
            {
                "title": payload["title"],
                "ok": 200 <= status < 300,
                "http_status": status,
                "response": response,
            }
        )

    trust_status, trust_payload = _request_json("GET", "/api/agent/me/trust", token=token)
    return {
        "ok": all(item.get("ok") for item in results) if results else False,
        "existing_http_status": existing_status,
        "created_or_skipped": results,
        "trust": {"ok": 200 <= trust_status < 300, "http_status": trust_status, "response": trust_payload},
    }


def _load_selected_opentask_targets(ranking_path: Path, *, limit: int) -> list[dict[str, Any]]:
    ranking = _read_json(ranking_path)
    selected = ranking.get("selected_first", [])
    if not isinstance(selected, list):
        return []
    targets = [
        item
        for item in selected
        if isinstance(item, dict)
        and item.get("source_id") == "opentask"
        and item.get("decision") == "account_gate_first"
        and item.get("external_id")
    ]
    unique: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in targets:
        external_id = str(item.get("external_id") or "")
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        unique.append(item)
    return unique[: max(0, limit)]


def _existing_bid_task_ids(token: str) -> set[str]:
    status, payload = _request_json("GET", "/api/agent/bids", token=token)
    if not (200 <= status < 300) or not isinstance(payload, dict):
        return set()
    bids = payload.get("bids", [])
    if not isinstance(bids, list):
        return set()
    task_ids: set[str] = set()
    for bid in bids:
        if not isinstance(bid, dict):
            continue
        task = bid.get("task")
        if isinstance(task, dict) and task.get("id"):
            task_ids.add(str(task["id"]))
    return task_ids


def bid_approach_for_task(task: dict[str, Any]) -> str:
    title = str(task.get("title") or "").lower()
    tags = " ".join(str(tag).lower() for tag in task.get("tags", []) if tag)
    text = title + " " + tags
    common = (
        "Assumptions: task inputs are public or provided in the task thread; no private credentials are required. "
        "Verification: run the included command and compare expected output. "
        f"Portfolio evidence: {DEFAULT_PUBLIC_BASE_URL}{WORKPROTOCOL_CLI_EVIDENCE_PATH}. "
        "Out of scope: social engagement, fake reviews, KYC, CAPTCHA bypass, secret extraction, malware, and bounty/audit work."
    )
    if any(term in text for term in ("openapi", "api docs", "api-documentation", "swagger")):
        return (
            "Plan: deliver a compact OpenAPI/API documentation artifact: OpenAPI YAML or Markdown docs, "
            "endpoint examples, request/response notes, assumptions, and a lint or review command where possible. "
            + common
        )
    if any(term in text for term in ("fastapi", "api integration", "rest", "webhook", "backend")):
        return (
            "Plan: deliver a small API integration artifact: focused FastAPI/REST/webhook code or docs, "
            "sample request/response, minimal tests or curl smoke checks, and clear assumptions. "
            + common
        )
    if any(term in text for term in ("qa report", "content qa", "api or content", "api qa")):
        return (
            "Plan: deliver a concise API/content QA report with pass/fail checks, issue severity, "
            "specific fixes, and one verification note per finding. "
            + common
        )
    if "json" in text and "csv" in text:
        if "json to csv" in text or "output csv" in text:
            direction = "JSON-to-CSV"
        elif "csv" in text and ("generate json" in text or "output json" in text):
            direction = "CSV-to-JSON"
        else:
            direction = "CSV/JSON"
        return (
            f"Plan: deliver a small {direction} Python parser with stdlib-first code, sample input, sample output, "
            "basic error handling, and a pytest or command-line verification check. "
            + common
        )
    if any(term in text for term in ("python", "automation", "parser", "parse", "microtask")):
        return (
            "Plan: deliver a small Python automation script with clear CLI input/output, a README snippet, "
            "sample data, and one reproducible verification command. "
            + common
        )
    return (
        "Plan: deliver a compact, verifiable artifact for this scoped public-input task. "
        "For parser/API/docs work I will provide the file changes or document, sample input/output, "
        "and exact verification commands. "
        + common
    )


def bid_payload_for_task(task: dict[str, Any]) -> dict[str, Any]:
    payout = task.get("payout_usd_estimate")
    try:
        payout_float = float(payout)
    except (TypeError, ValueError):
        payout_float = 5.0
    bid_amount = max(1.0, round(payout_float * 0.8, 2))
    return {
        "priceText": f"{bid_amount:g} USDC",
        "etaDays": 1,
        "approach": bid_approach_for_task(task),
    }


def capability_claims_for_task(task: dict[str, Any], capabilities_payload: dict[str, Any]) -> list[dict[str, Any]]:
    caps = _capabilities_by_name(capabilities_payload)
    title = str(task.get("title") or "").lower()
    tags = " ".join(str(tag).lower() for tag in task.get("tags", []) if tag)
    text = title + " " + tags
    claims: list[dict[str, Any]] = []
    if any(term in text for term in ("openapi", "api docs", "api-documentation", "swagger")):
        cap = caps.get("OpenAPI and API docs repair")
        if cap:
            claims.append(
                {
                    "capabilityId": cap["id"],
                    "fitSummary": "The task asks for API/OpenAPI documentation. This capability covers OpenAPI specs, endpoint examples, and lint notes.",
                    "promisedOutputs": ["OpenAPI or API docs", "examples", "verification notes"],
                }
            )
    if any(term in text for term in ("python", "csv", "json", "parser", "parse", "automation", "microtask")):
        cap = caps.get("Python data parser microtask")
        if cap:
            claims.append(
                {
                    "capabilityId": cap["id"],
                    "fitSummary": "The task is a small Python/data automation job. This capability covers CSV/JSON parsing, scripts, and reproducible checks.",
                    "promisedOutputs": ["script", "sample output", "verification notes"],
                }
            )
    if any(term in text for term in ("fastapi", "api integration", "rest", "webhook", "backend")):
        cap = caps.get("Small FastAPI and API integration task")
        if cap:
            claims.append(
                {
                    "capabilityId": cap["id"],
                    "fitSummary": "The task asks for a small API/backend integration. This capability covers FastAPI routes, REST glue, webhook handlers, examples, and smoke checks.",
                    "promisedOutputs": ["code or docs", "examples", "tests or smoke commands"],
                }
            )
    if any(term in text for term in ("qa report", "content qa", "api or content", "api qa")):
        cap = caps.get("Small API and content QA report")
        if cap:
            claims.append(
                {
                    "capabilityId": cap["id"],
                    "fitSummary": "The task asks for a small API/content QA report. This capability covers public-input QA checks, concrete issues, severity, and verification notes.",
                    "promisedOutputs": ["QA report", "issue list", "verification notes"],
                }
            )
    return claims[:2]


def _is_safe_manual_review_target(task: dict[str, Any]) -> bool:
    if task.get("decision") != "manual_review":
        return False
    if task.get("source_id") != "opentask":
        return False
    risk_flags = set(str(flag) for flag in task.get("risk_flags", []) if flag)
    if risk_flags.intersection({"bounty_route", "hard_reject", "broad_service_listing"}):
        return False
    title = str(task.get("title") or "").lower()
    if any(term in title for term in ("anti-detection", "any website", "telegram bot", "security audit", "bug hunting")):
        return False
    return True


def _load_opentask_bid_targets(ranking_path: Path, *, limit: int, include_manual_review: bool) -> list[dict[str, Any]]:
    ranking = _read_json(ranking_path)
    ranked = ranking.get("ranked", [])
    if not isinstance(ranked, list):
        return _load_selected_opentask_targets(ranking_path, limit=limit)
    targets: list[dict[str, Any]] = []
    for item in ranked:
        if not isinstance(item, dict) or item.get("source_id") != "opentask" or not item.get("external_id"):
            continue
        if item.get("decision") == "account_gate_first" or (include_manual_review and _is_safe_manual_review_target(item)):
            targets.append(item)
    unique: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in targets:
        external_id = str(item.get("external_id") or "")
        if external_id in seen_ids:
            continue
        seen_ids.add(external_id)
        unique.append(item)
    return unique[: max(0, limit)]


def _bid_from_ranking(
    token: str,
    ranking_path: Path,
    *,
    limit: int,
    submit: bool,
    include_manual_review: bool = False,
) -> dict[str, Any]:
    targets = _load_opentask_bid_targets(
        ranking_path,
        limit=limit * 3,
        include_manual_review=include_manual_review,
    )
    existing_task_ids = _existing_bid_task_ids(token)
    caps_status, caps_payload = _request_json("GET", "/api/agent/me/capabilities", token=token)
    if not isinstance(caps_payload, dict):
        caps_payload = {}
    bids = []
    for task in targets:
        if task.get("external_id") in existing_task_ids:
            bids.append(
                {
                    "task_id": task.get("external_id"),
                    "title": task.get("title"),
                    "submit": False,
                    "skipped": True,
                    "reason": "already_has_bid",
                }
            )
            continue
        if len([item for item in bids if not item.get("skipped")]) >= limit:
            break
        payload = bid_payload_for_task(task)
        claims = capability_claims_for_task(task, caps_payload)
        if claims:
            payload["capabilityClaims"] = claims
        result = {
            "task_id": task.get("external_id"),
            "title": task.get("title"),
            "submit": submit,
            "payload": payload,
        }
        if submit:
            status, response = _request_json(
                "POST",
                f"/api/agent/tasks/{task['external_id']}/bids",
                token=token,
                body=payload,
            )
            result.update({"ok": 200 <= status < 300, "http_status": status, "response": response})
        bids.append(result)
    return {
        "ok": bool(bids),
        "submit": submit,
        "targets_total": len(targets),
        "existing_bid_task_ids": sorted(existing_task_ids),
        "bids": bids,
    }


def _refresh_bid_claims(token: str) -> dict[str, Any]:
    caps_status, caps_payload = _request_json("GET", "/api/agent/me/capabilities", token=token)
    bids_status, bids_payload = _request_json("GET", "/api/agent/bids?status=active", token=token)
    if not isinstance(caps_payload, dict) or not isinstance(bids_payload, dict):
        return {
            "ok": False,
            "capabilities_http_status": caps_status,
            "bids_http_status": bids_status,
        }
    bids = bids_payload.get("bids", [])
    if not isinstance(bids, list):
        bids = []
    results = []
    for bid in bids:
        if not isinstance(bid, dict):
            continue
        task = bid.get("task") if isinstance(bid.get("task"), dict) else {}
        claims = capability_claims_for_task(task, caps_payload)
        if not claims:
            results.append({"bid_id": bid.get("id"), "ok": True, "skipped": True, "reason": "no_matching_capability"})
            continue
        body = {
            "action": "update",
            "priceText": bid.get("priceText") or "1 USDC",
            "etaDays": bid.get("etaDays"),
            "approach": bid_approach_for_task(task),
            "capabilityClaims": claims,
        }
        status, response = _request_json(
            "PATCH",
            f"/api/agent/bids/{bid.get('id')}",
            token=token,
            body=body,
        )
        results.append(
            {
                "bid_id": bid.get("id"),
                "task_id": task.get("id"),
                "title": task.get("title"),
                "ok": 200 <= status < 300,
                "http_status": status,
                "claims_total": len(claims),
                "response": response,
            }
        )
    return {
        "ok": all(item.get("ok") for item in results) if results else False,
        "updated_or_skipped": results,
    }


def _redact_status(status: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(status))
    secret = redacted.get("secret")
    if isinstance(secret, dict):
        secret["password"] = "***" if secret.get("password") else ""
        secret["token"] = _mask(secret.get("token"))
        secret["signing_key_hex"] = "***" if secret.get("signing_key_hex") else ""
    return redacted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret-path", type=Path, default=DEFAULT_SECRET_PATH)
    parser.add_argument("--status-path", type=Path, default=DEFAULT_STATUS_PATH)
    parser.add_argument("--ranking-path", type=Path, default=DEFAULT_RANKING_PATH)
    parser.add_argument("--public-base-url", default="")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--login-refresh", action="store_true")
    parser.add_argument("--setup-profile", action="store_true")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--register-key", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--tasks", action="store_true")
    parser.add_argument("--bids", action="store_true")
    parser.add_argument("--contracts", action="store_true")
    parser.add_argument("--notifications", action="store_true")
    parser.add_argument("--bid-from-ranking", action="store_true")
    parser.add_argument("--submit-bids", action="store_true")
    parser.add_argument("--include-manual-review", action="store_true")
    parser.add_argument("--refresh-bid-claims", action="store_true")
    parser.add_argument("--bid-limit", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    secret = _read_json(args.secret_path)
    register_result: dict[str, Any] | None = None
    if args.login_refresh:
        secret, login_result = _login_refresh(args.secret_path)
    else:
        login_result = None
    if args.register or not secret.get("token"):
        secret, register_result = _ensure_registered(args.secret_path)
    token = str(secret.get("token") or "")

    status: dict[str, Any] = {
        "secret_path": str(args.secret_path),
        "status_path": str(args.status_path),
        "secret": {
            "handle": secret.get("handle"),
            "profile_id": secret.get("profile_id"),
            "password": secret.get("password"),
            "token": token,
        },
        "register": register_result,
        "login_refresh": login_result,
    }

    if not token:
        status["error"] = "missing_opentask_token"
        _write_json(args.status_path, _redact_status(status))
        print(json.dumps(_redact_status(status), indent=2, sort_keys=True))
        return 1

    if args.setup_profile:
        status["setup_profile"] = _setup_profile(token, args.public_base_url or None)
    if args.portfolio:
        status["portfolio"] = _setup_portfolio(token, args.public_base_url)
    if args.register_key:
        status["register_key"] = _register_and_verify_key(token, secret, args.secret_path)
    if args.status:
        status["me"] = _auth_get("/api/agent/me", token)
        status["payout_methods"] = _auth_get("/api/agent/me/payout-methods", token)
        status["capabilities"] = _auth_get("/api/agent/me/capabilities", token)
    if args.bids:
        status["active_bids"] = _auth_get("/api/agent/bids?status=active", token)
        status["all_bids"] = _auth_get("/api/agent/bids", token)
    if args.contracts:
        status["seller_contracts"] = _auth_get("/api/agent/contracts?role=seller", token)
    if args.notifications:
        status["unread_notifications"] = _auth_get("/api/agent/notifications/unread-count", token)
        status["notifications"] = _auth_get("/api/agent/notifications?unreadOnly=1", token)
    if args.tasks:
        task_status, task_payload = _request_json("GET", "/api/tasks?sort=new&limit=20")
        status["tasks"] = {"ok": 200 <= task_status < 300, "http_status": task_status, "response": task_payload}
    if args.bid_from_ranking:
        status["bid_from_ranking"] = _bid_from_ranking(
            token,
            args.ranking_path,
            limit=args.bid_limit,
            submit=args.submit_bids,
            include_manual_review=args.include_manual_review,
        )
    if args.refresh_bid_claims:
        status["refresh_bid_claims"] = _refresh_bid_claims(token)

    redacted = _redact_status(status)
    _write_json(args.status_path, redacted)
    print(json.dumps(redacted, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
