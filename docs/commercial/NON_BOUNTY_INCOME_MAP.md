# x0tta6bl4 Non-Bounty Income Map

Generated: 2026-06-05T14:41:22Z

## Status

- Schema: x0tta6bl4.non_bounty_income_map.v1
- Status: map_ready
- Funds received claim allowed: False

## Thinking

- first_principles: Real money requires buyer, deliverable, acceptance rule, settlement path, and proof.
- reverse_planning: Start from confirmed payout, work backward to accepted delivery, accepted offer, account gate, and first artifact.
- scamper: Reuse bounty filters as paid APIs, adapt product ideas into Actors, combine reports with agent marketplaces.
- mapek: Monitor sources, analyze clean opportunities, plan one artifact, execute only one route, record outcomes.

## Ranked Routes

### Gate402 x402 catalog import

- Decision: take_first
- Score: 83.2
- Channel: x402 service registry
- Revenue model: Import the existing x402 manifest; buyers discover the service and pay USDC per call.
- First artifact: .tmp/non-bounty/gate402_import_status.json
- Next machine step: Keep the public x402 API online and poll Gate402 search until the active service is indexed.
- Gates: public_https_endpoint, manifest_validation, search_indexing, buyer_call
- Risks: new_marketplace, search_indexing_delay, unverified_first_sale_to_this_wallet
- Sources: https://gate402.net/for-agents.md, https://gate402.net/openapi.json

### x402 paid micro API

- Decision: take_first
- Score: 82.4
- Channel: pay-per-request API
- Revenue model: Agents or programs pay per HTTP request for data, reports, or MCP tools.
- First artifact: .tmp/non-bounty/x402_service_catalog.json
- Next machine step: Define one paid endpoint: repo-risk-score, bounty-filter, or scraper-result API.
- Gates: deployment, wallet, payment_facilitator, customer_discovery
- Risks: no_existing_traffic, payment_flow_can_move_real_money, needs_abuse_limits
- Sources: https://developers.cloudflare.com/agents/tools/payments/x402/, https://www.coinbase.com/developer-platform/products/x402

### Agora402 native x402 registry

- Decision: take_first
- Score: 78.2
- Channel: x402 agent registry
- Revenue model: Register a native x402 endpoint; buyers discover the agent by category and pay per call.
- First artifact: .tmp/non-bounty/agoragentic_seller_watch_status.json
- Next machine step: Keep the verified public listing online and poll invocations, earned balance, webhooks, and wallet balance.
- Gates: public_https_endpoint, registry_visibility, buyer_call, x402_payment
- Risks: buyer_demand_unknown, new_marketplace, unverified_first_sale_to_this_wallet
- Sources: https://agora402.io/

### AgentPact service offer

- Decision: take_first
- Score: 77.6
- Channel: agent marketplace
- Revenue model: USDC escrow-backed agent-to-agent deals on Base.
- First artifact: .tmp/non-bounty/agentpact_offer.json
- Next machine step: Generate an agent offer for data extraction, repo triage, and structured reports.
- Gates: external_account_or_api_key, deal_acceptance, wallet_or_payout_setup
- Risks: new_marketplace, unverified_real_payout_to_this_wallet, needs_reputation
- Sources: https://agentpact.xyz/

### Agent402 API listing

- Decision: take_first
- Score: 75.6
- Channel: agent API marketplace
- Revenue model: Register an existing x402 endpoint; buyers discover it by intent and pay per request.
- First artifact: .tmp/non-bounty/agent402_listing.json
- Next machine step: Point Agent402 at the current x402 paid API discovery URL and list repo triage plus API docs.
- Gates: seller_registration, service_review_or_indexing, buyer_call, onchain_payment
- Risks: new_marketplace, registration_gate, unverified_first_sale_to_this_wallet
- Sources: https://marketplace.agent402.app/

### Agent Bazaar x402 skill listing

- Decision: take_first
- Score: 75.0
- Channel: agent skill marketplace
- Revenue model: List one narrow x402 API skill and earn per paid call.
- First artifact: .tmp/non-bounty/agent_bazaar_skill_submission.json
- Next machine step: Prepare a skill listing for domain-health, URL snapshot, or CI/CD pipeline generator endpoints.
- Gates: skill_submission, review_within_platform_window, buyer_call, x402_payment
- Risks: manual_form_or_account_gate, review_delay, unverified_first_sale_to_this_wallet
- Sources: https://agent-bazaar.com/dev, https://agent-bazaar.com/marketplace

### Apify Actor factory

- Decision: take_first
- Score: 74.8
- Channel: automation marketplace
- Revenue model: Pay-per-event Actor monetization plus affiliate commission from Actor pages.
- First artifact: .tmp/non-bounty/apify_actor_backlog.json
- Next machine step: Package one useful scraper/checker as an Apify Actor with JSON input and output.
- Gates: apify_account, actor_publication, usage_or_referrals, payout_method
- Risks: needs_distribution, not_instant_cash, platform_payout_may_need_paypal_or_bank
- Sources: https://apify.com/partners/open-source-fair-share, https://apify.com/partners/affiliate

### 402.rest API publisher

- Decision: take_first
- Score: 73.6
- Channel: x402 API marketplace
- Revenue model: Publish a paid x402-ready API endpoint and earn per request from marketplace traffic.
- First artifact: .tmp/non-bounty/402_rest_publish_plan.json
- Next machine step: Mirror the current x402 discovery data into a 402.rest publisher-ready service description.
- Gates: publisher_onboarding, service_review_or_indexing, buyer_call, x402_payment
- Risks: registration_gate, buyer_demand_unknown, unverified_first_sale_to_this_wallet
- Sources: https://www.402.rest/

### SporeAgent task runner

- Decision: take_first
- Score: 73.4
- Channel: agent task marketplace
- Revenue model: Small paid tasks with proof-of-work verification.
- First artifact: .tmp/non-bounty/sporeagent_worker_profile.json
- Next machine step: Create a worker profile and poll tasks for web scraping, tests, translation, and reports.
- Gates: platform_account, accepted_bid, deliverable_approval, payout_setup
- Risks: limited_current_task_depth, unknown_payout_history_for_our_agent, competition
- Sources: https://sporeagent.com/

### the402 provider listing

- Decision: manual_review
- Score: 71.6
- Channel: x402 service marketplace
- Revenue model: List a data/API/automated service and receive USDC through x402 or escrowed marketplace flow.
- First artifact: .tmp/non-bounty/the402_provider_listing_plan.json
- Next machine step: Prepare a provider listing for the current domain-health, URL snapshot, and API-docs endpoints.
- Gates: provider_account, service_listing, catalog_visibility, buyer_call_or_order
- Risks: external_account_gate, catalog_currently_sparse, unverified_first_sale_to_this_wallet
- Sources: https://the402.ai/

### BotHire x402 bot

- Decision: manual_review
- Score: 70.8
- Channel: machine-first bot marketplace
- Revenue model: Register a bot skill and receive USDC on Base through x402 calls.
- First artifact: .tmp/non-bounty/bothire_bot_profile.json
- Next machine step: Expose the current repo-triage and API-docs endpoints as machine-readable bot skills.
- Gates: registration, machine_readable_docs, buyer_call, onchain_payment
- Risks: public_registration_unverified, new_marketplace, needs_discovery
- Sources: https://www.bothire.io/

### ClawGig agent freelancer

- Decision: manual_review
- Score: 67.2
- Channel: agent freelance marketplace
- Revenue model: USDC escrow; platform page says agent keeps 90 percent.
- First artifact: .tmp/non-bounty/clawgig_agent_profile.json
- Next machine step: Prepare a low-risk agent profile and skill list for research, data, Python, and code review gigs.
- Gates: agent_registration, api_key, accepted_proposal, escrow_release
- Risks: market_appears_empty, unproven_demand, external_account_gate
- Sources: https://clawgig.ai/

### Molted worker agent

- Decision: manual_review
- Score: 65.2
- Channel: agent task marketplace
- Revenue model: Bid on jobs and receive USDC on Base after accepted completion.
- First artifact: .tmp/non-bounty/molted_worker_probe.json
- Next machine step: Probe Molted job discovery daily; register only if open jobs are visible through API or CLI.
- Gates: agent_registration, open_job_visibility, accepted_bid, completion_approval
- Risks: api_probe_currently_404, buyer_acceptance_required, unverified_first_sale_to_this_wallet
- Sources: https://molted.work/

### ClawdGigs fixed x402 gig

- Decision: manual_review
- Score: 65.0
- Channel: agent gig marketplace
- Revenue model: Fixed-scope gig with x402 escrow; deliver one artifact, wait for release.
- First artifact: .tmp/non-bounty/clawdgigs_fixed_gig.json
- Next machine step: Create a fixed 3 USDC gig: API docs from endpoint JSON, delivered as Markdown.
- Gates: agent_registration, gig_publication, buyer_acceptance, escrow_release
- Risks: external_account_gate, buyer_demand_unknown, dispute_or_acceptance_delay
- Sources: https://www.clawdgigs.com/

### Apify affiliate content engine

- Decision: manual_review
- Score: 61.0
- Channel: affiliate
- Revenue model: Recurring commission from referred Apify customers.
- First artifact: .tmp/non-bounty/apify_affiliate_content_plan.json
- Next machine step: Generate search-targeted pages/tutorials around scraping workflows and x0tta6bl4 actors.
- Gates: affiliate_approval, audience_or_seo_traffic, minimum_payout, payout_method
- Risks: slow_cash, needs_distribution, paid_ads_forbidden_by_program
- Sources: https://apify.com/partners/affiliate

### ClawMart skill listing

- Decision: manual_review
- Score: 60.2
- Channel: agent skill marketplace
- Revenue model: Package a narrow paid developer-assistant role as a reusable agent skill.
- First artifact: .tmp/non-bounty/clawmart_skill_listing.json
- Next machine step: Turn the API-docs endpoint into a fixed role: 'API docs in Markdown from JSON specs'.
- Gates: seller_onboarding, skill_review, buyer_subscription_or_call, payout_setup
- Risks: not_verified_as_open_self_serve, less_direct_than_x402, needs_positioning
- Sources: https://clawmart.co/

### Telegram Stars microtools

- Decision: park
- Score: 57.4
- Channel: consumer bot
- Revenue model: Small paid Telegram Stars actions.
- First artifact: .tmp/non-bounty/telegram_microtool_menu.json
- Next machine step: Package one narrow tool: voice summary, document draft, or public-page digest.
- Gates: bot_token, telegram_stars_setup, users, withdrawal_eligibility
- Risks: user_acquisition, support_load, user_already_rejected_as_uninteresting
- Sources: https://core.telegram.org/bots/payments-stars

### StacksTasker STX tasks

- Decision: park
- Score: 56.8
- Channel: agent task marketplace
- Revenue model: Bid on public tasks and receive STX through an x402-style flow.
- First artifact: .tmp/non-bounty/stackstasker_task_probe.json
- Next machine step: Watch only; use it if Base-USDC routes dry up and STX payout handling is added.
- Gates: stx_wallet, agent_registration, accepted_bid, stx_settlement
- Risks: not_base_wallet_direct, public_api_currently_404, new_marketplace
- Sources: https://stackstasker.com/

### io.net worker rewards

- Decision: park
- Score: 55.8
- Channel: DePIN compute
- Revenue model: Supply CPU/GPU compute and receive IO Coin earnings or rewards if the worker is eligible.
- First artifact: .tmp/non-bounty/io_net_worker_probe.json
- Next machine step: Check local hardware eligibility only; do not install worker software until payout and staking requirements are verified.
- Gates: supported_hardware, account_wallet_link, worker_eligibility, withdrawal
- Risks: hardware_required, staking_or_account_gate, not_target_base_wallet_direct
- Sources: https://io.net/docs/guides/workers/rewards-wallets

### Bless edge compute node

- Decision: park
- Score: 51.2
- Channel: DePIN compute
- Revenue model: Contribute idle CPU/GPU or browser node resources and earn network rewards if eligible.
- First artifact: .tmp/non-bounty/bless_node_probe.json
- Next machine step: Treat as passive watchlist; verify eligibility and payout terms before installing node software.
- Gates: node_install, eligibility, uptime, reward_conversion_or_withdrawal
- Risks: unclear_immediate_cash, hardware_and_bandwidth_cost, jurisdiction_or_account_gate
- Sources: https://docs.bless.network/

### Akash Homenode provider

- Decision: park
- Score: 51.0
- Channel: DePIN compute
- Revenue model: Offer GPU compute to Akash demand and earn from hosted inference workloads if hardware is accepted.
- First artifact: .tmp/non-bounty/akash_homenode_probe.json
- Next machine step: Park unless a supported GPU is present; this is a hardware route, not a token-only route.
- Gates: supported_gpu, provider_onboarding, workload_demand, settlement
- Risks: hardware_required, beta_or_waitlist_gate, not_instant_cash
- Sources: https://akash.network/blog/akash-network-q1-2026-report/, https://akash.network/docs/providers/getting-started/should-i-run-a-provider/

### WorkUSDC micro contracts

- Decision: park
- Score: 41.0
- Channel: crypto freelance marketplace
- Revenue model: Submit proposals to USDC-funded work and receive payouts through Base USDC escrow.
- First artifact: .tmp/non-bounty/workusdc_market_probe.json
- Next machine step: Watch only until the wallet has seed USDC; proposal submission itself costs 2 USDC.
- Gates: account_registration, proposal_credit_2_usdc, client_hire, escrow_release
- Risks: requires_upfront_usdc, cyber_work_compliance_gate, buyer_acceptance_required
- Sources: https://workusdc.com/

### Nodepay signal rewards

- Decision: park
- Score: 32.6
- Channel: data contribution rewards
- Revenue model: Contribute human/input signals or network data to earn platform rewards.
- First artifact: .tmp/non-bounty/nodepay_signal_probe.json
- Next machine step: Do not prioritize for autonomous earning; monitor only if a legitimate agent-safe API/workflow appears.
- Gates: account_registration, eligible_contribution, reward_rules, withdrawal
- Risks: not_agent_direct, points_or_rewards_not_cash, account_gate
- Sources: https://docs.nodepay.ai/

### Gradient Sentry rewards

- Decision: park
- Score: 30.0
- Channel: DePIN compute
- Revenue model: Legacy uptime/tap/referral rewards for Sentry Nodes.
- First artifact: .tmp/non-bounty/gradient_sentry_probe.json
- Next machine step: Park this route; official docs say Sentry Node rewards do not currently pay.
- Gates: future_season, node_eligibility, reward_rules, withdrawal
- Risks: official_rewards_concluded, no_current_cash, sybil_policy
- Sources: https://docs.gradient.network/rewards

## Claim Boundary

This map ranks non-bounty earning routes. It proves only local analysis and artifact planning. It does not prove platform account access, accepted work, customer demand, payout eligibility, received funds, or tax/payment compliance.
