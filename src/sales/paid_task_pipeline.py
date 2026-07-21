"""Paid task automation pipeline for turning AI work into real payouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.sales.wallet_payment_intake import TARGET_WALLET_ADDRESS, mask_wallet


SCHEMA = "x0tta6bl4.paid_task_pipeline.v1"
GOAL = (
    "Find legitimate paid online tasks, select tasks that can be completed by "
    "AI-assisted engineering work, prepare or execute the work locally, submit "
    "through the platform's allowed flow, and route payouts or invoices toward "
    f"wallet {TARGET_WALLET_ADDRESS} where supported."
)
CLAIM_BOUNDARY = (
    "This pipeline proves a legal automation plan and local task-selection workflow. "
    "It does not prove platform account access, accepted assignments, merged pull "
    "requests, approved submissions, received funds, tax compliance, or settlement finality."
)


@dataclass(frozen=True)
class PaidTaskSource:
    source_id: str
    name: str
    url: str
    payout_style: str
    automation_fit: str
    allowed_ai_role: str
    human_gate: str
    search_hint: str
    source_basis: str


TASK_SOURCES: tuple[PaidTaskSource, ...] = (
    PaidTaskSource(
        source_id="ghbounty",
        name="GH Bounty",
        url="https://www.ghbounty.com/",
        payout_style="SOL on Solana through onchain escrow.",
        automation_fit="high",
        allowed_ai_role="Agent can list bounties, prepare code, submit PRs after one-time human authorization.",
        human_gate="GitHub OAuth device flow and local wallet/key handling.",
        search_hint="Use the platform app or MCP endpoint to list GitHub bounty tasks.",
        source_basis="Official page states AI agents can earn bounties and get paid in SOL after onboarding.",
    ),
    PaidTaskSource(
        source_id="gitwork",
        name="GitWork",
        url="https://gitwork.io/about",
        payout_style="USDC/Solana bounty on merged GitHub pull requests.",
        automation_fit="high",
        allowed_ai_role="Agent can monitor GitHub issues and prepare PRs; payout depends on merge.",
        human_gate="GitHub login and payout wallet setup.",
        search_hint="Search GitHub issues and GitWork bounties by language, tests, and bounty amount.",
        source_basis="Official page describes GitHub issue bounties and automatic payment when PRs are merged.",
    ),
    PaidTaskSource(
        source_id="algora",
        name="Algora",
        url="https://algora.io/",
        payout_style="USD bounty on GitHub issues, usually paid after accepted or merged work.",
        automation_fit="high",
        allowed_ai_role="Agent can collect public GitHub bounty issues, score them, patch code, and draft PR evidence.",
        human_gate="Account, payout setup, task rules, and final PR/submission approval.",
        search_hint="Search GitHub issues with the Algora bounty label and parse dollar amount labels or /bounty comments.",
        source_basis="Official pages describe creating bounties with /bounty comments and paying when work is merged.",
    ),
    PaidTaskSource(
        source_id="superteam_earn",
        name="Superteam Earn",
        url="https://earn.superteam.fun/",
        payout_style="Crypto bounties, freelance gigs, jobs, and grants.",
        automation_fit="medium",
        allowed_ai_role="Agent can find listings, draft submissions, code, and proof-of-work packages.",
        human_gate="Account, identity, submission, and platform code-of-conduct compliance.",
        search_hint="Filter for developer bounties, tooling, docs, integration, and agent-friendly tasks.",
        source_basis="Official docs describe bounties and freelance gigs for earning in crypto.",
    ),
    PaidTaskSource(
        source_id="dework",
        name="Dework",
        url="https://dework.xyz/",
        payout_style="On-chain token bounty payments from DAO/project tasks.",
        automation_fit="medium",
        allowed_ai_role="Agent can parse task requirements, prepare PRs/docs, and draft application text.",
        human_gate="Task application, assignment, wallet connection, and DAO/project approval.",
        search_hint="Search DAO tasks with GitHub sync, code, docs, infra, and bug-fix labels.",
        source_basis="Official page describes task bounties, GitHub sync, and wallet payments.",
    ),
    PaidTaskSource(
        source_id="dorahacks",
        name="DoraHacks",
        url="https://dorahacks.io/",
        payout_style="Hackathon, grant, DAO bounty, bug bounty, and mini-bounty rewards.",
        automation_fit="medium",
        allowed_ai_role="Agent can build BUIDLs, draft reports, implement code, and prepare submissions.",
        human_gate="Hackathon rules, account, team submission, and sponsor review.",
        search_hint="Search hackathons, DAO bounties, mini bounties, and bug bounties matching x0tta6bl4 assets.",
        source_basis="Terms describe hackathons, bounties, DAO bounties, bug bounties, mini bounties, and grants.",
    ),
)

TASK_TYPES = (
    {
        "task_type": "github_bugfix_bounty",
        "why_it_fits": "Repo inspection, patching, tests, and PR text are strong Codex workflows.",
        "automation_steps": [
            "Fetch issue requirements.",
            "Clone or inspect repository.",
            "Patch code locally.",
            "Run focused tests.",
            "Draft PR title, body, and evidence.",
        ],
        "human_or_platform_gate": "Submitting PR may require authenticated GitHub account and platform assignment.",
    },
    {
        "task_type": "docs_or_runbook_bounty",
        "why_it_fits": "x0tta6bl4 already has docs/export automation and can generate proof-bounded docs quickly.",
        "automation_steps": [
            "Read bounty brief.",
            "Produce Markdown/docs patch.",
            "Add citation or reproducible commands.",
            "Run formatting/link checks where available.",
        ],
        "human_or_platform_gate": "Submission and plagiarism/originality responsibility remain with the account owner.",
    },
    {
        "task_type": "integration_or_demo_bounty",
        "why_it_fits": "Current productization work can produce demos, snapshots, API examples, and small integrations.",
        "automation_steps": [
            "Map required SDK/API.",
            "Build minimal integration.",
            "Record commands and expected output.",
            "Package demo README and screenshots if needed.",
        ],
        "human_or_platform_gate": "API keys, private accounts, and final submission are human-gated.",
    },
    {
        "task_type": "hackathon_or_grant_submission",
        "why_it_fits": "The existing x0tta6bl4 product portfolio can be repackaged as BUIDL/grant material.",
        "automation_steps": [
            "Match x0tta6bl4 assets to theme.",
            "Draft project page, demo flow, and technical evidence.",
            "Generate productization snapshot.",
            "Prepare final submission checklist.",
        ],
        "human_or_platform_gate": "Team identity, eligibility, tax, and grant terms are human-gated.",
    },
)


def _source_to_dict(source: PaidTaskSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "name": source.name,
        "url": source.url,
        "payout_style": source.payout_style,
        "automation_fit": source.automation_fit,
        "allowed_ai_role": source.allowed_ai_role,
        "human_gate": source.human_gate,
        "search_hint": source.search_hint,
        "source_basis": source.source_basis,
    }


def build_paid_task_pipeline(root: Path | str = ".") -> dict[str, Any]:
    root_path = Path(root)
    repo_assets = [
        "src/sales/product_ideas.py",
        "src/sales/pilot_package.py",
        "src/sales/wallet_payment_intake.py",
        "scripts/ops/build_productization_snapshot.py",
        "docs/commercial/PAYMENT_INTAKE.md",
    ]
    return {
        "schema": SCHEMA,
        "goal": GOAL,
        "status": "pipeline_ready" if all((root_path / path).exists() for path in repo_assets) else "pipeline_blocked",
        "wallet": {
            "address": TARGET_WALLET_ADDRESS,
            "masked": mask_wallet(TARGET_WALLET_ADDRESS),
            "routing_note": "Use this wallet only where the platform supports direct EVM payout or invoice payment.",
        },
        "sources": [_source_to_dict(source) for source in TASK_SOURCES],
        "task_types": list(TASK_TYPES),
        "automation_loop": [
            "Collect listings from allowed public pages, platform APIs, or human-exported CSV/JSON.",
            "Run scripts/ops/collect_paid_task_listings.py to collect public GitHub bounty candidates.",
            "Run scripts/ops/score_paid_task_listings.py against the local listings JSON.",
            "Score by payout, fit to repo skills, deadline, rules, and probability of acceptance.",
            "Select one task at a time to avoid spam and duplicate low-quality submissions.",
            "Generate a local work plan and proof checklist.",
            "Implement the work in a disposable branch or worktree.",
            "Run tests and package evidence.",
            "Human approves platform login, final submission, wallet, and tax/legal responsibility.",
            "Record transaction hash only after payout is confirmed on the selected network.",
        ],
        "machine_commands": [
            "PYTHONPATH=. python3 scripts/ops/build_paid_task_automation_plan.py",
            (
                "PYTHONPATH=. python3 scripts/ops/collect_paid_task_listings.py "
                "--max-results 25"
            ),
            (
                "PYTHONPATH=. python3 scripts/ops/score_paid_task_listings.py "
                "--input .tmp/paid-task-listings-current.json"
            ),
        ],
        "hard_no": [
            "No fake engagement, review manipulation, spam, or mass low-quality submissions.",
            "No CAPTCHA bypass, credential scraping, or account creation in another person's name.",
            "No private keys or seed phrases in chat, repo, logs, or generated docs.",
            "No claim that funds were earned without a confirmed transaction or platform payout record.",
        ],
        "claim_gate": {
            "pipeline_claim_allowed": True,
            "autonomous_account_access_claim_allowed": False,
            "accepted_task_claim_allowed": False,
            "funds_received_claim_allowed": False,
            "settlement_finality_claim_allowed": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
    }
