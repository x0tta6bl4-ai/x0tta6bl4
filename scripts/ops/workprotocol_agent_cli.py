#!/usr/bin/env python3
"""Register and watch WorkProtocol jobs for non-bounty agent income."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sales.non_bounty_task_scout import _normalise_workprotocol, score_non_bounty_task


API_BASE = "https://workprotocol.ai"
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_SECRET = ARTIFACT_DIR / "workprotocol_agent.secret.json"
DEFAULT_STATUS = ARTIFACT_DIR / "workprotocol_agent_status.json"
DEFAULT_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"

SENSITIVE_KEYS = {"apikey", "api_key", "authorization", "bearer", "secret", "token", "key"}
HARD_CLAIM_RISKS = {
    "bounty_route",
    "broad_service_listing",
    "high_effort",
    "captcha",
    "kyc",
    "malware",
    "private key",
    "seed phrase",
    "social",
    "spam",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _chmod_secret(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any, *, secret: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if secret:
        _chmod_secret(path)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if (
                not isinstance(item, bool)
                and (lowered in SENSITIVE_KEYS or lowered.endswith("_secret") or lowered.endswith("_api_key"))
            ):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def _json_request(
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    api_key: str = "",
    timeout_seconds: float = 25.0,
) -> dict[str, Any]:
    url = path if path.startswith("http") else API_BASE + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "User-Agent": "x0tta6bl4-workprotocol-agent",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(text) if text else {}
            return {"ok": True, "http_status": int(response.status), "response": parsed}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = text[:2_000]
        return {"ok": False, "http_status": int(exc.code), "response": parsed}
    except Exception as exc:
        return {"ok": False, "http_status": 0, "error": exc.__class__.__name__, "detail": str(exc)[:700]}


def build_agent_payload(name: str, wallet: str) -> dict[str, Any]:
    return {
        "name": name,
        "description": (
            "x0tta6bl4 fixed-scope worker for public-input code, data, and research jobs. "
            "Best fit: CLI tools, JSON/CSV parsing, API checks, OpenAPI docs, URL/domain reports. "
            "Rejects bounty work, secrets, private accounts, KYC/CAPTCHA bypass, spam, and harmful automation."
        ),
        "walletAddress": wallet,
        "capabilities": {
            "categories": ["code", "data", "research"],
            "languages": ["python", "typescript", "javascript"],
            "maxJobValue": 150,
            "avgCompletionTime": "1-4h",
        },
        "pricing": {
            "minimumJobValue": 5,
            "acceptedCurrencies": ["USDC"],
        },
    }


def _extract_identity(response: dict[str, Any], *, wallet: str) -> dict[str, Any]:
    candidate = response.get("agent") if isinstance(response.get("agent"), dict) else response
    api_key = candidate.get("apiKey") or candidate.get("api_key") or response.get("apiKey") or response.get("api_key")
    agent_id = candidate.get("id") or candidate.get("agentId") or response.get("agentId")
    return {
        "agent_id": agent_id,
        "api_key": api_key,
        "walletAddress": candidate.get("walletAddress") or wallet,
        "name": candidate.get("name"),
        "raw": response,
    }


def _rank_workprotocol_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = _normalise_workprotocol(payload)
    ranked = [score_non_bounty_task(task) for task in tasks]
    return sorted(
        ranked,
        key=lambda item: (
            item["decision"] == "account_gate_first",
            item["token_roi_score"],
            item["score"],
            item["title"],
        ),
        reverse=True,
    )


def _claimable(item: dict[str, Any], *, min_score: int, max_estimated_tokens: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if item.get("source_id") != "workprotocol":
        reasons.append("not_workprotocol")
    if item.get("decision") != "account_gate_first":
        reasons.append(f"decision:{item.get('decision')}")
    if int(item.get("score") or 0) < min_score:
        reasons.append(f"score_below:{min_score}")
    if int(item.get("estimated_token_cost") or 999999999) > max_estimated_tokens:
        reasons.append(f"token_cost_above:{max_estimated_tokens}")
    risks = set(item.get("risk_flags") or [])
    blocked = sorted(risks.intersection(HARD_CLAIM_RISKS))
    if blocked:
        reasons.append("risk:" + ",".join(blocked))
    return not reasons, reasons


def extract_claim_id(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = [
        payload.get("claimId"),
        payload.get("id"),
        (payload.get("claim") or {}).get("id") if isinstance(payload.get("claim"), dict) else None,
        (payload.get("data") or {}).get("claimId") if isinstance(payload.get("data"), dict) else None,
        (payload.get("data") or {}).get("id") if isinstance(payload.get("data"), dict) else None,
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return ""


def _query_jobs(category: str, min_pay: float, limit: int) -> str:
    return "/api/jobs?" + urllib.parse.urlencode(
        {
            "status": "open",
            "category": category,
            "min_pay": f"{min_pay:g}",
            "limit": limit,
        }
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="x0tta6bl4-non-bounty-worker")
    parser.add_argument("--wallet", default=os.environ.get("X0T_TARGET_WALLET", DEFAULT_WALLET))
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_SECRET)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--force-register", action="store_true")
    parser.add_argument("--jobs", action="store_true")
    parser.add_argument("--claim-best", action="store_true")
    parser.add_argument("--claim-job-id", default="")
    parser.add_argument("--deliver-job-id", default="")
    parser.add_argument("--claim-id", default="")
    parser.add_argument("--deliverable-url", default="")
    parser.add_argument("--deliverable-type", default="url")
    parser.add_argument("--auto-verify", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--category", default="code")
    parser.add_argument("--min-pay", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-score", type=int, default=62)
    parser.add_argument("--max-estimated-tokens", type=int, default=60_000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (
        args.register
        or args.jobs
        or args.claim_best
        or args.claim_job_id
        or args.deliver_job_id
        or args.auto_verify
        or args.status_only
    ):
        args.register = True
        args.jobs = True

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    secret = _read_json(args.secret_file)
    api_key = str(secret.get("api_key") or "")
    agent_id = str(secret.get("agent_id") or "")

    status: dict[str, Any] = {
        "checked_at_utc": _utc_now(),
        "api_base": API_BASE,
        "wallet": args.wallet,
        "secret_file": str(args.secret_file),
        "has_api_key": bool(api_key),
        "has_agent_id": bool(agent_id),
        "actions": {},
        "claim_boundary": (
            "A WorkProtocol registration or claim is not money received. Money is only real after a verified "
            "delivery releases USDC to the target wallet."
        ),
    }

    if args.register:
        if api_key and agent_id and not args.force_register:
            status["actions"]["register"] = {"ok": True, "skipped": True, "reason": "existing_identity"}
        else:
            register = _json_request(
                "POST",
                "/api/agents/register",
                payload=build_agent_payload(args.name, args.wallet),
                timeout_seconds=args.timeout_seconds,
            )
            status["actions"]["register"] = redact(register)
            if register.get("ok") and isinstance(register.get("response"), dict):
                identity = _extract_identity(register["response"], wallet=args.wallet)
                if identity.get("api_key") and identity.get("agent_id"):
                    _write_json(args.secret_file, identity, secret=True)
                    secret = identity
                    api_key = str(identity.get("api_key") or "")
                    agent_id = str(identity.get("agent_id") or "")
                    status["has_api_key"] = bool(api_key)
                    status["has_agent_id"] = bool(agent_id)

    ranked: list[dict[str, Any]] = []
    if args.jobs or args.claim_best:
        jobs = _json_request(
            "GET",
            _query_jobs(args.category, args.min_pay, args.limit),
            timeout_seconds=args.timeout_seconds,
        )
        status["actions"]["jobs"] = redact(jobs)
        if jobs.get("ok") and isinstance(jobs.get("response"), dict):
            ranked = _rank_workprotocol_jobs(jobs["response"])
            for item in ranked:
                ok, reasons = _claimable(
                    item,
                    min_score=args.min_score,
                    max_estimated_tokens=args.max_estimated_tokens,
                )
                item["claimable_now"] = ok
                item["claim_blockers"] = reasons
            status["jobs_total"] = len(ranked)
            status["ranked"] = ranked[:10]
            status["claimable_total"] = sum(1 for item in ranked if item.get("claimable_now"))

    if args.claim_best:
        best = next((item for item in ranked if item.get("claimable_now")), None)
        if not best:
            status["actions"]["claim_best"] = {"ok": False, "skipped": True, "reason": "no_claimable_job"}
        elif not api_key or not agent_id:
            status["actions"]["claim_best"] = {"ok": False, "skipped": True, "reason": "missing_agent_identity"}
        elif args.dry_run:
            status["actions"]["claim_best"] = {"ok": True, "dry_run": True, "selected": best}
        else:
            claim = _json_request(
                "POST",
                f"/api/jobs/{best['external_id']}/claim",
                payload={"agentId": agent_id},
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            status["actions"]["claim_best"] = redact(claim)
            if claim.get("ok"):
                status["last_claim_id"] = extract_claim_id(claim.get("response"))

    if args.claim_job_id:
        if not api_key or not agent_id:
            status["actions"]["claim_job"] = {"ok": False, "skipped": True, "reason": "missing_agent_identity"}
        elif args.dry_run:
            status["actions"]["claim_job"] = {
                "ok": True,
                "dry_run": True,
                "job_id": args.claim_job_id,
                "agent_id": agent_id,
            }
        else:
            claim = _json_request(
                "POST",
                f"/api/jobs/{args.claim_job_id}/claim",
                payload={"agentId": agent_id},
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            status["actions"]["claim_job"] = redact(claim)
            claim_id = extract_claim_id(claim.get("response"))
            if claim_id:
                status["last_claim_id"] = claim_id

    if args.deliver_job_id:
        claim_id = args.claim_id or str(status.get("last_claim_id") or "")
        if not api_key:
            status["actions"]["deliver_job"] = {"ok": False, "skipped": True, "reason": "missing_api_key"}
        elif not claim_id:
            status["actions"]["deliver_job"] = {"ok": False, "skipped": True, "reason": "missing_claim_id"}
        elif not args.deliverable_url:
            status["actions"]["deliver_job"] = {"ok": False, "skipped": True, "reason": "missing_deliverable_url"}
        elif args.dry_run:
            status["actions"]["deliver_job"] = {
                "ok": True,
                "dry_run": True,
                "job_id": args.deliver_job_id,
                "claim_id": claim_id,
                "deliverable": {"type": args.deliverable_type, "url": args.deliverable_url},
            }
        else:
            delivery = _json_request(
                "POST",
                f"/api/jobs/{args.deliver_job_id}/deliver",
                payload={"claimId": claim_id, "deliverable": {"type": args.deliverable_type, "url": args.deliverable_url}},
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            status["actions"]["deliver_job"] = redact(delivery)

    if args.auto_verify:
        verify_job_id = args.deliver_job_id or args.claim_job_id
        claim_id = args.claim_id or str(status.get("last_claim_id") or "")
        if not api_key:
            status["actions"]["auto_verify"] = {"ok": False, "skipped": True, "reason": "missing_api_key"}
        elif not verify_job_id:
            status["actions"]["auto_verify"] = {"ok": False, "skipped": True, "reason": "missing_job_id"}
        elif not claim_id:
            status["actions"]["auto_verify"] = {"ok": False, "skipped": True, "reason": "missing_claim_id"}
        elif args.dry_run:
            status["actions"]["auto_verify"] = {
                "ok": True,
                "dry_run": True,
                "job_id": verify_job_id,
                "claim_id": claim_id,
            }
        else:
            verification = _json_request(
                "POST",
                f"/api/jobs/{verify_job_id}/verify-auto",
                payload={"claimId": claim_id},
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            status["actions"]["auto_verify"] = redact(verification)

    _write_json(args.status_file, redact(status))
    print(json.dumps(redact(status), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
