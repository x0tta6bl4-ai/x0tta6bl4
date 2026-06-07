from __future__ import annotations

from src.sales.paid_task_collectors import (
    collect_github_algora_bounty_listings,
    collect_github_paid_task_listings,
    extract_usd_bounty_amount,
    github_issue_to_paid_task_listing,
)


def _github_issue() -> dict:
    return {
        "repository_url": "https://api.github.com/repos/tine1117/oss-hunter-livefire",
        "html_url": "https://github.com/tine1117/oss-hunter-livefire/issues/1",
        "number": 1,
        "title": "parse_duration drops the days (d) unit",
        "state": "open",
        "comments": 7,
        "created_at": "2026-06-01T14:37:16Z",
        "updated_at": "2026-06-01T19:07:26Z",
        "labels": [
            {"name": "\U0001f48e Bounty"},
            {"name": "$50"},
        ],
        "body": "Fix parse_duration days support and add tests.\n\n/bounty $50\n",
    }


def test_extract_usd_bounty_amount_handles_plain_and_k_labels() -> None:
    assert extract_usd_bounty_amount(labels=["$50"], text="") == 50
    assert extract_usd_bounty_amount(labels=["$1.2k"], text="") == 1200
    assert extract_usd_bounty_amount(labels=[], text="/bounty $2,500") == 2500


def test_github_issue_to_paid_task_listing_normalises_algora_bounty() -> None:
    listing = github_issue_to_paid_task_listing(_github_issue())

    assert listing["source_id"] == "algora"
    assert listing["source_kind"] == "github_issue_search"
    assert listing["repository"] == "tine1117/oss-hunter-livefire"
    assert listing["payout_usd"] == 50
    assert listing["payout_asset"] == "USD"
    assert "\U0001f48e Bounty" in listing["labels"]


def test_collect_github_algora_bounty_listings_from_fixture() -> None:
    collection = collect_github_algora_bounty_listings(
        max_results=10,
        fixture_payload={"total_count": 624, "items": [_github_issue()]},
        collected_at_utc="2026-06-03T00:00:00Z",
    )

    assert collection["schema"] == "x0tta6bl4.paid_task_collection.v1"
    assert collection["status"] == "collection_ready"
    assert collection["public_network_used"] is False
    assert collection["github_total_count"] == 624
    assert collection["tasks_total"] == 1
    assert collection["tasks"][0]["payout_usd"] == 50
    assert collection["claim_gate"]["funds_received_claim_allowed"] is False


def test_collect_github_paid_task_listings_from_fixture() -> None:
    collection = collect_github_paid_task_listings(
        max_results=10,
        fixture_payload={"total_count": 1, "items": [_github_issue()]},
        collected_at_utc="2026-06-03T00:00:00Z",
    )

    assert collection["schema"] == "x0tta6bl4.paid_task_collection.v1"
    assert collection["status"] == "collection_ready"
    assert collection["source_id"] == "github_paid_issue_search"
    assert collection["public_network_used"] is False
    assert collection["tasks_total"] == 1
    assert collection["tasks"][0]["source_id"] == "algora"
    assert collection["claim_gate"]["funds_received_claim_allowed"] is False
