from __future__ import annotations

from src.sales.non_bounty_task_scout import (
    _normalise_agiotage,
    _normalise_riner,
    _normalise_sporeagent,
    _normalise_workprotocol,
    rank_non_bounty_tasks,
    score_non_bounty_task,
)


def test_non_bounty_task_scout_prioritises_openapi_work() -> None:
    collection = {
        "tasks": [
            {
                "source_id": "opentask",
                "source_kind": "public_task",
                "title": "OpenAPI documentation for REST API",
                "description": "Create OpenAPI YAML, endpoint examples, and lint results.",
                "requirements": "OpenAPI Redocly GitHub",
                "payout_usd": 500,
                "payout_asset": "USDC",
                "tags": ["openapi", "api-documentation", "rest-api"],
                "action_gate": "needs_headless_registration_and_bearer_token",
                "action_type": "bid_after_account_gate",
            },
            {
                "source_id": "chesto",
                "source_kind": "public_task",
                "title": "Follow and like a Twitter post",
                "description": "Follow, retweet, and like this social campaign.",
                "requirements": "Twitter account with followers.",
                "payout_usd": 0.1,
                "payout_asset": "USDC",
                "tags": ["social"],
            },
        ]
    }

    ranking = rank_non_bounty_tasks(collection)

    assert ranking["schema"] == "x0tta6bl4.non_bounty_task_scout.v1"
    assert ranking["account_gate_first_total"] == 1
    assert ranking["selected_first"][0]["title"] == "OpenAPI documentation for REST API"
    assert ranking["claim_gate"]["funds_received_claim_allowed"] is False


def test_non_bounty_task_scout_rejects_social_and_bounty_tasks() -> None:
    social = score_non_bounty_task(
        {
            "source_id": "chesto",
            "source_kind": "public_task",
            "title": "Follow + Engage @Project",
            "description": "Follow on X, like, retweet, and paste proof.",
            "requirements": "Twitter account",
            "payout_usd": 5,
            "payout_asset": "USDC",
            "tags": ["social"],
        }
    )
    bounty = score_non_bounty_task(
        {
            "source_id": "opentask",
            "source_kind": "public_task",
            "title": "Security Audit & Bug Hunting",
            "description": "Bug bounty style task for web apps.",
            "requirements": "OWASP",
            "payout_usd": 300,
            "payout_asset": "USDC",
            "tags": ["security", "bug-bounty"],
        }
    )

    assert social["decision"] == "reject"
    assert "social" in social["risk_flags"]
    assert bounty["decision"] == "reject"
    assert "bounty_route" in bounty["risk_flags"]


def test_non_bounty_task_scout_marks_clawdgigs_as_benchmark_not_direct_work() -> None:
    scored = score_non_bounty_task(
        {
            "source_id": "clawdgigs",
            "source_kind": "seller_market_benchmark",
            "title": "Micro API/code triage in 2 hours",
            "description": "I inspect one small API endpoint.",
            "payout_usd": 1.25,
            "payout_asset": "USDC",
            "tags": ["Coding", "2 hours"],
            "action_gate": "seller_registration_wallet_ui",
            "action_type": "price_benchmark_for_our_own_fixed_gig",
        }
    )

    assert scored["decision"] == "watch_only"
    assert "market_benchmark_not_direct_work" in scored["risk_flags"]


def test_non_bounty_task_scout_does_not_auto_bid_broad_service_listings() -> None:
    scored = score_non_bounty_task(
        {
            "source_id": "opentask",
            "source_kind": "public_task",
            "title": "Custom AI Agent 24/7 automation pipeline",
            "description": "Full pipeline depending on complexity with money-back guarantee.",
            "requirements": "Any website, any workflow.",
            "payout_usd": 500,
            "payout_asset": "USDC",
            "tags": ["python", "automation", "api"],
            "action_gate": "needs_headless_registration_and_bearer_token",
        }
    )

    assert scored["decision"] != "account_gate_first"
    assert "broad_service_listing" in scored["risk_flags"]


def test_non_bounty_task_scout_normalises_workprotocol_jobs() -> None:
    tasks = _normalise_workprotocol(
        {
            "jobs": [
                {
                    "id": "job-1",
                    "category": "code",
                    "title": "Build a GitHub Actions log parser CLI tool",
                    "description": "Parse a public GitHub Actions run URL and output JSON.",
                    "requirements": {"languages": ["TypeScript"], "deliverable": "CLI"},
                    "acceptanceCriteria": ["Outputs failing step", "Handles stack trace"],
                    "paymentAmount": "75.00",
                    "paymentCurrency": "USDC",
                    "paymentRail": "base",
                }
            ]
        }
    )

    assert tasks[0]["source_id"] == "workprotocol"
    assert tasks[0]["payout_usd"] == 75.0
    assert tasks[0]["payment_rail"] == "base"
    assert tasks[0]["acceptance_criteria_count"] == 2


def test_non_bounty_task_scout_normalises_sporeagent_tasks() -> None:
    tasks = _normalise_sporeagent(
        {
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Generate comprehensive pytest suite for FastAPI REST API",
                    "description": "Add pytest coverage for public API endpoints.",
                    "requirements": ["python", "testing", "fastapi"],
                    "budget_usd": 80,
                    "status": "open",
                    "posted_at": "2026-03-01T00:00:00Z",
                    "assigned_agent_id": None,
                    "bid_count": 6,
                }
            ]
        }
    )

    assert tasks[0]["source_id"] == "sporeagent"
    assert tasks[0]["payout_usd"] == 80.0
    assert tasks[0]["bid_count"] == 6
    assert tasks[0]["action_type"] == "bid_after_agent_registration"


def test_non_bounty_task_scout_normalises_riner_escrowed_tasks() -> None:
    tasks = _normalise_riner(
        {
            "tasks": [
                {
                    "id": "task-riner-1",
                    "title": "Build JSON parser",
                    "description": "Create a small Python parser for public JSON samples.",
                    "category": "data_processing",
                    "tags": ["python", "json"],
                    "requirements": {"language": "python"},
                    "output_spec": {"description": "Script and verification command"},
                    "budget_amount": 15,
                    "budget_token": "USDC",
                    "escrow_tx": "0xabc",
                    "selection_mode": "manual",
                    "max_applicants": 2,
                }
            ]
        }
    )

    assert tasks[0]["source_id"] == "riner"
    assert tasks[0]["payout_usd"] == 15.0
    assert tasks[0]["escrow_tx_hash"] == "0xabc"
    assert tasks[0]["action_type"] == "apply_after_wallet_signature_or_api_key"


def test_non_bounty_task_scout_rejects_riner_social_promotion() -> None:
    scored = score_non_bounty_task(
        {
            "source_id": "riner",
            "source_kind": "escrowed_open_task",
            "title": "Riner Promotion",
            "description": "Find Reddit and Twitter discussions and post replies.",
            "requirements": "community engagement",
            "payout_usd": 2,
            "payout_asset": "USDC",
            "tags": ["social_media"],
            "action_gate": "needs_wallet_signature_or_riner_api_key",
        }
    )

    assert scored["decision"] == "reject"
    assert "reddit" in scored["risk_flags"]
    assert "twitter" in scored["risk_flags"]


def test_non_bounty_task_scout_normalises_agiotage_jobs() -> None:
    tasks = _normalise_agiotage(
        {
            "jobs": [
                {
                    "id": 1,
                    "title": "Build a sentiment analysis pipeline",
                    "category": "code",
                    "budget": 25,
                    "token": "USDC",
                    "status": "BIDDING",
                    "created_at": "2026-04-23T00:19:20Z",
                }
            ]
        }
    )

    assert tasks[0]["source_id"] == "agiotage"
    assert tasks[0]["payout_usd"] == 25.0
    assert tasks[0]["action_type"] == "bid_after_agent_registration"


def test_non_bounty_task_scout_keeps_heavy_workprotocol_jobs_out_of_auto_claim() -> None:
    scored = score_non_bounty_task(
        {
            "source_id": "workprotocol",
            "source_kind": "escrowed_open_job",
            "title": "Build a configurable API rate limiter middleware for Express/Hono",
            "description": "Create an npm package with Redis support and multiple strategies.",
            "requirements": (
                "Full test suite, adapter pattern, fixed window, sliding window, token bucket, "
                "per-route configuration."
            ),
            "payout_usd": 120,
            "payout_asset": "USDC",
            "tags": ["code", "base", "TypeScript"],
            "action_gate": "needs_workprotocol_agent_registration_and_api_key",
        }
    )

    assert scored["decision"] != "account_gate_first"
    assert "high_effort" in scored["risk_flags"]
