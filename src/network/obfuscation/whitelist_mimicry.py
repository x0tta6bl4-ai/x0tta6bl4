"""Local-only whitelist mimicry descriptors for Ghost Pulse evidence scans.

The helpers here describe synthetic timing/profile labels used by local Ghost
Pulse experiments. They do not assert provider approval, whitelist behavior,
remote reachability, DPI bypass, anonymity, or production readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

WHITELIST_MIMICRY_CLAIM_BOUNDARY = (
    "Whitelist mimicry descriptors are local synthetic profile metadata only; "
    "they are not provider whitelist proof, DPI proof, remote reachability "
    "proof, anonymity proof, or production readiness proof."
)


@dataclass(frozen=True)
class WhitelistMimicryProfile:
    """Bounded local descriptor for a synthetic profile family."""

    label: str
    delay_bucket: str
    payload_bucket: str
    claim_boundary: str = WHITELIST_MIMICRY_CLAIM_BOUNDARY

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


LOCAL_WHITELIST_MIMICRY_PROFILES: tuple[WhitelistMimicryProfile, ...] = (
    WhitelistMimicryProfile(
        label="catalog",
        delay_bucket="medium",
        payload_bucket="small-to-medium",
    ),
    WhitelistMimicryProfile(
        label="cdn",
        delay_bucket="medium-high",
        payload_bucket="medium",
    ),
    WhitelistMimicryProfile(
        label="media-gap",
        delay_bucket="high",
        payload_bucket="variable",
    ),
)


def profile_inventory() -> dict[str, Any]:
    return {
        "profiles": [profile.as_dict() for profile in LOCAL_WHITELIST_MIMICRY_PROFILES],
        "profile_count": len(LOCAL_WHITELIST_MIMICRY_PROFILES),
        "claim_boundary": WHITELIST_MIMICRY_CLAIM_BOUNDARY,
        "proof_flags": {
            "provider_whitelist_confirmed": False,
            "external_dpi_tested": False,
            "remote_reachability_confirmed": False,
            "production_ready": False,
        },
    }
