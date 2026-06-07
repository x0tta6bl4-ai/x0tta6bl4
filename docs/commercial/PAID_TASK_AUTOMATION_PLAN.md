# x0tta6bl4 Paid Task Automation Plan

Generated: 2026-06-03T04:23:10Z

## Goal

Find legitimate paid online tasks, select tasks that can be completed by AI-assisted engineering work, prepare or execute the work locally, submit through the platform's allowed flow, and route payouts or invoices toward wallet 0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099 where supported.

## Wallet

- Address: 0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099
- Routing note: Use this wallet only where the platform supports direct EVM payout or invoice payment.

## Sources

### GH Bounty

- Source ID: ghbounty
- URL: https://www.ghbounty.com/
- Payout style: SOL on Solana through onchain escrow.
- Automation fit: high
- Allowed AI role: Agent can list bounties, prepare code, submit PRs after one-time human authorization.
- Human gate: GitHub OAuth device flow and local wallet/key handling.
- Search hint: Use the platform app or MCP endpoint to list GitHub bounty tasks.
- Source basis: Official page states AI agents can earn bounties and get paid in SOL after onboarding.

### GitWork

- Source ID: gitwork
- URL: https://gitwork.io/about
- Payout style: USDC/Solana bounty on merged GitHub pull requests.
- Automation fit: high
- Allowed AI role: Agent can monitor GitHub issues and prepare PRs; payout depends on merge.
- Human gate: GitHub login and payout wallet setup.
- Search hint: Search GitHub issues and GitWork bounties by language, tests, and bounty amount.
- Source basis: Official page describes GitHub issue bounties and automatic payment when PRs are merged.

### Algora

- Source ID: algora
- URL: https://algora.io/
- Payout style: USD bounty on GitHub issues, usually paid after accepted or merged work.
- Automation fit: high
- Allowed AI role: Agent can collect public GitHub bounty issues, score them, patch code, and draft PR evidence.
- Human gate: Account, payout setup, task rules, and final PR/submission approval.
- Search hint: Search GitHub issues with the Algora bounty label and parse dollar amount labels or /bounty comments.
- Source basis: Official pages describe creating bounties with /bounty comments and paying when work is merged.

### Superteam Earn

- Source ID: superteam_earn
- URL: https://earn.superteam.fun/
- Payout style: Crypto bounties, freelance gigs, jobs, and grants.
- Automation fit: medium
- Allowed AI role: Agent can find listings, draft submissions, code, and proof-of-work packages.
- Human gate: Account, identity, submission, and platform code-of-conduct compliance.
- Search hint: Filter for developer bounties, tooling, docs, integration, and agent-friendly tasks.
- Source basis: Official docs describe bounties and freelance gigs for earning in crypto.

### Dework

- Source ID: dework
- URL: https://dework.xyz/
- Payout style: On-chain token bounty payments from DAO/project tasks.
- Automation fit: medium
- Allowed AI role: Agent can parse task requirements, prepare PRs/docs, and draft application text.
- Human gate: Task application, assignment, wallet connection, and DAO/project approval.
- Search hint: Search DAO tasks with GitHub sync, code, docs, infra, and bug-fix labels.
- Source basis: Official page describes task bounties, GitHub sync, and wallet payments.

### DoraHacks

- Source ID: dorahacks
- URL: https://dorahacks.io/
- Payout style: Hackathon, grant, DAO bounty, bug bounty, and mini-bounty rewards.
- Automation fit: medium
- Allowed AI role: Agent can build BUIDLs, draft reports, implement code, and prepare submissions.
- Human gate: Hackathon rules, account, team submission, and sponsor review.
- Search hint: Search hackathons, DAO bounties, mini bounties, and bug bounties matching x0tta6bl4 assets.
- Source basis: Terms describe hackathons, bounties, DAO bounties, bug bounties, mini bounties, and grants.

## Task Types

### github_bugfix_bounty

- Fit: Repo inspection, patching, tests, and PR text are strong Codex workflows.
- Human/platform gate: Submitting PR may require authenticated GitHub account and platform assignment.

Automation steps:

- Fetch issue requirements.
- Clone or inspect repository.
- Patch code locally.
- Run focused tests.
- Draft PR title, body, and evidence.

### docs_or_runbook_bounty

- Fit: x0tta6bl4 already has docs/export automation and can generate proof-bounded docs quickly.
- Human/platform gate: Submission and plagiarism/originality responsibility remain with the account owner.

Automation steps:

- Read bounty brief.
- Produce Markdown/docs patch.
- Add citation or reproducible commands.
- Run formatting/link checks where available.

### integration_or_demo_bounty

- Fit: Current productization work can produce demos, snapshots, API examples, and small integrations.
- Human/platform gate: API keys, private accounts, and final submission are human-gated.

Automation steps:

- Map required SDK/API.
- Build minimal integration.
- Record commands and expected output.
- Package demo README and screenshots if needed.

### hackathon_or_grant_submission

- Fit: The existing x0tta6bl4 product portfolio can be repackaged as BUIDL/grant material.
- Human/platform gate: Team identity, eligibility, tax, and grant terms are human-gated.

Automation steps:

- Match x0tta6bl4 assets to theme.
- Draft project page, demo flow, and technical evidence.
- Generate productization snapshot.
- Prepare final submission checklist.

## Automation Loop

- Collect listings from allowed public pages, platform APIs, or human-exported CSV/JSON.
- Run scripts/ops/collect_paid_task_listings.py to collect public GitHub bounty candidates.
- Run scripts/ops/score_paid_task_listings.py against the local listings JSON.
- Score by payout, fit to repo skills, deadline, rules, and probability of acceptance.
- Select one task at a time to avoid spam and duplicate low-quality submissions.
- Generate a local work plan and proof checklist.
- Implement the work in a disposable branch or worktree.
- Run tests and package evidence.
- Human approves platform login, final submission, wallet, and tax/legal responsibility.
- Record transaction hash only after payout is confirmed on the selected network.

## Machine Commands

- `PYTHONPATH=. python3 scripts/ops/build_paid_task_automation_plan.py`
- `PYTHONPATH=. python3 scripts/ops/collect_paid_task_listings.py --max-results 25`
- `PYTHONPATH=. python3 scripts/ops/score_paid_task_listings.py --input .tmp/paid-task-listings-current.json`

## Hard No

- No fake engagement, review manipulation, spam, or mass low-quality submissions.
- No CAPTCHA bypass, credential scraping, or account creation in another person's name.
- No private keys or seed phrases in chat, repo, logs, or generated docs.
- No claim that funds were earned without a confirmed transaction or platform payout record.

## Claim Gate

- Pipeline claim allowed: True
- Accepted task claim allowed: False
- Funds received claim allowed: False
- Settlement finality claim allowed: False

This pipeline proves a legal automation plan and local task-selection workflow. It does not prove platform account access, accepted assignments, merged pull requests, approved submissions, received funds, tax compliance, or settlement finality.
