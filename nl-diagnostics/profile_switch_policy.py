#!/usr/bin/env python3
"""Local policy for NL runtime switch_profile signals.

This module is pure local decision logic. It does not connect to NL, does not
switch profiles, and does not mutate client or server state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SAFE_TRANSPORT_STATUSES = {"healthy", "advisory"}
PROVIDER_BLOCKING_STATUSES = {"provider_outage", "suspect_active", "host_degraded", "overloaded"}


@dataclass(frozen=True)
class ProfileSwitchDecision:
    decision: str
    automatic_allowed: bool
    manual_allowed: bool
    manual_review_required: bool
    requires_fresh_snapshot: bool
    reason: str
    nl_mutation_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_profile_switch(
    state: dict[str, Any],
    *,
    snapshot_fresh: bool,
    explicit_manual_approval: bool = False,
) -> ProfileSwitchDecision:
    """Decide what to do with runtime recommended_action=switch_profile.

    `switch_profile` is treated as an advisory signal. Automatic switching is
    never allowed by this policy. A manual profile review can be allowed only
    when the current snapshot is fresh, provider state is not blocking, and core
    VPN transport is still healthy/advisory.
    """
    action = str(state.get("runtime_recommended_action") or state.get("recommended_action") or "observe")
    mode = str(state.get("runtime_mode") or "unknown")
    transport = str(state.get("transport_status") or "unknown")
    overall = str(state.get("overall_status") or "unknown")
    failure_domain = str(state.get("failure_domain") or "unknown")
    provider_status = str(state.get("provider_status") or "unknown")

    if action != "switch_profile":
        return ProfileSwitchDecision(
            decision="observe",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=False,
            requires_fresh_snapshot=False,
            reason=f"runtime_recommended_action={action}",
        )

    if not snapshot_fresh:
        return ProfileSwitchDecision(
            decision="blocked_stale_snapshot",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=True,
            requires_fresh_snapshot=True,
            reason="fresh read-only snapshot is required before profile switch review",
        )

    if overall == "provider_outage" or failure_domain == "provider_host" or provider_status in PROVIDER_BLOCKING_STATUSES:
        return ProfileSwitchDecision(
            decision="blocked_provider_guard",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=True,
            requires_fresh_snapshot=True,
            reason="provider/host failure must be handled before profile switching",
        )

    if overall == "critical" and failure_domain == "local_client":
        return ProfileSwitchDecision(
            decision="blocked_local_client",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=True,
            requires_fresh_snapshot=True,
            reason="local client failure must be fixed before profile switching",
        )

    if transport not in SAFE_TRANSPORT_STATUSES:
        return ProfileSwitchDecision(
            decision="operator_review",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=True,
            requires_fresh_snapshot=True,
            reason=f"transport_status={transport}; profile switch is not enough evidence for recovery",
        )

    if not explicit_manual_approval:
        return ProfileSwitchDecision(
            decision="manual_profile_review",
            automatic_allowed=False,
            manual_allowed=False,
            manual_review_required=True,
            requires_fresh_snapshot=True,
            reason=(
                f"runtime mode={mode} requests switch_profile, but transport is {transport}; "
                "manual review required, no automatic action"
            ),
        )

    return ProfileSwitchDecision(
        decision="manual_profile_switch_approved",
        automatic_allowed=False,
        manual_allowed=True,
        manual_review_required=False,
        requires_fresh_snapshot=True,
        reason="manual approval present with fresh snapshot and healthy/advisory transport",
    )
